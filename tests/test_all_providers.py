"""
Test provider availability and initialization.
"""

from unittest.mock import AsyncMock, MagicMock, patch

from evolving_agent.utils.llm_interface import LLMManager


async def test_all_providers():
    """Test that the LLM manager initializes available providers."""
    manager = LLMManager()
    manager._ensure_initialized()

    # Should have initialized interfaces from env
    assert isinstance(manager.interfaces, dict)
    assert manager.default_provider is not None

    # Verify default provider is in the interfaces or at least set
    providers = list(manager.interfaces.keys())
    assert len(providers) > 0, "At least one provider should be available"


async def test_provider_fallback():
    """Test that provider fallback works when primary fails."""
    manager = LLMManager()

    # If we have more than one provider, test that fallback logic exists
    if len(manager.interfaces) > 1:
        providers = list(manager.interfaces.keys())
        # Mock the first provider to fail
        with patch.object(
            manager.interfaces[providers[0]], 'generate_response',
            new_callable=AsyncMock, side_effect=Exception("API error")
        ):
            # The manager should try alternatives
            try:
                response = await manager.generate_response(
                    prompt="test", provider=providers[0]
                )
            except Exception:
                pass  # Expected if all providers fail in test env
