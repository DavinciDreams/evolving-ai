"""
LLM interface for communicating with various language model providers.
"""

import asyncio
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Union, Tuple
from enum import Enum
import openai
import anthropic
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, RetryError
from loguru import logger

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
        **kwargs
    ) -> str:
        """Generate a response from the LLM."""
        pass
    
    @abstractmethod
    async def generate_chat_response(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs
    ) -> str:
        """Generate a chat response."""
        pass


class BaseInterface:
    """Base class with common interface functionality."""
    
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    def _filter_kwargs(self, kwargs: Dict, valid_keys: List[str]) -> Dict:
        """Filter kwargs based on valid keys."""
        return {k: v for k, v in kwargs.items() if k in valid_keys}

    async def _handle_api_error(self, error: Exception, api_name: str):
        """Handle API errors consistently."""
        logger.error(f"{api_name} API error: {error}")
        raise


class OpenAIInterface(BaseInterface, LLMInterface):
    """OpenAI API interface."""
    
    def __init__(self, api_key: str, model: str = "gpt-4"):
        super().__init__(api_key, model)
        self.client = openai.AsyncOpenAI(api_key=api_key)
        self.valid_keys = ['stream', 'stop', 'presence_penalty', 'frequency_penalty', 'logit_bias', 'user']

    def _prepare_messages(self, prompt: str, system_prompt: Optional[str] = None) -> List[Dict[str, str]]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return messages

    async def _make_completion_request(self, messages: List[Dict[str, str]], temperature: float, max_tokens: int, **kwargs) -> str:
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )
            return response.choices[0].message.content
        except Exception as e:
            await self._handle_api_error(e, "OpenAI")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def generate_response(self, prompt: str, system_prompt: Optional[str] = None,
                              temperature: float = 0.7, max_tokens: int = 2048, **kwargs) -> str:
        messages = self._prepare_messages(prompt, system_prompt)
        valid_kwargs = self._filter_kwargs(kwargs, self.valid_keys)
        return await self._make_completion_request(messages, temperature, max_tokens, **valid_kwargs)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def generate_chat_response(self, messages: List[Dict[str, str]],
                                   temperature: float = 0.7, max_tokens: int = 2048, **kwargs) -> str:
        valid_kwargs = self._filter_kwargs(kwargs, self.valid_keys)
        return await self._make_completion_request(messages, temperature, max_tokens, **valid_kwargs)


class AnthropicInterface(BaseInterface, LLMInterface):
    """Anthropic API interface."""
    
    def __init__(self, api_key: str, model: str = "claude-3-5-sonnet-20241022"):
        super().__init__(api_key, model)
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.valid_keys = ['stop_sequences', 'top_p', 'top_k']

    def _prepare_create_params(self, messages: List[Dict[str, str]], system_prompt: Optional[str],
                             temperature: float, max_tokens: int, **kwargs) -> Dict:
        create_params = {
            'model': self.model,
            'messages': messages,
            'temperature': temperature,
            'max_tokens': max_tokens,
            **kwargs
        }
        if system_prompt:
            create_params['system'] = system_prompt
        return create_params

    async def _make_completion_request(self, create_params: Dict) -> str:
        try:
            response = await self.client.messages.create(**create_params)
            return response.content[0].text
        except Exception as e:
            await self._handle_api_error(e, "Anthropic")

    def _extract_system_prompt(self, messages: List[Dict[str, str]]) -> Tuple[Optional[str], List[Dict[str, str]]]:
        system_prompt = None
        filtered_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_prompt = msg["content"]
            else:
                filtered_messages.append(msg)
        return system_prompt, filtered_messages

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def generate_response(self, prompt: str, system_prompt: Optional[str] = None,
                              temperature: float = 0.7, max_tokens: int = 2048, **kwargs) -> str:
        messages = [{"role": "user", "content": prompt}]
        valid_kwargs = self._filter_kwargs(kwargs, self.valid_keys)
        create_params = self._prepare_create_params(messages, system_prompt, temperature, max_tokens, **valid_kwargs)
        return await self._make_completion_request(create_params)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def generate_chat_response(self, messages: List[Dict[str, str]],
                                   temperature: float = 0.7, max_tokens: int = 2048, **kwargs) -> str:
        system_prompt, filtered_messages = self._extract_system_prompt(messages)
        valid_kwargs = self._filter_kwargs(kwargs, self.valid_keys)
        create_params = self._prepare_create_params(filtered_messages, system_prompt, temperature, max_tokens, **valid_kwargs)
        return await self._make_completion_request(create_params)


class OpenRouterInterface(BaseInterface, LLMInterface):
    """OpenRouter API interface for accessing multiple LLM providers."""
    
    def __init__(self, api_key: str, model: str = "anthropic/claude-3.5-sonnet"):
        super().__init__(api_key, model)
        self.base_url = "https://openrouter.ai/api/v1"
        self.valid_keys = ['stop', 'top_p', 'frequency_penalty', 'presence_penalty', 'stream']

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/DavinciDreams/evolving-ai",
            "X-Title": "Self-Improving AI Agent"
        }

    def _prepare_payload(self, messages: List[Dict[str, str]], temperature: float, max_tokens: int, **kwargs) -> Dict:
        return {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs
        }

    async def _make_completion_request(self, payload: Dict) -> str:
        try:
            headers = self._get_headers()
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]
        except Exception as e:
            await self._handle_api_error(e, "OpenRouter")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def generate_response(self, prompt: str, system_prompt: Optional[str] = None,
                              temperature: float = 0.7, max_tokens: int = 2048, **kwargs) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        valid_kwargs = self._filter_kwargs(kwargs, self.valid_keys)
        payload = self._prepare_payload(messages, temperature, max_tokens, **valid_kwargs)
        return await self._make_completion_request(payload)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def generate_chat_response(self, messages: List[Dict[str, str]],
                                   temperature: float = 0.7, max_tokens: int = 2048, **kwargs) -> str:
        valid_kwargs = self._filter_kwargs(kwargs, self.valid_keys)
        payload = self._prepare_payload(messages, temperature, max_tokens, **valid_kwargs)
        return await self._make_completion_request(payload)


class ProviderManager:
    """Handles provider initialization and status tracking."""
    
    def __init__(self):
        self.provider_status = {
            provider: {'available': False, 'last_error': None, 'last_check': None}
            for provider in ['openai', 'anthropic', 'openrouter']
        }

    def initialize_provider(self, provider: str, interface_class: type, api_key: str, model: str) -> Optional[LLMInterface]:
        try:
            interface = interface_class(api_key, model)
            logger.info(f"{provider.capitalize()} interface initialized")
            return interface
        except Exception as e:
            logger.error(f"Failed to initialize {provider} interface: {e}")
            return None

    def update_status(self, provider: str, available: bool, error: Optional[str] = None):
        self.provider_status[provider].update({
            'available': available,
            'last_error': error,
            'last_check': asyncio.get_event_loop().time()
        })


class LLMManager:
    """Manager for LLM interfaces."""
    
    def __init__(self):
        self.interfaces: Dict[str, LLMInterface] = {}
        self.default_provider = None
        self._initialized = False
        self.provider_manager = ProviderManager()

    def _initialize_interfaces(self):
        """Initialize available LLM interfaces."""
        self.default_provider = config.default_llm_provider
        
        provider_configs = [
            ('openai', OpenAIInterface, config.openai_api_key, 
             "gpt-4" if config.default_llm_provider != "openai" else config.default_model),
            ('anthropic', AnthropicInterface, config.anthropic_api_key,
             "claude-3-5-sonnet-20241022" if config.default_llm_provider != "anthropic" else config.default_model),
            ('openrouter', OpenRouterInterface, config.openrouter_api_key,
             "anthropic/claude-3-haiku" if config.default_llm_provider != "openrouter" else config.default_model)
        ]

        for provider, interface_class, api_key, model in provider_configs:
            if api_key and api_key != "your_openai_api_key_here":
                interface = self.provider_manager.initialize_provider(provider, interface_class, api_key, model)
                if interface:
                    self.interfaces[provider] = interface

    def _ensure_initialized(self):
        if not self._initialized:
            self._initialize_interfaces()
            self._initialized = True

    async def check_provider_availability(self, provider: str) -> bool:
        try:
            test_message = "Hello"
            response = await self.generate_response(test_message, provider=provider)
            self.provider_manager.update_status(provider, True)
            return True
        except Exception as e:
            self.provider_manager.update_status(provider, False, str(e))
            return False

    async def get_available_providers(self) -> List[str]:
        return [p for p in self.interfaces if await self.check_provider_availability(p)]

    async def get_best_provider(self, preferred_provider: Optional[str] = None) -> Optional[str]:
        available = await self.get_available_providers()
        
        if not available:
            logger.error("No LLM providers are currently available")
            return None
        
        if preferred_provider and preferred_provider in available:
            return preferred_provider
        
        provider_priority = ['anthropic', 'openrouter', 'openai']
        for provider in provider_priority:
            if provider in available:
                logger.info(f"Using provider: {provider}")
                return provider
        
        return available[0]

    async def generate_response(self, prompt: str, provider: Optional[str] = None, **kwargs) -> str:
        self._ensure_initialized()
        provider = await self.get_best_provider(provider)
        if not provider:
            raise RuntimeError("No available LLM providers")
        return await self.interfaces[provider].generate_response(prompt, **kwargs)

    async def generate_chat_response(self, messages: List[Dict[str, str]], provider: Optional[str] = None, **kwargs) -> str:
        self._ensure_initialized()
        provider = await self.get_best_provider(provider)
        if not provider:
            raise RuntimeError("No available LLM providers")
        return await self.interfaces[provider].generate_chat_response(messages, **kwargs)


llm_manager = LLMManager()