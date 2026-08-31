"""Pure selected-provider resolution shared by chat and bounded experiments.

No credential properties, environment reads, network requests, or fallback to
another provider occur here. Config exposes explicit DEFAULT_MODEL separately
from its historical baked-in default so model precedence is unambiguous.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit


@dataclass(frozen=True)
class ProviderSelection:
    provider: str
    model: str
    base_url: str
    endpoint: str


def _https_base(value: str, *, bare_host_v1: bool = False) -> str:
    try:
        if (
            not isinstance(value, str)
            or len(value) > 2048
            or "\\" in value
            or any(char.isspace() or ord(char) < 32 for char in value)
        ):
            raise ValueError
        parsed = urlsplit(value)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or "?" in value
            or "#" in value
            or parsed.port not in (None, 443)
        ):
            raise ValueError
    except (TypeError, ValueError):
        raise RuntimeError(
            "A configured HTTPS provider without URL credentials is required"
        ) from None
    # Canonical spelling keeps official OpenAI request-shape detection correct
    # for a configured :443, while preserving explicit version/proxy paths.
    host = parsed.hostname
    if ":" in host:
        host = f"[{host}]"
    base = "https://" + host + parsed.path.rstrip("/")
    if bare_host_v1 and not parsed.path.strip("/"):
        base += "/v1"
    return base


def resolve_provider(config) -> ProviderSelection:
    """Resolve the selected model and actual endpoint, never inspect credentials.

    Explicit DEFAULT_MODEL wins. Otherwise OpenAI/ZAI use their provider-specific
    model; Anthropic/OpenRouter retain default_model. Plain config test doubles
    without default_model_override treat their supplied default_model as explicit.
    """
    provider = config.default_llm_provider
    if provider not in {"openai", "zai", "anthropic", "openrouter"}:
        raise RuntimeError("Unsupported selected provider")
    override = getattr(config, "default_model_override", None)
    if override is None:
        override = getattr(config, "default_model", "")
    if provider == "openai":
        model = override or config.openai_model
        base = _https_base(
            config.openai_base_url or "https://api.openai.com/v1", bare_host_v1=True
        )
    elif provider == "zai":
        model = override or config.zai_model
        base = _https_base(config.zai_base_url)
    elif provider == "anthropic":
        model = override or config.default_model
        base = "https://api.anthropic.com/v1"
    else:
        model = override or config.default_model
        base = "https://openrouter.ai/api/v1"
    if (
        not isinstance(model, str)
        or not model.strip()
        or model != model.strip()
        or len(model) > 512
        or any(ord(char) < 32 for char in model)
    ):
        raise RuntimeError("A nonempty bounded selected-provider model is required")
    endpoint = base + ("/messages" if provider == "anthropic" else "/chat/completions")
    return ProviderSelection(provider, model, base, endpoint)
