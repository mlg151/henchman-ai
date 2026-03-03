# Documentation Improvement Record

## Date/Time
2026-03-03T11:30:00Z

## Files Changed
1. `CONTRIBUTING.md` - Updated pytest coverage command to include `--cov-fail-under=100` flag

## Smell Category Addressed
- **Consistency Error** (MEDIUM): Coverage threshold inconsistency between documentation files

## Rationale for Change
The documentation smell report identified a consistency error regarding coverage thresholds. The issue was that different files had inconsistent pytest coverage commands:

1. `pyproject.toml`: `--cov-fail-under=100` (line 138)
2. `.github/workflows/ci.yml`: `--cov-fail-under=100` (line 39)  
3. `CONTRIBUTING.md`: `pytest --cov=henchman --cov-report=term-missing` (line 57) - **MISSING `--cov-fail-under=100`**
4. `RELEASE_CHECKLIST.md`: `--cov-fail-under=100` (line 9)
5. `README.md`: `pytest --cov=henchman --cov-report=html` (line 238) - Shows HTML report (different use case)

The CONTRIBUTING.md file was missing the `--cov-fail-under=100` flag that enforces 100% test coverage, which is a project requirement. This created inconsistency between the contributing guidelines and the actual CI requirements.

## Changes Made

### Updated `CONTRIBUTING.md` line 57:
- Changed: `pytest --cov=henchman --cov-report=term-missing`
- To: `pytest --cov=henchman --cov-report=term-missing --cov-fail-under=100`

This aligns the contributing guidelines with the actual project requirements and CI configuration.

## Technical Details
- **Issue**: Documentation inconsistency for coverage enforcement
- **Root cause**: CONTRIBUTING.md showed a coverage command without the fail-under threshold
- **Impact**: Contributors might run tests without realizing 100% coverage is required
- **Fix**: Added `--cov-fail-under=100` flag to match CI configuration
- **Note**: The smell report's mention of "4% coverage threshold" was a misinterpretation of `pytest-cov>=4.0` (package version), not an actual threshold

## What to Verify
1. CONTRIBUTING.md now shows the complete coverage command with `--cov-fail-under=100`
2. The command matches what's in `pyproject.toml` and `.github/workflows/ci.yml`
3. No other documentation inconsistencies were introduced
4. The change accurately reflects the project's 100% test coverage requirement

## Testing Instructions
To verify the fix:
```bash
# Check the updated line in CONTRIBUTING.md
grep -n "pytest --cov" CONTRIBUTING.md

# Verify consistency across files
grep -n "--cov-fail-under=100" pyproject.toml .github/workflows/ci.yml CONTRIBUTING.md RELEASE_CHECKLIST.md

# Run the doc smell detector to confirm this issue is resolved
python -m scripts.doc_smell_detector . --skip-docstrings -f json | grep -i "consistency"
```

## Next Priority
The next highest-priority issues from the smell report are:
1. **Incomplete Docstring** in `src/henchman/agents/orchestrator_tools.py:56` ('ToolController.process_pending_tool_calls' has 4 parameters but no Args section)
2. **Incomplete Docstring** in `src/henchman/agents/orchestrator_validation.py:23` ('should_check_thinking' has 2 parameters but no Args section)
3. **Incomplete Docstring** in `src/henchman/agents/orchestrator_validation.py:32` ('handle_valid_thinking' has 2 parameters but no Args section)
4. **Incomplete Docstring** in `src/henchman/agents/orchestrator_validation.py:45` ('handle_missing_thinking' has 1 parameter but no Args section)

## Notes
This improvement addresses a genuine documentation consistency issue. The CONTRIBUTING.md file is a critical document for new contributors, and having accurate, consistent instructions is essential for maintaining project quality standards.

The fix ensures that:
1. Contributors see the correct command that enforces 100% coverage
2. The documentation matches the actual CI requirements
3. There's no confusion about the project's test coverage expectations

Note that README.md shows `--cov-report=html` without `--cov-fail-under=100`, which is acceptable as it demonstrates a different use case (generating HTML reports for visualization rather than CI enforcement). The key consistency issue was in CONTRIBUTING.md which should match the CI requirements exactly.