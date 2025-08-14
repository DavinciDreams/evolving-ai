"""
LLM interface for communicating with various language model providers.
"""

import asyncio
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

import anthropic
import httpx
import openai
from loguru import logger
from tenacity import RetryError, retry, stop_after_attempt, wait_exponential

from ..utils.config import config
from ..utils.logging import setup_logger

logger = setup_logger(__name__)


class LLMProvider(Enum):
    """Supported LLM providers."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OPENROUTER = "openrouter"


class LLMInterface(ABC):
    """Abstract base class for LLM interfaces."""

    @abstractmethod
    async def generate_response(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs,
    ) -> str:
        """Generate a response from the LLM."""
        pass

    @abstractmethod
    async def generate_chat_response(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs,
    ) -> str:
        """Generate a chat response."""
        pass


class OpenAIInterface(LLMInterface):
    """OpenAI API interface."""

    def __init__(self, api_key: str, model: str = "gpt-4"):
        self.client = openai.AsyncOpenAI(api_key=api_key)
        self.model = model

    def _prepare_messages(
        self, prompt: str, system_prompt: Optional[str] = None
    ) -> List[Dict[str, str]]:
        """Prepare messages list for OpenAI API."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return messages

    def _filter_kwargs(self, kwargs: Dict) -> Dict:
        """Filter valid kwargs for OpenAI API."""
        valid_keys = [
            "stream",
            "stop",
            "presence_penalty",
            "frequency_penalty",
            "logit_bias",
            "user",
        ]
        return {k: v for k, v in kwargs.items() if k in valid_keys}

    async def _make_completion_request(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        **kwargs,
    ) -> str:
        """Make completion request to OpenAI API."""
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise

    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def generate_response(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs,
    ) -> str:
        """Generate a response using OpenAI."""
        messages = self._prepare_messages(prompt, system_prompt)
        valid_kwargs = self._filter_kwargs(kwargs)
        return await self._make_completion_request(
            messages, temperature, max_tokens, **valid_kwargs
        )

    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def generate_chat_response(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs,
    ) -> str:
        """Generate a response from chat messages."""
        valid_kwargs = self._filter_kwargs(kwargs)
        return await self._make_completion_request(
            messages, temperature, max_tokens, **valid_kwargs
        )


class AnthropicInterface(LLMInterface):
    """Anthropic API interface."""

    def __init__(self, api_key: str, model: str = "claude-3-5-sonnet-20241022"):
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.model = model

    def _filter_kwargs(self, kwargs: Dict) -> Dict:
        """Filter valid kwargs for Anthropic API."""
        valid_keys = ["stop_sequences", "top_p", "top_k"]
        return {k: v for k, v in kwargs.items() if k in valid_keys}

    def _prepare_create_params(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int,
        **kwargs,
    ) -> Dict:
        """Prepare parameters for Anthropic API request."""
        create_params = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs,
        }
        if system_prompt:
            create_params["system"] = system_prompt
        return create_params

    async def _make_completion_request(self, create_params: Dict) -> str:
        """Make completion request to Anthropic API."""
        try:
            response = await self.client.messages.create(**create_params)
            return response.content[0].text
        except Exception as e:
            logger.error(f"Anthropic API error: {e}")
            raise

    def _extract_system_prompt(
        self, messages: List[Dict[str, str]]
    ) -> Tuple[Optional[str], List[Dict[str, str]]]:
        """Extract system prompt from messages and return filtered messages."""
        system_prompt = None
        filtered_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_prompt = msg["content"]
            else:
                filtered_messages.append(msg)
        return system_prompt, filtered_messages

    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def generate_response(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs,
    ) -> str:
        """Generate a response using Anthropic."""
        messages = [{"role": "user", "content": prompt}]
        valid_kwargs = self._filter_kwargs(kwargs)
        create_params = self._prepare_create_params(
            messages, system_prompt, temperature, max_tokens, **valid_kwargs
        )
        return await self._make_completion_request(create_params)

    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def generate_chat_response(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs,
    ) -> str:
        """Generate a response from chat messages."""
        system_prompt, filtered_messages = self._extract_system_prompt(messages)
        valid_kwargs = self._filter_kwargs(kwargs)
        create_params = self._prepare_create_params(
            filtered_messages, system_prompt, temperature, max_tokens, **valid_kwargs
        )
        return await self._make_completion_request(create_params)


class OpenRouterInterface(LLMInterface):
    """OpenRouter API interface for accessing multiple LLM providers."""

    def __init__(self, api_key: str, model: str = "anthropic/claude-3.5-sonnet"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://openrouter.ai/api/v1"

    def _get_headers(self) -> Dict[str, str]:
        """Get fresh headers for each request."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/DavinciDreams/evolving-ai",
            "X-Title": "Self-Improving AI Agent",
        }

    def _filter_kwargs(self, kwargs: Dict) -> Dict:
        """Filter valid kwargs for OpenRouter API."""
        valid_keys = [
            "stop",
            "top_p",
            "frequency_penalty",
            "presence_penalty",
            "stream",
        ]
        return {k: v for k, v in kwargs.items() if k in valid_keys}

    def _prepare_payload(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        **kwargs,
    ) -> Dict:
        """Prepare payload for OpenRouter API request."""
        return {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs,
        }

    async def _make_completion_request(self, payload: Dict) -> str:
        """Make completion request to OpenRouter API."""
        try:
            headers = self._get_headers()
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions", headers=headers, json=payload
                )
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"OpenRouter API error: {e}")
            raise

    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def generate_response(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs,
    ) -> str:
        """Generate a response using OpenRouter."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        valid_kwargs = self._filter_kwargs(kwargs)
        payload = self._prepare_payload(
            messages, temperature, max_tokens, **valid_kwargs
        )
        return await self._make_completion_request(payload)

    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def generate_chat_response(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs,
    ) -> str:
        """Generate a response from chat messages."""
        valid_kwargs = self._filter_kwargs(kwargs)
        payload = self._prepare_payload(
            messages, temperature, max_tokens, **valid_kwargs
        )
        return await self._make_completion_request(payload)


class LLMManager:
    """Manager for LLM interfaces."""

    def __init__(self):
        self.interfaces: Dict[str, LLMInterface] = {}
        self.default_provider = None
        self._initialized = False
        self.provider_status: Dict[str, Dict[str, Any]] = {}

    def _initialize_provider(
        self, provider: str, interface_class: type, api_key: str, model: str
    ) -> None:
        """Initialize a single provider interface."""
        try:
            self.interfaces[provider] = interface_class(api_key, model)
            logger.info(f"{provider.capitalize()} interface initialized")
        except Exception as e:
            logger.error(f"Failed to initialize {provider} interface: {e}")

    def _initialize_interfaces(self):
        """Initialize available LLM interfaces."""
        self.default_provider = config.default_llm_provider

        # Initialize OpenAI
        if (
            config.openai_api_key
            and config.openai_api_key != "your_openai_api_key_here"
        ):
            model = (
                config.default_model
                if config.default_llm_provider == "openai"
                else "gpt-4"
            )
            self._initialize_provider(
                "openai", OpenAIInterface, config.openai_api_key, model
            )

        # Initialize Anthropic
        if config.anthropic_api_key:
            model = (
                config.default_model
                if config.default_llm_provider == "anthropic"
                else "claude-3-5-sonnet-20241022"
            )
            self._initialize_provider(
                "anthropic", AnthropicInterface, config.anthropic_api_key, model
            )

        # Initialize OpenRouter
        if config.openrouter_api_key:
            model = (
                config.default_model
                if config.default_llm_provider == "openrouter"
                else "anthropic/claude-3-haiku"
            )
            self._initialize_provider(
                "openrouter", OpenRouterInterface, config.openrouter_api_key, model
            )

        self._initialize_provider_status()

    def _initialize_provider_status(self):
        """Initialize provider status tracking."""
        self.provider_status = {
            provider: {"available": False, "last_error": None, "last_check": None}
            for provider in ["openai", "anthropic", "openrouter"]
        }

    def _ensure_initialized(self):
        """Ensure interfaces are initialized with current config."""
        if not self._initialized:
            self._initialize_interfaces()
            self._initialized = True

    async def check_provider_availability(self, provider: str) -> bool:
        """Check if a provider is currently available."""
        try:
            test_message = "Hello"
            response = await self.generate_response(test_message, provider=provider)
            self._update_provider_status(provider, True)
            return True
        except Exception as e:
            self._update_provider_status(provider, False, str(e))
            return False

    def _update_provider_status(
        self, provider: str, available: bool, error: Optional[str] = None
    ):
        """Update provider status information."""
        self.provider_status[provider].update(
            {
                "available": available,
                "last_error": error,
                "last_check": asyncio.get_event_loop().time(),
            }
        )

    async def get_available_providers(self) -> List[str]:
        """Get list of currently available providers."""
        available = []
        for provider in ["anthropic", "openrouter", "openai"]:
            if provider in self.interfaces and await self.check_provider_availability(
                provider
            ):
                available.append(provider)
        return available

    async def get_best_provider(
        self, preferred_provider: Optional[str] = None
    ) -> Optional[str]:
        """Get the best available provider, optionally preferring one."""
        available = await self.get_available_providers()

        if not available:
            logger.error("No LLM providers are currently available")
            return None

        if preferred_provider and preferred_provider in available:
            return preferred_provider

        for provider in ["anthropic", "openrouter", "openai"]:
            if provider in available and provider != "openai":
                logger.info(f"Using provider: {provider}")
                return provider

        if "openai" in available and len(available) == 1:
            logger.warning("Using OpenAI as last resort")
            return "openai"

        return available[0]

    def _log_provider_suggestions(self):
        """Log helpful suggestions based on provider status."""
        suggestions = []
        for provider, status in self.provider_status.items():
            if not status["available"]:
                error_str


llm_manager = LLMManager()
