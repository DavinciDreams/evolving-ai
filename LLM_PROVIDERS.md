# LLM Provider Guide

This document explains how to configure and use different LLM providers with the Self-Improving AI Agent.

## Supported Providers

### 1. Anthropic (Default)
**Claude models with advanced reasoning capabilities**

- **Setup**: Add your Anthropic API key to `.env`
- **API Key**: `ANTHROPIC_API_KEY=your_anthropic_key_here`
- **Default Model**: `claude-3-5-sonnet-20241022`
- **Best For**: General conversation, code analysis, reasoning tasks

**Available Models:**
- `claude-3-5-sonnet-20241022` (Recommended)
- `claude-3-5-haiku-20241022` (Faster, lower cost)
- `claude-3-opus-20240229` (Most capable, higher cost)

### 2. OpenAI
**GPT models from OpenAI**

- **Setup**: Add your OpenAI API key to `.env`
- **API Key**: `OPENAI_API_KEY=your_openai_key_here`
- **Default Model**: `gpt-4`
- **Best For**: Creative tasks, broad knowledge

**Available Models:**
- `gpt-4-turbo` (Latest GPT-4)
- `gpt-4` (Stable GPT-4)
- `gpt-3.5-turbo` (Faster, lower cost)

### 3. OpenRouter
**Access to multiple LLM providers through a single API**

- **Setup**: Add your OpenRouter API key to `.env`
- **API Key**: `OPENROUTER_API_KEY=your_openrouter_key_here`
- **Default Model**: `anthropic/claude-3.5-sonnet`
- **Best For**: Model variety, cost optimization, fallback provider

**Popular Models via OpenRouter:**
- `anthropic/claude-3.5-sonnet` (Anthropic via OpenRouter)
- `openai/gpt-4-turbo` (OpenAI via OpenRouter)
- `google/gemini-pro` (Google's Gemini)
- `meta-llama/llama-3.1-70b-instruct` (Meta's Llama)
- `mistralai/mistral-7b-instruct` (Mistral AI)
- `cohere/command-r-plus` (Cohere)

## Configuration

### Environment Variables

```bash
# Primary providers (recommended to have at least one)
ANTHROPIC_API_KEY=your_anthropic_key_here
OPENAI_API_KEY=your_openai_key_here
OPENROUTER_API_KEY=your_openrouter_key_here

# Default provider configuration
DEFAULT_LLM_PROVIDER=anthropic
DEFAULT_MODEL=claude-3-5-sonnet-20241022
EVALUATION_MODEL=claude-3-5-sonnet-20241022
```

### Switching Providers

You can change the default provider by updating your `.env` file:

```bash
# Use OpenAI as default
DEFAULT_LLM_PROVIDER=openai
DEFAULT_MODEL=gpt-4-turbo

# Use OpenRouter as default
DEFAULT_LLM_PROVIDER=openrouter
DEFAULT_MODEL=anthropic/claude-3.5-sonnet
```

### Runtime Provider Selection

You can also specify the provider at runtime:

```python
from evolving_agent.utils.llm_interface import llm_manager

# Use specific provider for a single request
response = await llm_manager.generate_response(
    prompt="Hello, world!",
    provider="openai"  # or "anthropic", "openrouter"
)

# Use different models
response = await llm_manager.generate_response(
    prompt="Analyze this code",
    provider="openrouter",
    model="google/gemini-pro"
)
```

## Cost Optimization

### Provider Cost Comparison (Approximate)
1. **OpenRouter**: Often cheapest, especially for alternative models
2. **Anthropic**: Mid-range pricing, excellent quality
3. **OpenAI**: Higher cost, but reliable performance

### Model Selection Tips
- **Development/Testing**: Use smaller models (Claude Haiku, GPT-3.5-turbo)
- **Production**: Use larger models (Claude Sonnet, GPT-4)
- **Bulk Processing**: Consider OpenRouter's alternative models
- **Cost-Critical**: Use OpenRouter with smaller open-source models

## Getting API Keys

### Anthropic
1. Visit [console.anthropic.com](https://console.anthropic.com)
2. Create an account and verify email
3. Add payment method
4. Generate API key in the dashboard

### OpenAI
1. Visit [platform.openai.com](https://platform.openai.com)
2. Create account and verify phone number
3. Add payment method
4. Generate API key in API keys section

### OpenRouter
1. Visit [openrouter.ai](https://openrouter.ai)
2. Sign up with GitHub or email
3. Add credits to your account
4. Generate API key in the keys section

## Provider-Specific Features

### Anthropic Claude
- **Strengths**: Code analysis, reasoning, long context windows
- **Context Length**: Up to 200K tokens
- **Safety**: Built-in safety features
- **Best Use Cases**: Complex reasoning, code review, long document analysis

### OpenAI GPT
- **Strengths**: Creative writing, broad knowledge, plugin ecosystem
- **Context Length**: Up to 128K tokens (GPT-4 Turbo)
- **Features**: Function calling, vision (GPT-4V)
- **Best Use Cases**: Content generation, general chat, creative tasks

### OpenRouter
- **Strengths**: Model variety, cost flexibility, no vendor lock-in
- **Models**: 100+ models from different providers
- **Features**: Model routing, cost optimization
- **Best Use Cases**: Experimentation, cost optimization, model comparison

## Troubleshooting

### Common Issues

1. **API Key Not Working**
   - Verify key is correct and has sufficient credits
   - Check if key has proper permissions
   - Ensure key is in the correct `.env` file

2. **Rate Limiting**
   - Anthropic: 5 requests/minute (free), higher for paid
   - OpenAI: Varies by plan and model
   - OpenRouter: Varies by underlying provider

3. **Model Not Available**
   - Check if model name is correct
   - Verify your API key has access to the model
   - Some models require special access approval

### Testing Configuration

Run the test script to verify your setup:

```bash
python test_llm_config.py
```

This will show:
- Available providers
- API key status
- Default configuration
- Interface initialization status

## Best Practices

1. **Multiple Providers**: Configure multiple providers for redundancy
2. **Model Selection**: Choose models based on task complexity and cost requirements
3. **Error Handling**: The system automatically retries failed requests
4. **Monitoring**: Watch your API usage and costs
5. **Security**: Never commit API keys to version control

## Advanced Configuration

### Custom Models

You can use custom models by updating the configuration:

```python
# For OpenRouter with a specific model
llm_manager.interfaces["openrouter"].model = "custom/model-name"

# For direct provider integration
llm_manager.interfaces["anthropic"].model = "claude-3-opus-20240229"
```

### Provider Fallbacks

The system can be configured to fall back to different providers:

```python
async def generate_with_fallback(prompt: str):
    providers = ["anthropic", "openai", "openrouter"]
    
    for provider in providers:
        try:
            return await llm_manager.generate_response(
                prompt=prompt,
                provider=provider
            )
        except Exception as e:
            logger.warning(f"Provider {provider} failed: {e}")
            continue
    
    raise Exception("All providers failed")
```

This ensures your agent continues working even if one provider is down.
