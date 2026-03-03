# Henchman-AI

> Your AI Henchman for the Terminal - A Model-Agnostic AI Agent CLI

[![PyPI version](https://img.shields.io/pypi/v/henchman-ai.svg)](https://pypi.org/project/henchman-ai/)
[![Python versions](https://img.shields.io/pypi/pyversions/henchman-ai.svg)](https://pypi.org/project/henchman-ai/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Henchman-AI is a powerful, terminal-based AI agent that supports multiple LLM providers (DeepSeek, OpenAI, Anthropic, Ollama, and more) through a unified interface. Inspired by gemini-cli, built for extensibility and production use.

## ✨ Features

- 🤝 **Multi-Agent Dev Team**: Orchestrate a team of specialists (Architect, Coder, Reviewer, Tester, etc.) to solve complex engineering tasks.
- 🔄 **Model-Agnostic**: Support any LLM provider through a unified abstraction layer
- 🐍 **Pythonic**: Leverages Python's async ecosystem and rich libraries for optimal performance
- 🔌 **Extensible**: Plugin system for tools, providers, and custom commands
- 🚀 **Production-Ready**: Proper error handling, comprehensive testing, and semantic versioning
- 🛠️ **Tool Integration**: Built-in support for file operations, web search, code execution, and more
- ⚡ **Fast & Efficient**: Async-first design with intelligent caching and rate limiting
- 🔒 **Secure**: Environment-based configuration and safe execution sandboxing

## 📦 Installation

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
   export DEEPSEEK_API_KEY="your-api-key-here"
   # or
   export OPENAI_API_KEY="your-api-key-here"
   # or
   export ANTHROPIC_API_KEY="your-api-key-here"
   ```

2. **Start the CLI**:
   ```bash
   henchman
   ```

3. **Or run with a prompt directly**:
   ```bash
   henchman --prompt "Explain this Python code" < example.py
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

1. **REPL (Orchestrator)**: Main coordination class (406 lines, down from 559)
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
- **Testability**: Components can be tested independently (100% test coverage for core components)
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
henchman -p "Summarize the key points from README.md"

# Specify a provider
henchman --provider openai -p "Write a Python function to calculate fibonacci"

# Use a specific model
henchman --model gpt-4-turbo -p "Analyze this code for security issues"
```

### File Operations
```bash
# Read and analyze a file
henchman -p "Review this code for bugs" < script.py

# Process multiple files
cat *.py | henchman -p "Find common patterns in these files"

# Generate documentation
henchman -p "Create API documentation for this module" < module.py > docs.md
```

## ⚙️ Configuration

Henchman-AI uses hierarchical configuration (later settings override earlier ones):

1. **Default settings** (built-in sensible defaults)
2. **User settings**: `~/.henchman/settings.yaml`
3. **Workspace settings**: `.henchman/settings.yaml` (project-specific)
4. **Environment variables** (highest priority)

### Example `settings.yaml`
```yaml
# Provider configuration
providers:
  default: deepseek  # or openai, anthropic, ollama, openrouter
  deepseek:
    model: deepseek-chat
    base_url: "https://api.deepseek.com"
    temperature: 0.7
  openai:
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

# Configuration overrides
export HENCHMAN_DEFAULT_PROVIDER="openai"
export HENCHMAN_DEFAULT_MODEL="gpt-4"
export HENCHMAN_TEMPERATURE="0.5"
```

## 🔌 Supported Providers

| Provider | Models | Features |
|----------|--------|----------|
| **DeepSeek** | deepseek-chat, deepseek-coder | Free tier, Code completion |
| **OpenAI** | gpt-4, gpt-3.5-turbo, etc. | Function calling, JSON mode |
| **Anthropic** | claude-3-opus, claude-3-sonnet | Long context, Constitutional AI |
| **Ollama** | llama2, mistral, codellama | Local models, Custom models |
| **Custom** | Any OpenAI-compatible API | Self-hosted, Local inference |

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

### Running Tests
```bash
# Run all tests
pytest

# Run with coverage (100% required)
pytest --cov=henchman --cov-report=html --cov-fail-under=100

# Run specific test categories
pytest tests/unit/ -v
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

### Building and Publishing
```bash
# Build package
hatch build

# Test build
hatch run test

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