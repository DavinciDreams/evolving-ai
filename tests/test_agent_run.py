"""Unit tests for SelfImprovingAgent.run() with all dependencies mocked.

Heavy native libraries (chromadb, sentence_transformers, discord, openai,
ai_sdk) are stubbed in sys.modules before any evolving_agent import so that
the test runner never needs those packages installed.
"""
import asyncio
import sys
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Stub out native / optional libraries that are not installed in the test env
# before ANY evolving_agent import happens.
# ---------------------------------------------------------------------------
_STUB_MODULES = [
    "chromadb",
    "chromadb.config",
    "chromadb.api",
    "chromadb.api.models",
    "sentence_transformers",
    "openai",
    "ai_sdk",
    "ai_sdk.types",
    "ai_sdk.providers",
    "ai_sdk.providers.openai",
    "discord",
]
for _mod in _STUB_MODULES:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

# ---------------------------------------------------------------------------
# Now safe to import project code
# ---------------------------------------------------------------------------
import pytest
from unittest.mock import AsyncMock, patch

from evolving_agent.core.agent import SelfImprovingAgent
from evolving_agent.core.evaluator import EvaluationResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _drain_tasks():
    """Wait for all pending background tasks to complete."""
    current = asyncio.current_task()
    pending = [t for t in asyncio.all_tasks() if t is not current]
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)


def _make_config(
    *,
    enable_evaluation: bool = False,
    auto_update_knowledge: bool = False,
    enable_self_modification: bool = False,
    discord_status_on_knowledge_update: bool = False,
) -> MagicMock:
    """Return a minimal config mock with the flags read by run()."""
    cfg = MagicMock()
    cfg.enable_evaluation = enable_evaluation
    cfg.auto_update_knowledge = auto_update_knowledge
    cfg.enable_self_modification = enable_self_modification
    cfg.discord_status_on_knowledge_update = discord_status_on_knowledge_update
    cfg.reflexion_interval = 50  # prevent MagicMock arithmetic in _post_response_work
    return cfg


def _make_eval_result(overall_score: float = 0.9) -> EvaluationResult:
    """Construct a minimal EvaluationResult for use in tests."""
    return EvaluationResult(
        overall_score=overall_score,
        criteria_scores={},
        strengths=["Clear response"],
        weaknesses=[],
        improvement_suggestions=[],
        feedback="Good job",
        confidence=0.95,
        metadata={},
    )


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def agent():
    """Return a SelfImprovingAgent whose __init__ is bypassed and whose
    every external dependency is replaced with a mock so no real I/O occurs."""
    with patch.object(SelfImprovingAgent, "__init__", return_value=None):
        a = SelfImprovingAgent()

    # ---- State attributes ----
    a.initialized = True
    a.interaction_count = 0
    a.session_id = "test-session"
    a.improvement_cycle_count = 0
    a.last_evaluation_score = None
    a.component_health = {}

    # ---- Logging ----
    a.logger = MagicMock()

    # ---- Context manager ----
    a.context_manager = MagicMock()
    a.context_manager.get_relevant_context = AsyncMock(return_value={})

    # ---- Data manager ----
    a.data_manager = MagicMock()
    a.data_manager.get_conversation_history = AsyncMock(return_value=[])
    a.data_manager.save_interaction = AsyncMock(return_value="interaction-123")
    a.data_manager.save_evaluation = AsyncMock()
    a.data_manager.save_agent_state = AsyncMock()

    # ---- Evaluator ----
    a.evaluator = MagicMock()
    a.evaluator.evaluate_output = AsyncMock(return_value=_make_eval_result())

    # ---- Knowledge updater ----
    a.knowledge_updater = MagicMock()
    a.knowledge_updater.update_from_interaction = AsyncMock(return_value=0)

    # ---- Private methods that hit external systems ----
    a._generate_response = AsyncMock(return_value="Test answer")
    # _improve_response now returns (response_str, EvaluationResult)
    a._improve_response = AsyncMock(return_value=("Improved answer", _make_eval_result()))
    a._store_interaction = AsyncMock()
    a._store_error = AsyncMock()
    a._is_self_edit_request = MagicMock(return_value=False)
    a._handle_self_edit_request = AsyncMock(return_value="Self-edit response")
    a._consider_self_modification = AsyncMock()
    a._notify_status = AsyncMock()

    return a


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

async def test_run_raises_if_not_initialized(agent):
    """run() must raise RuntimeError when the agent has not been initialized."""
    agent.initialized = False
    with pytest.raises(RuntimeError, match="Agent not initialized"):
        await agent.run("hello")


async def test_run_returns_response(agent):
    """Happy-path: run() returns the string produced by _generate_response."""
    with patch("evolving_agent.core.agent.config", _make_config()):
        result = await agent.run("hello")
    assert result == "Test answer"


async def test_run_increments_interaction_count(agent):
    """Each call to run() must increment interaction_count by exactly 1."""
    with patch("evolving_agent.core.agent.config", _make_config()):
        await agent.run("hello")
    assert agent.interaction_count == 1


async def test_run_calls_context_manager(agent):
    """run() must call context_manager.get_relevant_context with the user query."""
    with patch("evolving_agent.core.agent.config", _make_config()):
        await agent.run("hello")

    agent.context_manager.get_relevant_context.assert_called_once()
    call = agent.context_manager.get_relevant_context.call_args
    # The method is called with keyword argument query=
    assert call.kwargs.get("query") == "hello"


async def test_run_fetches_history_when_conversation_id_provided(agent):
    """When a conversation_id is provided, run() fetches history from data_manager."""
    with patch("evolving_agent.core.agent.config", _make_config()):
        await agent.run("hello", conversation_id="conv-1")

    agent.data_manager.get_conversation_history.assert_called_once_with(
        "conv-1", limit=10
    )


async def test_run_skips_history_fetch_without_conversation_id(agent):
    """When no conversation_id is given, data_manager.get_conversation_history
    must not be called."""
    with patch("evolving_agent.core.agent.config", _make_config()):
        await agent.run("hello")

    agent.data_manager.get_conversation_history.assert_not_called()


async def test_run_uses_prebuilt_history_when_provided(agent):
    """When conversation_history is passed directly, the DB fetch is bypassed
    and _generate_response is still called."""
    prebuilt = [{"query": "hi", "response": "hello"}]

    with patch("evolving_agent.core.agent.config", _make_config()):
        await agent.run("hello", conversation_history=prebuilt)

    agent.data_manager.get_conversation_history.assert_not_called()
    agent._generate_response.assert_called_once()


async def test_run_stores_interaction(agent):
    """run() must persist the interaction with the correct query and response.
    Storage happens in a background task, so we drain the event loop first."""
    with patch("evolving_agent.core.agent.config", _make_config()):
        await agent.run("hello")
        await _drain_tasks()  # drain inside patch so background task sees mocked config

    agent.data_manager.save_interaction.assert_called_once()
    call_kwargs = agent.data_manager.save_interaction.call_args.kwargs
    assert call_kwargs["query"] == "hello"
    assert call_kwargs["response"] == "Test answer"


async def test_run_with_evaluation_enabled(agent):
    """When enable_evaluation=True, the evaluator is called and the improved
    response is returned."""
    mock_eval = _make_eval_result(overall_score=0.9)
    agent.evaluator.evaluate_output = AsyncMock(return_value=mock_eval)
    agent._improve_response = AsyncMock(return_value=("Improved answer", mock_eval))

    with patch("evolving_agent.core.agent.config", _make_config(enable_evaluation=True)):
        result = await agent.run("hello")

    agent.evaluator.evaluate_output.assert_called_once()
    agent._improve_response.assert_called_once()
    assert result == "Improved answer"


async def test_run_skips_evaluation_when_disabled(agent):
    """When enable_evaluation=False, the evaluator is never called and the
    initial _generate_response value is returned."""
    with patch("evolving_agent.core.agent.config", _make_config(enable_evaluation=False)):
        result = await agent.run("hello")

    agent.evaluator.evaluate_output.assert_not_called()
    assert result == "Test answer"


async def test_run_detects_self_edit_request(agent):
    """When _is_self_edit_request returns True and self-modification is enabled,
    run() delegates to _handle_self_edit_request and returns early without
    calling _generate_response."""
    agent._is_self_edit_request = MagicMock(return_value=True)

    with patch(
        "evolving_agent.core.agent.config",
        _make_config(enable_self_modification=True),
    ):
        result = await agent.run("improve yourself")

    assert result == "Self-edit response"
    agent._handle_self_edit_request.assert_called_once_with("improve yourself")
    agent._generate_response.assert_not_called()


async def test_run_triggers_self_modification_every_10_interactions(agent):
    """_consider_self_modification must be called when interaction_count becomes
    a multiple of 10 after the increment inside run()."""
    # Start at 9 so the increment brings it to 10.
    agent.interaction_count = 9

    with patch(
        "evolving_agent.core.agent.config",
        _make_config(enable_self_modification=True),
    ):
        await agent.run("hello")
        await _drain_tasks()  # drain inside patch so background task sees mocked config

    assert agent.interaction_count == 10
    agent._consider_self_modification.assert_called_once()


async def test_run_does_not_trigger_self_modification_on_other_counts(agent):
    """_consider_self_modification must NOT be called when interaction_count is
    not a multiple of 10 after the increment."""
    # Start at 5 → increments to 6, which is not divisible by 10.
    agent.interaction_count = 5

    with patch(
        "evolving_agent.core.agent.config",
        _make_config(enable_self_modification=True),
    ):
        await agent.run("hello")

    assert agent.interaction_count == 6
    agent._consider_self_modification.assert_not_called()


async def test_run_propagates_exceptions(agent):
    """When _generate_response raises, run() re-raises the same exception and
    calls _store_error so the failure is recorded."""
    agent._generate_response = AsyncMock(side_effect=Exception("LLM error"))

    with patch("evolving_agent.core.agent.config", _make_config()):
        with pytest.raises(Exception, match="LLM error"):
            await agent.run("hello")

    agent._store_error.assert_called_once()


async def test_run_updates_knowledge_when_enabled(agent):
    """When auto_update_knowledge=True, knowledge_updater.update_from_interaction
    must be called after the interaction is stored."""
    with patch(
        "evolving_agent.core.agent.config",
        _make_config(auto_update_knowledge=True),
    ):
        await agent.run("hello")
        await _drain_tasks()  # drain inside patch so background task sees mocked config

    agent.knowledge_updater.update_from_interaction.assert_called_once()


async def test_run_skips_knowledge_update_when_disabled(agent):
    """When auto_update_knowledge=False, knowledge_updater.update_from_interaction
    must not be called."""
    with patch(
        "evolving_agent.core.agent.config",
        _make_config(auto_update_knowledge=False),
    ):
        await agent.run("hello")
        await _drain_tasks()  # drain inside patch so background task sees mocked config

    agent.knowledge_updater.update_from_interaction.assert_not_called()
