"""Single-attempt, no-tool text provider for budgeted offline learning loops."""

from __future__ import annotations

import asyncio
import json
import math

import httpx

from .provider_config import resolve_provider


class BoundedTextProvider:
    """Never retries, falls back, health-probes, or executes model tools."""

    def __init__(self, config, transport=None):
        self.config = config
        self.transport = transport

    async def generate_response(
        self,
        *,
        prompt,
        system_prompt=None,
        max_tokens=900,
        temperature=0,
        timeout=20,
        **_,
    ):
        if type(max_tokens) is not int or not 1 <= max_tokens <= 4000:
            raise ValueError("Learning output limit is invalid")
        if (
            type(timeout) not in (int, float)
            or not math.isfinite(timeout)
            or not 0 < timeout <= 120
        ):
            raise ValueError("Learning timeout must be finite and within 120 seconds")
        if (
            type(temperature) not in (int, float)
            or not math.isfinite(temperature)
            or not 0 <= temperature <= 2
        ):
            raise ValueError("Learning temperature is invalid")
        if (
            not isinstance(prompt, str)
            or not prompt.strip()
            or (system_prompt is not None and not isinstance(system_prompt, str))
        ):
            raise ValueError("Learning prompts must be text")
        if len(prompt) + len(system_prompt or "") > 72000:
            raise ValueError("Learning input limit exceeded")
        cfg = self.config
        selected = resolve_provider(cfg)
        provider, model, url = selected.provider, selected.model, selected.endpoint
        if provider == "anthropic":
            if temperature > 1:
                raise ValueError("Anthropic learning temperature must not exceed one")
            key = cfg.anthropic_api_key
            headers = {"x-api-key": key, "anthropic-version": "2023-06-01"}
            body = {
                "model": model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "system": system_prompt or "",
                "messages": [{"role": "user", "content": prompt}],
            }
        else:
            # Resolve only the selected provider, never unrelated credentials/config.
            if provider == "zai":
                key = cfg.zai_api_key
            elif provider == "openrouter":
                key = cfg.openrouter_api_key
            elif provider == "openai":
                key = cfg.openai_api_key
            else:
                raise RuntimeError("Unsupported budgeted learning provider")
            headers = {"Authorization": f"Bearer {key}"}
            messages = (
                [{"role": "system", "content": system_prompt}] if system_prompt else []
            )
            messages.append({"role": "user", "content": prompt})
            official_openai = url == "https://api.openai.com/v1/chat/completions"
            token_field = "max_completion_tokens" if official_openai else "max_tokens"
            body = {
                "model": model,
                "messages": messages,
                token_field: max_tokens,
                "temperature": temperature,
            }
            if official_openai:
                body["store"] = False
        if not key:
            raise RuntimeError("Budgeted learning requires a configured HTTPS provider")
        try:
            async with asyncio.timeout(timeout):
                async with httpx.AsyncClient(
                    transport=self.transport,
                    timeout=timeout,
                    follow_redirects=False,
                    trust_env=False,
                ) as client:
                    async with client.stream(
                        "POST", url, headers=headers, json=body
                    ) as response:
                        response.raise_for_status()
                        chunks = bytearray()
                        async for chunk in response.aiter_bytes():
                            if len(chunks) + len(chunk) > 128000:
                                raise RuntimeError(
                                    "Learning provider response too large"
                                )
                            chunks.extend(chunk)
            payload = json.loads(chunks)
            if provider == "anthropic":
                text = "".join(
                    block["text"]
                    for block in payload["content"]
                    if block.get("type") == "text"
                )
            else:
                text = payload["choices"][0]["message"]["content"]
            if not isinstance(text, str) or not text.strip():
                raise ValueError("Empty response")
            return text
        except asyncio.CancelledError:
            raise
        except Exception:
            raise RuntimeError("Budgeted learning provider failed") from None
