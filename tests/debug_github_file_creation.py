"""
Simple test to debug GitHub file creation issue.
"""

import asyncio
import os

from github import Github, GithubException


async def debug_github_file_creation():
    """Debug the GitHub file creation issue."""
    print("🔍 Debugging GitHub File Creation")
    print("=" * 40)
    
    # Get credentials
    github_token = os.getenv("GITHUB_TOKEN")
    github_repo = os.getenv("GITHUB_REPO")
    
    if not github_token or not github_repo:
        print("❌ GitHub credentials not found")
        return
    
    try:
        # Initialize GitHub client
        g = Github(github_token)
        repo = g.get_repo(github_repo)
        
        print(f"✅ Connected to repository: {repo.full_name}")
        
        # Test creating a simple file
        branch_name = "test-simple-file"
        
        # Check if branch exists, if not create it
        try:
            branch = repo.get_branch(branch_name)
            print(f"✅ Branch {branch_name} already exists")
        except GithubException as e:
            if e.status == 404:
                print(f"🌿 Creating branch {branch_name}")
                # Get the default branch
                default_branch = repo.get_branch(repo.default_branch)
                repo.create_git_ref(f"refs/heads/{branch_name}", default_branch.commit.sha)
                print(f"✅ Created branch {branch_name}")
            else:
                raise
        
        # Test 1: Simple text file
        print("\n1. Testing simple text file creation...")
        simple_content = "Hello, GitHub!"
        
        try:
            result = repo.create_file(
                path="test_simple.txt",
                message="Test: Create simple file",
                content=simple_content,
                branch=branch_name
            )
            print(f"✅ Created simple file: {result['content'].html_url}")
        except Exception as e:
            print(f"❌ Failed to create simple file: {type(e).__name__}: {e}")
        
        # Test 2: Markdown file with more content
        print("\n2. Testing markdown file creation...")
        markdown_content = """# Test File

This is a test markdown file created by the AI agent.

## Features
- Simple text
- Markdown formatting
- Multiple lines

Created by GitHub integration test.
"""
        
        try:
            result = repo.create_file(
                path="test_markdown.md",
                message="Test: Create markdown file",
                content=markdown_content,
                branch=branch_name
            )
            print(f"✅ Created markdown file: {result['content'].html_url}")
        except Exception as e:
            print(f"❌ Failed to create markdown file: {type(e).__name__}: {e}")
        
        # Test 3: File with author info
        print("\n3. Testing file creation with author...")
        author_content = "File created with author info"
        
        try:
            result = repo.create_file(
                path="test_with_author.txt",
                message="Test: Create file with author",
                content=author_content,
                branch=branch_name,
                author={"name": "AI Agent", "email": "agent@example.com"}
            )
            print(f"✅ Created file with author: {result['content'].html_url}")
        except Exception as e:
            print(f"❌ Failed to create file with author: {type(e).__name__}: {e}")
        
        print(f"\n🎯 Debug complete! Check branch '{branch_name}' in GitHub.")
        
    except Exception as e:
        print(f"❌ Debug failed: {type(e).__name__}: {e}")


if __name__ == "__main__":
    asyncio.run(debug_github_file_creation())
