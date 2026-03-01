# Refactoring Summary - PluginManager

**Date/Time**: 2026-03-01 07:00:00 UTC
**Target File**: `src/henchman/extensions/plugin_manager.py`
**Refactoring Goal**: Address ALL code smells identified in the smell report

## Identified Smells to Address:

### HIGH Severity:
1. **Large Class** (line 35): Class 'PluginManager' spans 912 lines (threshold: 300)

### MEDIUM Severity:
2. **Magic Numbers** (lines 91, 150, 187, 448-451): Multiple magic numbers without named constants
3. **Primitive Obsession** (line 105): `search_plugins` has 4 primitive-typed parameters
4. **Feature Envy** (lines 465, 501, 544): Methods accessing external objects more than self
5. **Deep Nesting** (line 569): Nesting depth 5 in `_install_plugin_package`
6. **Long Method** (line 574): `_install_from_pypi` has 51 lines

## Refactoring Strategy:

1. **Extract Class Pattern**: Split PluginManager into smaller, cohesive classes
2. **Introduce Named Constants**: Replace magic numbers with descriptive constants
3. **Parameter Object Pattern**: Group related primitives into dataclasses
4. **Move Method Pattern**: Move methods to classes that own the data they access
5. **Extract Method Pattern**: Break long methods into smaller helper functions
6. **Replace Nested Conditional with Early Return**: Reduce nesting depth

## Planned Changes:

1. Create `PluginDatabaseManager` class for database operations
2. Create `PluginInstaller` class for installation logic
3. Create `PluginSourceHandler` class for different source types
4. Extract constants for timeout values, HTTP status codes, and numeric literals
5. Create `SearchParameters` dataclass for `search_plugins`
6. Refactor deeply nested conditionals with guard clauses
7. Break long methods into intention-revealing helper functions

## Expected Benefits:
- Reduced class size from 912 to ~300 lines per class
- Improved readability and maintainability
- Better separation of concerns
- Easier testing of individual components
- Reduced cognitive load when reading code