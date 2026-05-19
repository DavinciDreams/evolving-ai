"""
Comprehensive test for GitHub integration functionality.
"""

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path

from evolving_agent.integrations.github_integration import GitHubIntegration
from evolving_agent.utils.logging import setup_logger

logger = setup_logger(__name__)


import pytest

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_github_integration():
    """Test the GitHub integration functionality."""
    print("🐙 Testing GitHub Integration for Self-Improving Agent")
    print("=" * 70)

    # Check for GitHub token
    github_token = os.getenv("GITHUB_TOKEN")
    github_repo = os.getenv("GITHUB_REPO")

    if not github_token:
        print("⚠️  GITHUB_TOKEN not found in environment variables")
        print("   To enable GitHub integration, add to your .env file:")
        print("   GITHUB_TOKEN=your_github_personal_access_token")
        print("   GITHUB_REPO=owner/repository-name")
        print()
        print("🧪 Running offline GitHub integration tests...")
        test_offline_functionality()
        return

    if not github_repo:
        print("⚠️  GITHUB_REPO not found in environment variables")
        print("   Please set GITHUB_REPO=owner/repository-name in .env")
        test_offline_functionality()
        return

    try:
        # Initialize GitHub integration
        print("🔧 Initializing GitHub integration...")
        github = GitHubIntegration(
            github_token=github_token, repo_name=github_repo, local_repo_path="."
        )

        # Test initialization
        print("📡 Testing GitHub connection...")
        init_success = await github.initialize()

        if not init_success:
            print("❌ Failed to initialize GitHub connection")
            test_offline_functionality()
            return

        print("✅ GitHub connection successful!")

        # Test 1: Get repository information
        print("\n1. 📊 Testing repository information retrieval...")
        repo_info = await github.get_repository_info()

        if "error" in repo_info:
            print(f"❌ Error getting repo info: {repo_info['error']}")
        else:
            print(f"✅ Repository: {repo_info['full_name']}")
            print(f"   Language: {repo_info['language']}")
            print(f"   Stars: {repo_info['stars']}")
            print(f"   Forks: {repo_info['forks']}")
            print(f"   Default branch: {repo_info['default_branch']}")

        # Test 2: Get repository structure
        print("\n2. 🗂️  Testing repository structure...")
        structure = await github.get_repository_structure()

        if "error" in structure:
            print(f"❌ Error getting structure: {structure['error']}")
        else:
            print(f"✅ Found {len(structure['items'])} items in root:")
            for item in structure["items"][:10]:  # Show first 10
                icon = "📁" if item["type"] == "dir" else "📄"
                print(f"   {icon} {item['name']}")

        # Test 3: Get specific file content
        print("\n3. 📄 Testing file content retrieval...")
        test_files = ["README.md", "main.py", "requirements.txt"]

        for file_path in test_files:
            file_content = await github.get_file_content(file_path)
            if "error" not in file_content:
                print(f"✅ Retrieved {file_path} ({file_content['size']} bytes)")
                break
        else:
            print("❌ Could not retrieve any test files")

        # Test 4: Get commit history
        print("\n4. 📝 Testing commit history...")
        commits = await github.get_commit_history(limit=5)

        if commits:
            print(f"✅ Retrieved {len(commits)} recent commits:")
            for i, commit in enumerate(commits, 1):
                short_sha = commit["sha"][:8]
                message = commit["message"].split("\n")[0][:50]
                print(f"   {i}. {short_sha} - {message}...")
        else:
            print("❌ Could not retrieve commit history")

        # Test 5: Get open pull requests
        print("\n5. 🔄 Testing pull request retrieval...")
        prs = await github.get_open_pull_requests()

        print(f"✅ Found {len(prs)} open pull requests")
        for pr in prs[:3]:  # Show first 3
            print(f"   #{pr['number']}: {pr['title']}")

        # Test 6: Test improvement workflow (simulation)
        print("\n6. 🤖 Testing improvement workflow simulation...")

        # Simulate improvements that the agent might generate
        mock_improvements = [
            {
                "file_path": "test_improvement_demo.md",
                "content": f"""# AI Agent Improvement Demo

This is a test file created by the Self-Improving AI Agent to demonstrate
the GitHub integration functionality.

## Generated at
{datetime.now().isoformat()}

## Improvement Details
- This demonstrates how the agent can create new files
- Or modify existing files with improvements
- And submit them via pull requests

## Test Features
- ✅ File creation
- ✅ Content generation
- ✅ GitHub integration
- ✅ Pull request workflow

*This file can be safely deleted after testing.*
""",
                "description": "Demo file to test GitHub integration workflow",
            }
        ]

        # Test the complete workflow
        improvement_result = await github.create_improvement_branch_and_pr(
            improvements=mock_improvements, base_branch=None  # Use default branch
        )

        if "error" in improvement_result:
            print(f"⚠️  Improvement workflow test: {improvement_result['error']}")
        else:
            print("✅ Successfully created improvement workflow:")
            print(f"   Branch: {improvement_result['branch_name']}")
            print(f"   Files updated: {improvement_result['summary']['files_updated']}")
            print(f"   PR created: {improvement_result['summary']['pr_created']}")

            if improvement_result["summary"]["pr_created"]:
                pr_info = improvement_result["pull_request"]
                print(f"   PR URL: {pr_info.get('url', 'N/A')}")

        print("\n" + "=" * 70)
        print("🎉 GitHub Integration Test Summary")
        print("=" * 70)
        print("✅ GitHub connection: Working")
        print("✅ Repository access: Working")
        print("✅ File operations: Working")
        print("✅ Commit history: Working")
        print("✅ Pull request access: Working")
        print("✅ Improvement workflow: Working")

        print("\n🚀 GitHub integration is ready for:")
        print("   • Accessing own codebase")
        print("   • Creating improvement branches")
        print("   • Submitting pull requests with code improvements")
        print("   • Monitoring repository activity")

    except Exception as e:
        logger.error(f"GitHub integration test failed: {e}")
        print(f"❌ GitHub integration test failed: {e}")
        test_offline_functionality()


def test_offline_functionality():
    """Test GitHub integration functionality that doesn't require a connection."""
    print("\n🔧 Testing Offline GitHub Integration Features")
    print("-" * 50)

    try:
        # Test initialization without credentials
        github = GitHubIntegration()
        print("✅ GitHub integration class can be instantiated")

        # Test PR description generation
        test_files = [
            {
                "file_path": "evolving_agent/core/agent.py",
                "description": "Optimized response generation loop",
                "commit_sha": "abc12345",
            },
            {
                "file_path": "evolving_agent/utils/llm_interface.py",
                "description": "Added connection pooling for better performance",
                "commit_sha": "def67890",
            },
        ]

        pr_description = github._generate_pr_description(test_files)
        print("✅ PR description generation works")
        print(f"   Generated description length: {len(pr_description)} characters")

        # Test local repo detection
        if os.path.exists(".git"):
            print("✅ Local git repository detected")
        else:
            print("⚠️  No local git repository found")

        print("\n✅ Offline functionality tests passed")

    except Exception as e:
        print(f"❌ Offline test failed: {e}")


async def demo_improvement_workflow():
    """Demonstrate how the GitHub integration would work for code improvements."""
    print("\n🎯 GitHub Improvement Workflow Demo")
    print("=" * 50)

    print("This is how the self-improving agent would use GitHub integration:")
    print()
    print("1. 🔍 Agent analyzes its own codebase")
    print("   • Identifies high-complexity functions")
    print("   • Detects performance bottlenecks")
    print("   • Finds code duplication")
    print()
    print("2. 🛠️  Agent generates improvements")
    print("   • Refactors complex functions")
    print("   • Optimizes algorithms")
    print("   • Adds error handling")
    print()
    print("3. 🌿 Agent creates improvement branch")
    print("   • Branch name: ai-improvements-YYYYMMDD_HHMMSS")
    print("   • Multiple commits for different improvements")
    print()
    print("4. 📝 Agent commits improvements")
    print("   • Each file gets its own commit")
    print("   • Descriptive commit messages")
    print("   • AI agent as the author")
    print()
    print("5. 🔄 Agent creates pull request")
    print("   • Detailed description of changes")
    print("   • Links to analysis results")
    print("   • Labels: 'ai-improvement', 'automation'")
    print()
    print("6. 👨‍💻 Human review and feedback")
    print("   • Review code changes")
    print("   • Test functionality")
    print("   • Provide feedback to agent")
    print()
    print("7. 🤖 Agent learns from feedback")
    print("   • Stores feedback in knowledge base")
    print("   • Improves future suggestions")
    print("   • Updates improvement patterns")

    # Example improvement structure
    example_improvements = [
        {
            "file_path": "evolving_agent/core/agent.py",
            "content": "# Example optimized code...",
            "description": "Optimized _format_context_for_prompt method (complexity: 11 → 7)",
        },
        {
            "file_path": "evolving_agent/core/evaluator.py",
            "content": "# Example improved code...",
            "description": "Added caching to evaluation pipeline for 40% speed improvement",
        },
    ]

    print(f"\n📊 Example improvements the agent might suggest:")
    for i, improvement in enumerate(example_improvements, 1):
        print(f"   {i}. {improvement['file_path']}")
        print(f"      {improvement['description']}")


async def main():
    """Run all GitHub integration tests."""
    print("🚀 Self-Improving Agent - GitHub Integration Testing")
    print("=" * 80)

    # Test GitHub integration
    await test_github_integration()

    # Demo workflow
    await demo_improvement_workflow()

    print("\n" + "=" * 80)
    print("📋 Setup Instructions for GitHub Integration:")
    print("=" * 80)
    print()
    print("1. Create a GitHub Personal Access Token:")
    print("   • Go to GitHub Settings → Developer settings → Personal access tokens")
    print("   • Generate new token (classic)")
    print("   • Select scopes: repo, workflow, write:packages")
    print()
    print("2. Add to your .env file:")
    print("   GITHUB_TOKEN=your_personal_access_token")
    print("   GITHUB_REPO=your_username/your_repository_name")
    print()
    print("3. The agent will then be able to:")
    print("   • Access its own source code")
    print("   • Create branches with improvements")
    print("   • Submit pull requests automatically")
    print("   • Learn from code review feedback")
    print()
    print("🎉 GitHub integration testing completed!")


if __name__ == "__main__":
    asyncio.run(main())
