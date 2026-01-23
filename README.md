# MLG-CLI

> A Model-Agnostic AI Agent CLI in Python

MLG-CLI is a terminal-based AI agent that supports multiple LLM providers (DeepSeek, OpenAI, Anthropic, Ollama) through a unified interface. Inspired by gemini-cli, built for extensibility.

## Features

- 🔄 **Model-Agnostic**: Support any LLM provider through a unified abstraction
- 🐍 **Pythonic**: Leverages Python's async ecosystem and rich libraries
- 🔌 **Extensible**: Plugin system for tools, providers, and commands
- 🚀 **Production-Ready**: Proper error handling, testing, and packaging

## Installation

```bash
pip install mlg-cli
```

Or install from source:

```bash
git clone https://github.com/matthew/mlg-cli.git
cd mlg-cli
pip install -e ".[dev]"
```

## Quick Start

```bash
# Set your API key
export DEEPSEEK_API_KEY="your-api-key"

# Start the CLI
mlg

# Or run with a prompt directly
mlg --prompt "Explain this code" < file.py
```

## Usage

```bash
# Show version
mlg --version

# Show help
mlg --help

# Interactive mode (default)
mlg

# Headless mode with prompt
mlg -p "Summarize README.md"
```

## Configuration

MLG-CLI uses hierarchical configuration:

1. Default settings
2. User settings: `~/.mlg/settings.yaml`
3. Workspace settings: `.mlg/settings.yaml`
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
