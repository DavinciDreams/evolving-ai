"""
Test script for conversation tracking functionality.
"""
import asyncio
import sys
from evolving_agent.core.agent import SelfImprovingAgent
from evolving_agent.utils.logging import setup_logger

logger = setup_logger(__name__)


async def test_conversation_tracking():
    """Test conversation tracking with multiple interactions."""
    try:
        # Initialize agent
        logger.info("Initializing agent...")
        agent = SelfImprovingAgent()
        await agent.initialize()
        logger.info("Agent initialized successfully")

        # Test conversation ID
        conversation_id = "test_conv_001"

        # First interaction
        logger.info("\n" + "="*60)
        logger.info("TEST 1: First message in conversation")
        logger.info("="*60)
        response1 = await agent.run(
            query="What is Python?",
            conversation_id=conversation_id
        )
        print(f"\nQuery 1: What is Python?")
        print(f"Response 1: {response1[:200]}...")

        # Second interaction - should have context from first
        logger.info("\n" + "="*60)
        logger.info("TEST 2: Follow-up question (should reference Python)")
        logger.info("="*60)
        response2 = await agent.run(
            query="What about its history?",
            conversation_id=conversation_id
        )
        print(f"\nQuery 2: What about its history?")
        print(f"Response 2: {response2[:200]}...")

        # Third interaction
        logger.info("\n" + "="*60)
        logger.info("TEST 3: Another follow-up")
        logger.info("="*60)
        response3 = await agent.run(
            query="Who created it?",
            conversation_id=conversation_id
        )
        print(f"\nQuery 3: Who created it?")
        print(f"Response 3: {response3[:200]}...")

        # Retrieve conversation history
        logger.info("\n" + "="*60)
        logger.info("TEST 4: Retrieve conversation history")
        logger.info("="*60)
        history = await agent.data_manager.get_conversation_history(
            conversation_id=conversation_id
        )
        print(f"\nConversation history ({conversation_id}):")
        print(f"Total messages: {len(history)}")
        for i, interaction in enumerate(history, 1):
            print(f"\n{i}. Query: {interaction['query'][:80]}...")
            print(f"   Response: {interaction['response'][:80]}...")
            print(f"   Timestamp: {interaction['timestamp']}")

        # Test with different conversation
        logger.info("\n" + "="*60)
        logger.info("TEST 5: New conversation (should not have previous context)")
        logger.info("="*60)
        different_conv_id = "test_conv_002"
        response4 = await agent.run(
            query="What are you?",
            conversation_id=different_conv_id
        )
        print(f"\nQuery 4 (new conversation): What are you?")
        print(f"Response 4: {response4[:200]}...")

        logger.info("\n" + "="*60)
        logger.info("✓ All tests completed successfully!")
        logger.info("="*60)

    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(test_conversation_tracking())
