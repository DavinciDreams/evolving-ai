import asyncio
import inspect
import os
import sys

from dotenv import load_dotenv

load_dotenv()


def main():
    if len(sys.argv) != 2:
        print("Usage: python self_improve.py self-improve")
        return

    if sys.argv[1] == "self-improve":
        from evolving_agent.utils.github_enhanced_modifier import (
            GitHubEnabledSelfModifier,
        )

        github_token = os.environ.get("GITHUB_TOKEN")
        repo_name = os.environ.get("GITHUB_REPO")
        local_repo_path = os.environ.get("GITHUB_LOCAL_REPO_PATH")
        missing_vars = []
        if not github_token:
            missing_vars.append("GITHUB_TOKEN")
        if not repo_name:
            missing_vars.append("GITHUB_REPO")
        if not local_repo_path:
            missing_vars.append("GITHUB_LOCAL_REPO_PATH")
        if missing_vars:
            print(f"GITHUB_TOKEN: {github_token}")
            print(f"GITHUB_REPO: {repo_name}")
            print(f"GITHUB_LOCAL_REPO_PATH: {local_repo_path}")
            print(
                f"Error: Missing required environment variable(s): {', '.join(missing_vars)}"
            )
            print("Please set all required variables and try again.")
            sys.exit(1)
        print(f"GITHUB_TOKEN: {github_token}")
        print(f"GITHUB_REPO: {repo_name}")
        print(f"GITHUB_LOCAL_REPO_PATH: {local_repo_path}")
        modifier = GitHubEnabledSelfModifier(
            github_token=github_token,
            repo_name=repo_name,
            local_repo_path=local_repo_path,
        )
        from evolving_agent.utils.agent_pr_manager import AgentPRManager

        modifier.pr_manager = AgentPRManager(
            github_integration=modifier.github_integration,
            code_analyzer=modifier.code_analyzer,
            code_modifier=modifier.code_modifier,
            code_validator=modifier.code_validator,
        )

        # Ensure github_integration.initialize() is called and awaited if needed
        init_func = modifier.github_integration.initialize
        if inspect.iscoroutinefunction(init_func):
            asyncio.run(init_func())
        else:
            init_func()

        func = modifier.analyze_and_improve_codebase
        if inspect.iscoroutinefunction(func):
            asyncio.run(func())
        else:
            func()
    else:
        print("Unknown argument. Use 'self-improve' to run self-improvement.")


if __name__ == "__main__":
    main()
