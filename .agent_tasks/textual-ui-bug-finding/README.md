# Textual UI Bug Finding Report

**Date**: 2025-03-21  
**Engineer**: Henchman-AI Engineer  
**Scope**: Comprehensive bug finding on textual UI components (textual_app.py, textual_bridge.py, textual_config.py, textual_messages.py, textual_screens.py, textual_widgets.py)

## Methodology
- **Static Analysis**: Manual code review for logic errors, error handling gaps, boundary conditions
- **Dynamic Analysis**: Running existing test suites to identify failures
- **Exploratory Testing**: Analyzing code paths for potential crashes
- **Boundary Value Analysis**: Checking input validation and edge cases
- **Negative Testing**: Identifying error handling for invalid operations

## Summary of Findings
Found 10 distinct bugs/issues ranging from critical error handling gaps to minor code smells. Below are the 5 most significant bugs documented per requirements.

---

## Bug 1: Unhandled Exceptions in Provider Initialization

**File**: `src/henchman/cli/textual_app.py`  
**Method**: `_resolve_provider_from_env()` (lines 275-301)  
**Severity**: **Major** (could cause app crash on startup)

### Description
When auto-detecting provider from environment, only `_get_provider()` is wrapped in try-except. If `load_settings()`, `TextualConfig()`, `format_environment_block()`, or `gather_environment()` raise exceptions, the app crashes during initialization.

### Steps to Reproduce
1. Create a corrupted settings file that causes `load_settings()` to raise an exception
2. Launch the textual UI
3. App crashes with unhandled exception during initialization

### Expected Behavior
All initialization steps should have proper error handling with graceful fallbacks or informative error messages.

### Actual Behavior
App crashes with unhandled exception if any initialization step after `_get_provider()` fails.

### Suggested Fix
Wrap the entire method body in try-except or add individual error handling for each initialization step. Provide user-friendly error messages and fallback to safe defaults.

---

## Bug 2: Silent Error Suppression in Context Tree Loading

**File**: `src/henchman/cli/textual_app.py`  
**Method**: `_fill_context_tree()` (lines 658-689)  
**Severity**: **Minor** (debugging difficulty)

### Description
When context loading fails and trying to add an error message to the tree, `contextlib.suppress(Exception)` silently suppresses ALL exceptions, including those from `tree.root.add_leaf()`. This makes debugging impossible if the tree widget itself has issues.

### Steps to Reproduce
1. Cause `ContextLoader().discover_files()` to raise an exception
2. Also have `tree.root.add_leaf()` fail (e.g., tree is None)
3. Error is completely swallowed with no indication of failure

### Expected Behavior
Errors should be logged or at least one error should be visible to help debugging.

### Actual Behavior
All exceptions are silently suppressed, making debugging context loading issues difficult.

### Suggested Fix
Remove `contextlib.suppress(Exception)` or at least log the exception before suppressing. Consider using a more specific exception catch.

---

## Bug 3: Silent History Persistence Failure

**File**: `src/henchman/cli/textual_app.py`  
**Method**: `_persist_history_entry()` (lines 707-724)  
**Severity**: **Minor** (user experience issue)

### Description
When saving command history to file, `except Exception: pass` silently ignores ALL file I/O errors (permission denied, disk full, etc.). Users won't know their history isn't being saved.

### Steps to Reproduce
1. Set history file to a read-only location
2. Enter commands in the UI
3. Exit and restart - history is lost with no warning

### Expected Behavior
Users should be notified if history cannot be saved, or at least the error should be logged.

### Actual Behavior
History saving failures are completely silent.

### Suggested Fix
Log the exception or show a non-intrusive status message. Consider retrying with a fallback location.

---

## Bug 4: Potential UI Blocking on Large File Reads

**File**: `src/henchman/cli/textual_app.py`  
**Method**: `on_tree_node_selected()` (lines 1312-1331)  
**Severity**: **Major** (UI responsiveness)

### Description
When clicking a context file in the tree, `path.read_text()` reads the entire file into memory synchronously. For large files, this blocks the UI thread. Also, if `query_one("#chat-pane", ChatPane)` fails in the exception handler, an unhandled exception occurs.

### Steps to Reproduce
1. Add a very large file (100MB+) to context
2. Click the file in the context tree
3. UI becomes unresponsive while reading file

### Expected Behavior
Large file reads should be asynchronous or size-limited to prevent UI blocking.

### Actual Behavior
Synchronous file read blocks UI thread; exception handler could also crash.

### Suggested Fix
1. Use `asyncio.to_thread()` for file reading
2. Add size limit check before reading
3. Add error handling for `query_one()` in exception handler

---

## Bug 5: Inconsistent State on Provider Switch Failure

**File**: `src/henchman/cli/textual_app.py`  
**Method**: `_switch_provider()` (lines 986-1012)  
**Severity**: **Critical** (state corruption risk)

### Description
When switching providers fails partway through, the app state becomes inconsistent. If `registry.create()` fails after `self.provider = new` but before `_initialize_core_components()`, the provider is changed but core components aren't reinitialized. Also, `query_one()` in exception handler could fail.

### Steps to Reproduce
1. Trigger provider switch with invalid provider name
2. Have `registry.create()` raise exception after provider assignment
3. App state is inconsistent; `query_one()` could also fail

### Expected Behavior
Provider switch should be atomic: either fully succeeds or fully fails with state rolled back.

### Actual Behavior
Partial state changes leave app in inconsistent state; exception handler could crash.

### Suggested Fix
1. Use transactional pattern: validate first, then apply changes
2. Store old provider and revert on failure
3. Add try-except around `query_one()` in exception handler
4. Consider using a state machine for provider transitions

---

## Additional Issues Found (Brief)

6. **Bug 6**: `_format_tool_result()` could create huge strings from large dicts
7. **Bug 7**: `HenchmanTextArea` accesses private method `_navigate_history` without error handling
8. **Bug 8**: `ToolMessage` stores unused `tool_call` parameter
9. **Bug 9**: `ConfirmToolScreen._build_params_label()` could fail on circular references
10. **Bug 10**: `EventBridge.forward_events()` could expose traceback in error messages

## Verification
- All existing textual UI tests pass (12/12 in test_textual_app.py, 12/12 in test_textual_search.py)
- Static analysis revealed error handling gaps and potential crashes
- Boundary analysis identified file size and memory issues

## Recommendations
1. **Error Handling Audit**: Review all `except Exception:` clauses for proper logging/feedback
2. **Async Operations**: Move file I/O and long operations off UI thread
3. **State Management**: Implement transactional patterns for critical operations
4. **Input Validation**: Add size limits for file reads and result formatting
5. **Testing**: Add negative tests for error conditions identified

## Next Steps
Prioritize fixes for critical/major bugs (#1, #4, #5) first, then address minor issues. Consider adding integration tests for error scenarios.