#!/usr/bin/env python3
"""Export legacy Chroma memory and import it into HAM without deleting evidence.

The workflow is deliberately split into explicit export/import/verify/mark steps.
It never deletes the Chroma volume. Run it inside the Coolify application
container so the named volumes remain local to the deployment boundary.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

import chromadb

from evolving_agent.integrations.ham_memory import HAMMemoryClient
from evolving_agent.utils.config import config
from evolving_agent.utils.secret_redaction import (
    DETECTOR_VERSION,
    redact_text,
    redact_value,
)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _content_sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _write_private(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    path.chmod(0o600)


def export_snapshot(
    *,
    persist_directory: str,
    collection_name: str,
    snapshot_directory: Path,
) -> Dict[str, Any]:
    """Export a stable redacted snapshot plus a value-free quarantine manifest."""
    client = chromadb.PersistentClient(path=persist_directory)
    collection = client.get_collection(collection_name)
    result = collection.get(include=["documents", "metadatas"])

    rows: List[Dict[str, Any]] = []
    quarantine_rows: List[Dict[str, Any]] = []
    for source_id, content, metadata in zip(
        result.get("ids") or [],
        result.get("documents") or [],
        result.get("metadatas") or [],
    ):
        raw_content = str(content or "")
        raw_metadata = dict(metadata or {})
        timestamp = raw_metadata.get("timestamp")
        redacted_content, content_findings = redact_text(raw_content)
        redacted_metadata, metadata_findings = redact_value(raw_metadata)
        findings = sorted(set(content_findings + metadata_findings))
        if findings:
            quarantine_rows.append(
                {
                    "source_backend": "chroma",
                    "source_collection": collection_name,
                    "source_id": str(source_id),
                    "timestamp": timestamp,
                    "original_content_sha256": _content_sha256(raw_content),
                    "original_metadata_sha256": _content_sha256(
                        _canonical_json(raw_metadata)
                    ),
                    "detector_classes": findings,
                    "action": "redacted-before-export-and-import",
                }
            )
        rows.append(
            {
                "source_backend": "chroma",
                "source_collection": collection_name,
                "source_id": str(source_id),
                "timestamp": timestamp,
                "content": redacted_content,
                "content_sha256": _content_sha256(redacted_content),
                "metadata": {
                    **redacted_metadata,
                    "security_quarantined": bool(findings),
                    "redaction_detector_classes": findings,
                },
            }
        )
    rows.sort(key=lambda row: row["source_id"])
    quarantine_rows.sort(key=lambda row: row["source_id"])

    jsonl = "".join(f"{_canonical_json(row)}\n" for row in rows)
    snapshot_path = snapshot_directory / "chroma-memory.jsonl"
    _write_private(snapshot_path, jsonl)
    snapshot_sha256 = hashlib.sha256(jsonl.encode("utf-8")).hexdigest()

    quarantine_text = "".join(f"{_canonical_json(row)}\n" for row in quarantine_rows)
    quarantine_path = snapshot_directory / "quarantine-manifest.jsonl"
    _write_private(quarantine_path, quarantine_text)
    quarantine_sha256 = hashlib.sha256(quarantine_text.encode("utf-8")).hexdigest()

    metadata_keys = sorted(
        {key for row in rows for key in (row.get("metadata") or {}).keys()}
    )
    manifest = {
        "format": "evolving-ai-chroma-snapshot-v2-redacted",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_backend": "chroma",
        "source_collection": collection_name,
        "record_count": len(rows),
        "snapshot_file": snapshot_path.name,
        "snapshot_sha256": snapshot_sha256,
        "quarantine_file": quarantine_path.name,
        "quarantine_sha256": quarantine_sha256,
        "quarantined_record_count": len(quarantine_rows),
        "redaction_detector_version": DETECTOR_VERSION,
        "metadata_keys": metadata_keys,
        "visibility_policy": "legacy rows import as project-private unless explicitly republished",
        "security_policy": (
            "credential-shaped values are redacted before snapshot persistence; "
            "the quarantine manifest contains attribution and hashes, never matched values"
        ),
    }
    _write_private(
        snapshot_directory / "manifest.json",
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
    )
    return manifest


def load_snapshot(
    snapshot_directory: Path,
) -> tuple[Dict[str, Any], List[Dict[str, Any]]]:
    manifest = json.loads(
        (snapshot_directory / "manifest.json").read_text(encoding="utf-8")
    )
    if manifest.get("format") != "evolving-ai-chroma-snapshot-v2-redacted":
        raise RuntimeError("Only the redacted snapshot format may be imported")
    snapshot_path = snapshot_directory / manifest["snapshot_file"]
    snapshot_bytes = snapshot_path.read_bytes()
    actual_sha256 = hashlib.sha256(snapshot_bytes).hexdigest()
    if actual_sha256 != manifest["snapshot_sha256"]:
        raise RuntimeError("Snapshot checksum does not match manifest")
    rows = [
        json.loads(line) for line in snapshot_bytes.decode("utf-8").splitlines() if line
    ]
    if len(rows) != manifest["record_count"]:
        raise RuntimeError("Snapshot record count does not match manifest")
    if len({row["source_id"] for row in rows}) != len(rows):
        raise RuntimeError("Snapshot contains duplicate source IDs")
    _, snapshot_findings = redact_text(snapshot_bytes.decode("utf-8"))
    if snapshot_findings:
        raise RuntimeError("Snapshot still contains credential-shaped values")
    quarantine_path = snapshot_directory / manifest["quarantine_file"]
    quarantine_bytes = quarantine_path.read_bytes()
    if hashlib.sha256(quarantine_bytes).hexdigest() != manifest["quarantine_sha256"]:
        raise RuntimeError("Quarantine manifest checksum does not match manifest")
    quarantine_rows = [
        json.loads(line)
        for line in quarantine_bytes.decode("utf-8").splitlines()
        if line
    ]
    if len(quarantine_rows) != manifest["quarantined_record_count"]:
        raise RuntimeError("Quarantine record count does not match manifest")
    _, quarantine_findings = redact_text(quarantine_bytes.decode("utf-8"))
    if quarantine_findings:
        raise RuntimeError("Quarantine manifest contains credential-shaped values")
    return manifest, rows


def build_ham_client() -> HAMMemoryClient:
    return HAMMemoryClient(
        base_url=config.ham_api_url,
        api_key=config.ham_api_key,
        project=config.ham_project,
        scope=config.ham_scope,
        repo=config.ham_repo,
        expected_agent_id=config.ham_expected_agent_id,
        timeout=config.ham_timeout_seconds,
    )


async def import_snapshot(snapshot_directory: Path) -> Dict[str, Any]:
    """Import the snapshot with stable per-source idempotency keys."""
    manifest, rows = load_snapshot(snapshot_directory)
    client = build_ham_client()
    await client.initialize()
    imported: List[Dict[str, Any]] = []
    try:
        for row in rows:
            source_id = row["source_id"]
            metadata = {
                **(row.get("metadata") or {}),
                "audience": "project",
                "migration_source": "chroma",
                "legacy_source_id": source_id,
                "legacy_collection": row["source_collection"],
                "legacy_content_sha256": row["content_sha256"],
            }
            ham_id = await client.add(
                content=row["content"],
                source_id=source_id,
                timestamp=row.get("timestamp")
                or datetime.now(timezone.utc).isoformat(),
                memory_type=metadata.get("memory_type", "general"),
                metadata=metadata,
                idempotency_key=(
                    f"chroma:{row['source_collection']}:{source_id}:"
                    f"{row['content_sha256'][:16]}"
                ),
            )
            imported.append(
                {
                    "source_id": source_id,
                    "ham_id": ham_id,
                    "content_sha256": row["content_sha256"],
                }
            )
    finally:
        await client.close()

    mapping_text = "".join(f"{_canonical_json(row)}\n" for row in imported)
    mapping_path = snapshot_directory / "ham-import-map.jsonl"
    _write_private(mapping_path, mapping_text)
    result = {
        "source_count": manifest["record_count"],
        "imported_count": len(imported),
        "mapping_file": mapping_path.name,
        "mapping_sha256": hashlib.sha256(mapping_text.encode("utf-8")).hexdigest(),
    }
    _write_private(
        snapshot_directory / "import-result.json",
        json.dumps(result, indent=2, sort_keys=True) + "\n",
    )
    return result


def _representative_rows(rows: List[Dict[str, Any]]) -> Iterable[Dict[str, Any]]:
    if not rows:
        return []
    by_type: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        memory_type = (row.get("metadata") or {}).get("memory_type", "general")
        by_type.setdefault(str(memory_type), row)
    selected = [rows[0], rows[-1], *by_type.values()]
    unique: Dict[str, Dict[str, Any]] = {row["source_id"]: row for row in selected}
    return list(unique.values())[:12]


async def verify_import(snapshot_directory: Path) -> Dict[str, Any]:
    """Verify direct content checksums and representative semantic recall."""
    _, rows = load_snapshot(snapshot_directory)
    mapping_rows = [
        json.loads(line)
        for line in (snapshot_directory / "ham-import-map.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line
    ]
    mapping = {row["source_id"]: row for row in mapping_rows}
    client = build_ham_client()
    await client.initialize()
    checks = []
    try:
        for source in _representative_rows(rows):
            mapped = mapping[source["source_id"]]
            direct = await client.get(int(mapped["ham_id"]))
            direct_ok = bool(
                direct
                and _content_sha256(str(direct.get("content") or ""))
                == source["content_sha256"]
            )
            query = source["content"][:500].strip() or source["source_id"]
            recalled = await client.search(query, top_k=20)
            recall_ok = any(int(row["id"]) == int(mapped["ham_id"]) for row in recalled)
            checks.append(
                {
                    "source_id": source["source_id"],
                    "ham_id": mapped["ham_id"],
                    "direct_checksum_ok": direct_ok,
                    "representative_recall_ok": recall_ok,
                }
            )
    finally:
        await client.close()
    result = {
        "checks": checks,
        "passed": bool(checks)
        and all(
            check["direct_checksum_ok"] and check["representative_recall_ok"]
            for check in checks
        ),
    }
    _write_private(
        snapshot_directory / "verification-result.json",
        json.dumps(result, indent=2, sort_keys=True) + "\n",
    )
    return result


def mark_legacy_read_only(snapshot_directory: Path) -> Dict[str, Any]:
    verification = json.loads(
        (snapshot_directory / "verification-result.json").read_text(encoding="utf-8")
    )
    if not verification.get("passed"):
        raise RuntimeError(
            "Cannot mark legacy memory read-only before verification passes"
        )
    marker = {
        "state": "read-only",
        "marked_at": datetime.now(timezone.utc).isoformat(),
        "rollback": (
            "Set MEMORY_BACKEND=chroma and LEGACY_MEMORY_READ_ONLY=false only after "
            "an explicit operator decision; do not delete the named volume."
        ),
    }
    _write_private(
        snapshot_directory / "LEGACY_CHROMA_READ_ONLY.json",
        json.dumps(marker, indent=2, sort_keys=True) + "\n",
    )
    return marker


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command", choices=["export", "import", "verify", "mark-read-only"]
    )
    parser.add_argument(
        "--snapshot-directory",
        type=Path,
        default=Path(config.backup_directory) / "chroma-to-ham",
    )
    parser.add_argument("--persist-directory", default=config.memory_persist_directory)
    parser.add_argument("--collection", default=config.memory_collection_name)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "export":
        result = export_snapshot(
            persist_directory=args.persist_directory,
            collection_name=args.collection,
            snapshot_directory=args.snapshot_directory,
        )
    elif args.command == "import":
        result = asyncio.run(import_snapshot(args.snapshot_directory))
    elif args.command == "verify":
        result = asyncio.run(verify_import(args.snapshot_directory))
    else:
        result = mark_legacy_read_only(args.snapshot_directory)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
