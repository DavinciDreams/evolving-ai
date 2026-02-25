"""
Pytest configuration for evolving-ai tests.
"""

import os
import sys

import pytest

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Disable CUDA for tests (ChromaDB embedding model tries to use GPU)
os.environ["CUDA_VISIBLE_DEVICES"] = ""


def pytest_configure(config):
    """Configure pytest-asyncio mode."""
    config.addinivalue_line(
        "markers", "asyncio: mark test as async"
    )


@pytest.fixture(autouse=True)
def _isolate_memory_dir(tmp_path, monkeypatch):
    """Use a temporary directory for memory persistence during tests."""
    monkeypatch.setenv("MEMORY_PERSIST_DIRECTORY", str(tmp_path / "memory_db"))
    monkeypatch.setenv("KNOWLEDGE_BASE_PATH", str(tmp_path / "knowledge_base"))
    monkeypatch.setenv("BACKUP_DIRECTORY", str(tmp_path / "backups"))
