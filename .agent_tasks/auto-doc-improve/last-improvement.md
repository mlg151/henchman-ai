# Documentation Improvement Record

## Date/Time
2026-03-03T05:20:00Z

## Files Changed
1. `pyproject.toml` - Updated pytest configuration to include `--cov-fail-under=100` flag

## Smell Category Addressed
- **Consistency Error** (MEDIUM): Coverage threshold mismatch between pyproject.toml and other files

## Rationale for Change
The documentation smell report identified a consistency error: "States coverage threshold of 4% but other files require 80%. Found thresholds: 80%, 4%". 

The actual issue was:
1. The GitHub CI workflow (`.github/workflows/ci.yml:66`) uses `--cov-fail-under=100`
2. The copilot instructions (`.github/copilot-instructions.md:966`) specify `pytest --cov-fail-under=100`
3. The pytest configuration in `pyproject.toml` only had `--cov=henchman --cov-report=term-missing` without the `--cov-fail-under` flag
4. The project requires 100% test coverage according to quality requirements

The "4%" mentioned in the smell report was a false positive - it was referring to line 65: `"pytest-cov>=4.0",` which is the version requirement for pytest-cov, not a coverage threshold.

## Changes Made
Updated the `addopts` in `[tool.pytest.ini_options]` section of `pyproject.toml`:
- From: `addopts = "-v --cov=henchman --cov-report=term-missing"`
- To: `addopts = "-v --cov=henchman --cov-report=term-missing --cov-fail-under=100"`

## Technical Details
The `--cov-fail-under=100` flag ensures that pytest will fail if test coverage falls below 100%. This aligns with:
1. The GitHub CI workflow configuration
2. The copilot instructions quality requirements
3. The project's stated requirement of 100% test coverage

## What to Verify
1. The pytest configuration now matches the GitHub CI workflow
2. Running `pytest` locally will fail if coverage drops below 100%
3. The consistency error in the smell report should be resolved
4. All documentation references to coverage thresholds are now consistent (100%)

## Testing Instructions
To test the fix:
```bash
# Run pytest with the new configuration
pytest

# Verify that coverage failure threshold is set to 100%
pytest --help | grep -A2 "cov-fail-under"

# Check that the configuration is loaded correctly
pytest --co
```

## Next Priority
The next highest-priority issues are:
1. **Missing Docstring** in `src/henchman/agents/config.py:1` (module missing docstring)
2. **Missing Docstring** in `src/henchman/agents/identity.py:1` (module missing docstring)
3. **Incomplete Docstring** in `src/henchman/agents/metrics.py:91` ('PerformanceMetrics.track_file_access' has 1 parameter but no Args section)
4. **Incomplete Docstring** in `src/henchman/agents/metrics.py:95` ('PerformanceMetrics.track_tool_usage' has 1 parameter but no Args section)
5. **Incomplete Docstring** in `src/henchman/agents/metrics.py:152` ('ToolMetrics.track_tool_call' has 2 parameters but no Args section)