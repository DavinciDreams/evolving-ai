#!/usr/bin/env python3
"""
Test script for GitHub integration endpoints in the API server.
"""

import asyncio
import json
import os
import sys
from typing import Any, Dict

import aiohttp
from loguru import logger

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BASE_URL = "http://localhost:8000"


async def check_endpoint(
    session: aiohttp.ClientSession,
    method: str,
    endpoint: str,
    data: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """Test a single endpoint and return the response."""
    url = f"{BASE_URL}{endpoint}"

    try:
        logger.info(f"Testing {method} {endpoint}")

        if method.upper() == "GET":
            async with session.get(url) as response:
                result = {
                    "status": response.status,
                    "data": (
                        await response.json()
                        if response.content_type == "application/json"
                        else await response.text()
                    ),
                }
        elif method.upper() == "POST":
            headers = {"Content-Type": "application/json"}
            async with session.post(url, json=data, headers=headers) as response:
                result = {
                    "status": response.status,
                    "data": (
                        await response.json()
                        if response.content_type == "application/json"
                        else await response.text()
                    ),
                }
        else:
            raise ValueError(f"Unsupported method: {method}")

        if result["status"] == 200:
            logger.success(f"✅ {method} {endpoint} - SUCCESS")
        else:
            logger.warning(f"⚠️ {method} {endpoint} - Status {result['status']}")

        return result

    except Exception as e:
        logger.error(f"❌ {method} {endpoint} - ERROR: {e}")
        return {"status": "error", "error": str(e)}


async def check_github_endpoints():
    """Test all GitHub-related endpoints."""

    logger.info("🚀 Starting GitHub endpoints test...")

    async with aiohttp.ClientSession() as session:
        results = {}

        # Test health check first
        logger.info("Testing health check...")
        results["health"] = await check_endpoint(session, "GET", "/health")

        # Test GitHub status
        logger.info("Testing GitHub status...")
        results["github_status"] = await check_endpoint(session, "GET", "/github/status")

        # Test repository info (might fail if not connected)
        logger.info("Testing repository info...")
        results["repository_info"] = await check_endpoint(
            session, "GET", "/github/repository"
        )

        # Test pull requests list
        logger.info("Testing pull requests list...")
        results["pull_requests"] = await check_endpoint(
            session, "GET", "/github/pull-requests"
        )

        # Test recent commits
        logger.info("Testing recent commits...")
        results["recent_commits"] = await check_endpoint(
            session, "GET", "/github/commits?limit=5"
        )

        # Test improvement history
        logger.info("Testing improvement history...")
        results["improvement_history"] = await check_endpoint(
            session, "GET", "/github/improvement-history"
        )

        # Test code improvements (without creating PR)
        logger.info("Testing code improvements (dry run)...")
        improvement_request = {
            "create_pr": False,
            "evaluation_insights": ["Test improvement insight"],
            "knowledge_suggestions": ["Test knowledge suggestion"],
        }
        results["code_improvements"] = await check_endpoint(
            session, "POST", "/self-improve", improvement_request
        )

        # Only test demo PR if GitHub is available
        if results.get("github_status", {}).get("status") == 200 and results[
            "github_status"
        ]["data"].get("github_connected", False):

            logger.info("GitHub is connected - testing demo PR creation...")
            results["demo_pr"] = await check_endpoint(session, "POST", "/github/demo-pr")
        else:
            logger.info("GitHub not connected - skipping demo PR test")
            results["demo_pr"] = {"status": "skipped", "reason": "GitHub not connected"}

    return results


def print_results(results: Dict[str, Any]):
    """Print formatted test results."""

    logger.info("\n" + "=" * 50)
    logger.info("📊 GITHUB ENDPOINTS TEST RESULTS")
    logger.info("=" * 50)

    success_count = 0
    total_count = 0

    for endpoint, result in results.items():
        total_count += 1
        status = result.get("status", "unknown")

        if status == 200:
            logger.success(f"✅ {endpoint}: SUCCESS")
            success_count += 1
        elif status == "skipped":
            logger.info(
                f"⏭️ {endpoint}: SKIPPED ({result.get('reason', 'Unknown reason')})"
            )
        elif isinstance(status, int) and 400 <= status < 500:
            logger.warning(f"⚠️ {endpoint}: CLIENT ERROR ({status})")
            if "data" in result:
                logger.warning(f"   Response: {result['data']}")
        elif isinstance(status, int) and status >= 500:
            logger.error(f"❌ {endpoint}: SERVER ERROR ({status})")
            if "data" in result:
                logger.error(f"   Response: {result['data']}")
        else:
            logger.error(f"❌ {endpoint}: {result.get('error', 'Unknown error')}")

    logger.info(f"\n📈 Success rate: {success_count}/{total_count} endpoints")

    # Show GitHub status details
    if "github_status" in results and results["github_status"]["status"] == 200:
        github_data = results["github_status"]["data"]
        logger.info("\n🔗 GitHub Integration Status:")
        logger.info(f"   Connected: {github_data.get('github_connected', False)}")
        logger.info(f"   Repository: {github_data.get('repository_name', 'N/A')}")
        logger.info(f"   Local repo: {github_data.get('local_repo_available', False)}")
        logger.info(f"   Auto PR: {github_data.get('auto_pr_enabled', False)}")
        logger.info(f"   Open PRs: {github_data.get('open_prs_count', 0)}")


async def main():
    """Main test function."""

    logger.info("🧪 GitHub Endpoints Test Suite")
    logger.info("Make sure the API server is running on http://localhost:8000")

    # Test if server is running
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{BASE_URL}/health") as response:
                if response.status != 200:
                    logger.error("❌ API server is not responding correctly")
                    return
    except Exception as e:
        logger.error(f"❌ Cannot connect to API server: {e}")
        logger.info(
            "💡 Start the server with: python -m uvicorn api_server:app --host 127.0.0.1 --port 8000 --reload"
        )
        return

    # Run tests
    results = await check_github_endpoints()

    # Print results
    print_results(results)

    # Save detailed results
    with open("github_test_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)

    logger.info("\n💾 Detailed results saved to github_test_results.json")


if __name__ == "__main__":
    asyncio.run(main())
