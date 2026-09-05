"""Additive SQLite provenance migration; all writes confined to tmp_path."""

import sqlite3
from unittest.mock import AsyncMock, patch

import pytest

from tests import test_agent_run as agent_test_stubs  # noqa: F401
from evolving_agent.core.evaluator import OutputEvaluator
from evolving_agent.utils.persistent_storage import PersistentDataManager


async def manager_at(tmp_path):
    manager = PersistentDataManager()
    manager.interactions_db = tmp_path / "test.sqlite"
    manager._update_session_stats = AsyncMock()
    await manager._initialize_interactions_db()
    return manager


async def test_old_schema_migration_preserves_rows_and_marks_them_unverified(tmp_path):
    path = tmp_path / "test.sqlite"
    with sqlite3.connect(path) as connection:
        connection.execute(
            """CREATE TABLE evaluations (
            id INTEGER PRIMARY KEY AUTOINCREMENT, interaction_id INTEGER,
            timestamp DATETIME NOT NULL, overall_score REAL NOT NULL,
            criteria_scores TEXT, feedback TEXT, improvement_suggestions TEXT, confidence REAL
        )"""
        )
        connection.execute(
            """INSERT INTO evaluations
            (timestamp, overall_score, criteria_scores, feedback, confidence)
            VALUES ('2026-05-21T00:00:00', 0.7, '{"accuracy":0.7}', 'Legacy neutral', 0.9)"""
        )
    manager = await manager_at(tmp_path)
    await manager._initialize_interactions_db()  # migration is safe to repeat
    rows = await manager.get_recent_evaluations()
    assert len(rows) == 1 and rows[0]["overall_score"] == 0.7
    assert rows[0]["evaluation_kind"] == "legacy_unverified"


async def test_explicit_kind_is_round_tripped_and_old_callers_stay_unverified(tmp_path):
    manager = await manager_at(tmp_path)
    values = dict(
        interaction_id=1,
        overall_score=0.9,
        criteria_scores={"accuracy": 0.9},
        feedback="Observed LLM judgment",
        improvement_suggestions=[],
        confidence=0.0,
    )
    await manager.save_evaluation(**values)
    await manager.save_evaluation(
        **values, evaluation_kind="llm_judgment_not_independent_benchmark"
    )
    rows = await manager.get_recent_evaluations()
    assert {row["evaluation_kind"] for row in rows} == {
        "legacy_unverified",
        "llm_judgment_not_independent_benchmark",
    }
    evaluator = OutputEvaluator()
    with patch(
        "evolving_agent.core.evaluator.persistent_data_manager.get_recent_evaluations",
        AsyncMock(return_value=rows),
    ):
        await evaluator._load_history_from_db()
    assert len(evaluator.evaluation_history) == 1
    result = evaluator.evaluation_history[0][2]
    assert result.measured_score == 0.9 and result.confidence == 0.0
    assert (
        result.metadata["evaluation_kind"] == "llm_judgment_not_independent_benchmark"
    )


@pytest.mark.parametrize(
    "override",
    [
        {"overall_score": float("nan")},
        {"confidence": 2},
        {"criteria_scores": "{}"},
        {"criteria_scores": '{"accuracy":true}'},
        {"evaluation_kind": "unknown"},
    ],
)
async def test_invalid_historical_measurements_are_not_loaded(override):
    row = {
        "overall_score": 0.9,
        "confidence": 0.8,
        "criteria_scores": '{"accuracy":0.9}',
        "improvement_suggestions": "[]",
        "feedback": "",
        "timestamp": "2026-08-30T00:00:00",
        "evaluation_kind": "llm_judgment_not_independent_benchmark",
        **override,
    }
    evaluator = OutputEvaluator()
    with patch(
        "evolving_agent.core.evaluator.persistent_data_manager.get_recent_evaluations",
        AsyncMock(return_value=[row]),
    ):
        await evaluator._load_history_from_db()
    assert evaluator.evaluation_history == []


async def test_unknown_new_evidence_kind_is_rejected_before_write(tmp_path):
    manager = await manager_at(tmp_path)
    with pytest.raises(ValueError, match="evidence kind"):
        await manager.save_evaluation(
            1, 0.9, {"accuracy": 0.9}, "", [], 0.9, evaluation_kind="verified_truth"
        )
    assert await manager.get_recent_evaluations() == []
