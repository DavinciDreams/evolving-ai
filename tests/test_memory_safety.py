"""HAM-only storage safety without local embedding model imports."""
import json
from unittest.mock import AsyncMock

import pytest

from evolving_agent.core.memory import LongTermMemory, MemoryEntry
from evolving_agent.utils.secret_redaction import redact_text, redact_value


async def test_runtime_memory_redacts_content_and_sensitive_metadata():
    memory = LongTermMemory()
    memory.backend = "ham"
    memory.initialized = True
    memory.ham_client = AsyncMock()
    memory.ham_client.add.return_value = 123
    entry = MemoryEntry("api_key=example-secret", metadata={"nested": {"Authorization": "opaque-value"}})
    assert await memory.add_memory(entry) == "123"
    sent = memory.ham_client.add.call_args.kwargs
    assert "example-secret" not in str(sent)
    assert "opaque-value" not in str(sent)
    assert sent["metadata"]["redacted"] is True


def test_private_key_and_nsec_are_value_free():
    secret = "nsec1" + "q" * 58
    text = "-----BEGIN PRIVATE KEY-----\nopaque-key-data\n-----END PRIVATE KEY----- " + secret
    redacted, findings = redact_text(text)
    assert "opaque-key-data" not in redacted
    assert secret not in redacted
    assert set(findings) == {"private_key", "nsec"}


def test_sensitive_fields_do_not_destroy_ordinary_token_telemetry():
    clean, findings = redact_value({"tokens_used": 10, "max_tokens": 20, "api_key": "opaque-key"})
    assert clean["tokens_used"] == 10 and clean["max_tokens"] == 20
    assert clean["api_key"] == "[REDACTED:sensitive_field]"


@pytest.mark.parametrize(
    "key",
    [
        "clientSecret",
        "accessToken",
        "clientSecretValue",
        "accessTokenValue",
        "privateKeyPem",
        "oauthAccessTokenValue",
    ],
)
def test_camel_case_credential_keys_are_redacted(key):
    placeholder = "synthetic-secret-tail-24680"
    text = f"{key}={placeholder}"
    redacted, findings = redact_text(text)
    assert placeholder not in redacted
    assert redacted == f"{key}=[REDACTED:credential_assignment]"
    assert findings == ["credential_assignment"]


def test_camel_case_structured_credential_keys_are_redacted():
    placeholder = "synthetic-secret-tail-24680"
    credential_keys = [
        "clientSecret",
        "accessToken",
        "clientSecretValue",
        "accessTokenValue",
        "privateKeyPem",
        "oauthAccessTokenValue",
    ]
    redacted, findings = redact_value({key: placeholder for key in credential_keys})
    assert redacted == {
        key: "[REDACTED:sensitive_field]" for key in credential_keys
    }
    assert findings == ["sensitive_field"]


def test_escaped_json_credential_key_is_structurally_redacted():
    placeholder = "synthetic-secret-tail-24680"
    text = f'{{"P\\u0041SSWORD":"{placeholder}"}}'
    redacted, findings = redact_text(text)
    assert placeholder not in redacted
    assert json.loads(redacted) == {"PASSWORD": "[REDACTED:sensitive_field]"}
    assert findings == ["sensitive_field"]


def test_arbitrary_redaction_marker_is_not_trusted():
    text = "PASSWORD=[REDACTED:syntheticSecretTail24680]"
    assert redact_text(text) == (
        "PASSWORD=[REDACTED:credential_assignment]",
        ["credential_assignment"],
    )


def test_generic_assignment_capture_ignores_non_sensitive_multiline_name():
    text = "releaseNotes: |\n  ordinary public notes\n"
    assert redact_text(text) == (text, [])


@pytest.mark.parametrize(
    "text,expected",
    [
        (
            "ordinary=value PASSWORD=synthetic-secret-tail-24680",
            "ordinary=value PASSWORD=[REDACTED:credential_assignment]",
        ),
        (
            "ordinary=value;clientSecretValue=synthetic-secret-tail-24680",
            "ordinary=value;clientSecretValue=[REDACTED:credential_assignment]",
        ),
    ],
)
def test_non_sensitive_assignment_cannot_mask_later_credential(text, expected):
    assert redact_text(text) == (expected, ["credential_assignment"])


def test_prefixed_deployment_credentials_are_redacted_without_values():
    placeholder = "synthetic-placeholder-00000000000000000000000000"
    spaced_placeholder = "synthetic secret phrase 13579"
    punctuated_placeholder = "synthetic,value,12345"
    text = (
        f"HAM_API_KEY={placeholder}\nPROJECT_API_KEY: {placeholder}\n"
        f'{{"HAM_API_KEY":"{placeholder}"}}\n'
        f'os.environ["PROJECT_API_KEY"] = "{placeholder}"\n'
        f'{{"PASSWORD":"{spaced_placeholder}"}}\n'
        f'{{"HAM_API_KEY":"{punctuated_placeholder}"}}\n'
        "ordinary_field=ordinary-value"
    )
    redacted, findings = redact_text(text)
    assert placeholder not in redacted
    assert spaced_placeholder not in redacted
    assert punctuated_placeholder not in redacted
    assert "HAM_API_KEY=[REDACTED:credential_assignment]" in redacted
    assert "PROJECT_API_KEY: [REDACTED:credential_assignment]" in redacted
    assert '"HAM_API_KEY":"[REDACTED:credential_assignment]"' in redacted
    assert (
        'os.environ["PROJECT_API_KEY"] = "[REDACTED:credential_assignment]"'
        in redacted
    )
    assert '"PASSWORD":"[REDACTED:credential_assignment]"' in redacted
    assert '"HAM_API_KEY":"[REDACTED:credential_assignment]"' in redacted
    assert "ordinary_field=ordinary-value" in redacted
    assert findings == ["credential_assignment"]


@pytest.mark.parametrize(
    "text",
    [
        "PASSWORD: |\n  synthetic secret phrase 13579\n",
        "HAM_API_KEY: >-\n  synthetic,value,12345\n",
        "PROJECT_API_KEY=\\\nsynthetic-shell-secret-24680\n",
        'PASSWORD="synthetic\nquoted secret 97531"',
    ],
)
def test_multiline_credential_assignments_are_value_free(text):
    redacted, findings = redact_text(text)
    assert "synthetic" not in redacted
    assert "[REDACTED:" in redacted
    assert findings


@pytest.mark.parametrize(
    "text,plaintext_tail",
    [
        ("password: correct horse battery staple", "horse battery staple"),
        ("HAM_API_KEY=synthetic,value;tail", "value;tail"),
        (
            "PASSWORD=[REDACTED:credential_assignment] leaked tail",
            "leaked tail",
        ),
    ],
)
def test_unquoted_credential_assignment_owns_complete_line(text, plaintext_tail):
    redacted, findings = redact_text(text)
    assert plaintext_tail not in redacted
    assert redacted.endswith("[REDACTED:credential_assignment]")
    assert findings == ["credential_assignment"]


def test_quoted_marker_with_adjacent_shell_suffix_is_redacted():
    plaintext_tail = "synthetic-secret-tail-24680"
    text = f'PASSWORD="[REDACTED:credential_assignment]"{plaintext_tail}'
    redacted, findings = redact_text(text)
    assert plaintext_tail not in redacted
    assert redacted == "PASSWORD=[REDACTED:credential_assignment]"
    assert findings == ["credential_assignment"]


@pytest.mark.parametrize(
    "text",
    [
        "PASSWORD=[REDACTED:credential_assignment]",
        'PASSWORD="[REDACTED:credential_assignment]"',
    ],
)
def test_exact_redaction_marker_remains_idempotent(text):
    assert redact_text(text) == (text, [])
