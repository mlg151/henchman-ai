# Providers

Henchman-AI supports multiple LLM providers through a unified interface.

## Supported Providers

| Provider | Status | API Compatibility |
|----------|--------|-------------------|
| DeepSeek | ✅ Default | OpenAI-compatible |
| OpenAI | ✅ | Native |
| Anthropic | ✅ | Native |
| Ollama | ✅ | OpenAI-compatible |
| Together | ✅ | OpenAI-compatible |
| Groq | ✅ | OpenAI-compatible |

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

## OpenAI

### Setup

```bash
export OPENAI_API_KEY="your-api-key"
```

### Configuration

```yaml
providers:
  default: openai
  openai:
    model: gpt-4
```

### Models

- `gpt-4` - Most capable model
- `gpt-4-turbo` - Faster, cheaper GPT-4
- `gpt-3.5-turbo` - Fast and economical

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

## OpenAI-Compatible Providers

Many providers use the OpenAI-compatible API format.

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

## Programmatic Usage

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
