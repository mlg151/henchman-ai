# Getting Started

## Prerequisites

- **Python 3.10 or higher**: Henchman-AI requires Python 3.10+
- **API Key**: For your chosen LLM provider (DeepSeek, OpenAI, Anthropic, etc.)
- **Git** (optional): For installing from source
- **uv** (optional): For faster dependency management

## Installation

### From PyPI (Recommended)

```bash
pip install henchman-ai
```

### From Source

```bash
git clone https://github.com/mlg151/henchman-ai.git
cd henchman-ai
pip install -e ".[dev]"
```

### With uv (Fastest)

```bash
uv pip install henchman-ai
```

## API Key Setup

Henchman-AI requires an API key for your chosen LLM provider.

### DeepSeek (Default)

```bash
export DEEPSEEK_API_KEY="your-deepseek-api-key"
```

### OpenAI-Compatible Providers

Henchman-AI supports multiple OpenAI-compatible providers. Each has its own API key environment variable:

#### OpenAI
```bash
export OPENAI_API_KEY="your-openai-api-key"
```

#### Together AI
```bash
export TOGETHER_API_KEY="your-together-api-key"
```

#### Groq
```bash
export GROQ_API_KEY="your-groq-api-key"
```

#### Fireworks AI
```bash
export FIREWORKS_API_KEY="your-fireworks-api-key"
```

**Note**: For OpenAI specifically, use `openai_compat` provider with `base_url: https://api.openai.com/v1`. For other providers, use their specific provider names (`together`, `groq`, `fireworks`).

### Anthropic

```bash
export ANTHROPIC_API_KEY="your-anthropic-api-key"
```

### Ollama (Local Models)

Ollama allows you to run models locally without an API key:

1. Install Ollama from [ollama.ai](https://ollama.ai/)
2. Pull a model: `ollama pull llama3.2`
3. Start the server: `ollama serve`
4. No API key needed - Henchman-AI will connect to `http://localhost:11434` by default

### Other Providers

Henchman-AI also supports OpenRouter, Together AI, Groq, Fireworks AI, and other OpenAI-compatible services. See [Providers](providers.md) for complete setup instructions for these services.

## First Run

### Interactive Mode

Start the interactive REPL:

```bash
henchman
```

You'll see a welcome message and prompt. By default, you are talking to the **Tech Lead** of a multi-agent team.

```
Henchman-AI - /help for commands, /quit to exit

❯ 
```

### Headless Mode

Run with a single prompt:

```bash
henchman --prompt "What is 2 + 2?"
```

Or pipe input:

```bash
echo "Explain this code" | henchman -p -
cat file.py | henchman --prompt "Review this Python code"
```

## Slash Commands

| Command | Description |
|---------|-------------|
| `/help` | Show available commands |
| `/quit` | Exit the CLI |
| `/clear` | Clear conversation history |
| `/tools` | List available tools |
| `/chat save [tag]` | Save current session |
| `/chat list` | List saved sessions |
| `/chat resume <tag>` | Resume a session |

## Special Input Syntax

### File References

Use `@filename` to include file contents:

```
❯ Explain the code in @src/main.py
```

### Shell Commands

Prefix with `!` to run shell commands:

```
❯ !ls -la
```

## Next Steps

- [Configuration](configuration.md) - Customize settings
- [Providers](providers.md) - Set up different LLM providers
- [Tools](tools.md) - Learn about built-in tools
