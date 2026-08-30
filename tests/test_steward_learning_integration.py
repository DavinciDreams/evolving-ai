"""Real control-plane/dream/lab loop with in-memory HAM and a synthetic model."""

import json
from dataclasses import asdict
from datetime import datetime, timezone
from types import SimpleNamespace

from evolving_agent.core.dream_cycle import DreamConfig, DreamConsolidationService
from evolving_agent.core.learning_cycle import LearningConfig, LearningCycle
from evolving_agent.core.runtime import AgentRuntime
from evolving_agent.core.steward import StewardControl
from evolving_agent.self_modification.improvement_lab import (
    BenchmarkCase,
    GuidanceStrategy,
)


def entry(
    content, memory_type="interaction", metadata=None, timestamp=None, entry_id="1"
):
    return SimpleNamespace(
        content=content,
        memory_type=memory_type,
        metadata=metadata or {},
        timestamp=timestamp or datetime.now(timezone.utc),
        id=entry_id,
    )


class InMemoryHAM:
    backend = "ham"

    def __init__(self):
        self.rows = [
            entry(
                "The user values distinctions between evidence and inference.",
                entry_id="1",
            ),
            entry(
                "A recent response confused a hypothesis with a measurement.",
                entry_id="2",
            ),
        ]
        self.source_ids = {}

    async def list_recent_memories(self, limit=10, memory_type=None):
        rows = [
            row
            for row in self.rows
            if memory_type is None or row.memory_type == memory_type
        ]
        return sorted(rows, key=lambda row: row.timestamp, reverse=True)[:limit]

    async def add_memory(self, row):
        if row.id in self.source_ids:
            return self.source_ids[row.id]
        numeric_id = str(len(self.rows) + 1)
        self.source_ids[row.id] = numeric_id
        self.rows.append(
            entry(row.content, row.memory_type, row.metadata, row.timestamp, numeric_id)
        )
        return numeric_id

    async def get_memory(self, memory_id):
        return next((row for row in self.rows if row.id == str(memory_id)), None)


class SyntheticModel:
    def __init__(self):
        self.calls = []

    async def generate_response(self, **kwargs):
        self.calls.append(kwargs)
        if "UNTRUSTED_SOURCES_JSON:\n" in kwargs["prompt"]:
            sources = json.loads(kwargs["prompt"].split("UNTRUSTED_SOURCES_JSON:\n")[1])
            return json.dumps(
                {
                    "summary": "Evidence/inference separation is worth testing.",
                    "observations": [
                        {"source_id": sources[0]["id"], "quote": sources[0]["text"]}
                    ],
                    "hypotheses": [
                        {
                            "statement": "Explicit evidence labels might improve accuracy.",
                            "source_ids": [source["id"] for source in sources],
                            "test": "Evaluate a fixed paired fixture suite.",
                        }
                    ],
                }
            )
        if "Distinguish observed evidence" in kwargs["system_prompt"]:
            return kwargs["prompt"].split()[-1]
        return "wrong"


async def test_dream_to_experiment_promotion_rollback_and_exact_id_restore(monkeypatch):
    monkeypatch.setenv("IMPROVEMENT_LAB_ENABLED", "true")
    monkeypatch.setenv("DREAM_CYCLE_ENABLED", "false")
    memory, model = InMemoryHAM(), SyntheticModel()
    originals = [vars(row).copy() for row in memory.rows]
    agent = SimpleNamespace(
        memory=memory, runtime=AgentRuntime(), last_storage_status={}
    )
    steward = StewardControl(agent, model)
    dreams = DreamConsolidationService(
        memory,
        model,
        settings=DreamConfig(enabled=True, idle_seconds=0),
        entry_factory=entry,
        is_idle=lambda: agent.runtime.idle,
    )
    steward.dreams = dreams
    dream = await dreams.run_once()
    assert dream.created and dream.hypotheses == 1
    dream_row = await memory.get_memory(dream.memory_id)
    assert dream_row.metadata["source_memory_ids"] == ["1", "2"]
    assert dream_row.metadata["epistemic_status"] == "unverified_synthesis"

    cases = tuple(
        BenchmarkCase(
            str(i), f"Return {i}", str(i), "development" if i < 2 else "holdout", i == 0
        )
        for i in range(4)
    )
    learning = LearningCycle(
        steward,
        cases=cases,
        settings=LearningConfig(enabled=True, idle_seconds=0, auto_promote=True),
        entry_factory=entry,
    )
    steward.learning = learning
    admitted = await learning.run_once()
    assert admitted["status"] == "queued"
    await steward._task
    result = steward.jobs[admitted["job_id"]]["result"]
    assert result["promoted"] and result["eligible"] and result["revision"] == 1
    report_row = await memory.get_memory(result["evaluation_memory_id"])
    report = json.loads(report_row.content)
    assert report["candidate"]["source_memory_ids"] == [dream.memory_id]
    assert report["calls"] == 8
    assert report["scores"]["holdout"] == {"baseline": 0.0, "candidate": 1.0}
    assert "Distinguish observed evidence" in steward.lab.active_guidance

    # The rollback uses the same real control-plane admission and lab CAS path.
    rollback_job = steward.submit(
        "improvement",
        lambda: steward.lab.rollback(1, "Offline review requests rollback"),
    )
    await steward._task
    rollback = steward.jobs[rollback_job["job_id"]]["result"]
    assert rollback["revision"] == 2
    assert steward.lab.status()["active_strategy"] == asdict(GuidanceStrategy())
    assert [vars(row) for row in memory.rows[:2]] == originals

    # A new process restores the operator-pinned exact state artifact, not search.
    restarted = StewardControl(
        SimpleNamespace(memory=memory, runtime=AgentRuntime(), last_storage_status={}),
        model,
    )
    await restarted.lab.restore(rollback["state_memory_id"])
    assert restarted.lab.revision == 2
    assert restarted.lab.status()["active_strategy"] == asdict(GuidanceStrategy())
    assert (
        await DreamConsolidationService(
            memory,
            model,
            settings=DreamConfig(enabled=True, idle_seconds=0),
            entry_factory=entry,
        ).run_once()
    ).reason == "insufficient_new_sources"
    assert len(model.calls) == 9  # one dream + eight paired evaluation outputs
    await steward.close()
    await restarted.close()
