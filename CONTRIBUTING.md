# Contributing to Henchman-AI

Thank you for your interest in contributing to Henchman-AI! This document provides guidelines and instructions for contributing.

## 🎯 How to Contribute

### 1. Reporting Bugs
- Check if the bug has already been reported in [Issues](https://github.com/mlg151/henchman-ai/issues)
- Use the bug report template
- Include steps to reproduce, expected vs actual behavior, and environment details

### 2. Suggesting Features
- Check if the feature has already been suggested
- Explain the use case and benefits
- Consider if it aligns with the project's goals

### 3. Contributing Code
- Fork the repository
- Create a feature branch (`git checkout -b feature/amazing-feature`)
- Make your changes
- Add or update tests
- Ensure code passes linting and type checking
- Submit a pull request

## 🏗️ Development Setup

### Prerequisites
- Python 3.11–3.14
- Git
- (Optional) uv for faster dependency management

### Installation
```bash
# 1. First, fork the repository on GitHub: https://github.com/mlg151/henchman-ai
# 2. Then clone your fork:
#    Replace '{your-username}' with your actual GitHub username
git clone https://github.com/{your-username}/henchman-ai.git
cd henchman-ai

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install with development dependencies
pip install -e ".[dev]"

# Install pre-commit hooks (optional but recommended)
pre-commit install
```

### AI Agent Development

Henchman-AI is designed to be developed with AI assistance. The project includes comprehensive copilot instructions for AI agents working on the codebase:

**Copilot Instructions**: `.github/copilot-instructions.md`

This file contains:
- **Architecture overview** of the entire system
- **Development workflow** guidelines for AI agents
- **Performance optimization** strategies for agent effectiveness
- **Tool usage patterns** and best practices
- **Testing requirements** and quality standards
- **File structure** and conventions

**Key guidelines for AI agents**:
1. **Read the copilot instructions first** before making changes
2. **Follow the structured thinking protocols** for complex tasks
3. **Use the working memory system** to avoid redundant file reads
4. **Apply smart file reading strategies** to optimize context usage
5. **Delegate specialized tasks** to appropriate agent roles
6. **Track performance metrics** to improve efficiency
7. **Place non-source artifacts** in `.agent_tasks/` directory

The copilot instructions are regularly updated to reflect the current architecture and development practices. AI agents should reference this file to understand project conventions, tool capabilities, and performance expectations.

### Running Tests
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=henchman --cov-report=term-missing --cov-fail-under=90

# Run specific test files
pytest tests/cli/test_app.py -v

# Run integration tests
pytest -m integration
```

Pytest pins its coverage configuration to `pyproject.toml` so child shell and
Python executions use the same branch settings as the test runner. When running
from another directory, pass an absolute `--cov-config` path.

### Code Quality
```bash
# Format code
ruff format src/ tests/

# Check linting
ruff check src/ tests/

# Type checking
mypy src/

# Security audit
bandit -r src/
```

## 📁 Project Structure

```
henchman-ai/
├── src/henchman/          # Source code
│   ├── cli/              # CLI interface
│   ├── core/             # Core functionality
│   ├── providers/        # LLM provider implementations
│   ├── tools/            # Tool implementations
│   └── utils/            # Utility functions
├── tests/                # Test suite
├── docs/                 # Documentation
├── scripts/              # Development scripts
└── evals/                # Evaluation scripts
```

## 🛠️ Temporary Debugging Files

During development and debugging, you may create temporary test files to reproduce specific issues or test fixes. These files differ from the official test suite:

### Guidelines for Temporary Debugging Files

**Location**: Root directory (not in `tests/`)
**Naming**: Use `test_` prefix followed by descriptive name (e.g., `test_delegation_bug.py`, `test_actual_bug_manifestation.py`)
**Purpose**: For reproducing bugs, testing fixes, or quick experiments
**Cleanup**: Remove temporary debugging files before committing changes
**Official Tests**: Permanent tests that should be part of the test suite belong in the `tests/` directory

### Example Temporary Files
```
test_actual_bug_manifestation.py    # Reproduce specific bug
test_delegation_bug.py              # Test delegation fix
test_raw_string_simple.py           # Test string parsing issue
```

### Before Committing
1. **Move to tests/**: If the test should be permanent, move it to `tests/` directory
2. **Clean up**: Remove temporary debugging files from root directory
3. **Verify**: Ensure only official tests remain in `tests/` directory

## 📝 Code Style

### Python Style Guide
- Follow [PEP 8](https://peps.python.org/pep-0008/)
- Use type hints for all functions and methods
- Document public APIs with docstrings (Google style)
- Keep functions focused and small (aim for concise, single-purpose functions)

### Docstring Format (Google Style)
```python
def process_file(filepath: str, mode: str = "read") -> str:
    """Process a file with the given mode.
    
    Args:
        filepath: Path to the file to process
        mode: Processing mode ('read', 'write', 'append')
    
    Returns:
        The processed content as a string
    
    Raises:
        FileNotFoundError: If the file doesn't exist
        ValueError: If mode is invalid
    """
    # Implementation
```

### Commit Messages
Follow [Conventional Commits](https://www.conventionalcommits.org/):
```
feat: add new provider for Gemini
fix: handle API rate limiting properly
docs: update installation instructions
test: add unit tests for file tools
refactor: simplify configuration loading
chore: update dependencies
```

## 🧪 Testing Guidelines

### Unit Tests
- Test one thing per test function
- Use descriptive test names
- Mock external dependencies
- Keep whole-project coverage at or above the 90% CI floor; fully test changed behavior

### Integration Tests
- Test end-to-end functionality
- Use real API calls (with test credentials)
- Clean up after tests

### Example Test
```python
import pytest
from henchman.core.processor import process_prompt

def test_process_prompt_with_valid_input():
    """Test prompt processing with valid input."""
    result = process_prompt("Hello, world!")
    assert isinstance(result, str)
    assert len(result) > 0

def test_process_prompt_with_empty_input():
    """Test prompt processing with empty input raises error."""
    with pytest.raises(ValueError):
        process_prompt("")
```

## 🔌 Adding New Providers

1. Create a new file in `src/henchman/providers/`
2. Implement the `ModelProvider` interface
3. Add tests in `tests/providers/`
4. Update documentation
5. Add to provider registry

## 🛠️ Adding New Tools

1. Create a new file in `src/henchman/tools/`
2. Implement the `Tool` interface
3. Add safety checks and user confirmation
4. Add tests
5. Update documentation

## 📚 Documentation

### Updating Documentation
- Documentation is in the `docs/` directory
- Use Markdown with MkDocs
- Build locally: `mkdocs serve`
- Update API documentation when changing interfaces

### Adding Examples
- Add practical examples to relevant documentation
- Include code snippets that can be copied
- Show common use cases and edge cases

## 🚀 Release Process

### Versioning
We follow [Semantic Versioning](https://semver.org/):
- **MAJOR**: Breaking changes
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes (backward compatible)

### Release Checklist
1. Update version in `pyproject.toml`
2. Update `CHANGELOG.md`
3. Run full test suite
4. Update documentation
5. Create release tag
6. Build and publish to PyPI

## ❓ Getting Help

- Check the [documentation](https://github.com/mlg151/henchman-ai)
- Search existing [issues](https://github.com/mlg151/henchman-ai/issues)
- Join discussions in [GitHub Discussions](https://github.com/mlg151/henchman-ai/discussions)

## 📄 License

By contributing, you agree that your contributions will be licensed under the project's MIT License.

---

Thank you for contributing to make Henchman-AI better! 🎉
