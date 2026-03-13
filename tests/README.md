# Test Suite Structure

This directory contains the comprehensive test suite for Henchman-AI. The project maintains **100% test coverage** as a strict requirement.

## Test Organization

The test suite is organized to mirror the source code structure:

```
tests/
├── agents/           # Multi-agent system tests
├── api/              # REST API server tests
├── cli/              # CLI and UI layer tests
├── config/           # Configuration system tests
├── core/             # Core agent system tests
├── extensions/       # Extension/plugin system tests
├── knowledge/        # Knowledge graph tests
├── mcp/              # MCP integration tests
├── metrics/          # Performance metrics tests
├── providers/        # Provider implementation tests
├── rag/              # RAG system tests
├── tools/            # Tool system tests
├── utils/            # Utility function tests
├── e2e/              # End-to-end integration tests
├── integration/      # Integration tests
├── smoke/            # Smoke tests
├── ui_integration/   # UI integration tests
└── empty_message_validation/  # Specialized validation tests
```

## Test Types

### Unit Tests
- Located in directories matching source structure (e.g., `tests/agents/`, `tests/cli/`)
- Test individual components in isolation
- Use mocks for external dependencies

### Integration Tests
- Located in `tests/integration/`
- Test interactions between components
- May use real providers with test API keys

### End-to-End Tests
- Located in `tests/e2e/`
- Test complete workflows
- Simulate real user scenarios

### Smoke Tests
- Located in `tests/smoke/`
- Quick validation of critical functionality
- Run as part of CI pipeline

### UI Integration Tests
- Located in `tests/ui_integration/`
- Test CLI interface and user interactions
- May include interactive session tests

## Test Conventions

### Naming
- Test files: `test_*.py`
- Test functions: `test_*`
- Test classes: `Test*`

### Fixtures
- Common fixtures defined in `conftest.py`
- Module-specific fixtures in local `conftest.py` files
- Use `@pytest.fixture` decorator

### Markers
- `@pytest.mark.integration`: Integration tests that may call real APIs
- `@pytest.mark.e2e`: End-to-end tests
- `@pytest.mark.slow`: Tests that take longer to run
- `@pytest.mark.skip`: Tests that are temporarily disabled

## Running Tests

### Full Test Suite
```bash
# Run all tests with coverage
pytest --cov-fail-under=100

# Run with verbose output
pytest -v

# Run specific test categories
pytest tests/unit/ -v
pytest tests/integration/ -v
pytest tests/e2e/ -v
```

### CI Pipeline
The CI pipeline (`scripts/ci.sh`) runs:
1. **Ruff** - Linting
2. **Mypy** - Type checking
3. **Pytest** - Tests with 100% coverage requirement
4. **Doctests** - Documentation examples
5. **Doc coverage** - All public functions must have docstrings

### Coverage Requirements
- **100% test coverage** - All code paths must be tested
- **100% documentation coverage** - All public functions/classes have docstrings
- Coverage reports generated in `htmlcov/` and `coverage.json`

## Test Development Guidelines

### Adding New Tests
1. Create test file in appropriate directory structure
2. Write test cases covering all functionality
3. Ensure tests pass with 100% coverage
4. Run `./scripts/ci.sh` to verify all checks pass

### Mocking
- Use `unittest.mock` for mocking external dependencies
- Mock providers for unit tests to avoid API calls
- Use `AsyncMock` for async functions

### Async Testing
- Use `pytest.mark.asyncio` for async tests
- Use `anyio` for async test infrastructure
- Handle async context managers properly

## Test Data

### Test Files
- Test data files should be placed in test-specific directories
- Use temporary directories for file operations
- Clean up test files after tests

### Environment Variables
- Use `monkeypatch` to set environment variables for tests
- Never use real API keys in unit tests
- Test-specific configuration should be isolated

## Debugging Tests

### Running Specific Tests
```bash
# Run single test file
pytest tests/cli/test_app.py

# Run single test function
pytest tests/cli/test_app.py::test_cli_version

# Run tests matching pattern
pytest -k "test_version"
```

### Debug Output
```bash
# Show print statements
pytest -s

# Show log output
pytest --log-cli-level=DEBUG

# Show captured output
pytest -v --tb=short
```

## Quality Requirements

### Test Coverage
- All code must be tested
- Branch coverage must be 100%
- Exception paths must be tested
- Edge cases must be covered

### Code Quality
- Tests must follow same linting rules as source code
- Tests must have type hints
- Tests must have docstrings for complex test cases
- Tests must be maintainable and readable

### Performance
- Tests should run quickly
- Avoid unnecessary I/O operations
- Use appropriate test markers for slow tests
- Parallelize tests when possible

## Common Test Patterns

### Testing Async Code
```python
import pytest
from unittest.mock import AsyncMock

@pytest.mark.asyncio
async def test_async_function():
    mock_provider = AsyncMock()
    # Test async function
```

### Testing with Fixtures
```python
import pytest

@pytest.fixture
def sample_data():
    return {"key": "value"}

def test_with_fixture(sample_data):
    assert sample_data["key"] == "value"
```

### Testing Exceptions
```python
import pytest

def test_exception():
    with pytest.raises(ValueError, match="Expected error message"):
        raise ValueError("Expected error message")
```

## Root-Level Test Files

**Note**: Some test files in the project root (e.g., `test_*.py`) are temporary debugging files or specialized test utilities. These are not part of the main test suite and may be cleaned up periodically. The main test suite is organized in the `tests/` directory structure.

## Continuous Integration

The project uses GitHub Actions for CI. The workflow:
1. Runs on all pushes and pull requests
2. Executes `scripts/ci.sh` for full test suite
3. Enforces 100% coverage requirement
4. Fails if any quality check fails

## Test Maintenance

- Regularly review and update tests
- Remove obsolete tests
- Refactor tests for clarity
- Ensure tests remain fast and reliable
- Update tests when APIs change