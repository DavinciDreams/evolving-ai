"""
Test the LLM fallback system.
"""

from unittest.mock import AsyncMock, patch

from evolving_agent.utils.llm_interface import LLMManager


async def test_fallback_system_initialization():
    """Test that the fallback system initializes with available providers."""
    manager = LLMManager()
    manager._ensure_initialized()

    assert isinstance(manager.interfaces, dict)
    assert manager.default_provider is not None


async def test_get_available_providers():
    """Test checking provider availability."""
    manager = LLMManager()

    # Mock all providers as available
    for name, interface in manager.interfaces.items():
        interface.generate_response = AsyncMock(return_value="OK")

    available = await manager.get_available_providers()
    assert isinstance(available, list)


async def test_fallback_on_provider_failure():
    """Test that the manager tries alternative providers when default fails."""
    manager = LLMManager()

    if len(manager.interfaces) < 2:
        import pytest
        pytest.skip("Need at least 2 providers to test fallback")

    providers = list(manager.interfaces.keys())
    primary = providers[0]
    secondary = providers[1]

    # Mock primary to fail, secondary to succeed
    with patch.object(
        manager.interfaces[primary], 'generate_response',
        new_callable=AsyncMock, side_effect=Exception("Primary failed")
    ), patch.object(
        manager.interfaces[secondary], 'generate_response',
        new_callable=AsyncMock, return_value="Fallback response"
    ):
        response = await manager.generate_response(
            prompt="test", provider=primary
        )
        assert response == "Fallback response"
