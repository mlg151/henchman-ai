# Documentation Improvement Record

## Date/Time
2026-03-03T05:35:00Z

## Files Changed
1. `RELEASE_CHECKLIST.md` - Updated coverage requirement from 80% to 100%

## Smell Category Addressed
- **Consistency Error** (MEDIUM): Coverage threshold mismatch between RELEASE_CHECKLIST.md and other files

## Rationale for Change
The documentation smell report identified a consistency error: "States coverage threshold of 80% but other files require 100%. Found thresholds: 100%, 80%, 4%".

The actual issue was:
1. The RELEASE_CHECKLIST.md file stated "Ensure test coverage > 80%"
2. The project actually requires 100% test coverage according to:
   - Copilot instructions (.github/copilot-instructions.md): "100% test coverage - All code must be tested"
   - CI workflow (.github/workflows/ci.yml): Uses `--cov-fail-under=100`
   - Pyproject.toml: Already fixed in previous improvement to include `--cov-fail-under=100`
   - Quality requirements: Project mandates 100% test coverage

## Changes Made
Updated line 9 in RELEASE_CHECKLIST.md:
- From: `- [ ] Ensure test coverage > 80%: `pytest --cov=henchman --cov-report=term-missing``
- To: `- [ ] Ensure test coverage = 100%: `pytest --cov=henchman --cov-report=term-missing --cov-fail-under=100``

## Technical Details
The change ensures:
1. Consistency across all project documentation
2. The release checklist matches actual project requirements
3. The command includes the `--cov-fail-under=100` flag for explicit failure threshold
4. Clear expectation that coverage must be exactly 100% (not "greater than 80%")

## What to Verify
1. All documentation now consistently states 100% coverage requirement
2. The release checklist provides the correct command for checking coverage
3. No other files reference 80% coverage threshold (checked via grep)
4. The consistency error should be resolved in the next smell report

## Testing Instructions
To verify the fix:
```bash
# Check that RELEASE_CHECKLIST.md now has correct coverage requirement
grep -n "test coverage" RELEASE_CHECKLIST.md

# Verify no other documentation files mention 80% coverage
grep -r "80%" docs/ *.md 2>/dev/null | grep -v ".agent_tasks" | grep -v "log"

# Test the actual coverage check command
pytest --cov=henchman --cov-report=term-missing --cov-fail-under=100
```

## Next Priority
The next highest-priority issues are:
1. **Missing Docstring** in `src/henchman/agents/config.py:1` (module missing docstring)
2. **Missing Docstring** in `src/henchman/agents/identity.py:1` (module missing docstring)
3. **Incomplete Docstring** in `src/henchman/agents/metrics.py:91` ('PerformanceMetrics.track_file_access' has 1 parameter but no Args section)
4. **Incomplete Docstring** in `src/henchman/agents/metrics.py:95` ('PerformanceMetrics.track_tool_usage' has 1 parameter but no Args section)
5. **Incomplete Docstring** in `src/henchman/agents/metrics.py:152` ('ToolMetrics.track_tool_call' has 2 parameters but no Args section)

## Notes on mkdocs.yml Issue
The smell report listed "No mkdocs.yml found" as HIGH priority, but this appears to be a false positive:
1. mkdocs.yml file exists and is properly configured
2. The file contains valid mkdocs configuration with Python YAML tags (`!!python/name:pymdownx.superfences.fence_code_format`)
3. These tags are valid for mkdocs but cause issues with strict YAML parsers
4. The documentation site builds correctly with the current configuration
5. This is not an actual documentation issue that needs fixing