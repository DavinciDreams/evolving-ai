"""Opt-in, finite autonomous experiments over operator-curated fixtures.

Dreams supply provenance, never graders or executable instructions. A fixed
closed candidate population is measured by ImprovementLab; default is staging.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
import time
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from .runtime import RuntimeBusyError
from ..self_modification.improvement_lab import (
    BenchmarkCase,
    GuidanceCandidate,
    GuidanceStrategy,
)


@dataclass(frozen=True)
class LearningConfig:
    enabled: bool = False
    auto_promote: bool = False
    interval_seconds: float = 900
    idle_seconds: float = 60
    timeout_seconds: float = 120
    stop_timeout_seconds: float = 2
    max_daily_experiments: int = 4
    suite_file: str = ""

    def __post_init__(self):
        if not isinstance(self.suite_file, str) or len(self.suite_file) > 4096:
            raise ValueError("Learning suite_file must be an operator-configured path")
        if type(self.enabled) is not bool or type(self.auto_promote) is not bool:
            raise ValueError("Learning enablement and promotion must be booleans")
        for key in (
            "interval_seconds",
            "idle_seconds",
            "timeout_seconds",
            "stop_timeout_seconds",
        ):
            value = getattr(self, key)
            minimum = 0 if key == "idle_seconds" else 0.01
            maximum = 86400 if key in {"interval_seconds", "idle_seconds"} else 300
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or not minimum <= value <= maximum
            ):
                raise ValueError(f"Invalid learning limit: {key}")
        if (
            type(self.max_daily_experiments) is not int
            or not 1 <= self.max_daily_experiments <= 100
        ):
            raise ValueError("Learning daily experiments must be in 1..100")
        if self.stop_timeout_seconds > 10:
            raise ValueError("Learning shutdown deadline must not exceed 10 seconds")

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None):
        env = os.environ if environ is None else environ
        values = {}
        for key, default in asdict(cls()).items():
            raw = env.get(f"LEARNING_CYCLE_{key.upper()}")
            if raw is None:
                continue
            if isinstance(default, bool):
                if raw.lower() not in {"true", "false", "1", "0"}:
                    raise ValueError(f"Invalid learning boolean: {key}")
                values[key] = raw.lower() in {"true", "1"}
            elif isinstance(default, str):
                values[key] = raw
            else:
                values[key] = float(raw) if key.endswith("seconds") else int(raw)
        return cls(**values)


def load_suite(path: str) -> tuple[BenchmarkCase, ...]:
    """Read a bounded, operator-owned JSON fixture file; never follow a URL.

    File contents are configuration, not an agent-generated proposal. Symlinks
    and non-files are rejected. No schema field can supply executable grading.
    """
    target = Path(path)
    if not path or target.is_symlink() or not target.is_file():
        raise ValueError("Learning suite must be a regular operator-configured file")
    with target.open("rb") as source:
        raw = source.read(1_000_001)
    if len(raw) > 1_000_000:
        raise ValueError("Learning suite exceeds the one-megabyte limit")
    try:
        payload = json.loads(raw)
        if not isinstance(payload, dict) or set(payload) != {"cases"}:
            raise ValueError("Learning suite must contain only a cases array")
        rows = payload["cases"]
        if not isinstance(rows, list) or not 4 <= len(rows) <= 24:
            raise ValueError("Learning suite must contain 4 to 24 cases")
        if any(not isinstance(row, dict) for row in rows):
            raise ValueError("Learning suite cases must be objects")
        return tuple(BenchmarkCase(**row) for row in rows)
    except (TypeError, ValueError, UnicodeError) as exc:
        raise ValueError("Invalid operator benchmark JSON schema") from exc


class LearningCycle:
    """Schedule at most one population experiment per tick through the steward.

    ``cases`` must be trusted operator configuration, not generated memories.
    No mutation of the fixture set, expected answers, or grading policy occurs.
    """

    def __init__(
        self,
        steward: Any,
        *,
        cases: Sequence[BenchmarkCase],
        settings: LearningConfig | None = None,
        entry_factory: Callable[..., Any] | None = None,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        monotonic: Callable[[], float] = time.monotonic,
    ):
        self.steward = steward
        self.settings = settings or LearningConfig.from_env()
        self.cases = tuple(cases)
        if any(not isinstance(case, BenchmarkCase) for case in self.cases):
            raise ValueError(
                "Learning fixtures must be operator-supplied BenchmarkCase objects"
            )
        if self.settings.enabled:
            if steward.lab is None:
                raise ValueError("Learning cycle requires an enabled improvement lab")
            if getattr(steward.agent.memory, "backend", None) != "ham":
                raise ValueError("Learning cycle requires authoritative HAM memory")
            # The trusted lab's validator is the single source of fixture limits.
            steward.lab._validate_suite(self.cases)
        self._suite_digest = self._digest([asdict(case) for case in self.cases])
        self._entry_factory = entry_factory
        self._now = now
        self._monotonic = monotonic
        self._last_activity = monotonic()
        self._next_due = monotonic()
        self._task = None
        self._operation = None
        self._closed = False
        self._generation = 0
        self._last_result: dict[str, Any] | None = None

    @staticmethod
    def _digest(value):
        return hashlib.sha256(
            json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    def note_activity(self):
        self._last_activity = self._monotonic()

    def start(self) -> bool:
        if not self.settings.enabled or (self._task and not self._task.done()):
            return False
        self._closed = False
        self._task = asyncio.create_task(self._loop(), name="katbot-learning-cycle")
        return True

    async def stop(self) -> bool:
        self._closed = True
        self._generation += 1
        tasks = {
            task for task in (self._task, self._operation) if task and not task.done()
        }
        for task in tasks:
            task.cancel()
        if not tasks:
            return True
        _, pending = await asyncio.wait(
            tasks, timeout=self.settings.stop_timeout_seconds
        )
        return not pending

    def status(self) -> dict[str, Any]:
        return {
            "enabled": self.settings.enabled,
            "auto_promote": self.settings.auto_promote,
            "running": bool(self._operation and not self._operation.done()),
            "worker_started": bool(self._task and not self._task.done()),
            "suite_digest": self._suite_digest,
            "case_count": len(self.cases),
            "last_result": self._last_result,
            "max_daily_experiments": self.settings.max_daily_experiments,
            "next_due_in_seconds": max(0, round(self._next_due - self._monotonic(), 2)),
            "adaptation_scope": "finite_closed_guidance_population",
        }

    async def _loop(self):
        while not self._closed:
            await self.run_once()
            await asyncio.sleep(min(5, self.settings.interval_seconds))

    async def run_once(self) -> dict[str, Any]:
        """Nonblocking admission: return the steward job ID, not its evaluation."""
        if not self.settings.enabled or self._closed:
            return {"reason": "disabled"}
        if self._monotonic() - self._last_activity < self.settings.idle_seconds:
            return {"reason": "not_idle"}
        if self._monotonic() < self._next_due:
            return {"reason": "not_due"}
        if self._operation and not self._operation.done():
            return {"reason": "already_running"}
        try:
            result = self.steward.submit("improvement", self._run_bounded)
        except RuntimeBusyError:
            return {"reason": "busy"}
        self._next_due = self._monotonic() + self.settings.interval_seconds
        return result

    async def _run_bounded(self):
        generation = self._generation
        task = asyncio.create_task(
            self._experiment(generation), name="katbot-learning-experiment"
        )
        task.add_done_callback(
            lambda done: None if done.cancelled() else done.exception()
        )
        self._operation = task
        try:
            done, _ = await asyncio.wait({task}, timeout=self.settings.timeout_seconds)
            if not done:
                self._generation += 1
                task.cancel()
                result = {"reason": "timeout"}
            else:
                result = task.result()
        except asyncio.CancelledError:
            self._generation += 1
            task.cancel()
            self._last_result = {"reason": "cancelled"}
            raise
        except Exception:
            result = {"reason": "dependency_error"}
        self._last_result = result
        return result

    def _valid(self, generation):
        return not self._closed and generation == self._generation

    def _entry(self, **kwargs):
        factory = self._entry_factory
        if factory is None:
            from .memory import MemoryEntry

            factory = MemoryEntry
        return factory(**kwargs)

    @staticmethod
    def _population(baseline: GuidanceStrategy):
        # Deliberately finite and declared before scores are observed. No model
        # generates instructions, changes graders, or tunes against held-out text.
        candidates = [
            replace(baseline, separate_evidence=True),
            replace(baseline, acknowledge_uncertainty=True),
            replace(baseline, verify_calculations=True),
            replace(baseline, max_response_words=250),
            replace(baseline, response_format="json"),
        ]
        seen = {json.dumps(asdict(baseline), sort_keys=True)}
        for candidate in candidates:
            key = json.dumps(asdict(candidate), sort_keys=True)
            if key not in seen:
                seen.add(key)
                yield candidate

    async def _experiment(self, generation):
        memory, lab = self.steward.agent.memory, self.steward.lab
        attempts = await memory.list_recent_memories(
            limit=100, memory_type="learning_attempt"
        )
        cutoff = self._now() - timedelta(hours=24)
        recent = 0
        attempted = set()
        for attempt in attempts:
            stamp = attempt.timestamp
            if stamp.tzinfo is None:
                stamp = stamp.replace(tzinfo=timezone.utc)
            if stamp >= cutoff:
                recent += 1
            fingerprint = attempt.metadata.get("experiment_fingerprint")
            if not isinstance(fingerprint, str):
                raise ValueError("Invalid durable learning reservation")
            attempted.add(fingerprint)
        if recent >= self.settings.max_daily_experiments:
            return {"reason": "daily_budget_exhausted"}
        dreams = await memory.list_recent_memories(
            limit=10, memory_type="dream_consolidation"
        )
        dream = next(
            (row for row in dreams if row.metadata.get("dream_schema") == "dream-v1"),
            None,
        )
        if dream is None:
            return {"reason": "no_dream_evidence"}
        state = lab.status()
        baseline = GuidanceStrategy(**state["active_strategy"])
        revision = state["revision"]
        selected = None
        for strategy in self._population(baseline):
            fingerprint = self._digest(
                {
                    "suite": self._suite_digest,
                    "baseline": asdict(baseline),
                    "revision": revision,
                    "candidate": asdict(strategy),
                }
            )
            if fingerprint not in attempted:
                selected = (strategy, fingerprint)
                break
        if selected is None:
            return {"reason": "population_exhausted"}
        strategy, fingerprint = selected
        candidate = GuidanceCandidate(
            f"learning:{fingerprint[:32]}",
            strategy,
            (str(dream.id),),
            "Operator-defined closed strategy probe triggered by dream evidence; no dream claim is treated as fact.",
        )
        if not self._valid(generation):
            return {"reason": "interrupted"}
        # A reservation intentionally survives invalid output, cancellation,
        # failure, and restart. A failed experiment is not automatically retried.
        await memory.add_memory(
            self._entry(
                content="Autonomous learning experiment reservation; grading remains operator-controlled.",
                memory_type="learning_attempt",
                entry_id=f"learning-attempt:{fingerprint}",
                timestamp=self._now(),
                metadata={
                    "experiment_fingerprint": fingerprint,
                    "suite_digest": self._suite_digest,
                    "baseline_revision": revision,
                    "candidate_id": candidate.candidate_id,
                    "source_memory_ids": [str(dream.id)],
                    "derived": True,
                    "audience": "project",
                },
            )
        )
        if not self._valid(generation):
            return {"reason": "interrupted"}
        run_id = f"learning-run:{fingerprint}"
        report = await lab.evaluate(candidate, self.cases, run_id)
        result = {
            "reason": "evaluated",
            "run_id": run_id,
            "eligible": report["eligible"],
            "status": report["status"],
            "evaluation_memory_id": report.get("memory_id"),
            "baseline_revision": revision,
            "promoted": False,
        }
        if (
            self.settings.auto_promote
            and report["eligible"]
            and report["status"] == "staged"
            and self._valid(generation)
            and lab.revision == revision
        ):
            promoted = await lab.promote(run_id, expected_revision=revision)
            result.update(
                promoted=True,
                state_memory_id=promoted.get("state_memory_id"),
                revision=promoted["revision"],
            )
        return result
