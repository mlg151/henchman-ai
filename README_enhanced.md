# Henchman-AI

> Your AI Henchman for the Terminal - A Model-Agnostic AI Agent CLI

[![PyPI version](https://img.shields.io/pypi/v/henchman-ai.svg)](https://pypi.org/project/henchman-ai/)
[![Python versions](https://img.shields.io/pypi/pyversions/henchman-ai.svg)](https://pypi.org/project/henchman-ai/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Documentation](https://img.shields.io/badge/docs-latest-blue)](https://mlg151.github.io/henchman-ai/)

Henchman-AI is a powerful, terminal-based AI agent that supports multiple LLM providers (DeepSeek, OpenAI, Anthropic, Ollama, and more) through a unified interface. Inspired by gemini-cli, built for extensibility and production use.

## ✨ Features

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

### Tool Usage
```bash
# Enable web search
henchman --enable-tool web_search -p "What's the latest news about AI?"

# Use shell commands (with confirmation)
henchman --enable-tool shell -p "List files in current directory"

# Mathematical calculations
henchman --enable-tool calculator -p "Calculate 2^10 * pi / 3"
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
  default: deepseek  # or openai, anthropic, ollama
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

# Run with coverage
pytest --cov=henchman --cov-report=html

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

Comprehensive documentation is available at: [https://mlg151.github.io/henchman-ai/](https://mlg151.github.io/henchman-ai/)

- [Getting Started](https://mlg151.github.io/henchman-ai/getting-started/)
- [Configuration Guide](https://mlg151.github.io/henchman-ai/configuration/)
- [API Reference](https://mlg151.github.io/henchman-ai/api/)
- [Tool Development](https://mlg151.github.io/henchman-ai/tools/)
- [Provider Integration](https://mlg151.github.io/henchman-ai/providers/)

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](https://github.com/mlg151/henchman-ai/blob/main/CONTRIBUTING.md) for details.

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 🐛 Reporting Issues

Found a bug or have a feature request? Please [open an issue](https://github.com/mlg151/henchman-ai/issues) on GitHub.

## 📄 License

Henchman-AI is released under the MIT License. See the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Inspired by [gemini-cli](https://github.com/google/gemini-cli)
- Built with [Rich](https://github.com/Textualize/rich) for beautiful terminal output
- Uses [Pydantic](https://docs.pydantic.dev/) for data validation
- Powered by the Python async ecosystem

---

**Happy coding with your AI Henchman!** 🦸‍♂️🤖