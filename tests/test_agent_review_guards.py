"""Regression tests from independent runtime/evaluation boundary review."""

import asyncio
from unittest.mock import AsyncMock, patch

from tests import test_agent_run as agent_tests
from evolving_agent.core.agent import SelfImprovingAgent


agent = agent_tests.agent
_drain_tasks = agent_tests._drain_tasks
_make_config = agent_tests._make_config
_make_eval_result = agent_tests._make_eval_result


def invalid_evaluation(score=0.95):
    result = _make_eval_result(score)
    result.metadata = {"failed_criteria": ["safety"]}
    return result


async def test_best_of_n_cannot_prefer_an_unmeasured_partial_failure(agent):
    cfg = _make_config(enable_evaluation=True)
    cfg.best_of_n_count = 2
    cfg.enable_best_of_n = True
    measured = _make_eval_result(0.4)
    measured.confidence = 0.5
    agent._generate_response.return_value = "original measured answer"
    agent._generate_text_candidate = AsyncMock(return_value="unreliable candidate")
    agent.evaluator.evaluate_output.side_effect = [measured, invalid_evaluation()]
    agent._improve_response.side_effect = lambda query, response, result, context: (
        response,
        result,
    )
    with patch("evolving_agent.core.agent.config", cfg):
        result = await agent.run("question", wait_for_storage=True)
    assert result == "original measured answer"
    assert agent.last_evaluation_score == 0.4
    agent._generate_response.assert_awaited_once()
    agent._generate_text_candidate.assert_awaited_once()


async def test_revision_cannot_treat_partial_failure_score_as_improvement(agent):
    cfg = _make_config(enable_evaluation=True)
    cfg.iterative_revision_target_score = 0.9
    cfg.iterative_revision_max_rounds = 1
    cfg.temperature = 0.2
    cfg.max_tokens = 100
    baseline = _make_eval_result(0.4)
    baseline.weaknesses = ["clarity"]
    baseline.improvement_suggestions = ["Clarify the answer"]
    agent._evaluate_bounded = AsyncMock(return_value=invalid_evaluation(0.8))
    with patch("evolving_agent.core.agent.config", cfg), patch(
        "evolving_agent.core.agent.llm_manager.generate_response",
        AsyncMock(return_value="unmeasured revision"),
    ):
        response, result = await SelfImprovingAgent._improve_response(
            agent, "question", "original measured answer", baseline, {}
        )
    assert response == "original measured answer"
    assert result is baseline


async def test_preference_training_pairs_are_redacted_before_persistence(agent):
    cfg = _make_config(enable_evaluation=True)
    baseline = _make_eval_result(0.4)
    agent.evaluator.evaluate_output.return_value = baseline
    agent._generate_response.return_value = "api_key=original-secret-value"
    agent._improve_response.return_value = (
        "api_key=revised-secret-value",
        _make_eval_result(0.9),
    )
    agent.data_manager.save_preference_pair = AsyncMock()
    with patch("evolving_agent.core.agent.config", cfg):
        await agent.run("api_key=query-secret-value", wait_for_storage=True)
    stored = str(agent.data_manager.save_preference_pair.call_args)
    assert "original-secret-value" not in stored
    assert "revised-secret-value" not in stored
    assert "query-secret-value" not in stored


async def test_early_self_edit_response_uses_same_redaction_boundary(agent):
    cfg = _make_config(enable_self_modification=True)
    agent._is_self_edit_request.return_value = True
    agent._handle_self_edit_request.return_value = "api_key=early-secret-value"
    with patch("evolving_agent.core.agent.config", cfg):
        response = await agent.run("api_key=query-secret-value", wait_for_storage=True)
    assert "early-secret-value" not in response
    stored = str(agent.data_manager.save_interaction.call_args)
    assert "early-secret-value" not in stored and "query-secret-value" not in stored


async def test_deferred_maintenance_does_not_receive_unredacted_query(agent):
    cfg = _make_config(enable_evaluation=True, auto_update_knowledge=True)
    with patch("evolving_agent.core.agent.config", cfg):
        await agent.run("api_key=maintenance-secret-value", wait_for_storage=True)
        await _drain_tasks()
    assert "maintenance-secret-value" not in str(
        agent.knowledge_updater.update_from_interaction.call_args
    )


async def test_optional_evaluation_deadline_survives_cancellation_resistance(
    agent, monkeypatch
):
    monkeypatch.setenv("EVALUATION_TIMEOUT_SECONDS", "0.01")
    released = asyncio.Event()

    async def stubborn(**kwargs):
        while not released.is_set():
            try:
                await released.wait()
            except asyncio.CancelledError:
                pass
        return _make_eval_result(0.9)

    agent.evaluator.evaluate_output.side_effect = stubborn
    cfg = _make_config(enable_evaluation=True)
    try:
        with patch("evolving_agent.core.agent.config", cfg):
            task = asyncio.create_task(agent.run("question", wait_for_storage=True))
            done, _ = await asyncio.wait({task}, timeout=0.1)
            assert done, "optional evaluator must not consume the whole chat deadline"
            assert task.result() == "Test answer"
            assert agent.last_evaluation_score is None
            assert (
                agent.runtime.busy
            ), "resistant evaluator must retain an occupied dependency lease"
    finally:
        released.set()
        if "task" in locals():
            await asyncio.gather(task, return_exceptions=True)
