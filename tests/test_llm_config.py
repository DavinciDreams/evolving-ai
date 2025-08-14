"""
Test script to verify LLM provider configuration changes.
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from evolving_agent.utils.config import config
from evolving_agent.utils.llm_interface import LLMManager


import pytest
@pytest.mark.asyncio
async def test_llm_configuration():
    """Test the updated LLM configuration."""
    print("=== LLM Configuration Test ===")
    
    # Test configuration
    print(f"Default LLM Provider: {config.default_llm_provider}")
    print(f"Default Model: {config.default_model}")
    print(f"Evaluation Model: {config.evaluation_model}")
    
    # Test available providers
    print("\nAPI Key Status:")
    print(f"OpenAI API Key: {'✓ Set' if config.openai_api_key else '✗ Not set'}")
    print(f"Anthropic API Key: {'✓ Set' if config.anthropic_api_key else '✗ Not set'}")
    print(f"OpenRouter API Key: {'✓ Set' if config.openrouter_api_key else '✗ Not set'}")
    
    # Initialize LLM Manager
    llm_manager = LLMManager()
    
    print(f"\nAvailable Providers: {list(llm_manager.interfaces.keys())}")
    
    # Test provider selection
    try:
        default_interface = llm_manager.get_interface()
        print(f"Default interface type: {type(default_interface).__name__}")
    except Exception as e:
        print(f"Error getting default interface: {e}")
    
    # Test each available provider
    for provider in llm_manager.interfaces.keys():
        try:
            interface = llm_manager.get_interface(provider)
            print(f"✓ {provider}: {type(interface).__name__}")
        except Exception as e:
            print(f"✗ {provider}: {e}")


if __name__ == "__main__":
    asyncio.run(test_llm_configuration())
