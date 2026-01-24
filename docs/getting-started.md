# Getting Started

## Installation

### From PyPI (Recommended)

```bash
pip install henchman-ai
```

### From Source

```bash
git clone https://github.com/matthew/henchman-ai.git
cd henchman-ai
pip install -e ".[dev]"
```

## API Key Setup

Henchman-AI requires an API key for your chosen LLM provider.

### DeepSeek (Default)

```bash
export DEEPSEEK_API_KEY="your-deepseek-api-key"
```

### OpenAI

```bash
export OPENAI_API_KEY="your-openai-api-key"
```

### Anthropic

```bash
export ANTHROPIC_API_KEY="your-anthropic-api-key"
```

## First Run

### Interactive Mode

Start the interactive REPL:

```bash
henchman
```

You'll see a welcome message and prompt:

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
