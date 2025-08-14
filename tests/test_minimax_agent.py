#!/usr/bin/env python3
"""
Test script to verify the self-improving agent works with MiniMax model
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import asyncio
import os
import sys

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pytest
from loguru import logger

from evolving_agent.core.agent import SelfImprovingAgent
from evolving_agent.utils.config import config


@pytest.mark.asyncio
async def test_minimax_agent():
    """Test the agent with MiniMax model"""
    logger.info("Testing self-improving agent with MiniMax model...")
    
    try:
        # Create agent instance
        agent = SelfImprovingAgent()
        
        # Initialize the agent
        await agent.initialize()
        logger.info("Agent initialized successfully")
        
        # Test a simple query
        query = "What is the capital of France? Please provide a brief answer."
        logger.info(f"Sending query: {query}")
        
        response = await agent.run(query)
        logger.info(f"Agent response: {response}")
        
        # Test memory storage - not directly, as it's handled internally
        logger.info("Interaction handled internally")
        
        # Clean up
        await agent.cleanup()
        logger.info("Agent cleaned up successfully")
        
        print("\n✅ SUCCESS: Agent works perfectly with MiniMax model!")
        print(f"Query: {query}")
        print(f"Response: {response}")
        
    except Exception as e:
        logger.error(f"Error during agent test: {e}")
        print(f"\n❌ FAILED: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(test_minimax_agent())
