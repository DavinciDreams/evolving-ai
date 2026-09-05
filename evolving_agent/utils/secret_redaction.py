"""Deterministic credential-shape detection shared by migration and serving."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List

DETECTOR_VERSION = "credential-redaction-v12"

_SENSITIVE_KEY = re.compile(
    r"(?:^|_)(?:password|secret|token|api_key|authorization|nsec|private_key)(?:$|_)"
)
_UNICODE_ESCAPE = re.compile(r"\\u([0-9A-Fa-f]{4})")
_CAMEL_ACRONYM_BOUNDARY = re.compile(r"(?<=[A-Z])(?=[A-Z][a-z])")
_CAMEL_WORD_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_NON_KEY_CHARACTER = re.compile(r"[^A-Za-z0-9]+")
_PRIVATE_KEY = re.compile(r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----.*?-----END (?:[A-Z ]+ )?PRIVATE KEY-----", re.DOTALL)
_NSEC = re.compile(r"(?<![A-Za-z0-9])nsec1[023456789acdefghjklmnpqrstuvwxyz]{20,}")

_ASSIGNMENT_NAME = (
    r"[A-Za-z][A-Za-z0-9_-]*(?:[ ]+[A-Za-z][A-Za-z0-9_-]*)*"
)
_MULTILINE_CREDENTIAL_ASSIGNMENT = re.compile(
    rf"(?im)(?<![A-Za-z0-9_-])(?:"
    rf"(?P<multiline_name>{_ASSIGNMENT_NAME})"
    rf"|(?P<multiline_key_quote>['\"])(?P<multiline_quoted_name>{_ASSIGNMENT_NAME})"
    rf"(?P=multiline_key_quote)(?:\s*\])?"
    rf")(?![A-Za-z0-9_-])\s*(?:=|:)\s*"
    rf"(?:[|>](?:[+-][1-9]?|[1-9][+-]?)?|[\\^`])"
    rf"[ \t]*(?:#[^\r\n]*)?(?:\r?\n|$)"
)
_ASSIGNMENT_CANDIDATE = re.compile(
    rf"(?i)(?<![A-Za-z0-9_-])(?:"
    rf"(?P<name>{_ASSIGNMENT_NAME})"
    rf"|(?P<key_quote>['\"])(?P<quoted_name>{_ASSIGNMENT_NAME})"
    rf"(?P=key_quote)(?:\s*\])?"
    rf")(?![A-Za-z0-9_-])(?P<separator>\s*(?:=|:)\s*)"
)
_CANONICAL_REDACTED_VALUES = frozenset(
    {
        "[REDACTED:credential_assignment]",
        "[REDACTED:credential_multiline_record]",
        "[REDACTED:nsec]",
        "[REDACTED:private_key]",
        "[REDACTED:secret_prefix]",
        "[REDACTED:sensitive_field]",
    }
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


def _normalize_key(value: str) -> str:
    """Canonicalize serialized, camelCase, snake_case, and kebab-case keys."""
    unescaped = _UNICODE_ESCAPE.sub(lambda match: chr(int(match.group(1), 16)), value)
    separated = _CAMEL_ACRONYM_BOUNDARY.sub("_", unescaped)
    separated = _CAMEL_WORD_BOUNDARY.sub("_", separated)
    return _NON_KEY_CHARACTER.sub("_", separated).strip("_").lower()


def _is_sensitive_key(value: str) -> bool:
    normalized = _normalize_key(value)
    return bool(_SENSITIVE_KEY.search(normalized))


def _is_sensitive_assignment_name(value: str) -> bool:
    normalized = _normalize_key(value)
    return _is_sensitive_key(value) or normalized.startswith("tellus")


def _line_end(value: str, start: int) -> int:
    candidates = [position for position in (value.find("\r", start), value.find("\n", start)) if position >= 0]
    return min(candidates) if candidates else len(value)


def _closing_quote(value: str, start: int) -> int | None:
    quote = value[start]
    position = start + 1
    while position < len(value):
        if value[position] == "\\":
            position += 2
            continue
        if value[position] == quote:
            return position
        position += 1
    return None


def _is_quoted_value_boundary(
    value: str, position: int, *, serialized_key: bool = False
) -> bool:
    if position >= len(value) or value[position] in "\r\n":
        return True
    if value[position] in " \t":
        return True
    if value.startswith(("&&", "||"), position) or value[position] in ";&|":
        return True
    if serialized_key and value[position] in "}]":
        return not value[position + 1 : _line_end(value, position + 1)].strip()
    return False


def redact_text(value: str) -> tuple[str, List[str]]:
    """Redact credential-shaped values without returning or logging matches."""
    try:
        structured = json.loads(value)
    except (json.JSONDecodeError, TypeError):
        structured = None
    if isinstance(structured, (dict, list)):
        redacted_structured, structured_findings = redact_value(structured)
        if structured_findings:
            return (
                json.dumps(redacted_structured, ensure_ascii=False, separators=(",", ":")),
                structured_findings,
            )

    findings: set[str] = set()
    for multiline_match in _MULTILINE_CREDENTIAL_ASSIGNMENT.finditer(value):
        multiline_name = multiline_match.group("multiline_name") or (
            multiline_match.group("multiline_quoted_name")
        )
        if _is_sensitive_assignment_name(multiline_name):
            findings.add("credential_multiline_assignment")
            return "[REDACTED:credential_multiline_record]", sorted(findings)
    value, count = _PRIVATE_KEY.subn("[REDACTED:private_key]", value)
    if count:
        findings.add("private_key")
    value, count = _NSEC.subn("[REDACTED:nsec]", value)
    if count:
        findings.add("nsec")

    operations: List[tuple[int, int, str]] = []
    for match in _ASSIGNMENT_CANDIDATE.finditer(value):
        name = match.group("name") or match.group("quoted_name")
        if not _is_sensitive_assignment_name(name):
            continue
        value_start = match.end()
        if value_start < len(value) and value[value_start] in "'\"":
            closing_quote = _closing_quote(value, value_start)
            if closing_quote is None:
                operations.append(
                    (value_start, len(value), "[REDACTED:credential_assignment]")
                )
                findings.add("credential_assignment")
                continue
            matched_value = value[value_start + 1 : closing_quote]
            serialized_key = bool(
                match.group("quoted_name") and ":" in match.group("separator")
            )
            has_value_boundary = _is_quoted_value_boundary(
                value, closing_quote + 1, serialized_key=serialized_key
            )
            if (
                matched_value.strip() in _CANONICAL_REDACTED_VALUES
                and has_value_boundary
            ):
                continue
            if has_value_boundary:
                operations.append(
                    (
                        value_start + 1,
                        closing_quote,
                        "[REDACTED:credential_assignment]",
                    )
                )
            else:
                operations.append(
                    (
                        value_start,
                        _line_end(value, closing_quote + 1),
                        "[REDACTED:credential_assignment]",
                    )
                )
        else:
            value_end = _line_end(value, value_start)
            matched_value = value[value_start:value_end]
            if matched_value.strip() in _CANONICAL_REDACTED_VALUES:
                continue
            operations.append(
                (value_start, value_end, "[REDACTED:credential_assignment]")
            )
        findings.add("credential_assignment")

    non_overlapping: List[tuple[int, int, str]] = []
    for operation in operations:
        if non_overlapping and operation[0] < non_overlapping[-1][1]:
            continue
        non_overlapping.append(operation)
    redacted = value
    for start, end, replacement in reversed(non_overlapping):
        redacted = redacted[:start] + replacement + redacted[end:]

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
            if _is_sensitive_key(str(key)) and item:
                sanitized[str(key)] = "[REDACTED:sensitive_field]"
                findings.add("sensitive_field")
                continue
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
