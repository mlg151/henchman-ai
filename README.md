# Henchman-AI

> A Model-Agnostic AI Agent CLI in Python

Henchman-AI is a terminal-based AI agent that supports multiple LLM providers (DeepSeek, OpenAI, Anthropic, Ollama) through a unified interface. Inspired by gemini-cli, built for extensibility.

## Features

- 🔄 **Model-Agnostic**: Support any LLM provider through a unified abstraction
- 🐍 **Pythonic**: Leverages Python's async ecosystem and rich libraries
- 🔌 **Extensible**: Plugin system for tools, providers, and commands
- 🚀 **Production-Ready**: Proper error handling, testing, and packaging

## Installation

```bash
pip install henchman-ai
```

Or install from source:

```bash
git clone https://github.com/matthew/henchman-ai.git
cd henchman-ai
pip install -e ".[dev]"
```

## Quick Start

```bash
# Set your API key
export DEEPSEEK_API_KEY="your-api-key"

# Start the CLI
henchman

# Or run with a prompt directly
henchman --prompt "Explain this code" < file.py
```

## Usage

```bash
# Show version
henchman --version

# Show help
henchman --help

# Interactive mode (default)
henchman

# Headless mode with prompt
henchman -p "Summarize README.md"
```

## Configuration

Henchman-AI uses hierarchical configuration:

1. Default settings
2. User settings: `~/.henchman/settings.yaml`
3. Workspace settings: `.henchman/settings.yaml`
4. Environment variables

Example `settings.yaml`:

```yaml
providers:
  default: deepseek
  deepseek:
    model: deepseek-chat

tools:
  auto_accept_read: true
  shell_timeout: 60
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Linting
ruff check src/ tests/

# Type checking
mypy src/
```

## License

MIT License - see [LICENSE](LICENSE) for details.
