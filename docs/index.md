# Henchman-AI

**A Model-Agnostic AI Agent CLI in Python**

Henchman-AI is a terminal-based AI agent that supports multiple LLM providers through a unified interface. Inspired by gemini-cli, it is built for extensibility and local developer workflows.

**Project status**: Beta. The core local CLI, multi-agent orchestration, registered web search, configured MCP support, and local extension loading are shipped. Remote agent/plugin marketplace installs, a Slack runtime, cron execution, and the broader remote operations platform are not shipped in this variant.

## Features

- 🤝 **Multi-Agent Dev Team**: Orchestrate a team of specialists (Tech Lead, Planner, Explorer, Engineer, Data Engineer) to solve complex engineering tasks.
- 🔄 **Model-Agnostic**: Support any LLM provider through a unified abstraction layer
- 🐍 **Pythonic**: Leverages Python's async ecosystem and rich libraries for optimal performance
- 🔌 **Extensible**: Local extensions and UI plugins for tools, context, and commands
- 🧪 **Tested**: CI covers Python 3.11–3.14 and smoke-tests installed wheels and the source distribution across CLI, API, and RAG boundaries
- 🛠️ **Built-in Tools**: Runtime-registered tools for code analysis, testing, file operations, and multi-agent coordination
- 🔗 **MCP Integration**: Connect to configured external tool servers when the `mcp` and `mcp_auth` runtime tools are registered
- ⚡ **Fast & Efficient**: Async-first design with intelligent caching and rate limiting
- 🔒 **Secure**: Environment-based configuration and safe execution sandboxing

## Quick Start

**Prerequisites**: Python 3.11–3.14

```bash
# Install from PyPI
pip install henchman-ai

# Set your API key
export DEEPSEEK_API_KEY="your-api-key"

# Start interactive mode
henchman

# Or run with a prompt
henchman chat --prompt "Explain the code in @file.py"
```

## Supported Providers

| Provider | Status | Configuration Name | Notes |
|----------|--------|-------------------|-------|
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

Henchman-AI registers tools according to the active runtime and agent preset. Representative tools include:

- **read_file** - Read file contents
- **write_file** - Write to files  
- **edit_file** - Make surgical edits
- **shell** - Execute shell commands
- **delegate_task** - Delegate to specialist agents (multi-agent core)
- **ask_user** - Ask user questions during execution
- **pytest_run** - Run pytest tests
- **git_ops** - Git operations (status, log, blame, etc.)
- **web_fetch** - Fetch web pages

Use `/tools` or the discovery surfaces for the live inventory, and see [Tools](tools.md) for tool behavior and examples.

## Capability Boundaries

The shared capability matrix is the source of truth for help, doctor, and tool discovery. Runtime-wired classifications are further constrained by which tools are actually registered.

| Capability | Current classification |
|------------|------------------------|
| `web_search` | Runtime-wired when registered; otherwise unavailable |
| MCP | Runtime-wired only when both `mcp` and `mcp_auth` are registered |
| Skills | Local-only discovery and inspection |
| Integration blueprints, including Slack | Export-only; no runtime is launched or configured |
| `schedule_cron` | Metadata-only; no background runner executes schedules |
| Plugin marketplace install | Unavailable; local plugin list/remove and loading remain supported |
| Agent registry install | Unavailable; local list/show/publish remain supported |
| GitHub webhook helper | Documentation-only |
| Tier 10 dialogs | Implemented in `henchman chat --tui`, intentionally absent from generic discovery |

## Documentation

- [Getting Started](getting-started.md) - Installation and first steps
- [Architecture](architecture.md) - System design and components
- [Multi-Agent Dev Team](agents.md) - Specialist agent orchestration
- [Configuration](configuration.md) - Settings and customization
- [Intelligent Context Management](intelligent-context-management.md) - Advanced context compression
- [Providers](providers.md) - LLM provider setup
- [Tools](tools.md) - Built-in and custom tools
- [MCP Integration](mcp.md) - External tool servers
- [Standards Adoption RFC](standards.md) - Researched MCP, A2A, telemetry, and schema roadmap; adoption remains proposed
- [Terminal UI Research](terminal-ui-research.md) - Coding-agent feedback, Python application exemplars, and proposed UI quality phases
- [Extensions](extensions.md) - Creating plugins
- [API Reference](api.md) - Programmatic interfaces
- [Contributing](CONTRIBUTING.md) - How to contribute
- [Changelog](CHANGELOG.md) - Release history and changes

## License

MIT License - see [LICENSE](https://github.com/mlg151/henchman-ai/blob/main/LICENSE) for details.
