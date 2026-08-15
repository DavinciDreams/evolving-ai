"""Security and integrity tests for the explicit Chroma-to-HAM migration."""

import hashlib
import json
from unittest.mock import MagicMock, patch

import pytest

from scripts.migrate_chroma_to_ham import export_snapshot, load_snapshot


def test_export_redacts_and_quarantines_credentials_without_storing_values(tmp_path):
    credential = "sk-" + "not-a-real-secret-value-12345"
    collection = MagicMock()
    collection.get.return_value = {
        "ids": ["legacy-1", "legacy-2"],
        "documents": [f"TELLUS_TOKEN={credential}", "ordinary memory"],
        "metadatas": [
            {"timestamp": "2026-01-01T00:00:00Z", "memory_type": "fact"},
            {"timestamp": "2026-01-02T00:00:00Z", "memory_type": "note"},
        ],
    }
    chroma = MagicMock()
    chroma.get_collection.return_value = collection

    with patch(
        "scripts.migrate_chroma_to_ham.chromadb.PersistentClient", return_value=chroma
    ):
        manifest = export_snapshot(
            persist_directory="/unused",
            collection_name="agent_memory",
            snapshot_directory=tmp_path,
        )

    persisted = "\n".join(
        path.read_text(encoding="utf-8") for path in tmp_path.iterdir()
    )
    assert credential not in persisted
    assert manifest["record_count"] == 2
    assert manifest["quarantined_record_count"] == 1

    _, rows = load_snapshot(tmp_path)
    quarantined = rows[0]
    assert "[REDACTED:credential_assignment]" in quarantined["content"]
    assert quarantined["metadata"]["security_quarantined"] is True

    quarantine = json.loads(
        (tmp_path / "quarantine-manifest.jsonl").read_text(encoding="utf-8")
    )
    assert quarantine["source_id"] == "legacy-1"
    assert (
        quarantine["original_content_sha256"]
        == hashlib.sha256(f"TELLUS_TOKEN={credential}".encode()).hexdigest()
    )
    assert "value" not in quarantine


def test_export_quarantine_manifest_detects_secret_prefix_in_metadata(tmp_path):
    credential = "github_pat_" + "x" * 24
    collection = MagicMock()
    collection.get.return_value = {
        "ids": ["legacy-meta"],
        "documents": ["safe content"],
        "metadatas": [{"debug": f"Authorization: Bearer {credential}"}],
    }
    chroma = MagicMock()
    chroma.get_collection.return_value = collection

    with patch(
        "scripts.migrate_chroma_to_ham.chromadb.PersistentClient", return_value=chroma
    ):
        export_snapshot(
            persist_directory="/unused",
            collection_name="agent_memory",
            snapshot_directory=tmp_path,
        )

    persisted = "\n".join(
        path.read_text(encoding="utf-8") for path in tmp_path.iterdir()
    )
    assert credential not in persisted
    _, rows = load_snapshot(tmp_path)
    assert "[REDACTED:secret_prefix]" in rows[0]["metadata"]["debug"]


def test_load_rejects_snapshot_if_secret_is_reintroduced(tmp_path):
    collection = MagicMock()
    collection.get.return_value = {
        "ids": ["legacy-safe"],
        "documents": ["ordinary memory"],
        "metadatas": [{}],
    }
    chroma = MagicMock()
    chroma.get_collection.return_value = collection

    with patch(
        "scripts.migrate_chroma_to_ham.chromadb.PersistentClient", return_value=chroma
    ):
        export_snapshot(
            persist_directory="/unused",
            collection_name="agent_memory",
            snapshot_directory=tmp_path,
        )

    snapshot_path = tmp_path / "chroma-memory.jsonl"
    rows = [json.loads(line) for line in snapshot_path.read_text().splitlines()]
    rows[0]["content"] = "API_KEY=sk-" + "reintroduced-test-value-12345"
    tampered = "".join(
        f"{json.dumps(row, sort_keys=True, separators=(',', ':'))}\n" for row in rows
    )
    snapshot_path.write_text(tampered)
    manifest_path = tmp_path / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["snapshot_sha256"] = hashlib.sha256(tampered.encode()).hexdigest()
    manifest_path.write_text(json.dumps(manifest))

    with pytest.raises(RuntimeError, match="credential-shaped"):
        load_snapshot(tmp_path)
