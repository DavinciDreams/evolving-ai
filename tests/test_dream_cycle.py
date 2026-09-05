"""Offline adversarial/contract tests for append-only dream consolidation."""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from evolving_agent.core.dream_cycle import DreamConfig, DreamConsolidationService


NOW = datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)


def entry(
    content, memory_type="interaction", metadata=None, timestamp=None, entry_id="1"
):
    return SimpleNamespace(
        content=content,
        memory_type=memory_type,
        metadata=metadata or {},
        timestamp=timestamp or NOW,
        id=entry_id,
    )


class Memory:
    backend = "ham"

    def __init__(self, rows=None):
        self.rows = (
            rows
            if rows is not None
            else [
                entry("The user prefers deterministic checks.", entry_id="1"),
                entry("The Rust port repeats those checks.", entry_id="2"),
            ]
        )
        self.writes = []
        self.reads = []

    async def list_recent_memories(self, limit=10, memory_type=None):
        self.reads.append((limit, memory_type))
        return sorted(
            [
                row
                for row in self.rows
                if memory_type is None or row.memory_type == memory_type
            ],
            key=lambda row: row.timestamp,
            reverse=True,
        )[:limit]

    async def add_memory(self, row):
        # Models HAM's stable source-id idempotency, not in-memory service state.
        existing = next(
            (existing for existing in self.rows if existing.id == row.id), None
        )
        if existing:
            return existing.id
        self.rows.append(row)
        self.writes.append(row)
        return row.id


class Model:
    def __init__(self, override=None):
        self.calls = []
        self.override = override

    async def generate_response(self, **kwargs):
        self.calls.append(kwargs)
        if self.override is not None:
            return self.override
        rows = json.loads(kwargs["prompt"].split("UNTRUSTED_SOURCES_JSON:\n")[1])
        return json.dumps(
            {
                "summary": "Repeated interest in deterministic verification.",
                "observations": [
                    {"source_id": rows[0]["id"], "quote": rows[0]["text"][:200]}
                ],
                "hypotheses": [
                    {
                        "statement": "A shared fixture suite may reveal cross-language divergences.",
                        "source_ids": [row["id"] for row in rows],
                        "test": "Compare identical fixed inputs and expected outputs in both implementations.",
                    }
                ],
            }
        )


def service(memory=None, model=None, **kwargs):
    settings = kwargs.pop("settings", DreamConfig(enabled=True, idle_seconds=0))
    return DreamConsolidationService(
        memory or Memory(),
        model,
        settings=settings,
        entry_factory=entry,
        now=lambda: NOW,
        **kwargs,
    )


@pytest.mark.asyncio
async def test_synthesis_is_cited_hypothetical_bounded_and_append_only():
    memory, model = Memory(), Model()
    originals = list(memory.rows)
    dream = service(memory, model)
    result = await dream.run_once()
    assert result.created and result.source_count == 2 and result.hypotheses == 1
    assert [row.memory_type for row in memory.writes] == [
        "dream_attempt",
        "dream_consolidation",
    ]
    assert memory.rows[:2] == originals
    receipt = memory.writes[-1]
    assert receipt.metadata["epistemic_status"] == "unverified_synthesis"
    assert receipt.metadata["pruning_enabled"] is False
    assert receipt.metadata["source_memory_ids"] == ["1", "2"]
    assert len(receipt.metadata["source_checksums"]) == 2
    assert all(len(checksum) == 64 for checksum in receipt.metadata["source_checksums"])
    assert model.calls[0]["max_tokens"] == 900
    assert len(model.calls[0]["prompt"]) <= dream.settings.max_input_chars
    assert len(receipt.content) <= dream.settings.max_output_chars
    assert "source text" not in json.dumps(dream.status())


@pytest.mark.asyncio
async def test_new_service_after_restart_skips_exact_covered_sources_without_llm_call():
    memory, model = Memory(), Model()
    assert (await service(memory, model).run_once()).created
    result = await service(memory, model).run_once()
    assert not result.created and result.reason == "insufficient_new_sources"
    assert len(model.calls) == 1
    assert len(memory.writes) == 2


@pytest.mark.asyncio
async def test_changed_content_same_source_id_has_distinct_snapshot_checksum():
    memory = Memory()
    first = await service(memory).run_once()
    memory.rows[0] = entry("The user now prefers stochastic tests.", entry_id="1")
    memory.rows[1] = entry("The port now includes property-based checks.", entry_id="2")
    second = await service(memory).run_once()
    assert first.created and second.created and first.memory_id != second.memory_id


@pytest.mark.asyncio
async def test_duplicate_text_retains_ids_but_not_double_evidence():
    memory = Memory(
        [
            entry("Same text.", entry_id="1"),
            entry("Same text.", entry_id="2"),
            entry("Another independent source.", entry_id="3"),
        ]
    )
    result = await service(memory).run_once()
    assert result.created and result.source_count == 2
    assert memory.writes[-1].metadata["source_memory_ids"] == ["1", "2", "3"]


@pytest.mark.asyncio
async def test_full_content_checksum_not_prefix_controls_deduplication():
    prefix = "x" * 2000
    memory = Memory(
        [entry(prefix + " one", entry_id="1"), entry(prefix + " two", entry_id="2")]
    )
    result = await service(memory).run_once()
    assert result.created and result.source_count == 2


@pytest.mark.asyncio
async def test_oversized_full_sources_are_skipped_before_synchronous_redaction():
    memory = Memory(
        [entry("x" * 65537, entry_id="1"), entry("small source", entry_id="2")]
    )
    assert (await service(memory).run_once()).reason == "insufficient_new_sources"
    assert not memory.writes


@pytest.mark.asyncio
async def test_oversized_or_invalid_receipt_manifest_fails_closed():
    memory = Memory()
    memory.rows.append(
        entry(
            "receipt",
            "dream_consolidation",
            {"dream_schema": "dream-v1", "source_checksums": ["not-a-sha256"]},
            entry_id="3",
        )
    )
    assert (await service(memory).run_once()).reason == "dependency_error"
    assert not memory.writes


@pytest.mark.asyncio
async def test_extracts_without_model_and_never_claims_generated_insights():
    memory = Memory()
    result = await service(memory).run_once()
    assert result.created and result.hypotheses == 0
    assert memory.writes[-1].metadata["mode"] == "extractive"
    assert memory.writes[0].metadata["reserved_output_tokens"] == 0


@pytest.mark.asyncio
async def test_sensitive_values_are_redacted_before_prompt_or_persistence():
    secret = "sk-" + "z" * 30
    nsec = "nsec1" + "q" * 58
    pem = "-----BEGIN PRIVATE KEY-----\nvery-private-data\n-----END PRIVATE KEY-----"
    memory = Memory(
        [
            entry(f"api_key={secret}; user asks about tests. {nsec}", entry_id="1"),
            entry(f"Old key material: {pem}", entry_id="2"),
        ]
    )
    model = Model()
    assert (await service(memory, model).run_once()).created
    serialized = json.dumps(model.calls) + json.dumps(
        [vars(row) for row in memory.writes], default=str
    )
    for value in [secret, nsec, "very-private-data"]:
        assert value not in serialized
    assert all(
        source["redacted"] for source in memory.writes[-1].metadata["source_manifest"]
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response",
    [
        "not JSON",
        "[]",
        '{"summary":"unbacked fact","observations":[],"hypotheses":[]}',
        json.dumps(
            {
                "summary": "x",
                "observations": [{"source_id": "999", "quote": "fabricated"}],
                "hypotheses": [],
            }
        ),
        json.dumps(
            {
                "summary": "x",
                "observations": [{"source_id": "1", "quote": "fabricated"}],
                "hypotheses": [],
            }
        ),
        json.dumps(
            {
                "summary": "password=ultra-secret-value",
                "observations": [],
                "hypotheses": [],
            }
        ),
        "x" * 7000,
    ],
)
async def test_invalid_or_unsafe_generation_is_rejected_without_consolidation(response):
    memory = Memory()
    result = await service(memory, Model(response)).run_once()
    assert result.reason == "invalid_synthesis"
    assert [row.memory_type for row in memory.writes] == ["dream_attempt"]


@pytest.mark.asyncio
async def test_dreams_evaluations_quarantine_and_private_memories_are_not_sources():
    memory = Memory(
        [
            entry("Generated interpretation", "dream_consolidation", entry_id="d"),
            entry("Score 0.7", "evaluation", entry_id="e"),
            entry("Private content", metadata={"audience": "private"}, entry_id="p"),
            entry("Quarantined content", metadata={"quarantined": True}, entry_id="q"),
            entry("Derived content", metadata={"derived": True}, entry_id="g"),
        ]
    )
    assert (await service(memory).run_once()).reason == "insufficient_new_sources"
    assert memory.writes == []


@pytest.mark.asyncio
async def test_daily_reservation_budget_survives_restart_and_failed_model_output():
    memory, model = Memory(), Model("invalid")
    settings = DreamConfig(enabled=True, idle_seconds=0, max_daily_cycles=1)
    assert (
        await service(memory, model, settings=settings).run_once()
    ).reason == "invalid_synthesis"
    assert (
        await service(memory, model, settings=settings).run_once()
    ).reason == "daily_budget_exhausted"
    assert len(model.calls) == 1


@pytest.mark.asyncio
async def test_daily_output_token_limit_prevents_call():
    memory, model = Memory(), Model()
    settings = DreamConfig(enabled=True, idle_seconds=0, max_daily_output_tokens=100)
    assert (
        await service(memory, model, settings=settings).run_once()
    ).reason == "daily_budget_exhausted"
    assert not model.calls and not memory.writes


@pytest.mark.asyncio
@pytest.mark.parametrize("amount", [-1, True, "unknown", 1.5])
async def test_corrupt_persisted_quota_fails_closed(amount):
    memory, model = Memory(), Model()
    memory.rows.append(
        entry(
            "Reservation",
            "dream_attempt",
            {"reserved_output_tokens": amount},
            entry_id="bad",
        )
    )
    assert (await service(memory, model).run_once()).reason == "dependency_error"
    assert not model.calls and not memory.writes


@pytest.mark.asyncio
async def test_old_reservations_expire_on_rolling_24_hour_boundary():
    memory = Memory()
    memory.rows.append(
        entry(
            "Reservation",
            "dream_attempt",
            {"reserved_output_tokens": 900},
            NOW - timedelta(hours=25),
            "old",
        )
    )
    settings = DreamConfig(enabled=True, idle_seconds=0, max_daily_cycles=1)
    assert (await service(memory, Model(), settings=settings).run_once()).created


@pytest.mark.asyncio
async def test_unknown_budget_state_fails_closed_without_provider_call():
    memory, model = Memory(), Model()

    async def unavailable(**kwargs):
        raise RuntimeError("password=must-not-leak")

    memory.list_recent_memories = unavailable
    dream = service(memory, model)
    assert (await dream.run_once()).reason == "dependency_error"
    assert not model.calls and not memory.writes
    assert "must-not-leak" not in json.dumps(dream.status())


@pytest.mark.asyncio
async def test_uncertain_post_write_failure_recovers_using_durable_receipt():
    memory, model = Memory(), Model()
    original_add = memory.add_memory

    async def uncertain(row):
        result = await original_add(row)
        if row.memory_type == "dream_consolidation":
            raise RuntimeError("transport disconnected after durable write")
        return result

    memory.add_memory = uncertain
    assert (await service(memory, model).run_once()).reason == "dependency_error"
    memory.add_memory = original_add
    assert (
        await service(memory, model).run_once()
    ).reason == "insufficient_new_sources"
    assert len(model.calls) == 1


class WaitingModel:
    def __init__(self):
        self.entered = asyncio.Event()
        self.cancelled = False

    async def generate_response(self, **kwargs):
        self.entered.set()
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            self.cancelled = True
            raise


@pytest.mark.asyncio
async def test_non_reentrant_skips_instead_of_queuing():
    memory, model = Memory(), WaitingModel()
    dream = service(memory, model)
    first = asyncio.create_task(dream.run_once())
    await model.entered.wait()
    assert (await dream.run_once()).reason == "already_running"
    first.cancel()
    with pytest.raises(asyncio.CancelledError):
        await first
    await dream.stop()
    assert model.cancelled and not dream.status()["running"]


@pytest.mark.asyncio
async def test_model_timeout_keeps_only_quota_reservation():
    memory, model = Memory(), WaitingModel()
    settings = DreamConfig(enabled=True, idle_seconds=0, llm_timeout_seconds=0.01)
    assert (
        await service(memory, model, settings=settings).run_once()
    ).reason == "model_timeout"
    assert model.cancelled
    assert [row.memory_type for row in memory.writes] == ["dream_attempt"]


@pytest.mark.asyncio
async def test_model_that_returns_after_ignoring_timeout_cannot_publish():
    class LateModel(Model):
        async def generate_response(self, **kwargs):
            try:
                await asyncio.Future()
            except asyncio.CancelledError:
                await asyncio.sleep(0.01)
                return await super().generate_response(**kwargs)

    memory = Memory()
    settings = DreamConfig(enabled=True, idle_seconds=0, llm_timeout_seconds=0.01)
    result = await service(memory, LateModel(), settings=settings).run_once()
    assert result.reason == "model_timeout"
    assert [row.memory_type for row in memory.writes] == ["dream_attempt"]


@pytest.mark.asyncio
async def test_cycle_timeout_covers_storage_not_only_model():
    memory = Memory()

    async def waiting(**kwargs):
        await asyncio.Future()

    memory.list_recent_memories = waiting
    settings = DreamConfig(enabled=True, idle_seconds=0, timeout_seconds=0.01)
    assert (await service(memory, settings=settings).run_once()).reason == "timeout"
    assert not memory.writes


@pytest.mark.asyncio
async def test_cancellation_resistant_dependency_cannot_extend_deadline_or_reenter():
    memory = Memory()
    released = asyncio.Event()
    calls = [0]
    original_recent = memory.list_recent_memories

    async def stubborn(**kwargs):
        calls[0] += 1
        if calls[0] == 1:
            while not released.is_set():
                try:
                    await released.wait()
                except asyncio.CancelledError:
                    pass
        return await original_recent(**kwargs)

    memory.list_recent_memories = stubborn
    settings = DreamConfig(
        enabled=True, idle_seconds=0, timeout_seconds=0.01, stop_timeout_seconds=0.01
    )
    dream = service(memory, settings=settings)
    result = await asyncio.wait_for(dream.run_once(), timeout=0.2)
    assert result.reason == "timeout"
    assert dream.status()["running"]
    assert (await dream.run_once()).reason == "already_running"
    assert await dream.stop() is False
    released.set()
    for _ in range(10):
        await asyncio.sleep(0)
    assert not dream.status()["running"]
    assert not memory.writes


@pytest.mark.asyncio
async def test_idle_predicate_failure_is_safe_noop():
    def failing():
        raise RuntimeError("private diagnostic")

    memory = Memory()
    assert (await service(memory, is_idle=failing).run_once()).reason == "not_idle"
    assert not memory.reads


@pytest.mark.asyncio
async def test_foreground_activity_cancels_active_dream_without_stopping_scheduler():
    memory, model = Memory(), WaitingModel()
    dream = service(memory, model)
    assert dream.start() is True
    assert dream.start() is False
    await model.entered.wait()
    dream.note_activity()
    for _ in range(10):
        await asyncio.sleep(0)
    assert dream.status()["worker_started"]
    assert model.cancelled
    assert await dream.stop()
    assert not dream.status()["worker_started"]
    assert [row.memory_type for row in memory.writes] == ["dream_attempt"]


@pytest.mark.asyncio
async def test_idle_gate_checked_again_before_output():
    state = {"idle": True}
    model = Model()
    original_generate = model.generate_response

    async def changed(**kwargs):
        result = await original_generate(**kwargs)
        state["idle"] = False
        return result

    model.generate_response = changed
    memory = Memory()
    result = await service(memory, model, is_idle=lambda: state["idle"]).run_once()
    assert result.reason == "interrupted"
    assert [row.memory_type for row in memory.writes] == ["dream_attempt"]


@pytest.mark.asyncio
async def test_disabled_unsupported_busy_and_interval_gates_do_no_extra_io():
    memory = Memory()
    assert (
        await service(memory, settings=DreamConfig()).run_once()
    ).reason == "disabled"
    assert (
        await service(memory, is_idle=lambda: False).run_once()
    ).reason == "not_idle"
    memory.backend = "chroma"
    assert (await service(memory).run_once()).reason == "ham_required"
    assert not memory.reads and not memory.writes
    memory.backend = "ham"
    dream = service(memory)
    assert (await dream.run_once()).created
    reads = len(memory.reads)
    assert (await dream.run_once()).reason == "not_due"
    assert len(memory.reads) == reads


@pytest.mark.asyncio
async def test_idle_timer_is_reset_by_activity():
    clock = [0.0]
    dream = service(
        monotonic=lambda: clock[0], settings=DreamConfig(enabled=True, idle_seconds=60)
    )
    clock[0] = 59
    assert (await dream.run_once()).reason == "not_idle"
    dream.note_activity()
    clock[0] = 100
    assert (await dream.run_once()).reason == "not_idle"
    clock[0] = 120
    assert (await dream.run_once()).created


@pytest.mark.asyncio
async def test_prompt_budget_excludes_whole_sources():
    memory = Memory([entry("x" * 7000 + str(i), entry_id=str(i)) for i in range(1, 8)])
    model = Model()
    settings = DreamConfig(
        enabled=True, idle_seconds=0, max_input_chars=5000, max_source_chars=2000
    )
    result = await service(memory, model, settings=settings).run_once()
    if result.created:
        assert len(model.calls[0]["prompt"]) <= 5000
    else:
        assert result.reason == "input_budget_exhausted"
        assert not model.calls


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_sources": 0},
        {"max_sources": 101},
        {"idle_seconds": -1},
        {"timeout_seconds": float("nan")},
        {"max_daily_cycles": 101},
        {"max_sources": 1, "min_sources": 2},
        {"max_tokens": 99.5},
        {"enabled": "true"},
    ],
)
def test_invalid_limits_fail_closed(kwargs):
    with pytest.raises(ValueError):
        DreamConfig(**kwargs)


def test_environment_configuration_is_explicit_and_opt_in():
    assert not DreamConfig.from_env({}).enabled
    cfg = DreamConfig.from_env(
        {
            "DREAM_CYCLE_ENABLED": "true",
            "DREAM_CYCLE_IDLE_SECONDS": "60",
            "DREAM_CYCLE_MAX_TOKENS": "500",
        }
    )
    assert cfg.enabled and cfg.idle_seconds == 60 and cfg.max_tokens == 500
    with pytest.raises(ValueError):
        DreamConfig.from_env({"DREAM_CYCLE_ENABLED": "perhaps"})
    with pytest.raises(ValueError):
        DreamConfig.from_env({"DREAM_CYCLE_MAX_TOKENS": "a lot"})
