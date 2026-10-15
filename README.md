# Henchman-AI

> Your AI Henchman for the Terminal - A Model-Agnostic AI Agent CLI

[![PyPI version](https://img.shields.io/pypi/v/henchman-ai.svg)](https://pypi.org/project/henchman-ai/)
[![Python versions](https://img.shields.io/pypi/pyversions/henchman-ai.svg)](https://pypi.org/project/henchman-ai/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Henchman-AI is a terminal-based AI agent that supports multiple LLM providers (DeepSeek, OpenAI-compatible APIs, Anthropic, Ollama, OpenRouter, and more) through a unified interface. Inspired by gemini-cli, it is built for extensibility and local developer workflows.

**Project status**: Beta. The core local CLI, multi-agent orchestration, registered web search, configured MCP support, and local extension loading are shipped. Remote agent/plugin marketplace installs, a Slack runtime, cron execution, and the broader remote operations platform are not shipped in this variant.

## ✨ Features

- 🤝 **Multi-Agent Dev Team**: Orchestrate a team of specialists (Tech Lead, Planner, Explorer, Engineer, Data Engineer) to solve complex engineering tasks.
- 🔄 **Model-Agnostic**: Support any LLM provider through a unified abstraction layer
- 🐍 **Pythonic**: Leverages Python's async ecosystem and rich libraries for optimal performance
- 🔌 **Extensible**: Local extensions and UI plugins for tools, context, and commands
- 🧪 **Tested**: CI exercises Python 3.11–3.14 and smoke-tests installed wheels and the source distribution across CLI, API, and RAG boundaries
- 🛠️ **Built-in Tools**: Runtime-registered tools for file operations, shell commands, web access, code analysis, testing, and multi-agent coordination
- 🔗 **MCP Integration**: Connect to configured external tool servers when the `mcp` and `mcp_auth` runtime tools are registered
- ⚡ **Fast & Efficient**: Async-first design with intelligent caching and rate limiting
- 🔒 **Secure**: Environment-based configuration and safe execution sandboxing

## 📦 Installation

### Prerequisites

- **Python 3.11–3.14**: These are the currently supported and CI-tested Python versions
- **API Key**: For your chosen LLM provider (DeepSeek, OpenAI, Anthropic, etc.)
- **Git** (optional): For installing from source
- **uv** (optional): For faster dependency management

The base install includes `chromadb>=1.5.9` for RAG storage and `scipy>=1.11.2`, which NetworkX-backed PageRank queries require. If an older environment is missing either dependency, reinstall or upgrade Henchman-AI rather than installing only the top-level package without dependencies.

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

## 🚀 Quick Start

1. **Set your API key** (choose your preferred provider):
   ```bash
   # DeepSeek (default provider)
   export DEEPSEEK_API_KEY="your-api-key-here"
   
   # OpenAI or OpenAI-compatible services
   export OPENAI_API_KEY="your-api-key-here"
   
   # Anthropic Claude
   export ANTHROPIC_API_KEY="your-api-key-here"
   
   # OpenRouter
   export OPENROUTER_API_KEY="your-api-key-here"
   
   # For other providers, see the Providers documentation
   ```

2. **Start the CLI**:
   ```bash
   henchman
   ```

3. **Or run with a prompt directly**:
   ```bash
   henchman chat --prompt "Explain the Python code in @example.py"
   ```

## 🏗️ Architecture

Henchman-AI features a modular, component-based architecture designed for maintainability and extensibility. The core interactive REPL (Read-Eval-Print Loop) has been refactored into specialized components:

### REPL Component Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     REPL (Orchestrator)                      │
│  ┌──────────┐  ┌───────────┐  ┌─────────────┐  ┌─────────┐  │
│  │  Input   │  │  Output   │  │   Command   │  │  Tool   │  │
│  │ Handler  │◄─┤  Handler  │◄─┤  Processor  │◄─┤Executor │  │
│  └──────────┘  └───────────┘  └─────────────┘  └─────────┘  │
│         │             │              │               │       │
│         ▼             ▼              ▼               ▼       │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                Multi-Agent Orchestrator               │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

1. **REPL (Orchestrator)**: Main coordination class
   - Initializes and connects all components
   - Manages the main interaction loop
   - Delegates work to specialized components
   - Maintains backward compatibility

2. **InputHandler**: User input processing
   - Manages prompt sessions with history
   - Handles @file expansion and shell command detection
   - Processes keyboard interrupts and EOF
   - Validates and sanitizes user input

3. **OutputHandler**: Console output and status display
   - Manages rich console output and formatting
   - Displays status bars and tool information
   - Shows welcome/goodbye messages
   - Handles event streaming and turn status

4. **CommandProcessor**: Slash command execution
   - Processes /quit, /clear, /help, and other commands
   - Manages command registry and argument parsing
   - Delegates to specialized command handlers
   - Provides command completion and validation

5. **ToolExecutor**: Tool execution and agent coordination
   - Executes tool calls from agents
   - Manages tool confirmation requests
   - Processes agent event streams
   - Handles tool iteration limits and cancellation

### Benefits of Component Architecture
- **Single Responsibility**: Each component has a clear, focused purpose
- **Testability**: Components can be tested independently with unit, integration, and contract suites
- **Maintainability**: Smaller, focused classes are easier to understand and modify
- **Extensibility**: New components can be added without modifying the REPL
- **Performance**: Business logic moved out of REPL, leaving only orchestration

## 📖 Usage Examples

### Basic Commands
```bash
# Show version
henchman --version

# Show help
henchman --help

# Interactive mode (default)
henchman

# Headless mode with prompt
henchman chat -p "Summarize the key points from README.md"

# Specify a provider
henchman config set providers.default openai_compat --scope project
henchman chat -p "Write a Python function to calculate fibonacci"

# Use a specific model
henchman config set providers.openai_compat.model gpt-4-turbo --scope project
henchman chat -p "Analyze this code for security issues"
```

### File Operations
```bash
# Read and analyze a file
henchman chat -p "Review @script.py for bugs"

# Process multiple files
henchman chat -p "Find common patterns in @first.py and @second.py"

# Generate documentation
henchman chat -p "Create API documentation for @module.py" > docs.md
```

## ⚙️ Configuration

Henchman-AI uses hierarchical configuration (later settings override earlier ones):

1. **Default settings** (built-in sensible defaults)
2. **User settings**: `~/.henchman/settings.yaml`
3. **Workspace settings**: `.henchman/settings.yaml` (project-specific)
4. **Environment variables** (highest priority)

Project instruction discovery has an explicit trust boundary. Inside a Git repository, Henchman walks from the repository root to the working directory. Outside Git, it reads project context only from the current directory and does not search parents or subdirectories. Global context in `~/.henchman/HENCHMAN.md` remains separate.

### Example `settings.yaml`
```yaml
# Provider configuration
providers:
  default: deepseek  # or openai_compat, anthropic, ollama, openrouter
  deepseek:
    model: deepseek-chat
    base_url: "https://api.deepseek.com"
    temperature: 0.7
  openai_compat:
    model: gpt-4-turbo-preview
    organization: "org-xxx"

# Tool settings
tools:
  auto_accept_read: true
  shell_timeout: 60
  web_search_max_results: 5

# UI settings
ui:
  theme: "monokai"
  show_tokens: true
  streaming: true

# System settings
system:
  cache_enabled: true
  cache_ttl: 3600
  max_tokens: 4096
```

### Environment Variables
```bash
# Provider API keys
export DEEPSEEK_API_KEY="sk-xxx"
export OPENAI_API_KEY="sk-xxx"
export ANTHROPIC_API_KEY="sk-xxx"
export OPENROUTER_API_KEY="sk-xxx"
export TOGETHER_API_KEY="sk-xxx"
export GROQ_API_KEY="sk-xxx"
export FIREWORKS_API_KEY="sk-xxx"

# Configuration overrides
export HENCHMAN_DEFAULT_PROVIDER="openai_compat"
export HENCHMAN_DEFAULT_MODEL="gpt-4"
export HENCHMAN_TEMPERATURE="0.5"
```

## 🔌 Supported Providers

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

**Configuration Names**: Use these names in `settings.yaml` (for example, `providers.default: deepseek`) or with `henchman config set providers.default <name> --scope project`.

**See [Providers](docs/providers.md) for complete details and configuration.**

## 🛠️ Development

### Setup Development Environment
```bash
# Clone and install
git clone https://github.com/mlg151/henchman-ai.git
cd henchman-ai
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -e ".[dev]"
```

**For AI Agent Development**: Henchman-AI includes comprehensive copilot instructions for AI agents working on the codebase. See [.github/copilot-instructions.md](https://github.com/mlg151/henchman-ai/blob/main/.github/copilot-instructions.md) for architecture overview, development workflows, performance optimization strategies, and agent effectiveness guidelines.

### Running Tests
```bash
# Run all tests
pytest

# Run the same coverage gate configured in CI
pytest --cov=henchman --cov-report=html --cov-fail-under=90

# Run specific test categories
pytest tests/api/ -v
pytest tests/integration/ -v
```

### Code Quality
```bash
# Linting
ruff check src/ tests/
ruff format src/ tests/

# Type checking
mypy src/

# Security scanning
bandit -r src/
```

CI runs the test suite on Python 3.11, 3.12, 3.13, and 3.14. It builds both distribution formats, installs the wheel on Python 3.11 and 3.14, and installs the source distribution on Python 3.11. Every artifact smoke test checks both entry-point versions, `henchman --help`, unknown-command rejection, API readiness, and an explicit-embedding Chroma add/query round trip without credentials or model downloads.

## 🔎 Capability Boundaries

Discovery, help, and doctor surfaces derive their status from the shared capability matrix in `src/henchman/cli/commands/discovery_capabilities.py` and, for runtime-wired tools, the live tool registry.

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

### Building and Publishing
```bash
# Build package
uv build

# Test build
uv run --extra dev python -m pytest --cov-fail-under=90

# Publish to PyPI (requires credentials)
hatch publish
```

## 📚 Documentation

### Online Documentation
For detailed documentation, see the [docs directory](docs/index.md) in this repository:

- [Getting Started](docs/getting-started.md)
- [Configuration Guide](docs/configuration.md)
- [API Reference](docs/api.md)
- [Tool Development](docs/tools.md)
- [Provider Integration](docs/providers.md)
- [MCP Integration](docs/mcp.md)
- [Extensions](docs/extensions.md)

### Building Documentation Locally
You can build and view the documentation locally:

```bash
# Install documentation dependencies
pip install mkdocs mkdocs-material mkdocstrings[python]

# Build static HTML documentation
python scripts/build_docs.py

# Or serve documentation locally (live preview)
mkdocs serve
```

The documentation will be available at `http://localhost:8000` when served locally.

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for details.

## 🐛 Reporting Issues

Found a bug or have a feature request? Please [open an issue](https://github.com/mlg151/henchman-ai/issues) on GitHub.

## 📄 License

Henchman-AI is released under the MIT License. See the [LICENSE](https://github.com/mlg151/henchman-ai/blob/main/LICENSE) file for details.

## 🙏 Acknowledgments

- Inspired by [gemini-cli](https://github.com/google/gemini-cli)
- Built with [Rich](https://github.com/Textualize/rich) for beautiful terminal output
- Uses [Pydantic](https://docs.pydantic.dev/) for data validation
- Powered by the Python async ecosystem

---

**Happy coding with your AI Henchman!** 🦸‍♂️🤖
