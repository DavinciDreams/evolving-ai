"""
LLM interface for communicating with various language model providers.
"""

import asyncio
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Union
from enum import Enum
import openai
import anthropic
from tenacity import retry, stop_after_attempt, wait_exponential

from ..utils.config import config
from ..utils.logging import setup_logger

logger = setup_logger(__name__)


class LLMProvider(Enum):
    """Supported LLM providers."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


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
    
    def __init__(self, api_key: str, model: str = "claude-3-sonnet-20240229"):
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
            
            response = await self.client.messages.create(
                model=self.model,
                messages=messages,
                system=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )
            
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
            
            response = await self.client.messages.create(
                model=self.model,
                messages=filtered_messages,
                system=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )
            
            return response.content[0].text
            
        except Exception as e:
            logger.error(f"Anthropic API error: {e}")
            raise


class LLMManager:
    """Manager for LLM interfaces."""
    
    def __init__(self):
        self.interfaces: Dict[str, LLMInterface] = {}
        self.default_provider = config.default_llm_provider
        self._initialize_interfaces()
    
    def _initialize_interfaces(self):
        """Initialize available LLM interfaces."""
        # Initialize OpenAI
        if config.openai_api_key:
            try:
                self.interfaces["openai"] = OpenAIInterface(
                    config.openai_api_key,
                    config.default_model
                )
                logger.info("OpenAI interface initialized")
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI interface: {e}")
        
        # Initialize Anthropic
        if config.anthropic_api_key:
            try:
                self.interfaces["anthropic"] = AnthropicInterface(
                    config.anthropic_api_key,
                    "claude-3-sonnet-20240229"
                )
                logger.info("Anthropic interface initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Anthropic interface: {e}")
    
    def get_interface(self, provider: Optional[str] = None) -> LLMInterface:
        """Get LLM interface by provider."""
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


# Global LLM manager instance
llm_manager = LLMManager()
