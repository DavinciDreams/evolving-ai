"""
LLM interface for communicating with various language model providers.
"""

from abc import ABC, abstractmethod
import asyncio
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union
from datetime import datetime
from collections import defaultdict
import uuid

import anthropic
import httpx
import openai
from loguru import logger
from tenacity import RetryError, retry, stop_after_attempt, wait_exponential

from ..utils.config import config
from ..utils.logging import setup_logger
from .error_recovery import (
    error_recovery_manager,
    CircuitBreakerConfig,
    RetryConfig,
    CircuitBreakerOpenError,
    FallbackExhaustedError
)

logger = setup_logger(__name__)

# Ensure logger does not propagate to avoid duplicate logs if root logger is configured elsewhere
logger.propagate = False


class LLMProvider(Enum):
    """Supported LLM providers."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OPENROUTER = "openrouter"
    ZAI = "zai"


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


class ZAIInterface(LLMInterface):
    """Z AI API interface for GLM models."""

    def __init__(self, api_key: str, model: str = "glm-4.7"):
        self.api_key = api_key
        self.model = model
        # Z.AI Coding API endpoint (international/overseas)
        # Separate endpoint specifically for coding tasks
        self.base_url = "https://api.z.ai/api/coding/paas/v4"

    def _get_headers(self) -> Dict[str, str]:
        """Get headers for Z AI requests."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _filter_kwargs(self, kwargs: Dict) -> Dict:
        """Filter valid kwargs for Z AI API."""
        valid_keys = ["top_p", "stop", "stream"]
        return {k: v for k, v in kwargs.items() if k in valid_keys}

    def _prepare_payload(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        **kwargs,
    ) -> Dict:
        """Prepare payload for Z AI API request."""
        return {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs,
        }

    async def _make_completion_request(self, payload: Dict) -> str:
        """Make completion request to Z AI API."""
        try:
            headers = self._get_headers()
            # GLM-4.7 is a coding model - use standard chat completions endpoint
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions", headers=headers, json=payload
                )
                response.raise_for_status()
                data = response.json()
                message = data["choices"][0]["message"]
                # GLM-4.7 may return reasoning in reasoning_content with empty content
                content = message.get("content") or ""
                reasoning = message.get("reasoning_content") or ""
                return content if content else reasoning
        except Exception as e:
            logger.error(f"Z AI API error: {e}")
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
        """Generate a response using Z AI."""
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
    """Manager for LLM interfaces with intelligent error recovery."""

    def __init__(self):
        self.interfaces: Dict[str, LLMInterface] = {}
        self.default_provider = None
        self._initialized = False
        self.provider_status: Dict[str, Dict[str, Any]] = {}
        self.request_queue: Dict[str, List[Dict]] = defaultdict(list)
        self.partial_responses: Dict[str, Dict] = {}
        self.provider_priority: List[str] = ["anthropic", "openrouter", "zai", "openai"]
        self.last_health_check: Dict[str, float] = {}
        self.health_check_interval = 60.0  # seconds
        self.request_timeout = 120.0

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
        if (
            config.anthropic_api_key
            and config.anthropic_api_key != "your_anthropic_api_key_here"
        ):
            model = (
                config.default_model
                if config.default_llm_provider == "anthropic"
                else "claude-3-5-sonnet-20241022"
            )
            self._initialize_provider(
                "anthropic", AnthropicInterface, config.anthropic_api_key, model
            )

        # Initialize OpenRouter
        if (
            config.openrouter_api_key
            and config.openrouter_api_key != "your_openrouter_api_key_here"
        ):
            model = (
                config.default_model
                if config.default_llm_provider == "openrouter"
                else "anthropic/claude-3-haiku"
            )
            self._initialize_provider(
                "openrouter", OpenRouterInterface, config.openrouter_api_key, model
            )

        # Initialize Z AI
        if config.zai_api_key:
            model = (
                config.default_model
                if config.default_llm_provider == "zai"
                else "glm-4.7"
            )
            self._initialize_provider(
                "zai", ZAIInterface, config.zai_api_key, model
            )

        self._initialize_provider_status()

    def _initialize_provider_status(self):
        """Initialize provider status tracking."""
        self.provider_status = {
            provider: {
                "available": False,
                "last_error": None,
                "last_check": None,
                "consecutive_failures": 0,
                "consecutive_successes": 0,
                "average_response_time": 0.0,
                "request_count": 0,
                "circuit_breaker_state": "closed"
            }
            for provider in ["openai", "anthropic", "openrouter", "zai"]
        }
        
        # Register health checks with error recovery manager
        for provider in ["openai", "anthropic", "openrouter", "zai"]:
            error_recovery_manager.register_health_check(
                f"llm_{provider}",
                lambda p=provider: self._check_provider_health(p)
            )

    def _ensure_initialized(self):
        """Ensure interfaces are initialized with current config."""
        if not self._initialized:
            self._initialize_interfaces()
            self._initialized = True

    async def check_provider_availability(self, provider: str) -> bool:
        """Check if a provider is currently available."""
        # Check if we've recently verified this provider
        current_time = datetime.now().timestamp()
        last_check = self.last_health_check.get(provider, 0)
        
        if current_time - last_check < self.health_check_interval:
            return self.provider_status[provider]["available"]
        
        try:
            test_message = "Hello"
            response = await self.generate_response(test_message, provider=provider, timeout=30.0)
            self._update_provider_status(provider, True)
            self.last_health_check[provider] = current_time
            return True
        except Exception as e:
            self._update_provider_status(provider, False, str(e))
            self.last_health_check[provider] = current_time
            return False
    
    async def _check_provider_health(self, provider: str) -> bool:
        """Health check function for error recovery manager."""
        return await self.check_provider_availability(provider)

    def _update_provider_status(
        self, provider: str, available: bool, error: Optional[str] = None
    ):
        """Update provider status information."""
        status = self.provider_status[provider]
        status["available"] = available
        status["last_error"] = error
        status["last_check"] = asyncio.get_event_loop().time()
        
        if available:
            status["consecutive_successes"] += 1
            status["consecutive_failures"] = 0
        else:
            status["consecutive_failures"] += 1
            status["consecutive_successes"] = 0
        
        # Track error patterns
        if error:
            error_recovery_manager.track_error_pattern(
                f"llm_{provider}",
                type(Exception(error).__name__ if isinstance(error, str) else error).__name__,
                {"error": error}
            )

    async def get_available_providers(self) -> List[str]:
        """Get list of currently available providers sorted by priority."""
        available = []
        for provider in self.provider_priority:
            if provider in self.interfaces and await self.check_provider_availability(
                provider
            ):
                available.append(provider)
        return available
    
    def get_provider_health_status(self) -> Dict[str, Dict[str, Any]]:
        """Get health status of all providers."""
        return {
            provider: {
                **status,
                "circuit_breaker": error_recovery_manager.circuit_breakers.get(
                    f"llm_{provider}", {}
                ).get_state() if f"llm_{provider}" in error_recovery_manager.circuit_breakers else None
            }
            for provider, status in self.provider_status.items()
        }

    async def generate_response(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        provider: Optional[str] = None,
        timeout: Optional[float] = None,
        request_id: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Generate a response using the specified or best available provider."""
        self._ensure_initialized()
        
        # Generate request ID if not provided
        request_id = request_id or str(uuid.uuid4())
        timeout = timeout or self.request_timeout
        
        # Try specified provider first
        if provider:
            if provider not in self.interfaces:
                raise RuntimeError(f"LLM provider '{provider}' is not initialized")
            
            try:
                return await self._generate_with_recovery(
                    provider,
                    request_id,
                    prompt,
                    system_prompt,
                    temperature,
                    max_tokens,
                    timeout,
                    **kwargs
                )
            except Exception as e:
                logger.warning(f"Provider {provider} failed: {e}, trying alternatives")
                # Fall back to other providers
                return await self._generate_with_fallback(
                    provider,
                    request_id,
                    prompt,
                    system_prompt,
                    temperature,
                    max_tokens,
                    timeout,
                    **kwargs
                )
        
        # Use default provider directly if available, avoiding expensive health checks
        if self.default_provider and self.default_provider in self.interfaces:
            try:
                return await self._generate_with_recovery(
                    self.default_provider,
                    request_id,
                    prompt,
                    system_prompt,
                    temperature,
                    max_tokens,
                    timeout,
                    **kwargs
                )
            except Exception as e:
                logger.warning(f"Default provider {self.default_provider} failed: {e}, trying alternatives")

        # Fall back to intelligent provider selection
        use_provider = await self.get_best_provider()
        if not use_provider:
            raise RuntimeError("No LLM providers are currently available")
        
        try:
            return await self._generate_with_recovery(
                use_provider,
                request_id,
                prompt,
                system_prompt,
                temperature,
                max_tokens,
                timeout,
                **kwargs
            )
        except Exception as e:
            logger.warning(f"Provider {use_provider} failed: {e}, trying alternatives")
            return await self._generate_with_fallback(
                use_provider,
                request_id,
                prompt,
                system_prompt,
                temperature,
                max_tokens,
                timeout,
                **kwargs
            )
    
    async def _generate_with_recovery(
        self,
        provider: str,
        request_id: str,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int,
        timeout: float,
        **kwargs
    ) -> str:
        """Generate response with error recovery."""
        interface = self.interfaces[provider]
        
        # Store partial response data
        error_recovery_manager.store_partial_response(
            request_id,
            {
                "provider": provider,
                "prompt": prompt[:100],  # Store partial prompt
                "timestamp": datetime.now().isoformat(),
                "status": "in_progress"
            }
        )
        
        try:
            # Use error recovery manager for the request
            result = await error_recovery_manager.execute_with_recovery(
                f"llm_{provider}",
                interface.generate_response,
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )
            
            # Clear partial response on success
            error_recovery_manager.clear_partial_response(request_id)
            
            return result
        except CircuitBreakerOpenError:
            # Queue the request if circuit is open
            logger.info(f"Circuit breaker open for {provider}, queuing request")
            return await self._queue_request(
                provider,
                request_id,
                prompt,
                system_prompt,
                temperature,
                max_tokens,
                **kwargs
            )
        except Exception as e:
            # Record failure
            self._update_provider_status(provider, False, str(e))
            raise
    
    async def _generate_with_fallback(
        self,
        failed_provider: str,
        request_id: str,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int,
        timeout: float,
        **kwargs
    ) -> str:
        """Generate response with fallback to other providers."""
        available = await self.get_available_providers()
        
        # Filter out the failed provider
        available = [p for p in available if p != failed_provider]
        
        if not available:
            raise RuntimeError(f"All LLM providers failed. Original error from {failed_provider}")
        
        for provider in available:
            try:
                logger.info(f"Falling back to provider {provider}")
                return await self._generate_with_recovery(
                    provider,
                    request_id,
                    prompt,
                    system_prompt,
                    temperature,
                    max_tokens,
                    timeout,
                    **kwargs
                )
            except Exception as e:
                logger.warning(f"Fallback provider {provider} also failed: {e}")
                continue
        
        raise RuntimeError(f"All fallback providers failed")
    
    async def _queue_request(
        self,
        provider: str,
        request_id: str,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int,
        **kwargs
    ) -> str:
        """Queue a request when provider is unavailable."""
        future = asyncio.Future()
        self.request_queue[provider].append({
            "future": future,
            "request_id": request_id,
            "prompt": prompt,
            "system_prompt": system_prompt,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "kwargs": kwargs
        })
        
        # Wait for the request to be processed or timeout
        try:
            return await asyncio.wait_for(future, timeout=300.0)
        except asyncio.TimeoutError:
            raise RuntimeError(f"Request timed out waiting for provider {provider} to recover")
    
    async def process_queued_requests(self, provider: str):
        """Process queued requests when provider becomes available."""
        while self.request_queue[provider]:
            queued = self.request_queue[provider].pop(0)
            try:
                result = await self._generate_with_recovery(
                    provider,
                    queued["request_id"],
                    queued["prompt"],
                    queued["system_prompt"],
                    queued["temperature"],
                    queued["max_tokens"],
                    self.request_timeout,
                    **queued["kwargs"]
                )
                if not queued["future"].done():
                    queued["future"].set_result(result)
            except Exception as e:
                if not queued["future"].done():
                    queued["future"].set_exception(e)

    async def get_best_provider(
        self, preferred_provider: Optional[str] = None
    ) -> Optional[str]:
        """Get the best available provider based on health and performance."""
        available = await self.get_available_providers()

        if not available:
            logger.error("No LLM providers are currently available")
            return None

        if preferred_provider and preferred_provider in available:
            return preferred_provider

        # Respect the configured default provider if available
        if self.default_provider and self.default_provider in available:
            return self.default_provider

        # Score providers based on multiple factors
        provider_scores = []
        for provider in available:
            status = self.provider_status[provider]
            score = 0
            
            # Priority based on provider order
            if provider in self.provider_priority:
                score += (len(self.provider_priority) - self.provider_priority.index(provider)) * 10
            
            # Success rate bonus
            total_requests = status["consecutive_successes"] + status["consecutive_failures"]
            if total_requests > 0:
                success_rate = status["consecutive_successes"] / total_requests
                score += success_rate * 20
            
            # Penalty for recent failures
            if status["consecutive_failures"] > 0:
                score -= status["consecutive_failures"] * 5
            
            # Check circuit breaker state
            breaker = error_recovery_manager.circuit_breakers.get(f"llm_{provider}")
            if breaker and breaker.state.value == "open":
                score -= 100
            elif breaker and breaker.state.value == "half_open":
                score -= 20
            
            provider_scores.append((provider, score))
        
        # Sort by score (descending)
        provider_scores.sort(key=lambda x: x[1], reverse=True)
        
        best_provider = provider_scores[0][0]
        logger.info(f"Selected best provider: {best_provider} (score: {provider_scores[0][1]})")
        return best_provider
    
    def get_partial_response(self, request_id: str) -> Optional[Dict[str, Any]]:
        """Get partial response data for a request."""
        return error_recovery_manager.get_partial_response(request_id)

    def _log_provider_suggestions(self):
        """Log helpful suggestions based on provider status."""
        suggestions = []
        for provider, status in self.provider_status.items():
            if not status["available"]:
                suggestions.append(f"Provider {provider} is unavailable: {status.get('last_error', 'Unknown error')}")
        
        if suggestions:
            logger.warning("Provider status issues: " + "; ".join(suggestions))


llm_manager = LLMManager()
