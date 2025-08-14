#!/usr/bin/env python3
"""
Test the LLM fallback system.
"""

import asyncio
import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from evolving_agent.utils.config import config
from evolving_agent.utils.llm_interface import llm_manager

import pytest
@pytest.mark.asyncio
async def test_fallback_system():
    """Test the intelligent fallback system."""
    print("=== Testing LLM Fallback System ===")
    
    # Force config refresh
    # config._load_config()  # Not needed
    llm_manager.refresh_interfaces()
    
    print(f"Current default provider: {config.default_llm_provider}")
    print(f"Available interfaces: {list(llm_manager.interfaces.keys())}")
    
    # Check provider availability
    print("\n🔍 Checking provider availability...")
    available_providers = await llm_manager.get_available_providers()
    print(f"Available providers: {available_providers}")
    
    # Test fallback response generation
    print("\n🤖 Testing response generation with fallback...")
    test_message = "What is 2+2? Please respond with just the number."
    
    response, error = await llm_manager.generate_response_with_fallback(
        message=test_message,
        preferred_provider=config.default_llm_provider
    )
    
    if response:
        print(f"✅ Success! Response: {response}")
    else:
        print(f"❌ Failed: {error}")
        
    # Show provider status
    print("\n📊 Provider Status Details:")
    llm_manager._log_provider_status()

if __name__ == "__main__":
    asyncio.run(test_fallback_system())
