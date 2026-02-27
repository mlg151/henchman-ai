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
- Python 3.10 or higher
- Git
- (Optional) uv for faster dependency management

### Installation
```bash
# 1. First, fork the repository on GitHub: https://github.com/mlg151/henchman-ai
# 2. Then clone your fork (replace 'your-username' with your GitHub username):
git clone https://github.com/your-username/henchman-ai.git
cd henchman-ai

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install with development dependencies
pip install -e ".[dev]"

# Install pre-commit hooks (optional but recommended)
pre-commit install
```

### Running Tests
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=henchman --cov-report=term-missing

# Run specific test files
pytest tests/test_cli.py -v

# Run integration tests
pytest -m integration
```

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

## 📝 Code Style

### Python Style Guide
- Follow [PEP 8](https://peps.python.org/pep-0008/)
- Use type hints for all functions and methods
- Document public APIs with docstrings (Google style)
- Keep functions focused and small (< 50 lines when possible)

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
- Aim for high coverage (> 80%)

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

- Check the [documentation](https://mlg151.github.io/henchman-ai/)
- Search existing [issues](https://github.com/mlg151/henchman-ai/issues)
- Join discussions in [GitHub Discussions](https://github.com/mlg151/henchman-ai/discussions)

## 📄 License

By contributing, you agree that your contributions will be licensed under the project's MIT License.

---

Thank you for contributing to make Henchman-AI better! 🎉