# Providers

Henchman-AI supports multiple LLM providers through a unified interface.

## Supported Providers

| Provider | Status | API Compatibility | Configuration Name | Notes |
|----------|--------|-------------------|-------------------|-------|
| DeepSeek (`deepseek`) | ✅ Default | OpenAI-compatible | `deepseek` | Default provider |
| Anthropic (`anthropic`) | ✅ | Native SDK | `anthropic` | Claude models via native SDK |
| Ollama (`ollama`) | ✅ | OpenAI-compatible | `ollama` | Local models, no API key required |
| OpenRouter (`openrouter`) | ✅ | OpenAI-compatible | `openrouter` | Access to hundreds of models |
| OpenAI-Compatible (`openai_compat`) | ✅ | OpenAI-compatible | `openai_compat` | Generic provider for ANY OpenAI-compatible API (OpenAI, Together, Groq, Fireworks, etc.) |
| Together AI (`together`) | ✅ | OpenAI-compatible | `together` | Alias for `openai_compat` with Together base URL |
| Groq (`groq`) | ✅ | OpenAI-compatible | `groq` | Alias for `openai_compat` with Groq base URL |
| Fireworks AI (`fireworks`) | ✅ | OpenAI-compatible | `fireworks` | Alias for `openai_compat` with Fireworks base URL |

**Note**: The `openai_compat` provider is a generic provider for any OpenAI-compatible API. Specific providers like `together`, `groq`, and `fireworks` are aliases for `openai_compat` that require you to configure the appropriate base URL (see examples below). For OpenAI specifically, use `openai_compat` with `base_url: https://api.openai.com/v1` and `api_key: ${OPENAI_API_KEY}`.

**Configuration Names**: Use these names in your `settings.yaml` file (e.g., `providers.default: deepseek`) or with the `--provider` CLI flag.

## DeepSeek (Default)

DeepSeek is the default provider, offering high-quality responses at competitive prices.

### Setup

```bash
export DEEPSEEK_API_KEY="your-api-key"
```

### Configuration

```yaml
providers:
  default: deepseek
  deepseek:
    model: deepseek-chat  # or deepseek-coder
```

### Models

- `deepseek-chat` - General purpose chat model
- `deepseek-coder` - Optimized for code generation

## OpenAI-Compatible Providers

The `openai_compat` provider works with any API that follows the OpenAI chat completions format. This includes OpenAI itself, Together AI, Groq, Fireworks AI, and other compatible services.

### OpenAI

To use OpenAI models, configure the `openai_compat` provider with OpenAI's base URL:

#### Setup

```bash
export OPENAI_API_KEY="your-api-key"
```

#### Configuration

```yaml
providers:
  default: openai_compat
  openai_compat:
    model: gpt-4
    base_url: https://api.openai.com/v1
    api_key: ${OPENAI_API_KEY}
```

#### Models

- `gpt-4` - Most capable model
- `gpt-4-turbo` - Faster, cheaper GPT-4
- `gpt-3.5-turbo` - Fast and economical

### Together AI

```yaml
providers:
  default: together
  together:
    model: meta-llama/Llama-3-70b-chat-hf
    base_url: https://api.together.xyz/v1
    api_key: ${TOGETHER_API_KEY}
```

### Groq

```yaml
providers:
  default: groq
  groq:
    model: llama3-70b-8192
    base_url: https://api.groq.com/openai/v1
    api_key: ${GROQ_API_KEY}
```

### Fireworks AI

```yaml
providers:
  default: fireworks
  fireworks:
    model: fireworks-ai/llama-v3-70b-instruct
    base_url: https://api.fireworks.ai/inference/v1
    api_key: ${FIREWORKS_API_KEY}
```

## Anthropic

### Setup

```bash
export ANTHROPIC_API_KEY="your-api-key"
```

### Configuration

```yaml
providers:
  default: anthropic
  anthropic:
    model: claude-3-opus-20240229
```

### Models

- `claude-3-opus-20240229` - Most capable
- `claude-3-sonnet-20240229` - Balanced
- `claude-3-haiku-20240307` - Fast and efficient

## Ollama (Local)

Run models locally with Ollama.

### Setup

1. Install Ollama: https://ollama.ai/
2. Pull a model: `ollama pull llama2`
3. Start the server: `ollama serve`

### Configuration

```yaml
providers:
  default: ollama
  ollama:
    model: llama2
    base_url: http://localhost:11434
```

### Models

Any model available in Ollama:

- `llama2`, `llama3`
- `codellama`
- `mistral`, `mixtral`
- `phi3`
- And many more...

## OpenRouter

Access hundreds of models through [OpenRouter](https://openrouter.ai/).

### Setup

```bash
export OPENROUTER_API_KEY="your-api-key"
```

### Configuration

```yaml
providers:
  default: openrouter
  openrouter:
    model: "anthropic/claude-3.5-sonnet"
```

### Models

OpenRouter supports hundreds of models from various providers. Refer to the [OpenRouter Model List](https://openrouter.ai/models) for specific model identifiers.

## Basic Usage

```python
from henchman.providers import DeepSeekProvider, Message

# Create provider
provider = DeepSeekProvider(
    api_key="your-key",
    model="deepseek-chat"
)

# Stream responses
async for chunk in provider.chat_completion_stream(
    messages=[Message(role="user", content="Hello!")],
):
    if chunk.content:
        print(chunk.content, end="")
```

## Provider Registry

Access providers programmatically:

```python
from henchman.providers import get_default_registry

registry = get_default_registry()

# Create provider by name
provider = registry.create(
    "deepseek",
    api_key="...",
    model="deepseek-chat"
)
```

## Switching Providers

### Via Environment Variable

```bash
HENCHMAN_PROVIDER=anthropic henchman
```

### Via Settings

```yaml
providers:
  default: anthropic
```

### At Runtime

Use the `/model` command (if implemented) or restart with different settings.
