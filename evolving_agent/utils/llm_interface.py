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
        """Generate a response from chat messages."""
        pass


class OpenAIInterface(LLMInterface):
    """OpenAI API interface."""
    
    def __init__(self, api_key: str, model: str = "gpt-4"):
        self.client = openai.AsyncOpenAI(api_key=api_key)
        self.model = model
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def generate_response(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs
    ) -> str:
        """Generate a response using OpenAI."""
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            # Filter out invalid kwargs for OpenAI API
            valid_kwargs = {k: v for k, v in kwargs.items() 
                          if k in ['stream', 'stop', 'presence_penalty', 'frequency_penalty', 'logit_bias', 'user']}
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **valid_kwargs
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def generate_chat_response(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs
    ) -> str:
        """Generate a response from chat messages."""
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
            logger.error(f"OpenAI API error: {e}")
            raise


class AnthropicInterface(LLMInterface):
    """Anthropic API interface."""
    
    def __init__(self, api_key: str, model: str = "claude-3-5-sonnet-20241022"):
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.model = model
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def generate_response(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs
    ) -> str:
        """Generate a response using Anthropic."""
        try:
            messages = [{"role": "user", "content": prompt}]
            
            # Filter out invalid kwargs for Anthropic API
            valid_kwargs = {k: v for k, v in kwargs.items() 
                          if k in ['stop_sequences', 'top_p', 'top_k']}
            
            # Only include system parameter if it's provided
            create_params = {
                'model': self.model,
                'messages': messages,
                'temperature': temperature,
                'max_tokens': max_tokens,
                **valid_kwargs
            }
            if system_prompt:
                create_params['system'] = system_prompt
            
            response = await self.client.messages.create(**create_params)
            
            return response.content[0].text
            
        except Exception as e:
            logger.error(f"Anthropic API error: {e}")
            raise
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def generate_chat_response(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs
    ) -> str:
        """Generate a response from chat messages."""
        try:
            # Convert system messages to system parameter
            system_prompt = None
            filtered_messages = []
            
            for msg in messages:
                if msg["role"] == "system":
                    system_prompt = msg["content"]
                else:
                    filtered_messages.append(msg)
            
            # Filter out invalid kwargs for Anthropic API
            valid_kwargs = {k: v for k, v in kwargs.items() 
                          if k in ['stop_sequences', 'top_p', 'top_k']}
            
            # Only include system parameter if it's not None
            create_params = {
                'model': self.model,
                'messages': filtered_messages,
                'temperature': temperature,
                'max_tokens': max_tokens,
                **valid_kwargs
            }
            if system_prompt:
                create_params['system'] = system_prompt
            
            response = await self.client.messages.create(**create_params)
            
            return response.content[0].text
            
        except Exception as e:
            logger.error(f"Anthropic API error: {e}")
            raise


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
            "X-Title": "Self-Improving AI Agent"
        }
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def generate_response(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs
    ) -> str:
        """Generate a response using OpenRouter."""
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            # Filter out invalid kwargs for OpenRouter API
            valid_kwargs = {k: v for k, v in kwargs.items() 
                          if k in ['stop', 'top_p', 'frequency_penalty', 'presence_penalty', 'stream']}
            
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                **valid_kwargs
            }
            
            # Get fresh headers for each request
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
            logger.error(f"OpenRouter API error: {e}")
            raise
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def generate_chat_response(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs
    ) -> str:
        """Generate a response from chat messages."""
        try:
            # Filter out invalid kwargs for OpenRouter API
            valid_kwargs = {k: v for k, v in kwargs.items() 
                          if k in ['stop', 'top_p', 'frequency_penalty', 'presence_penalty', 'stream']}
            
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                **valid_kwargs
            }
            
            # Get fresh headers for each request
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
            logger.error(f"OpenRouter API error: {e}")
            raise


class LLMManager:
    """Manager for LLM interfaces."""
    
    def __init__(self):
        self.interfaces: Dict[str, LLMInterface] = {}
        self.default_provider = None
        self._initialized = False
        self.provider_status: Dict[str, Dict[str, Any]] = {}
        
    def _ensure_initialized(self):
        """Ensure interfaces are initialized with current config."""
        if not self._initialized:
            self._initialize_interfaces()
            self._initialized = True
    
    def _initialize_interfaces(self):
        """Initialize available LLM interfaces."""
        self.default_provider = config.default_llm_provider
        
        # Initialize OpenAI only if API key is properly configured (not placeholder)
        if config.openai_api_key and config.openai_api_key != "your_openai_api_key_here":
            try:
                self.interfaces["openai"] = OpenAIInterface(
                    config.openai_api_key,
                    config.default_model if config.default_llm_provider == "openai" else "gpt-4"
                )
                logger.info("OpenAI interface initialized")
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI interface: {e}")
        else:
            logger.info("OpenAI interface skipped - API key not configured")
        
        # Initialize Anthropic (Claude) - prioritized
        if config.anthropic_api_key:
            try:
                self.interfaces["anthropic"] = AnthropicInterface(
                    config.anthropic_api_key,
                    config.default_model if config.default_llm_provider == "anthropic" else "claude-3-5-sonnet-20241022"
                )
                logger.info("Anthropic (Claude) interface initialized - PRIMARY PROVIDER")
            except Exception as e:
                logger.error(f"Failed to initialize Anthropic interface: {e}")
        
        # Initialize OpenRouter as backup
        if config.openrouter_api_key:
            try:
                # Use a working model that we verified
                model = config.default_model if config.default_llm_provider == "openrouter" else "anthropic/claude-3-haiku"
                self.interfaces["openrouter"] = OpenRouterInterface(
                    config.openrouter_api_key,
                    model
                )
                logger.info("OpenRouter interface initialized - BACKUP PROVIDER")
            except Exception as e:
                logger.error(f"Failed to initialize OpenRouter interface: {e}")
        
        # Initialize provider status tracking
        self.provider_status = {
            'openai': {'available': False, 'last_error': None, 'last_check': None},
            'anthropic': {'available': False, 'last_error': None, 'last_check': None},
            'openrouter': {'available': False, 'last_error': None, 'last_check': None}
        }
    
    async def check_provider_availability(self, provider: str) -> bool:
        """Check if a provider is currently available."""
        try:
            test_message = "Hello"
            # Call generate_response without max_retries parameter
            response = await self.generate_response(test_message, provider=provider)
            self.provider_status[provider]['available'] = True
            self.provider_status[provider]['last_error'] = None
            return True
        except Exception as e:
            self.provider_status[provider]['available'] = False
            self.provider_status[provider]['last_error'] = str(e)
            logger.warning(f"Provider {provider} unavailable: {str(e)}")
            return False
    
    async def get_available_providers(self) -> List[str]:
        """Get list of currently available providers."""
        available = []
        # Check providers in priority order: anthropic -> openrouter -> openai
        for provider in ['anthropic', 'openrouter', 'openai']:
            if provider in self.interfaces:
                if await self.check_provider_availability(provider):
                    available.append(provider)
        return available
    
    async def get_best_provider(self, preferred_provider: Optional[str] = None) -> Optional[str]:
        """Get the best available provider, optionally preferring one."""
        available = await self.get_available_providers()
        
        if not available:
            logger.error("No LLM providers are currently available")
            return None
        
        # Try preferred provider first
        if preferred_provider and preferred_provider in available:
            return preferred_provider
        
        # Prioritize Claude (Anthropic) first, then fallback to OpenRouter, skip OpenAI
        fallback_order = ['anthropic', 'openrouter', 'openai']
        for provider in fallback_order:
            if provider in available:
                if provider != 'openai':  # Skip OpenAI unless it's the only option
                    logger.info(f"Using provider: {provider}")
                    return provider
        
        # Only use OpenAI if it's the absolute last resort
        if 'openai' in available and len(available) == 1:
            logger.warning("Using OpenAI as last resort - consider setting up Claude/Anthropic")
            return 'openai'
        
        # Return first available if no preferred order matches
        return available[0]
    
    async def generate_response_with_fallback(
        self,
        message: str,
        system_prompt: Optional[str] = None,
        preferred_provider: Optional[str] = None,
        **kwargs
    ) -> Tuple[Optional[str], Optional[str]]:
        """Generate response with automatic provider fallback."""
        provider = await self.get_best_provider(preferred_provider)
        
        if not provider:
            error_msg = "No LLM providers are currently available. Please check your API keys and credits."
            logger.error(error_msg)
            self._log_provider_status()
            return None, error_msg
        
        try:
            response = await self.generate_response(
                prompt=message,
                system_prompt=system_prompt,
                provider=provider,
                **kwargs
            )
            return response, None
        except Exception as e:
            logger.error(f"Failed to generate response with provider {provider}: {str(e)}")
            return None, str(e)
    
    def _log_provider_status(self):
        """Log the current status of all providers."""
        logger.info("=== Provider Status ===")
        for provider, status in self.provider_status.items():
            if status['available']:
                logger.info(f"✓ {provider}: Available")
            else:
                error = status.get('last_error', 'Unknown error')
                logger.error(f"❌ {provider}: {error}")
        
        # Provide helpful suggestions
        suggestions = []
        if not self.provider_status['anthropic']['available']:
            error_str = str(self.provider_status['anthropic'].get('last_error', ''))
            if 'credit balance' in error_str:
                suggestions.append("• Add credits to your Anthropic account at https://console.anthropic.com/")
            elif 'system' in error_str:
                suggestions.append("• Anthropic API format issue - checking latest code...")
            else:
                suggestions.append("• Check your Anthropic (Claude) API key and account status - PRIMARY PROVIDER")
        
        if not self.provider_status['openrouter']['available']:
            error_str = str(self.provider_status['openrouter'].get('last_error', ''))
            if '429' in error_str:
                suggestions.append("• Wait for OpenRouter rate limit reset (daily limit: 50 requests)")
            else:
                suggestions.append("• Check your OpenRouter account and API key - BACKUP PROVIDER")
        
        if not self.provider_status['openai']['available'] and 'openai' in self.interfaces:
            error_str = str(self.provider_status['openai'].get('last_error', ''))
            if 'invalid_api_key' in error_str or 'Incorrect API key' in error_str:
                suggestions.append("• OpenAI API key invalid - intentionally disabled, using Claude instead")
            else:
                suggestions.append("• OpenAI disabled by design - using Claude (Anthropic) as primary")
        
        if suggestions:
            logger.info("💡 Suggestions:")
            for suggestion in suggestions:
                logger.info(suggestion)

    def get_interface(self, provider: Optional[str] = None) -> LLMInterface:
        """Get LLM interface by provider."""
        self._ensure_initialized()
        provider = provider or self.default_provider
        
        if provider not in self.interfaces:
            raise ValueError(f"Provider {provider} not available")
        
        return self.interfaces[provider]
    
    async def generate_response(
        self,
        prompt: str,
        provider: Optional[str] = None,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> str:
        """Generate a response using the specified provider."""
        interface = self.get_interface(provider)
        
        return await interface.generate_response(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature or config.temperature,
            max_tokens=max_tokens or config.max_tokens,
            **kwargs
        )
    
    async def generate_chat_response(
        self,
        messages: List[Dict[str, str]],
        provider: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> str:
        """Generate a chat response using the specified provider."""
        interface = self.get_interface(provider)
        
        return await interface.generate_chat_response(
            messages=messages,
            temperature=temperature or config.temperature,
            max_tokens=max_tokens or config.max_tokens,
            **kwargs
        )
    
    def refresh_interfaces(self):
        """Refresh all interfaces with current configuration."""
        self.interfaces.clear()
        self._initialized = False
        
        # Force reload the .env file to pick up any changes
        from dotenv import load_dotenv
        load_dotenv(override=True)
        
        # Force reload the config module
        import importlib
        from ..utils import config as config_module
        importlib.reload(config_module)
        global config
        config = config_module.config
        
        self._ensure_initialized()
        logger.info("LLM interfaces refreshed with current configuration")


# Global LLM manager instance
llm_manager = LLMManager()
