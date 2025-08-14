"""
Test real GitHub integration functionality with actual credentials.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import asyncio
import os

from evolving_agent.utils.github_integration import GitHubIntegration
from evolving_agent.utils.logging import setup_logger

logger = setup_logger(__name__)


import pytest


@pytest.mark.asyncio
async def test_real_github_integration():
    """Test GitHub integration with real credentials."""
    print("🎯 Testing Real GitHub Integration")
    print("=" * 50)
    
    # Get credentials from environment
    github_token = os.getenv("GITHUB_TOKEN")
    github_repo = os.getenv("GITHUB_REPO")
    
    if not github_token or not github_repo:
        print("❌ GitHub credentials not found in environment")
        return
    
    print(f"✅ Using repository: {github_repo}")
    
    try:
        # Initialize GitHub integration
        github = GitHubIntegration(
            github_token=github_token,
            repo_name=github_repo,
            local_repo_path="."
        )
        
        # Test initialization
        print("\n1. 🔧 Testing initialization...")
        success = await github.initialize()
        print(f"   Result: {'✅ Success' if success else '❌ Failed'}")
        
        # Test repository info
        print("\n2. 📊 Testing repository info...")
        repo_info = await github.get_repository_info()
        if "error" not in repo_info:
            print(f"   ✅ Repository: {repo_info['full_name']}")
            print(f"   Stars: {repo_info['stars']}")
            print(f"   Language: {repo_info['language']}")
        else:
            print(f"   ❌ Error: {repo_info['error']}")
        
        # Test file content
        print("\n3. 📄 Testing file access...")
        file_content = await github.get_file_content("README.md")
        if "error" not in file_content:
            print(f"   ✅ README.md found ({file_content['size']} bytes)")
        else:
            print(f"   ❌ Error: {file_content['error']}")
        
        # Test commit history
        print("\n4. 📝 Testing commit history...")
        commits = await github.get_commit_history(limit=3)
        if commits:
            print(f"   ✅ Found {len(commits)} recent commits:")
            for commit in commits:
                short_sha = commit['sha'][:8]
                message = commit['message'].split('\n')[0][:40]
                print(f"      {short_sha} - {message}...")
        else:
            print("   ❌ No commits found")
        
        # Test pull requests
        print("\n5. 🔄 Testing pull requests...")
        prs = await github.get_open_pull_requests()
        print(f"   ✅ Found {len(prs)} open pull requests")
        
        # Test creating a branch (safe test)
        print("\n6. 🌿 Testing branch creation...")
        branch_name = f"test-branch-{int(asyncio.get_event_loop().time())}"
        branch_result = await github.create_branch(branch_name)
        
        if "error" not in branch_result:
            print(f"   ✅ Created branch: {branch_name}")
            
            # Test creating a simple file
            print("\n7. 📁 Testing file creation...")
            test_content = f"""# GitHub Integration Test

This file was created by the Self-Improving AI Agent to test GitHub integration.

Created at: {asyncio.get_event_loop().time()}

## Features Tested
- ✅ Repository connection
- ✅ File access
- ✅ Branch creation
- ✅ File creation

This file can be safely deleted.
"""
            
            file_result = await github.update_file(
                file_path="test_ai_integration.md",
                new_content=test_content,
                commit_message="🤖 AI Agent: Test file creation",
                branch=branch_name
            )
            
            if "error" not in file_result:
                print(f"   ✅ Created test file successfully")
                
                # Create a simple PR
                print("\n8. 🔄 Testing PR creation...")
                pr_result = await github.create_pull_request(
                    title="🤖 AI Agent: Test Integration",
                    body="This is a test PR created by the Self-Improving AI Agent to verify GitHub integration is working correctly.\n\nThis PR can be safely closed.",
                    head_branch=branch_name,
                    base_branch="main"
                )
                
                if "error" not in pr_result:
                    print(f"   ✅ Created PR #{pr_result['number']}")
                    print(f"   🔗 URL: {pr_result['url']}")
                    print(f"\n🎉 FULL GITHUB INTEGRATION SUCCESS!")
                    print(f"   • Created branch: {branch_name}")
                    print(f"   • Created file: test_ai_integration.md")
                    print(f"   • Created PR: #{pr_result['number']}")
                    print(f"\n📋 Next steps:")
                    print(f"   1. Review the PR in GitHub")
                    print(f"   2. Merge or close as needed")
                    print(f"   3. Delete the test branch if desired")
                else:
                    print(f"   ❌ PR creation failed: {pr_result['error']}")
            else:
                print(f"   ❌ File creation failed: {file_result['error']}")
        else:
            print(f"   ❌ Branch creation failed: {branch_result['error']}")
            
    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        logger.error(f"GitHub integration test failed: {e}")


if __name__ == "__main__":
    asyncio.run(test_real_github_integration())
