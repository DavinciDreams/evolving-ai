import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _mask_secret(value: str | None) -> str:
    """Return a non-sensitive display value for configured secrets."""
    if not value:
        return "unset"
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}...{value[-4:]}"


def main():
    if len(sys.argv) != 2:
        print("Usage: python self_improve.py self-improve")
        return

    if sys.argv[1] == "self-improve":
        from evolving_agent.self_modification.github_enhanced_modifier import (
            GitHubEnabledSelfModifier,
        )

        github_token = os.environ.get("GITHUB_TOKEN")
        repo_name = os.environ.get("GITHUB_REPO")
        local_repo_path = os.environ.get("GITHUB_LOCAL_REPO_PATH") or str(
            Path.cwd()
        )
        missing_vars = []
        if not github_token:
            missing_vars.append("GITHUB_TOKEN")
        if not repo_name:
            missing_vars.append("GITHUB_REPO")
        if missing_vars:
            print(f"GITHUB_TOKEN: {_mask_secret(github_token)}")
            print(f"GITHUB_REPO: {repo_name}")
            print(f"GITHUB_LOCAL_REPO_PATH: {local_repo_path}")
            print(
                f"Error: Missing required environment variable(s): {', '.join(missing_vars)}"
            )
            print("Please set all required variables and try again.")
            sys.exit(1)
        print(f"GITHUB_TOKEN: {_mask_secret(github_token)}")
        print(f"GITHUB_REPO: {repo_name}")
        print(f"GITHUB_LOCAL_REPO_PATH: {local_repo_path}")
        modifier = GitHubEnabledSelfModifier(
            github_token=github_token,
            repo_name=repo_name,
            local_repo_path=local_repo_path,
        )
        asyncio.run(modifier.initialize())
        result = asyncio.run(modifier.analyze_and_improve_codebase())
        summary = result.get("summary", {})
        print(
            "Self-improvement complete: "
            f"{summary.get('improvements_validated', 0)} validated improvement(s), "
            f"GitHub type={summary.get('github_type', 'none')}"
        )
    else:
        print("Unknown argument. Use 'self-improve' to run self-improvement.")


if __name__ == "__main__":
    main()
