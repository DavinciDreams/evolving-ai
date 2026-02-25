"""
Test Anthropic Claude provider integration.
"""

from unittest.mock import AsyncMock, patch

from evolving_agent.utils.llm_interface import LLMManager


async def test_anthropic_agent():
    """Test that the Anthropic provider is configured and accessible."""
    manager = LLMManager()

    # Check if anthropic provider is available
    if "anthropic" in manager.interfaces:
        # Mock the actual API call
        with patch.object(
            manager.interfaces["anthropic"], 'generate_response',
            new_callable=AsyncMock, return_value="Hello! I'm Claude."
        ) as mock_gen:
            response = await manager.generate_response(
                prompt="Hello!",
                provider="anthropic",
                temperature=0.7,
                max_tokens=200,
            )

            assert response == "Hello! I'm Claude."
            mock_gen.assert_called_once()
    else:
        # Anthropic key not configured — that's OK, skip gracefully
        import pytest
        pytest.skip("Anthropic API key not configured")
