"""
Dream-time memory consolidation for the agent.

This module turns recent interaction rows into compact long-term memories while
the chat path stays responsive. It is intentionally conservative: it synthesizes
and rehearses, but does not prune memories yet.
"""

import asyncio
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

from ..utils.config import config
from ..utils.logging import setup_logger
from .memory import MemoryEntry


logger = setup_logger(__name__)


class DreamPhase(str, Enum):
    """Named phases from the dream-cycle design."""

    REHEARSAL = "rehearsal"
    CLUSTERING = "clustering"
    SYNTHESIS = "synthesis"
    PRUNING = "pruning"
    CONSOLIDATION = "consolidation"


@dataclass
class DreamResult:
    """Result from one dream consolidation pass."""

    created: bool
    reason: str
    source_interaction_count: int = 0
    memory_id: Optional[str] = None
    summary: str = ""
    insights: List[str] = field(default_factory=list)


class DreamConsolidationService:
    """Consolidate recent short-term interaction history into durable memory."""

    CAPABILITY_MEMORY_QUERY = "tool-backed code changes github pull request branch commit"
    CAPABILITY_MEMORY_KEY = "tool_backed_pr_workflow"
    CAPABILITY_MEMORY_CONTENT = (
        "Capability: I can use tool-backed workflows for real code changes and PRs. "
        "When a user asks me to implement, inspect code, run tests, self-modify, or "
        "prepare a pull request, I should use available tools such as read_file, "
        "list_files, run_command, GitHub/self-modification workflows, and memory search. "
        "I should not pretend that pasted source code in chat changes the repository. "
        "For PR-worthy work, create or use a branch, edit files, validate with tests or "
        "linters, commit, push, and report the PR or compare link."
    )

    def __init__(self, memory: Any, data_manager: Any, llm_manager: Any = None):
        self.memory = memory
        self.data_manager = data_manager
        self.llm_manager = llm_manager
        self.last_cycle_at: Optional[datetime] = None
        self._lock = asyncio.Lock()

    async def seed_capability_memory(self) -> Optional[str]:
        """Store the durable reminder that implementation requires real tools."""
        try:
            existing = await self.memory.search_memories(
                query=self.CAPABILITY_MEMORY_QUERY,
                n_results=5,
                memory_type="capability",
                similarity_threshold=0.72,
            )
            for entry, _score in existing:
                if entry.metadata.get("capability_key") == self.CAPABILITY_MEMORY_KEY:
                    return entry.id
                if self.CAPABILITY_MEMORY_KEY in entry.content:
                    return entry.id
        except Exception as exc:
            logger.warning(f"Could not check existing capability memory: {exc}")

        entry = MemoryEntry(
            content=self.CAPABILITY_MEMORY_CONTENT,
            memory_type="capability",
            metadata={
                "capability_key": self.CAPABILITY_MEMORY_KEY,
                "source": "dream_cycle_seed",
                "session_id": getattr(self.data_manager, "session_id", None),
            },
        )
        return await self.memory.add_memory(entry)

    def due_for_cycle(self, interaction_count: int) -> bool:
        """Return true when enough time and interaction history have accumulated."""
        if not config.dream_cycle_enabled:
            return False

        min_interactions = config.dream_cycle_min_interactions
        if interaction_count < min_interactions:
            return False

        if not self.last_cycle_at:
            return True

        interval = timedelta(seconds=config.dream_cycle_interval_seconds)
        return datetime.now() - self.last_cycle_at >= interval

    async def run_once(self, reason: str = "scheduled") -> DreamResult:
        """Run one non-pruning consolidation pass."""
        if self._lock.locked():
            return DreamResult(created=False, reason="already_running")

        async with self._lock:
            interactions = await self.data_manager.get_recent_interactions(
                limit=config.dream_cycle_batch_size
            )
            if not interactions:
                return DreamResult(created=False, reason="no_interactions")

            selected = self._dedupe_interactions(interactions)
            if not selected:
                return DreamResult(created=False, reason="no_new_interactions")

            summary, insights = await self._synthesize(selected)
            if not summary.strip() and not insights:
                return DreamResult(created=False, reason="empty_synthesis")

            memory_entry = MemoryEntry(
                content=self._format_memory_content(summary, insights, reason),
                memory_type="dream_consolidation",
                metadata={
                    "source": "dream_cycle",
                    "reason": reason,
                    "source_interaction_count": len(selected),
                    "source_interaction_ids": [str(item.get("id")) for item in selected],
                    "phases_json": json.dumps([phase.value for phase in DreamPhase]),
                    "pruning_enabled": False,
                    "session_id": getattr(self.data_manager, "session_id", None),
                },
            )
            memory_id = await self.memory.add_memory(memory_entry)
            self.last_cycle_at = datetime.now()

            if hasattr(self.data_manager, "save_dream_consolidation"):
                await self.data_manager.save_dream_consolidation(
                    source_interaction_count=len(selected),
                    memory_id=memory_id,
                    summary=summary,
                    insights=insights,
                    metadata={
                        "reason": reason,
                        "phases": [phase.value for phase in DreamPhase],
                        "pruning_enabled": False,
                    },
                )

            return DreamResult(
                created=True,
                reason=reason,
                source_interaction_count=len(selected),
                memory_id=memory_id,
                summary=summary,
                insights=insights,
            )

    def _dedupe_interactions(self, interactions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen = set()
        selected = []
        for item in interactions:
            key = (
                str(item.get("conversation_id") or ""),
                self._normalize_text(str(item.get("query") or ""))[:160],
                self._normalize_text(str(item.get("response") or ""))[:160],
            )
            if key in seen:
                continue
            seen.add(key)
            selected.append(item)
        return selected[: config.dream_cycle_batch_size]

    async def _synthesize(self, interactions: List[Dict[str, Any]]) -> tuple[str, List[str]]:
        prompt = self._build_synthesis_prompt(interactions)
        if self.llm_manager:
            try:
                response = await asyncio.wait_for(
                    self.llm_manager.generate_response(
                        prompt=prompt,
                        temperature=0.25,
                        max_tokens=config.dream_cycle_max_tokens,
                    ),
                    timeout=config.dream_cycle_llm_timeout_seconds,
                )
                parsed = self._parse_synthesis_response(response)
                if parsed:
                    return parsed
            except Exception as exc:
                logger.warning(f"Dream synthesis LLM failed, using fallback: {exc}")

        return self._fallback_synthesis(interactions)

    def _build_synthesis_prompt(self, interactions: List[Dict[str, Any]]) -> str:
        chunks = []
        max_chars = config.dream_cycle_prompt_max_chars
        for item in interactions:
            chunk = (
                f"Interaction {item.get('id')} "
                f"conversation={item.get('conversation_id') or 'unknown'}\n"
                f"User: {str(item.get('query') or '')[:600]}\n"
                f"Assistant: {str(item.get('response') or '')[:900]}"
            )
            chunks.append(chunk)
            if sum(len(part) for part in chunks) >= max_chars:
                break

        return (
            "Consolidate these recent interactions into durable long-term memory.\n"
            "Extract only stable facts, user preferences, active projects, unresolved "
            "tasks, tool/capability lessons, and recurring patterns. Do not include "
            "transient chatter. Return JSON with keys summary (string) and insights "
            "(array of short strings).\n\n"
            + "\n\n".join(chunks)[:max_chars]
        )

    def _parse_synthesis_response(self, response: str) -> Optional[tuple[str, List[str]]]:
        if not response:
            return None
        start = response.find("{")
        end = response.rfind("}") + 1
        if start < 0 or end <= start:
            return None
        data = json.loads(response[start:end])
        summary = str(data.get("summary") or "").strip()
        insights = [str(item).strip() for item in data.get("insights", []) if str(item).strip()]
        if not summary and not insights:
            return None
        return summary, insights[: config.dream_cycle_max_insights]

    def _fallback_synthesis(self, interactions: List[Dict[str, Any]]) -> tuple[str, List[str]]:
        queries = [str(item.get("query") or "").strip() for item in interactions]
        conversation_ids = sorted(
            {str(item.get("conversation_id")) for item in interactions if item.get("conversation_id")}
        )
        summary = (
            f"Dream consolidation of {len(interactions)} recent interaction(s)"
            + (f" across conversations {', '.join(conversation_ids[:5])}" if conversation_ids else "")
            + "."
        )
        insights = []
        for query in queries[: config.dream_cycle_max_insights]:
            if query:
                insights.append(f"Recent user focus: {query[:180]}")
        return summary, insights

    def _format_memory_content(self, summary: str, insights: List[str], reason: str) -> str:
        insight_text = "\n".join(f"- {insight}" for insight in insights)
        return (
            f"Dream consolidation ({reason})\n\n"
            f"Summary: {summary.strip()}\n\n"
            f"Insights:\n{insight_text if insight_text else '- No discrete insights extracted.'}"
        )

    def _normalize_text(self, value: str) -> str:
        return re.sub(r"\s+", " ", value).strip().lower()
