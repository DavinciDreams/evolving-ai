#!/usr/bin/env python3
"""
Project organization maintenance script.
Helps keep the project structure clean and organized.
"""

import fnmatch
import os
import shutil
from pathlib import Path
from typing import List, Tuple


def get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent


def read_gitignore_patterns() -> List[str]:
    """Read and parse .gitignore patterns."""
    root = get_project_root()
    gitignore_path = root / ".gitignore"

    patterns = []
    if gitignore_path.exists():
        try:
            content = gitignore_path.read_text(encoding="utf-8")
            for line in content.splitlines():
                line = line.strip()
                # Skip empty lines and comments
                if line and not line.startswith("#"):
                    patterns.append(line)
        except Exception:
            pass

    return patterns


def should_ignore_file(file_path: Path, patterns: List[str]) -> bool:
    """Check if a file matches any gitignore pattern."""
    relative_path = str(file_path.relative_to(get_project_root()))

    for pattern in patterns:
        # Handle different pattern types
        if pattern.startswith("/"):
            # Absolute path from root
            if fnmatch.fnmatch(relative_path, pattern[1:]):
                return True
        elif pattern.endswith("/"):
            # Directory pattern
            if relative_path.startswith(pattern) or fnmatch.fnmatch(
                relative_path + "/", pattern
            ):
                return True
        else:
            # File or glob pattern
            if fnmatch.fnmatch(relative_path, pattern) or fnmatch.fnmatch(
                file_path.name, pattern
            ):
                return True
            # Also check if any parent directory matches
            for parent in file_path.parents:
                if fnmatch.fnmatch(parent.name, pattern):
                    return True

    return False


def find_ignored_files() -> List[Path]:
    """Find files that match .gitignore patterns and shouldn't be in repo."""
    root = get_project_root()
    patterns = read_gitignore_patterns()
    ignored_files = []

    # Check specific problematic files that often get created
    problem_patterns = [
        "*.pyc",
        "__pycache__/",
        "*.log",
        "*.tmp",
        "*.backup",
        ".DS_Store",
        "Thumbs.db",
    ]

    all_patterns = patterns + problem_patterns

    for file_path in root.rglob("*"):
        if file_path.is_file():
            # Skip important files we should never delete
            if file_path.name in [
                ".gitignore",
                ".env",
                "README.md",
                "requirements.txt",
                "main.py",
            ]:
                continue

            # Skip files in .git directory
            if ".git" in file_path.parts:
                continue

            if should_ignore_file(file_path, all_patterns):
                ignored_files.append(file_path)

    return ignored_files


def find_misplaced_files() -> Tuple[List[str], List[str]]:
    """Find test and doc files in the main directory."""
    root = get_project_root()

    misplaced_tests = []
    misplaced_docs = []

    # Find test files in main directory
    for test_file in root.glob("test_*.py"):
        if test_file.is_file():
            misplaced_tests.append(str(test_file.name))

    for debug_file in root.glob("debug_*.py"):
        if debug_file.is_file():
            misplaced_tests.append(str(debug_file.name))

    # Find doc files in main directory (except README.md)
    for doc_file in root.glob("*.md"):
        if doc_file.is_file() and doc_file.name != "README.md":
            misplaced_docs.append(str(doc_file.name))

    return misplaced_tests, misplaced_docs


def move_misplaced_files(dry_run: bool = True) -> None:
    """Move misplaced files to their correct directories."""
    root = get_project_root()
    tests_dir = root / "tests"
    docs_dir = root / "docs"

    # Ensure target directories exist
    tests_dir.mkdir(exist_ok=True)
    docs_dir.mkdir(exist_ok=True)

    misplaced_tests, misplaced_docs = find_misplaced_files()

    print("🔍 Project Organization Check")
    print("=" * 50)

    if not misplaced_tests and not misplaced_docs:
        print("✅ Project is properly organized!")
        return

    if misplaced_tests:
        print(f"\n📁 Found {len(misplaced_tests)} misplaced test files:")
        for test_file in misplaced_tests:
            source = root / test_file
            target = tests_dir / test_file

            if dry_run:
                print(f"   📄 {test_file} → tests/{test_file}")
            else:
                if target.exists():
                    print(f"   ⚠️  {test_file} → tests/{test_file} (overwriting)")
                    target.unlink()
                shutil.move(str(source), str(target))
                print(f"   ✅ {test_file} → tests/{test_file}")

    if misplaced_docs:
        print(f"\n📚 Found {len(misplaced_docs)} misplaced doc files:")
        for doc_file in misplaced_docs:
            source = root / doc_file
            target = docs_dir / doc_file

            if dry_run:
                print(f"   📄 {doc_file} → docs/{doc_file}")
            else:
                if target.exists():
                    print(f"   ⚠️  {doc_file} → docs/{doc_file} (overwriting)")
                    target.unlink()
                shutil.move(str(source), str(target))
                print(f"   ✅ {doc_file} → docs/{doc_file}")

    if dry_run:
        print(f"\n💡 This was a dry run. To actually move files, run:")
        print("   python organize_project.py --apply")
    else:
        print(f"\n🎉 Project organization complete!")


def check_api_keys() -> List[str]:
    """Check for hardcoded API keys in Python files."""
    root = get_project_root()
    violations = []

    # Common API key patterns
    patterns = [
        "sk-ant-",
        "sk-or-",
        "gsk_",
        "ghp_",
        'api_key = "sk-',
        "api_key = 'sk-",
    ]

    for py_file in root.rglob("*.py"):
        if "/.venv/" in str(py_file) or "/__pycache__/" in str(py_file):
            continue

        try:
            content = py_file.read_text(encoding="utf-8")
            for pattern in patterns:
                if pattern in content:
                    violations.append(f"{py_file.relative_to(root)}: Found '{pattern}'")
        except Exception:
            continue

    return violations


def organize_project():
    """Enhanced project organization with gitignore cleanup."""
    print("🧹 Self-Improving AI Agent - Project Organization")
    print("=" * 60)

    # Step 1: Clean up gitignored files
    print("\n📁 Checking for gitignored files...")
    ignored_files = find_ignored_files()

    if ignored_files:
        print(f"Found {len(ignored_files)} files matching .gitignore patterns:")
        for file_path in ignored_files:
            print(f"  - {file_path.relative_to(get_project_root())}")

        response = input("\nRemove these files? (y/N): ").lower().strip()
        if response == "y":
            removed_count = 0
            for file_path in ignored_files:
                try:
                    file_path.unlink()
                    removed_count += 1
                    print(f"  ✅ Removed: {file_path.relative_to(get_project_root())}")
                except Exception as e:
                    print(
                        f"  ❌ Failed to remove {file_path.relative_to(get_project_root())}: {e}"
                    )
            print(f"\n🗑️ Removed {removed_count} gitignored files")
        else:
            print("⏭️ Skipped gitignore cleanup")
    else:
        print("✅ No gitignored files found")

    # Step 2: Check file organization
    print("\n📂 Checking file organization...")
    move_misplaced_files(dry_run=False)

    # Step 3: Check for API key violations
    print("\n🔐 Checking for hardcoded API keys...")
    violations = check_api_keys()

    if violations:
        print(f"\n❌ Found {len(violations)} potential API key violations:")
        for violation in violations:
            print(f"   🚨 {violation}")
        print("\n💡 Move all API keys to .env file!")
    else:
        print("✅ No hardcoded API keys found!")

    # Step 4: Show current structure
    root = get_project_root()
    tests_count = len(list((root / "tests").glob("*.py")))
    docs_count = len(list((root / "docs").glob("*.md")))

    print(f"\n📊 Current Project Structure:")
    print(f"   📁 tests/: {tests_count} files")
    print(f"   📁 docs/: {docs_count} files")
    print(f"   📁 main/: {len(list(root.glob('*.py')))} Python files")

    print("\n✨ Project organization complete!")
    print("\n📋 Remember:")
    print("  - Tests go in tests/ folder")
    print("  - Documentation goes in docs/ folder")
    print("  - API keys go in .env file")
    print("  - Keep main directory clean")


def main():
    """Main function."""
    import sys

    if "--organize" in sys.argv:
        organize_project()
    else:
        # Legacy behavior for backwards compatibility
        apply_changes = "--apply" in sys.argv

        print("🧹 Self-Improving AI Agent - Project Organization")
        print("=" * 60)

        # Check file organization
        move_misplaced_files(dry_run=not apply_changes)

        # Check for API key violations
        print("\n🔐 Checking for hardcoded API keys...")
        violations = check_api_keys()

        if violations:
            print(f"\n❌ Found {len(violations)} potential API key violations:")
            for violation in violations:
                print(f"   🚨 {violation}")
            print("\n💡 Move all API keys to .env file!")
        else:
            print("✅ No hardcoded API keys found!")

        # Show current structure
        root = get_project_root()
        tests_count = len(list((root / "tests").glob("*.py")))
        docs_count = len(list((root / "docs").glob("*.md")))

        print(f"\n📊 Current Project Structure:")
        print(f"   📁 tests/: {tests_count} files")
        print(f"   📁 docs/: {docs_count} files")
        print(f"   📁 main/: {len(list(root.glob('*.py')))} Python files")


if __name__ == "__main__":
    main()
