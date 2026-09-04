"""HAM-only storage safety without local embedding model imports."""
from unittest.mock import AsyncMock

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
