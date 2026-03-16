# Henchman-AI

**A Model-Agnostic AI Agent CLI in Python**

Henchman-AI is a powerful terminal-based AI agent that supports multiple LLM providers through a unified interface. Inspired by gemini-cli, built for extensibility.

## Features

- 🤝 **Multi-Agent Dev Team**: Orchestrate a team of specialists (Tech Lead, Planner, Explorer, Engineer, Data Engineer) to solve complex engineering tasks.
- 🔄 **Model-Agnostic**: Support any LLM provider through a unified abstraction layer
- 🐍 **Pythonic**: Leverages Python's async ecosystem and rich libraries for optimal performance
- 🔌 **Extensible**: Plugin system for tools, providers, and custom commands
- 🚀 **Production-Ready**: Proper error handling, comprehensive testing with 100% coverage, and semantic versioning
- 🛠️ **Built-in Tools**: 34 tools for code analysis, testing, file operations, and multi-agent coordination
- 🔗 **MCP Integration**: Connect to external tool servers via Model Context Protocol
- ⚡ **Fast & Efficient**: Async-first design with intelligent caching and rate limiting
- 🔒 **Secure**: Environment-based configuration and safe execution sandboxing

## Quick Start

**Prerequisites**: Python 3.10 or higher

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

| Provider | Status | Registry Name | Notes |
|----------|--------|---------------|-------|
| DeepSeek (`deepseek`) | ✅ | `deepseek` | Default provider, OpenAI-compatible API |
| Anthropic (`anthropic`) | ✅ | `anthropic` | Claude models (native SDK) |
| Ollama (`ollama`) | ✅ | `ollama` | Local models, OpenAI-compatible API |
| OpenRouter (`openrouter`) | ✅ | `openrouter` | Access to hundreds of models, OpenAI-compatible API |
| OpenAI-Compatible (`openai_compat`) | ✅ | `openai_compat` | Generic provider for ANY OpenAI-compatible API (OpenAI, Together, Groq, Fireworks, etc.) |
| Together AI (`together`) | ✅ | `together` | Alias for `openai_compat` with Together base URL |
| Groq (`groq`) | ✅ | `groq` | Alias for `openai_compat` with Groq base URL |
| Fireworks AI (`fireworks`) | ✅ | `fireworks` | Alias for `openai_compat` with Fireworks base URL |

**Note**: The `openai_compat` provider is a generic provider for any OpenAI-compatible API. Specific providers like `together`, `groq`, and `fireworks` are aliases for `openai_compat` that require you to configure the appropriate base URL in your settings.

**See [Providers](providers.md) for complete details and configuration.**

## Built-in Tools

Henchman-AI includes a comprehensive set of 34 tools for code analysis, testing, file operations, and multi-agent coordination, including:

- **read_file** - Read file contents
- **write_file** - Write to files  
- **edit_file** - Make surgical edits
- **shell** - Execute shell commands
- **delegate_task** - Delegate to specialist agents (multi-agent core)
- **ask_user** - Ask user questions during execution
- **pytest_run** - Run pytest tests
- **git_ops** - Git operations (status, log, blame, etc.)
- **web_fetch** - Fetch web pages

*See [Tools](tools.md) for the complete list of all 34 tools.*

## Documentation

- [Getting Started](getting-started.md) - Installation and first steps
- [Architecture](architecture.md) - System design and components
- [Multi-Agent Dev Team](agents.md) - Specialist agent orchestration
- [Configuration](configuration.md) - Settings and customization
- [Intelligent Context Management](intelligent-context-management.md) - Advanced context compression
- [Providers](providers.md) - LLM provider setup
- [Tools](tools.md) - Built-in and custom tools
- [MCP Integration](mcp.md) - External tool servers
- [Extensions](extensions.md) - Creating plugins
- [API Reference](api.md) - Programmatic interfaces
- [Contributing](CONTRIBUTING.md) - How to contribute
- [Changelog](CHANGELOG.md) - Release history and changes

## License

MIT License - see [LICENSE](https://github.com/mlg151/henchman-ai/blob/main/LICENSE) for details.
