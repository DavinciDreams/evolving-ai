"""
Test script for web search integration.

This script demonstrates the web search capabilities of the agent.
"""

import asyncio
import os
import sys

from dotenv import load_dotenv

from evolving_agent.integrations.web_search import WebSearchIntegration
from evolving_agent.utils.logging import setup_logger

# Load environment variables
load_dotenv()

logger = setup_logger(__name__)


async def test_web_search():
    """Test web search integration."""
    try:
        logger.info("Initializing web search integration...")

        # Initialize web search
        web_search = WebSearchIntegration(
            tavily_api_key=os.getenv("TAVILY_API_KEY"),
            serpapi_key=os.getenv("SERPAPI_KEY"),
            default_provider=os.getenv("WEB_SEARCH_DEFAULT_PROVIDER", "duckduckgo"),
            max_results=int(os.getenv("WEB_SEARCH_MAX_RESULTS", "5")),
        )

        await web_search.initialize()
        logger.info("Web search initialized successfully")

        # Test queries
        test_queries = [
            "Latest developments in AI 2025",
            "Python best practices",
            "Self-improving AI systems",
        ]

        for query in test_queries:
            logger.info(f"\n{'='*80}")
            logger.info(f"Testing query: {query}")
            logger.info(f"{'='*80}\n")

            # Search the web
            results = await web_search.search_and_summarize(query, max_results=3)

            # Display results
            print(f"\nQuery: {results.get('query')}")
            print(f"Provider: {results.get('provider')}")
            print(f"Timestamp: {results.get('timestamp')}")
            print(f"\nSources ({len(results.get('sources', []))}):")

            for i, source in enumerate(results.get("sources", []), 1):
                print(f"\n{i}. {source.get('title', 'No title')}")
                print(f"   URL: {source.get('url', 'No URL')}")
                print(f"   Snippet: {source.get('snippet', 'No snippet')[:200]}...")

            print("\n" + "="*80 + "\n")

        # Clean up
        await web_search.close()
        logger.info("Web search test completed successfully")

    except Exception as e:
        logger.error(f"Web search test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    print("Web Search Integration Test")
    print("="*80)
    print("\nThis script tests the web search capabilities of the agent.")
    print("It will perform several test searches using the configured provider.\n")

    asyncio.run(test_web_search())
