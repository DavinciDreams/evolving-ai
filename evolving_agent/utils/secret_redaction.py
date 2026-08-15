"""Deterministic credential-shape detection shared by migration and serving."""

from __future__ import annotations

import re
from typing import Any, Dict, List

DETECTOR_VERSION = "credential-redaction-v1"

_CREDENTIAL_ASSIGNMENT = re.compile(
    r"(?i)\b(?P<name>"
    r"tellus(?:[_ -]?(?:api[_ -]?)?(?:key|token))?"
    r"|api[_ -]?key|access[_ -]?token|auth[_ -]?token|secret|password"
    r")(?P<separator>\s*(?:=|:)\s*)(?P<quote>['\"]?)(?P<value>[^\s,;'\"}]+)(?P=quote)"
)
_SECRET_PREFIXES = re.compile(
    r"(?i)(?<![A-Za-z0-9])(?:"
    r"sk-[A-Za-z0-9_-]{12,}"
    r"|gh[pousr]_[A-Za-z0-9]{20,}"
    r"|github_pat_[A-Za-z0-9_]{20,}"
    r"|xox[baprs]-[A-Za-z0-9-]{10,}"
    r"|tellus[_-][A-Za-z0-9_-]{12,}"
    r"|bearer\s+[A-Za-z0-9._~+/-]{12,}"
    r")"
)


def redact_text(value: str) -> tuple[str, List[str]]:
    """Redact credential-shaped values without returning or logging matches."""
    findings: set[str] = set()

    def redact_assignment(match: re.Match[str]) -> str:
        if match.group("value").startswith("[REDACTED:"):
            return match.group(0)
        findings.add("credential_assignment")
        return (
            f"{match.group('name')}{match.group('separator')}"
            "[REDACTED:credential_assignment]"
        )

    redacted = _CREDENTIAL_ASSIGNMENT.sub(redact_assignment, value)

    def redact_prefix(_: re.Match[str]) -> str:
        findings.add("secret_prefix")
        return "[REDACTED:secret_prefix]"

    redacted = _SECRET_PREFIXES.sub(redact_prefix, redacted)
    return redacted, sorted(findings)


def redact_value(value: Any) -> tuple[Any, List[str]]:
    """Recursively sanitize string values while preserving structure."""
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        findings: set[str] = set()
        sanitized: Dict[str, Any] = {}
        for key, item in value.items():
            sanitized_item, item_findings = redact_value(item)
            sanitized[str(key)] = sanitized_item
            findings.update(item_findings)
        return sanitized, sorted(findings)
    if isinstance(value, list):
        findings = set()
        sanitized_items = []
        for item in value:
            sanitized_item, item_findings = redact_value(item)
            sanitized_items.append(sanitized_item)
            findings.update(item_findings)
        return sanitized_items, sorted(findings)
    return value, []
