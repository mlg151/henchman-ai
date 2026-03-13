# Code Smell Report — ✅ A (Score: 92.3/100)

_Scanned: /home/matthew/mlg-cli/src/henchman_  

_Generated: 2026-03-05T14:52:10.880819+00:00_

## Executive Summary

| Metric | Value |
|:-------|------:|
| **Overall Grade** | ✅ A |
| **Overall Score** | 92.3/100 |
| **Files Scanned** | 193 |
| **Total Lines (non-blank)** | 38,221 |
| **Total Smells** | 519 |
| **Avg Maintainability Index** | 100.0 |
| **Avg Cyclomatic Complexity** | 0.0 |

### Smells by Severity

| Severity | Count |
|:---------|------:|
| low | 352 |
| medium | 146 |
| high | 21 |

### Smells by Category

| Category | Count |
|:---------|------:|
| Missing Type Hint | 153 |
| Duplicate Code | 129 |
| Long Method | 69 |
| Feature Envy | 60 |
| Primitive Obsession | 37 |
| Deep Nesting | 32 |
| Magic Number | 29 |
| Large Class | 10 |

## 🎯 Prioritised Refactoring Queue

These are the highest-impact smells to address first:

1. **agents/delegation.py:907** — 🟠 HIGH — Duplicate Code  
   Function '_parse_completion_report' is an exact duplicate of 'parameters' at tools/builtins/file_edit.py:204  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

2. **cli/textual_messages.py:38** — 🟠 HIGH — Duplicate Code  
   Function '_str_payload' is an exact duplicate of 'request' at cli/textual_messages.py:83  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

3. **knowledge/scanner.py:332** — 🟠 HIGH — Long Method  
   Function 'scan_repository' has 100 lines (threshold: 30)  
   → _Extract Method — break this function into smaller, intention-revealing helper functions._

4. **metrics/exporter.py:80** — 🟠 HIGH — Duplicate Code  
   Function 'export_to_csv' is an exact duplicate of 'export_to_prometheus' at metrics/exporter.py:94  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

5. **tools/builtins/delegate.py:149** — 🟠 HIGH — Duplicate Code  
   Function 'parameters' is an exact duplicate of 'parameters' at tools/builtins/python_ast.py:53  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

6. **tools/builtins/delegate.py:149** — 🟠 HIGH — Duplicate Code  
   Function 'parameters' is an exact duplicate of 'parameters' at tools/builtins/shell.py:632  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

7. **tools/builtins/delegate.py:149** — 🟠 HIGH — Duplicate Code  
   Function 'parameters' is an exact duplicate of 'parameters' at tools/builtins/test_gen.py:341  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

8. **tools/builtins/delegate.py:149** — 🟠 HIGH — Duplicate Code  
   Function 'parameters' is an exact duplicate of 'parameters' at tools/builtins/traceback_parse.py:118  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

9. **tools/builtins/delegate.py:149** — 🟠 HIGH — Duplicate Code  
   Function 'parameters' is an exact duplicate of 'parameters' at tools/security/shell_secure.py:570  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

10. **tools/builtins/import_graph.py:586** — 🟠 HIGH — Duplicate Code  
   Function '_file_imports_module' is an exact duplicate of '_process_output' at tools/builtins/pytest_run.py:294  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

11. **tools/builtins/python_ast.py:53** — 🟠 HIGH — Duplicate Code  
   Function 'parameters' is an exact duplicate of 'parameters' at tools/builtins/shell.py:632  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

12. **tools/builtins/python_ast.py:53** — 🟠 HIGH — Duplicate Code  
   Function 'parameters' is an exact duplicate of 'parameters' at tools/builtins/test_gen.py:341  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

13. **tools/builtins/python_ast.py:53** — 🟠 HIGH — Duplicate Code  
   Function 'parameters' is an exact duplicate of 'parameters' at tools/builtins/traceback_parse.py:118  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

14. **tools/builtins/python_ast.py:53** — 🟠 HIGH — Duplicate Code  
   Function 'parameters' is an exact duplicate of 'parameters' at tools/security/shell_secure.py:570  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

15. **tools/builtins/shell.py:632** — 🟠 HIGH — Duplicate Code  
   Function 'parameters' is an exact duplicate of 'parameters' at tools/builtins/test_gen.py:341  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._


## 📊 Files Ranked by Quality

| Rank | File | Grade | Score | Smells | LOC | MI | Avg CC |
|-----:|:-----|:------|------:|-------:|----:|---:|-------:|
| 1 | tools/builtins/delegate.py | 🔶 D | 65.0 | 5 | 150 | 100 | 0.0 |
| 2 | tools/builtins/shell.py | 🔶 D | 69.9 | 8 | 530 | 100 | 0.0 |
| 3 | cli/commands/__init__.py | ⚠️ C | 72.0 | 8 | 161 | 100 | 0.0 |
| 4 | extensions/plugin_manager.py | ⚠️ C | 72.0 | 17 | 295 | 100 | 0.0 |
| 5 | tools/builtins/python_ast.py | ⚠️ C | 72.0 | 4 | 90 | 100 | 0.0 |
| 6 | cli/textual_screens.py | ⚠️ C | 74.1 | 17 | 373 | 100 | 0.0 |
| 7 | agents/ledger.py | ⚠️ C | 76.2 | 14 | 176 | 100 | 0.0 |
| 8 | extensions/plugin_database.py | ⚠️ C | 76.2 | 14 | 155 | 100 | 0.0 |
| 9 | mcp/tool.py | ⚠️ C | 76.2 | 11 | 82 | 100 | 0.0 |
| 10 | mcp/manager.py | ⚠️ C | 76.9 | 12 | 167 | 100 | 0.0 |

## 📁 Per-File Details

_Showing 20 worst files. 173 additional files omitted._

### tools/builtins/delegate.py — 🔶 D (65.0/100)

LOC: 150 | Classes: 2 | Functions: 1 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 149 | 🟠 HIGH | Duplicate Code | Function 'parameters' is an exact duplicate of 'parameters' at tools/builtins/python_ast.py:53 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 149 | 🟠 HIGH | Duplicate Code | Function 'parameters' is an exact duplicate of 'parameters' at tools/builtins/shell.py:632 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 149 | 🟠 HIGH | Duplicate Code | Function 'parameters' is an exact duplicate of 'parameters' at tools/builtins/test_gen.py:341 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 149 | 🟠 HIGH | Duplicate Code | Function 'parameters' is an exact duplicate of 'parameters' at tools/builtins/traceback_parse.py:118 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 149 | 🟠 HIGH | Duplicate Code | Function 'parameters' is an exact duplicate of 'parameters' at tools/security/shell_secure.py:570 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |

### tools/builtins/shell.py — 🔶 D (69.9/100)

LOC: 530 | Classes: 3 | Functions: 19 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 632 | 🟠 HIGH | Duplicate Code | Function 'parameters' is an exact duplicate of 'parameters' at tools/builtins/test_gen.py:341 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 632 | 🟠 HIGH | Duplicate Code | Function 'parameters' is an exact duplicate of 'parameters' at tools/builtins/traceback_parse.py:118 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 632 | 🟠 HIGH | Duplicate Code | Function 'parameters' is an exact duplicate of 'parameters' at tools/security/shell_secure.py:570 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 475 | 🟡 MEDIUM | Long Method | Function '_run_sudo_with_pty' has 76 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 515 | 🟢 LOW | Deep Nesting | Nesting depth 4 in '_run_sudo_with_pty' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 523 | 🟢 LOW | Deep Nesting | Nesting depth 4 in '_run_sudo_with_pty' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 642 | 🟢 LOW | Long Method | Function 'execute' has 36 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 642 | 🟢 LOW | Primitive Obsession | Function 'execute' has 3 primitive-typed parameters: command: Name(id='str', ctx=Load()), timeout: BinOp(left=Name(id='int', ctx=Load()), op=BitOr(), right=Constant(value=None)), cwd: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |

### cli/commands/__init__.py — ⚠️ C (72.0/100)

LOC: 161 | Classes: 4 | Functions: 2 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 138 | 🟡 MEDIUM | Duplicate Code | Function '__init__' is 100% similar to '__init__' at extensions/manager.py:150 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 142 | 🟡 MEDIUM | Duplicate Code | Function 'register' is 100% similar to 'register_theme' at cli/console.py:372 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 150 | 🟡 MEDIUM | Duplicate Code | Function 'get' is 100% similar to 'get' at extensions/manager.py:177 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 150 | 🟡 MEDIUM | Duplicate Code | Function 'get' is 100% similar to 'get' at tools/registry.py:108 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 161 | 🟡 MEDIUM | Duplicate Code | Function 'get_commands' is 100% similar to 'list_extensions' at extensions/manager.py:188 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 161 | 🟡 MEDIUM | Duplicate Code | Function 'get_commands' is 100% similar to 'get_server_names' at mcp/manager.py:38 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 161 | 🟡 MEDIUM | Duplicate Code | Function 'get_commands' is 100% similar to 'list_providers' at providers/registry.py:47 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 161 | 🟡 MEDIUM | Duplicate Code | Function 'get_commands' is 100% similar to 'list_tools' at tools/registry.py:127 | Extract Shared Function — identify the common logic and parameterise the differences. |

### extensions/plugin_manager.py — ⚠️ C (72.0/100)

LOC: 295 | Classes: 1 | Functions: 0 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 113 | 🟡 MEDIUM | Primitive Obsession | Function 'search_plugins' has 4 primitive-typed parameters: query: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), page: Name(id='int', ctx=Load()), page_size: Name(id='int', ctx=Load()), category: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 170 | 🟡 MEDIUM | Long Method | Function 'install_plugin' has 57 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 30 | 🟢 LOW | Large Class | Class 'PluginManager' spans 382 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
| 47 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 68 | 🟢 LOW | Missing Type Hint | Function 'initialize' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 104 | 🟢 LOW | Missing Type Hint | Function 'close' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 113 | 🟢 LOW | Missing Type Hint | Function 'search_plugins' has incomplete type hints: 1/5 params untyped | Add Type Annotations for all parameters and return type. |
| 146 | 🟢 LOW | Missing Type Hint | Function 'get_plugin_info' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 170 | 🟢 LOW | Missing Type Hint | Function 'install_plugin' has incomplete type hints: 1/4 params untyped | Add Type Annotations for all parameters and return type. |
| 170 | 🟢 LOW | Primitive Obsession | Function 'install_plugin' has 3 primitive-typed parameters: plugin_name: Name(id='str', ctx=Load()), version: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), confirm_permissions: Name(id='bool', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 249 | 🟢 LOW | Missing Type Hint | Function 'uninstall_plugin' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 284 | 🟢 LOW | Missing Type Hint | Function 'update_plugin' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 323 | 🟢 LOW | Missing Type Hint | Function 'check_updates' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 345 | 🟢 LOW | Long Method | Function 'scan_security' has 31 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 345 | 🟢 LOW | Missing Type Hint | Function 'scan_security' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |

_... and 2 more smells._

### tools/builtins/python_ast.py — ⚠️ C (72.0/100)

LOC: 90 | Classes: 1 | Functions: 0 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 53 | 🟠 HIGH | Duplicate Code | Function 'parameters' is an exact duplicate of 'parameters' at tools/builtins/shell.py:632 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 53 | 🟠 HIGH | Duplicate Code | Function 'parameters' is an exact duplicate of 'parameters' at tools/builtins/test_gen.py:341 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 53 | 🟠 HIGH | Duplicate Code | Function 'parameters' is an exact duplicate of 'parameters' at tools/builtins/traceback_parse.py:118 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 53 | 🟠 HIGH | Duplicate Code | Function 'parameters' is an exact duplicate of 'parameters' at tools/security/shell_secure.py:570 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |

### cli/textual_screens.py — ⚠️ C (74.1/100)

LOC: 373 | Classes: 4 | Functions: 0 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 87 | 🟡 MEDIUM | Duplicate Code | Function '__init__' is 95% similar to '__init__' at mcp/client.py:33 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 87 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 96 | 🟢 LOW | Long Method | Function 'compose' has 35 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 96 | 🟢 LOW | Missing Type Hint | Function 'compose' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 138 | 🟢 LOW | Missing Type Hint | Function '_build_params_label' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 155 | 🟢 LOW | Missing Type Hint | Function 'on_button_pressed' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 163 | 🟢 LOW | Missing Type Hint | Function 'action_approve' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 167 | 🟢 LOW | Missing Type Hint | Function 'action_deny' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 195 | 🟢 LOW | Missing Type Hint | Function 'compose' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 229 | 🟢 LOW | Missing Type Hint | Function 'on_button_pressed' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 264 | 🟢 LOW | Missing Type Hint | Function 'compose' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 344 | 🟢 LOW | Missing Type Hint | Function 'on_button_pressed' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 398 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 408 | 🟢 LOW | Missing Type Hint | Function 'compose' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 435 | 🟢 LOW | Missing Type Hint | Function '_build_entries' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |

_... and 2 more smells._

### agents/ledger.py — ⚠️ C (76.2/100)

LOC: 176 | Classes: 4 | Functions: 0 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 79 | 🟡 MEDIUM | Duplicate Code | Function 'add_checklist_item' is 92% similar to 'add_delegation' at agents/ledger.py:110 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 124 | 🟡 MEDIUM | Duplicate Code | Function 'complete_delegation' is 100% similar to 'fail_delegation' at agents/ledger.py:137 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 79 | 🟢 LOW | Missing Type Hint | Function 'add_checklist_item' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 92 | 🟢 LOW | Missing Type Hint | Function 'check_item' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 110 | 🟢 LOW | Missing Type Hint | Function 'add_delegation' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 124 | 🟢 LOW | Missing Type Hint | Function 'complete_delegation' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 135 | 🟢 LOW | Magic Number | Magic number 500 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 137 | 🟢 LOW | Missing Type Hint | Function 'fail_delegation' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 148 | 🟢 LOW | Magic Number | Magic number 500 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 150 | 🟢 LOW | Missing Type Hint | Function 'mark_verified' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 162 | 🟢 LOW | Missing Type Hint | Function 'mission_recap' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 189 | 🟢 LOW | Long Method | Function 'render' has 49 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 189 | 🟢 LOW | Missing Type Hint | Function 'render' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 240 | 🟢 LOW | Magic Number | Magic number 120 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |

### extensions/plugin_database.py — ⚠️ C (76.2/100)

LOC: 155 | Classes: 1 | Functions: 0 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 97 | 🟡 MEDIUM | Feature Envy | Method 'PluginDatabase._row_to_installation' accesses 'PC' 6 times but 'self' only 0 times | Move Method — consider moving '_row_to_installation' to the class that owns 'PC'. |
| 154 | 🟡 MEDIUM | Feature Envy | Method 'PluginDatabase._build_installation_params' accesses 'installation' 6 times but 'self' only 0 times | Move Method — consider moving '_build_installation_params' to the class that owns 'installation'. |
| 28 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 36 | 🟢 LOW | Missing Type Hint | Function 'initialize' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 36 | 🟢 LOW | Feature Envy | Method 'PluginDatabase.initialize' accesses 'conn' 3 times but 'self' only 1 times | Move Method — consider moving 'initialize' to the class that owns 'conn'. |
| 36 | 🟢 LOW | Feature Envy | Method 'PluginDatabase.initialize' accesses 'cursor' 3 times but 'self' only 1 times | Move Method — consider moving 'initialize' to the class that owns 'cursor'. |
| 70 | 🟢 LOW | Missing Type Hint | Function 'load_installations' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 86 | 🟢 LOW | Deep Nesting | Nesting depth 4 in 'load_installations' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 97 | 🟢 LOW | Missing Type Hint | Function '_row_to_installation' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 131 | 🟢 LOW | Missing Type Hint | Function 'save_installation' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 131 | 🟢 LOW | Feature Envy | Method 'PluginDatabase.save_installation' accesses 'conn' 3 times but 'self' only 2 times | Move Method — consider moving 'save_installation' to the class that owns 'conn'. |
| 154 | 🟢 LOW | Missing Type Hint | Function '_build_installation_params' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 180 | 🟢 LOW | Missing Type Hint | Function 'delete_installation' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 180 | 🟢 LOW | Feature Envy | Method 'PluginDatabase.delete_installation' accesses 'conn' 3 times but 'self' only 1 times | Move Method — consider moving 'delete_installation' to the class that owns 'conn'. |

### mcp/tool.py — ⚠️ C (76.2/100)

LOC: 82 | Classes: 1 | Functions: 0 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 23 | 🟡 MEDIUM | Duplicate Code | Function '__init__' is 100% similar to '__init__' at tools/builtins/rag_search.py:28 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 23 | 🟡 MEDIUM | Duplicate Code | Function '__init__' is 100% similar to '__init__' at utils/message_clusterer.py:24 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 45 | 🟡 MEDIUM | Duplicate Code | Function 'name' is 100% similar to 'description' at mcp/tool.py:54 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 63 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 94% similar to 'parameters' at tools/builtins/grep.py:584 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 23 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/5 params untyped | Add Type Annotations for all parameters and return type. |
| 45 | 🟢 LOW | Missing Type Hint | Function 'name' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 54 | 🟢 LOW | Missing Type Hint | Function 'description' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 63 | 🟢 LOW | Missing Type Hint | Function 'parameters' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 72 | 🟢 LOW | Missing Type Hint | Function 'kind' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 85 | 🟢 LOW | Missing Type Hint | Function 'execute' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 85 | 🟢 LOW | Feature Envy | Method 'McpTool.execute' accesses 'result' 4 times but 'self' only 2 times | Move Method — consider moving 'execute' to the class that owns 'result'. |

### mcp/manager.py — ⚠️ C (76.9/100)

LOC: 167 | Classes: 1 | Functions: 0 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 38 | 🟡 MEDIUM | Duplicate Code | Function 'get_server_names' is 100% similar to 'list_providers' at providers/registry.py:47 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 38 | 🟡 MEDIUM | Duplicate Code | Function 'get_server_names' is 100% similar to 'list_tools' at tools/registry.py:127 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 124 | 🟡 MEDIUM | Feature Envy | Method 'McpManager._build_logging_env' accesses 'command' 5 times but 'self' only 0 times | Move Method — consider moving '_build_logging_env' to the class that owns 'command'. |
| 26 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 38 | 🟢 LOW | Missing Type Hint | Function 'get_server_names' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 46 | 🟢 LOW | Missing Type Hint | Function 'is_trusted' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 59 | 🟢 LOW | Missing Type Hint | Function 'connect_all' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 83 | 🟢 LOW | Missing Type Hint | Function 'disconnect_all' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 90 | 🟢 LOW | Missing Type Hint | Function 'get_all_tools' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 98 | 🟢 LOW | Missing Type Hint | Function 'call_tool' has incomplete type hints: 1/4 params untyped | Add Type Annotations for all parameters and return type. |
| 124 | 🟢 LOW | Long Method | Function '_build_logging_env' has 35 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 176 | 🟢 LOW | Feature Envy | Method 'McpManager.create_from_settings' accesses 'server_config' 4 times but 'self' only 0 times | Move Method — consider moving 'create_from_settings' to the class that owns 'server_config'. |

### agents/presets.py — ⚠️ C (77.6/100)

LOC: 194 | Classes: 1 | Functions: 7 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 123 | 🟡 MEDIUM | Duplicate Code | Function '_create_planner_config' is 100% similar to '_create_explorer_config' at agents/presets.py:145 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 123 | 🟡 MEDIUM | Duplicate Code | Function '_create_planner_config' is 100% similar to '_create_engineer_config' at agents/presets.py:167 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 123 | 🟡 MEDIUM | Duplicate Code | Function '_create_planner_config' is 100% similar to '_create_data_engineer_config' at agents/presets.py:188 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 145 | 🟡 MEDIUM | Duplicate Code | Function '_create_explorer_config' is 100% similar to '_create_engineer_config' at agents/presets.py:167 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 145 | 🟡 MEDIUM | Duplicate Code | Function '_create_explorer_config' is 100% similar to '_create_data_engineer_config' at agents/presets.py:188 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 167 | 🟡 MEDIUM | Duplicate Code | Function '_create_engineer_config' is 100% similar to '_create_data_engineer_config' at agents/presets.py:188 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 49 | 🟢 LOW | Primitive Obsession | Function '_create_agent_config' has 3 primitive-typed parameters: name: Name(id='str', ctx=Load()), role: Name(id='str', ctx=Load()), description: Name(id='str', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |

### agents/metrics_reporter.py — ⚠️ C (79.7/100)

LOC: 251 | Classes: 2 | Functions: 4 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 32 | 🟡 MEDIUM | Duplicate Code | Function '_build_metrics_section' is 100% similar to '_format_findings' at tools/builtins/dead_code.py:597 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 257 | 🟡 MEDIUM | Duplicate Code | Function '_format_documentation_coverage' is 94% similar to '_str_payload' at cli/textual_messages.py:38 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 257 | 🟡 MEDIUM | Duplicate Code | Function '_format_documentation_coverage' is 94% similar to 'request' at cli/textual_messages.py:83 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 264 | 🟡 MEDIUM | Duplicate Code | Function '_format_tool_call_statistics' is 93% similar to 'list_themes' at cli/console.py:364 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 264 | 🟡 MEDIUM | Duplicate Code | Function '_format_tool_call_statistics' is 93% similar to 'list_auto_approve_policies' at tools/registry.py:171 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 191 | 🟢 LOW | Feature Envy | Method 'MetricsReporter._format_task_completion_time' accesses 'time' 4 times but 'self' only 2 times | Move Method — consider moving '_format_task_completion_time' to the class that owns 'time'. |
| 202 | 🟢 LOW | Magic Number | Magic number 60 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |

### utils/tokens.py — ⚠️ C (79.7/100)

LOC: 125 | Classes: 1 | Functions: 1 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 139 | 🟡 MEDIUM | Feature Envy | Method 'TokenCounter.count_messages' accesses 'msg' 5 times but 'self' only 0 times | Move Method — consider moving 'count_messages' to the class that owns 'msg'. |
| 70 | 🟢 LOW | Missing Type Hint | Function '_get_encoding' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 70 | 🟢 LOW | Feature Envy | Method 'TokenCounter._get_encoding' accesses 'tiktoken' 3 times but 'self' only 0 times | Move Method — consider moving '_get_encoding' to the class that owns 'tiktoken'. |
| 70 | 🟢 LOW | Feature Envy | Method 'TokenCounter._get_encoding' accesses 'cls' 3 times but 'self' only 0 times | Move Method — consider moving '_get_encoding' to the class that owns 'cls'. |
| 98 | 🟢 LOW | Missing Type Hint | Function 'count_text' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 115 | 🟢 LOW | Missing Type Hint | Function 'truncate_text' has incomplete type hints: 1/4 params untyped | Add Type Annotations for all parameters and return type. |
| 115 | 🟢 LOW | Primitive Obsession | Function 'truncate_text' has 3 primitive-typed parameters: text: Name(id='str', ctx=Load()), max_tokens: Name(id='int', ctx=Load()), model: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 139 | 🟢 LOW | Long Method | Function 'count_messages' has 39 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 139 | 🟢 LOW | Missing Type Hint | Function 'count_messages' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 139 | 🟢 LOW | Feature Envy | Method 'TokenCounter.count_messages' accesses 'encoding' 4 times but 'self' only 0 times | Move Method — consider moving 'count_messages' to the class that owns 'encoding'. |
| 158 | 🟢 LOW | Magic Number | Magic number 3 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 181 | 🟢 LOW | Magic Number | Magic number 10 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 188 | 🟢 LOW | Magic Number | Magic number 3 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |

### agents/pool.py — 👍 B (80.4/100)

LOC: 195 | Classes: 1 | Functions: 1 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 65 | 🟡 MEDIUM | Primitive Obsession | Function '__init__' has 5 primitive-typed parameters: environment_context: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), intelligent_context: Name(id='bool', ctx=Load()), importance_threshold: Name(id='float', ctx=Load()), cluster_similarity_threshold: Name(id='float', ctx=Load()), adaptive_compression: Name(id='bool', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 105 | 🟡 MEDIUM | Long Method | Function 'get_agent' has 63 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 65 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/11 params untyped | Add Type Annotations for all parameters and return type. |
| 105 | 🟢 LOW | Missing Type Hint | Function 'get_agent' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 181 | 🟢 LOW | Missing Type Hint | Function 'get_identity' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 202 | 🟢 LOW | Missing Type Hint | Function 'list_agents' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 202 | 🟢 LOW | Feature Envy | Method 'AgentPool.list_agents' accesses 'config' 3 times but 'self' only 1 times | Move Method — consider moving 'list_agents' to the class that owns 'config'. |
| 219 | 🟢 LOW | Missing Type Hint | Function 'list_active_agents' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 227 | 🟢 LOW | Missing Type Hint | Function 'reset_agent' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 239 | 🟢 LOW | Missing Type Hint | Function 'reset_all' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 248 | 🟢 LOW | Missing Type Hint | Function 'shutdown' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |

### mcp/client.py — 👍 B (81.8/100)

LOC: 194 | Classes: 4 | Functions: 0 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 33 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 42 | 🟢 LOW | Long Method | Function 'write' has 46 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 42 | 🟢 LOW | Missing Type Hint | Function 'write' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 42 | 🟢 LOW | Feature Envy | Method 'FilteredStream.write' accesses 're' 3 times but 'self' only 1 times | Move Method — consider moving 'write' to the class that owns 're'. |
| 42 | 🟢 LOW | Feature Envy | Method 'FilteredStream.write' accesses 'line' 3 times but 'self' only 1 times | Move Method — consider moving 'write' to the class that owns 'line'. |
| 133 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/4 params untyped | Add Type Annotations for all parameters and return type. |
| 149 | 🟢 LOW | Missing Type Hint | Function 'is_connected' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 153 | 🟢 LOW | Long Method | Function 'connect' has 34 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 153 | 🟢 LOW | Missing Type Hint | Function 'connect' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 195 | 🟢 LOW | Missing Type Hint | Function 'disconnect' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 204 | 🟢 LOW | Missing Type Hint | Function 'discover_tools' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 224 | 🟢 LOW | Missing Type Hint | Function 'get_tools' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 232 | 🟢 LOW | Missing Type Hint | Function 'call_tool' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |

### utils/compression_strategy.py — 👍 B (81.8/100)

LOC: 221 | Classes: 4 | Functions: 0 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 64 | 🟡 MEDIUM | Long Method | Function 'compress' has 51 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 233 | 🟡 MEDIUM | Feature Envy | Method 'CompressionStrategyFactory.create_for_conversation_type' accesses 'CSC' 6 times but 'self' only 0 times | Move Method — consider moving 'create_for_conversation_type' to the class that owns 'CSC'. |
| 102 | 🟢 LOW | Deep Nesting | Nesting depth 4 in 'compress' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 111 | 🟢 LOW | Deep Nesting | Nesting depth 4 in 'compress' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 121 | 🟢 LOW | Deep Nesting | Nesting depth 4 in 'compress' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 128 | 🟢 LOW | Deep Nesting | Nesting depth 4 in 'compress' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 158 | 🟢 LOW | Feature Envy | Method 'CompressionStrategy._generate_cluster_summary' accesses 'msg' 4 times but 'self' only 0 times | Move Method — consider moving '_generate_cluster_summary' to the class that owns 'msg'. |
| 204 | 🟢 LOW | Deep Nesting | Nesting depth 4 in '_preserve_tool_sequences_in_cluster' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 207 | 🟢 LOW | Feature Envy | Method 'CompressionStrategy._preserve_code_blocks_in_cluster' accesses 'msg' 4 times but 'self' only 0 times | Move Method — consider moving '_preserve_code_blocks_in_cluster' to the class that owns 'msg'. |
| 233 | 🟢 LOW | Long Method | Function 'create_for_conversation_type' has 42 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |

### knowledge/scanner.py — 👍 B (83.2/100)

LOC: 325 | Classes: 0 | Functions: 11 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 332 | 🟠 HIGH | Long Method | Function 'scan_repository' has 100 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 40 | 🟡 MEDIUM | Duplicate Code | Function '_path_to_entity_id' is 100% similar to '_slugify' at knowledge/store.py:70 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 253 | 🟡 MEDIUM | Long Method | Function '_find_import_target_optimized' has 55 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 173 | 🟢 LOW | Long Method | Function '_build_module_lookup' has 44 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 253 | 🟢 LOW | Primitive Obsession | Function '_find_import_target_optimized' has 3 primitive-typed parameters: mod: Name(id='str', ctx=Load()), file_eid: Name(id='str', ctx=Load()), file_module: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |

### metrics/exporter.py — 👍 B (83.2/100)

LOC: 96 | Classes: 1 | Functions: 0 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 80 | 🟠 HIGH | Duplicate Code | Function 'export_to_csv' is an exact duplicate of 'export_to_prometheus' at metrics/exporter.py:94 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 21 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 29 | 🟢 LOW | Missing Type Hint | Function 'export_to_json' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 70 | 🟢 LOW | Missing Type Hint | Function '_get_current_timestamp' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 80 | 🟢 LOW | Missing Type Hint | Function 'export_to_csv' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 94 | 🟢 LOW | Missing Type Hint | Function 'export_to_prometheus' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 108 | 🟢 LOW | Missing Type Hint | Function 'export_summary' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 124 | 🟢 LOW | Missing Type Hint | Function 'get_available_formats' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |

### config/context.py — 👍 B (83.9/100)

LOC: 160 | Classes: 1 | Functions: 0 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 132 | 🟡 MEDIUM | Long Method | Function 'discover_files' has 51 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 43 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/4 params untyped | Add Type Annotations for all parameters and return type. |
| 68 | 🟢 LOW | Missing Type Hint | Function 'filename' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 72 | 🟢 LOW | Missing Type Hint | Function '_find_git_root' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 88 | 🟢 LOW | Missing Type Hint | Function '_load_gitignore_patterns' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 88 | 🟢 LOW | Feature Envy | Method 'ContextLoader._load_gitignore_patterns' accesses 'line' 3 times but 'self' only 0 times | Move Method — consider moving '_load_gitignore_patterns' to the class that owns 'line'. |
| 109 | 🟢 LOW | Missing Type Hint | Function '_is_ignored' has incomplete type hints: 1/4 params untyped | Add Type Annotations for all parameters and return type. |
| 132 | 🟢 LOW | Missing Type Hint | Function 'discover_files' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 185 | 🟢 LOW | Deep Nesting | Nesting depth 4 in 'discover_files' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 190 | 🟢 LOW | Missing Type Hint | Function 'load' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |

### utils/validation.py — 👍 B (83.9/100)

LOC: 180 | Classes: 0 | Functions: 4 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 94 | 🟠 HIGH | Long Method | Function 'repair_message_sequence' has 84 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 12 | 🟡 MEDIUM | Long Method | Function 'validate_message_sequence' has 62 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 43 | 🟢 LOW | Deep Nesting | Nesting depth 4 in 'validate_message_sequence' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 53 | 🟢 LOW | Deep Nesting | Nesting depth 4 in 'validate_message_sequence' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 130 | 🟢 LOW | Deep Nesting | Nesting depth 4 in 'repair_message_sequence' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 231 | 🟢 LOW | Magic Number | Magic number 50 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |

## ✨ Clean Files (63 files with no smells)

<details><summary>Click to expand</summary>

- __init__.py — ✅ A
- __main__.py — ✅ A
- agents/__init__.py — ✅ A
- agents/config.py — ✅ A
- agents/orchestrator_components.py — ✅ A
- agents/orchestrator_delegation_ctrl.py — ✅ A
- agents/orchestrator_events.py — ✅ A
- agents/orchestrator_init.py — ✅ A
- agents/orchestrator_loop.py — ✅ A
- agents/orchestrator_prompts.py — ✅ A
- agents/orchestrator_run.py — ✅ A
- agents/orchestrator_tech_lead.py — ✅ A
- agents/orchestrator_timeout.py — ✅ A
- agents/orchestrator_tools.py — ✅ A
- agents/orchestrator_turns.py — ✅ A
- agents/orchestrator_types.py — ✅ A
- agents/orchestrator_validation.py — ✅ A
- api/__init__.py — ✅ A
- api/auth.py — ✅ A
- api/endpoints/__init__.py — ✅ A
- cli/__init__.py — ✅ A
- cli/app.py — ✅ A
- cli/commands/model.py — ✅ A
- cli/commands/plan.py — ✅ A
- cli/commands/rag.py — ✅ A
- cli/commands/team.py — ✅ A
- cli/input.py — ✅ A
- cli/prompts.py — ✅ A
- cli/stream_event_handlers.py — ✅ A
- config/__init__.py — ✅ A
- config/settings.py — ✅ A
- core/__init__.py — ✅ A
- core/agent_stall.py — ✅ A
- core/events.py — ✅ A
- core/session.py — ✅ A
- core/session_branch.py — ✅ A
- core/session_export.py — ✅ A
- core/session_helpers.py — ✅ A
- core/session_manager.py — ✅ A
- core/session_merge.py — ✅ A
- core/session_templates.py — ✅ A
- extensions/__init__.py — ✅ A
- extensions/constants.py — ✅ A
- extensions/models.py — ✅ A
- extensions/plugin_registry_client.py — ✅ A
- knowledge/__init__.py — ✅ A
- knowledge/models.py — ✅ A
- mcp/__init__.py — ✅ A
- metrics/__init__.py — ✅ A
- metrics/models.py — ✅ A
- providers/__init__.py — ✅ A
- providers/utils.py — ✅ A
- rag/__init__.py — ✅ A
- tools/__init__.py — ✅ A
- tools/builtins/__init__.py — ✅ A
- tools/builtins/dead_code.py — ✅ A
- tools/builtins/kg_common.py — ✅ A
- tools/builtins/pytest_run.py — ✅ A
- tools/security/__init__.py — ✅ A
- tools/utils.py — ✅ A
- utils/__init__.py — ✅ A
- utils/lazy_import.py — ✅ A
- version.py — ✅ A

</details>

---

_Report generated by XP Code Smell Detector. Smells are static heuristics — use judgement when prioritising fixes._
