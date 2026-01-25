# Immediate Action Plan for CI Fix

## Hour 1-2: Source Restoration
1. Restore clean `agent.py`:
   ```bash
   git checkout HEAD -- src/henchman/core/agent.py
   # Fix get_tool_schemas() -> get_declarations()
   ```

2. Restore clean `repl.py`:
   ```bash
   git checkout HEAD -- src/henchman/cli/repl.py
   # Fix Agent instantiation to include tool_registry
   ```

3. Create missing command modules:
   ```bash
   # Create minimal commands/__init__.py with CommandContext
   # Create CommandRegistry stub
   ```

## Hour 3-5: Test Fixes
1. Fix unit tests first:
   ```bash
   python -m pytest tests/cli/commands/ --tb=short -x
   ```

2. Update test fixtures to pass tool_registry:
   ```python
   # In test files:
   tool_registry = ToolRegistry()
   agent = Agent(provider, tool_registry=tool_registry, ...)
   ```

## Hour 6-7: Quality Gates
1. Auto-fix linting:
   ```bash
   ruff check --fix src/ tests/
   ```

2. Fix type errors:
   ```bash
   mypy src/
   ```

## Hour 8-10: Final Validation
1. Run full test suite:
   ```bash
   python -m pytest tests/ --cov=henchman --cov-report=term-missing
   ```

2. Run CI pipeline:
   ```bash
   ./scripts/ci.sh
   ```
