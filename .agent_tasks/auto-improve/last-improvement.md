# Session Command Refactoring - 2026-03-01T10:15:00

## Target File: `src/henchman/cli/commands/session.py`

### Identified Issues:
1. **Large Class** (380 lines, threshold 300) - Extract Class needed
2. **Feature Envy** (8 instances) - Methods access `ctx` excessively
3. **Complex Function** - `_list` has cyclomatic complexity 11
4. **Missing Type Hints** - Multiple methods incomplete

### Refactoring Plan:
1. **Extract Class**: Create `SessionCommandHelper` for argument parsing and validation
2. **Introduce Parameter Objects**: Create `SessionOperationParams` for common parameter groups
3. **Extract Methods**: Break down `_list` into smaller, focused methods
4. **Add Type Hints**: Complete all method signatures
5. **Simplify Constants**: Group related constants

### Expected Benefits:
- Reduced class size (< 300 lines)
- Lower cyclomatic complexity (< 10 per method)
- Better separation of concerns
- Improved maintainability
- Full type hint coverage

### Testing Strategy:
- All existing tests must pass
- No change to public API
- Verify command functionality unchanged