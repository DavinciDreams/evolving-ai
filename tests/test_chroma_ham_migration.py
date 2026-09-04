"""Security and integrity tests for the explicit Chroma-to-HAM migration."""

import hashlib
import json
from unittest.mock import MagicMock, patch

import pytest

from scripts.migrate_chroma_to_ham import (
    export_snapshot,
    load_snapshot,
    import_snapshot,
    verify_import,
    mark_legacy_read_only,
)


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


def test_export_redacts_prefixed_deployment_assignments_and_load_accepts_only_redacted(tmp_path):
    placeholder = "synthetic-placeholder-00000000000000000000000000"
    collection = MagicMock()
    collection.get.return_value = {
        "ids": ["legacy-deployment-note"],
        "documents": [
            f"HAM_API_KEY={placeholder}\n"
            f"PROJECT_API_KEY={placeholder}\n"
            f'{{"HAM_API_KEY":"{placeholder}"}}\n'
            f'os.environ["PROJECT_API_KEY"] = "{placeholder}"'
        ],
        "metadatas": [
            {"timestamp": "2026-08-31T00:00:00Z", "memory_type": "fact"}
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
    persisted = "\n".join(path.read_text() for path in tmp_path.iterdir())
    assert placeholder not in persisted
    assert manifest["quarantined_record_count"] == 1
    _, rows = load_snapshot(tmp_path)
    assert rows[0]["content"].count("[REDACTED:credential_assignment]") == 4
    assert json.loads(rows[0]["content"].splitlines()[2]) == {
        "HAM_API_KEY": "[REDACTED:credential_assignment]"
    }
    assert rows[0]["metadata"]["security_quarantined"] is True


@pytest.mark.parametrize(
    "credential_value",
    [
        "synthetic secret phrase 13579",
        "synthetic,value,12345",
    ],
)
def test_export_redacts_quoted_values_with_spaces_or_commas(
    tmp_path, credential_value
):
    collection = MagicMock()
    collection.get.return_value = {
        "ids": ["legacy-quoted-value"],
        "documents": [
            json.dumps({"PASSWORD": credential_value}, separators=(",", ":"))
        ],
        "metadatas": [{}],
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

    persisted = "\n".join(path.read_text() for path in tmp_path.iterdir())
    assert credential_value not in persisted
    assert manifest["quarantined_record_count"] == 1
    _, rows = load_snapshot(tmp_path)
    assert json.loads(rows[0]["content"]) == {
        "PASSWORD": "[REDACTED:credential_assignment]"
    }
    assert rows[0]["metadata"]["security_quarantined"] is True


@pytest.mark.parametrize(
    "credential_text",
    [
        "PASSWORD: |\n  synthetic secret phrase 13579\n",
        "HAM_API_KEY: >-\n  synthetic,value,12345\n",
        "PROJECT_API_KEY=\\\nsynthetic-shell-secret-24680\n",
        'PASSWORD="synthetic\nquoted secret 97531"',
    ],
)
def test_export_removes_and_quarantines_multiline_credential(
    tmp_path, credential_text
):
    collection = MagicMock()
    collection.get.return_value = {
        "ids": ["legacy-multiline-credential"],
        "documents": [credential_text],
        "metadatas": [{}],
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

    persisted = "\n".join(path.read_text() for path in tmp_path.iterdir())
    assert "synthetic" not in persisted
    assert manifest["quarantined_record_count"] == 1
    _, rows = load_snapshot(tmp_path)
    assert "[REDACTED:" in rows[0]["content"]
    assert rows[0]["metadata"]["security_quarantined"] is True


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
    rows[0]["content_sha256"] = hashlib.sha256(
        rows[0]["content"].encode()
    ).hexdigest()
    tampered = "".join(
        f"{json.dumps(row, sort_keys=True, separators=(',', ':'))}\n" for row in rows
    )
    snapshot_path.write_bytes(tampered.encode())
    manifest_path = tmp_path / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["snapshot_sha256"] = hashlib.sha256(tampered.encode()).hexdigest()
    manifest_path.write_text(json.dumps(manifest))

    with pytest.raises(RuntimeError, match="credential-shaped"):
        load_snapshot(tmp_path)


@pytest.mark.parametrize(
    "credential_text",
    [
        '{"HAM_API_KEY":"synthetic-placeholder-00000000000000000000000000"}',
        'os.environ["HAM_API_KEY"] = "synthetic-placeholder-00000000000000000000000000"',
        '{"PASSWORD":"synthetic secret phrase 13579"}',
        '{"HAM_API_KEY":"synthetic,value,12345"}',
        "PASSWORD: |\n  synthetic secret phrase 13579\n",
        "HAM_API_KEY: >-\n  synthetic,value,12345\n",
        "PROJECT_API_KEY=\\\nsynthetic-shell-secret-24680\n",
        'PASSWORD="synthetic\nquoted secret 97531"',
    ],
)
def test_load_rejects_quoted_credential_key_reintroduced(
    tmp_path, credential_text
):
    _export(tmp_path, count=1)
    snapshot_path = tmp_path / "chroma-memory.jsonl"
    rows = [json.loads(line) for line in snapshot_path.read_text().splitlines()]
    rows[0]["content"] = credential_text
    rows[0]["content_sha256"] = hashlib.sha256(
        credential_text.encode()
    ).hexdigest()
    tampered = "".join(
        f"{json.dumps(row, sort_keys=True, separators=(',', ':'))}\n" for row in rows
    )
    snapshot_path.write_bytes(tampered.encode())
    manifest_path = tmp_path / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["snapshot_sha256"] = hashlib.sha256(tampered.encode()).hexdigest()
    manifest_path.write_text(json.dumps(manifest))

    with pytest.raises(RuntimeError, match="credential-shaped"):
        load_snapshot(tmp_path)


def _export(tmp_path, count=3):
    collection = MagicMock()
    collection.get.return_value = {
        "ids": [f"source-{i:03d}" for i in range(count)],
        "documents": [f"Ordinary safe note {i}" for i in range(count)],
        "metadatas": [{"memory_type": "note"} for _ in range(count)],
    }
    chroma = MagicMock()
    chroma.get_collection.return_value = collection
    with patch(
        "scripts.migrate_chroma_to_ham.chromadb.PersistentClient", return_value=chroma
    ):
        return export_snapshot(
            persist_directory="unused",
            collection_name="agent_memory",
            snapshot_directory=tmp_path,
        )


class FakeHAM:
    def __init__(self):
        self.entries = {}
        self.keys = {}
        self.add_calls = []
        self.get_calls = []
        self.closed = False

    async def initialize(self):
        pass

    async def add(self, **kwargs):
        self.add_calls.append(kwargs)
        key = kwargs["idempotency_key"]
        if key not in self.keys:
            memory_id = len(self.entries) + 1
            self.keys[key] = memory_id
            self.entries[memory_id] = {
                "id": memory_id,
                "content": kwargs["content"],
                "metadata": kwargs["metadata"],
            }
        return self.keys[key]

    async def get(self, memory_id):
        self.get_calls.append(memory_id)
        return self.entries.get(memory_id)

    async def search(self, query, *, top_k):
        return [
            entry
            for entry in self.entries.values()
            if entry["content"].startswith(query)
        ]

    async def close(self):
        self.closed = True


@pytest.mark.asyncio
async def test_complete_import_verify_and_marker_with_no_live_services(tmp_path):
    manifest = _export(tmp_path, 16)
    client = FakeHAM()
    with patch("scripts.migrate_chroma_to_ham.build_ham_client", return_value=client):
        imported = await import_snapshot(tmp_path)
        verified = await verify_import(tmp_path)
    assert imported["source_snapshot_sha256"] == manifest["snapshot_sha256"]
    assert verified["passed"]
    assert verified["direct_checked_count"] == 16
    assert len(client.get_calls) == 16
    assert len(verified["recall_checks"]) < 16
    assert mark_legacy_read_only(tmp_path)["state"] == "read-only"
    assert client.closed


@pytest.mark.asyncio
async def test_unsampled_corruption_is_caught_by_full_direct_verification(tmp_path):
    _export(tmp_path, 16)
    client = FakeHAM()
    with patch("scripts.migrate_chroma_to_ham.build_ham_client", return_value=client):
        await import_snapshot(tmp_path)
        client.entries[8]["content"] = "corrupted middle record"
        verified = await verify_import(tmp_path)
    assert not verified["passed"]
    assert verified["direct_checked_count"] == 16
    assert all(check["representative_recall_ok"] for check in verified["recall_checks"])
    with pytest.raises(RuntimeError, match="before verification passes"):
        mark_legacy_read_only(tmp_path)


@pytest.mark.asyncio
async def test_repeated_import_keeps_keys_timestamps_and_cardinality(tmp_path):
    _export(tmp_path)
    client = FakeHAM()
    with patch("scripts.migrate_chroma_to_ham.build_ham_client", return_value=client):
        await import_snapshot(tmp_path)
        await import_snapshot(tmp_path)
    assert len(client.entries) == 3
    assert client.add_calls[:3] == client.add_calls[3:]


@pytest.mark.parametrize(
    "result",
    [
        {"ids": ["one", "two"], "documents": ["only one"], "metadatas": [{}, {}]},
        {"ids": ["one", "one"], "documents": ["one", "two"], "metadatas": [{}, {}]},
    ],
)
def test_export_fails_before_writing_on_truncation_or_duplicate_ids(tmp_path, result):
    chroma = MagicMock()
    chroma.get_collection.return_value.get.return_value = result
    with patch(
        "scripts.migrate_chroma_to_ham.chromadb.PersistentClient", return_value=chroma
    ):
        with pytest.raises(RuntimeError):
            export_snapshot(
                persist_directory="unused",
                collection_name="agent_memory",
                snapshot_directory=tmp_path,
            )
    assert list(tmp_path.iterdir()) == []


def test_per_record_checksum_is_verified_even_if_manifest_hash_matches(tmp_path):
    _export(tmp_path)
    snapshot = tmp_path / "chroma-memory.jsonl"
    rows = [json.loads(line) for line in snapshot.read_text().splitlines()]
    rows[1]["content"] = "tampered but safe content"
    payload = "".join(json.dumps(row) + "\n" for row in rows).encode()
    snapshot.write_bytes(payload)
    manifest_path = tmp_path / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["snapshot_sha256"] = hashlib.sha256(payload).hexdigest()
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(RuntimeError, match="per-record"):
        load_snapshot(tmp_path)


def test_manifest_cannot_reference_files_outside_snapshot(tmp_path):
    _export(tmp_path)
    manifest_path = tmp_path / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["snapshot_file"] = "../outside.jsonl"
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(RuntimeError, match="artifact paths"):
        load_snapshot(tmp_path)


@pytest.mark.asyncio
async def test_mapping_tampering_rejected_before_network(tmp_path):
    _export(tmp_path)
    client = FakeHAM()
    with patch("scripts.migrate_chroma_to_ham.build_ham_client", return_value=client):
        await import_snapshot(tmp_path)
    mapping = tmp_path / "ham-import-map.jsonl"
    mapping.write_bytes(mapping.read_bytes() + b"\n")
    with patch(
        "scripts.migrate_chroma_to_ham.build_ham_client",
        side_effect=AssertionError("no network"),
    ):
        with pytest.raises(RuntimeError, match="mapping checksum"):
            await verify_import(tmp_path)


@pytest.mark.asyncio
async def test_stale_verification_cannot_mark_a_different_snapshot(tmp_path):
    _export(tmp_path)
    client = FakeHAM()
    with patch("scripts.migrate_chroma_to_ham.build_ham_client", return_value=client):
        await import_snapshot(tmp_path)
        await verify_import(tmp_path)
    _export(tmp_path, count=4)
    with pytest.raises(RuntimeError, match="before verification passes"):
        mark_legacy_read_only(tmp_path)


@pytest.mark.asyncio
async def test_client_is_closed_if_preflight_fails(tmp_path):
    _export(tmp_path)
    client = FakeHAM()

    async def failed():
        raise RuntimeError("preflight denied")

    client.initialize = failed
    with patch("scripts.migrate_chroma_to_ham.build_ham_client", return_value=client):
        with pytest.raises(RuntimeError, match="preflight"):
            await import_snapshot(tmp_path)
    assert client.closed


def test_timestamp_metadata_does_not_bypass_redaction(tmp_path):
    credential = "sk-" + "synthetic-test-value-12345"
    chroma = MagicMock()
    chroma.get_collection.return_value.get.return_value = {
        "ids": ["one"],
        "documents": ["safe"],
        "metadatas": [{"timestamp": credential}],
    }
    with patch(
        "scripts.migrate_chroma_to_ham.chromadb.PersistentClient", return_value=chroma
    ):
        export_snapshot(
            persist_directory="unused",
            collection_name="agent_memory",
            snapshot_directory=tmp_path,
        )
    assert credential not in "".join(path.read_text() for path in tmp_path.iterdir())
    _, rows = load_snapshot(tmp_path)
    assert rows[0]["timestamp"] is None
