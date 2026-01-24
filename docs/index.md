# Henchman-AI

**A Model-Agnostic AI Agent CLI in Python**

Henchman-AI is a powerful terminal-based AI agent that supports multiple LLM providers through a unified interface. Inspired by gemini-cli, built for extensibility.

## Features

- 🔄 **Model-Agnostic**: Support any LLM provider through a unified abstraction
- 🐍 **Pythonic**: Leverages Python's async ecosystem and rich libraries
- 🔌 **Extensible**: Plugin system for tools, providers, and commands
- 🚀 **Production-Ready**: Proper error handling, testing, and 100% test coverage
- 🛠️ **Built-in Tools**: File operations, shell commands, web fetching, and more
- 🔗 **MCP Integration**: Connect to external tool servers via Model Context Protocol

## Quick Start

```bash
# Install from PyPI
pip install henchman-ai

# Set your API key
export DEEPSEEK_API_KEY="your-api-key"

# Start interactive mode
henchman

# Or run with a prompt
henchman --prompt "Explain this code" < file.py
```

## Supported Providers

| Provider | Status | Notes |
|----------|--------|-------|
| DeepSeek | ✅ | Default provider, OpenAI-compatible |
| OpenAI | ✅ | GPT-4, GPT-3.5, etc. |
| Anthropic | ✅ | Claude models |
| Ollama | ✅ | Local models |

## Built-in Tools

- **read_file** - Read file contents
- **write_file** - Write to files
- **edit_file** - Make surgical edits
- **shell** - Execute shell commands
- **ls** - List directory contents
- **glob** - Find files by pattern
- **grep** - Search file contents
- **web_fetch** - Fetch web pages

## Documentation

- [Getting Started](getting-started.md) - Installation and first steps
- [Configuration](configuration.md) - Settings and customization
- [Providers](providers.md) - LLM provider setup
- [Tools](tools.md) - Built-in and custom tools
- [MCP Integration](mcp.md) - External tool servers
- [Extensions](extensions.md) - Creating plugins

## License

MIT License - see [LICENSE](https://github.com/matthew/henchman-ai/blob/main/LICENSE) for details.
