# Code Smell Report — ⚠️ C (Score: 70.7/100)

_Scanned: /home/matthew/mlg-cli/src/henchman_  

_Generated: 2026-03-03T18:00:30.264785+00:00_

## Executive Summary

| Metric | Value |
|:-------|------:|
| **Overall Grade** | ⚠️ C |
| **Overall Score** | 70.7/100 |
| **Files Scanned** | 191 |
| **Total Lines (non-blank)** | 36,143 |
| **Total Smells** | 1042 |
| **Avg Maintainability Index** | 71.4 |
| **Avg Cyclomatic Complexity** | 13.6 |

### Smells by Severity

| Severity | Count |
|:---------|------:|
| low | 757 |
| medium | 254 |
| high | 31 |

### Smells by Category

| Category | Count |
|:---------|------:|
| Missing Type Hint | 368 |
| Feature Envy | 204 |
| Duplicate Code | 158 |
| Long Method | 106 |
| Magic Number | 68 |
| Deep Nesting | 52 |
| Primitive Obsession | 43 |
| Complex Function | 27 |
| Large Class | 16 |

## 🎯 Prioritised Refactoring Queue

These are the highest-impact smells to address first:

1. **cli/app.py:656** — 🟠 HIGH — Primitive Obsession  
   Function 'chat_command' has 8 primitive-typed parameters: prompt: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), agent: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), team: Name(id='bool', ctx=Load()), output_format: Name(id='str', ctx=Load()), plan: Name(id='bool', ctx=Load()), yes: Name(id='bool', ctx=Load()), tui: Name(id='bool', ctx=Load()), debug: Name(id='bool', ctx=Load())  
   → _Introduce Parameter Object — group related primitives into a dataclass or NamedTuple._

2. **cli/commands/plan.py:41** — 🟠 HIGH — Feature Envy  
   Method 'PlanCommand.execute' accesses 'ctx' 11 times but 'self' only 0 times  
   → _Move Method — consider moving 'execute' to the class that owns 'ctx'._

3. **cli/json_output.py:43** — 🟠 HIGH — Duplicate Code  
   Function 'render' is an exact duplicate of 'render_stream_json' at cli/json_output.py:77  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

4. **cli/textual_widgets.py:923** — 🟠 HIGH — Duplicate Code  
   Function 'add_user_message' is an exact duplicate of 'add_system_message' at cli/textual_widgets.py:931  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

5. **cli/textual_widgets.py:923** — 🟠 HIGH — Duplicate Code  
   Function 'add_user_message' is an exact duplicate of 'add_error_message' at cli/textual_widgets.py:939  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

6. **cli/textual_widgets.py:931** — 🟠 HIGH — Duplicate Code  
   Function 'add_system_message' is an exact duplicate of 'add_error_message' at cli/textual_widgets.py:939  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

7. **knowledge/scanner.py:198** — 🟠 HIGH — Long Method  
   Function 'scan_repository' has 94 lines (threshold: 30)  
   → _Extract Method — break this function into smaller, intention-revealing helper functions._

8. **knowledge/store.py:548** — 🟠 HIGH — Feature Envy  
   Method 'KnowledgeStore.format_entity_for_llm' accesses 'entity' 11 times but 'self' only 1 times  
   → _Move Method — consider moving 'format_entity_for_llm' to the class that owns 'entity'._

9. **metrics/exporter.py:80** — 🟠 HIGH — Duplicate Code  
   Function 'export_to_csv' is an exact duplicate of 'export_to_prometheus' at metrics/exporter.py:94  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

10. **tools/builtins/code_format.py:49** — 🟠 HIGH — Long Method  
   Function 'execute' has 94 lines (threshold: 30)  
   → _Extract Method — break this function into smaller, intention-revealing helper functions._

11. **tools/builtins/delegate.py:157** — 🟠 HIGH — Duplicate Code  
   Function 'parameters' is an exact duplicate of 'parameters' at tools/builtins/file_edit.py:158  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

12. **tools/builtins/delegate.py:157** — 🟠 HIGH — Duplicate Code  
   Function 'parameters' is an exact duplicate of 'parameters' at tools/builtins/git_ops.py:254  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

13. **tools/builtins/delegate.py:157** — 🟠 HIGH — Duplicate Code  
   Function 'parameters' is an exact duplicate of 'parameters' at tools/builtins/python_ast.py:53  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

14. **tools/builtins/delegate.py:157** — 🟠 HIGH — Duplicate Code  
   Function 'parameters' is an exact duplicate of 'parameters' at tools/builtins/shell.py:639  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

15. **tools/builtins/diff_view.py:79** — 🟠 HIGH — Primitive Obsession  
   Function 'execute' has 7 primitive-typed parameters: path: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), staged: Name(id='bool', ctx=Load()), compare: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), stat: Name(id='bool', ctx=Load()), name_only: Name(id='bool', ctx=Load()), context_lines: BinOp(left=Name(id='int', ctx=Load()), op=BitOr(), right=Constant(value=None)), cwd: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None))  
   → _Introduce Parameter Object — group related primitives into a dataclass or NamedTuple._


## 📊 Files Ranked by Quality

| Rank | File | Grade | Score | Smells | LOC | MI | Avg CC |
|-----:|:-----|:------|------:|-------:|----:|---:|-------:|
| 1 | tools/security/shell_secure.py | ❌ F | 15.4 | 32 | 359 | 51 | 15.5 |
| 2 | extensions/plugin_installer.py | ❌ F | 41.3 | 32 | 320 | 54 | 0.0 |
| 3 | knowledge/store.py | ❌ F | 41.7 | 23 | 470 | 46 | 0.0 |
| 4 | extensions/manager.py | ❌ F | 42.7 | 24 | 159 | 63 | 0.0 |
| 5 | cli/textual_widgets.py | ❌ F | 43.1 | 7 | 956 | 27 | 0.0 |
| 6 | tools/builtins/grep.py | ❌ F | 44.2 | 16 | 494 | 47 | 0.0 |
| 7 | cli/console.py | ❌ F | 46.2 | 14 | 670 | 42 | 0.0 |
| 8 | tools/builtins/test_gen.py | ❌ F | 46.4 | 16 | 362 | 52 | 11.0 |
| 9 | cli/commands/theme.py | ❌ F | 47.6 | 23 | 196 | 61 | 0.0 |
| 10 | providers/openai_compat.py | ❌ F | 47.7 | 27 | 303 | 59 | 0.0 |

## 📁 Per-File Details

_Showing 20 worst files. 171 additional files omitted._

### tools/security/shell_secure.py — ❌ F (15.4/100)

LOC: 359 | Classes: 3 | Functions: 0 | MI: 51 | Avg CC: 15.5

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 413 | 🟠 HIGH | Feature Envy | Method 'SecureShellTool._apply_security_level' accesses 'adjusted' 25 times but 'self' only 0 times | Move Method — consider moving '_apply_security_level' to the class that owns 'adjusted'. |
| 42 | 🟡 MEDIUM | Magic Number | Magic number 4096 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 43 | 🟡 MEDIUM | Magic Number | Magic number 50 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 114 | 🟡 MEDIUM | Complex Function | Function 'validate_command' has cyclomatic complexity 11 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 197 | 🟡 MEDIUM | Complex Function | Function '_validate_parsed_command' has cyclomatic complexity 20 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 438 | 🟡 MEDIUM | Magic Number | Magic number 1024 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 439 | 🟡 MEDIUM | Magic Number | Magic number 20 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 454 | 🟡 MEDIUM | Magic Number | Magic number 2048 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 455 | 🟡 MEDIUM | Magic Number | Magic number 30 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 464 | 🟡 MEDIUM | Magic Number | Magic number 8192 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 465 | 🟡 MEDIUM | Magic Number | Magic number 100 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 54 | 🟢 LOW | Long Method | Function '__post_init__' has 42 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 54 | 🟢 LOW | Missing Type Hint | Function '__post_init__' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 106 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 114 | 🟢 LOW | Long Method | Function 'validate_command' has 35 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |

_... and 17 more smells._

### extensions/plugin_installer.py — ❌ F (41.3/100)

LOC: 320 | Classes: 1 | Functions: 0 | MI: 54 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 25 | 🟢 LOW | Large Class | Class 'PluginInstaller' spans 404 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
| 28 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 36 | 🟢 LOW | Missing Type Hint | Function 'install_plugin_package' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 68 | 🟢 LOW | Missing Type Hint | Function '_install_from_pypi' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 97 | 🟢 LOW | Missing Type Hint | Function '_install_package_with_pip' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 97 | 🟢 LOW | Feature Envy | Method 'PluginInstaller._install_package_with_pip' accesses 'asyncio' 3 times but 'self' only 0 times | Move Method — consider moving '_install_package_with_pip' to the class that owns 'asyncio'. |
| 132 | 🟢 LOW | Missing Type Hint | Function '_copy_installed_files' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 132 | 🟢 LOW | Feature Envy | Method 'PluginInstaller._copy_installed_files' accesses 'item' 4 times but 'self' only 0 times | Move Method — consider moving '_copy_installed_files' to the class that owns 'item'. |
| 148 | 🟢 LOW | Missing Type Hint | Function '_install_from_github' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 148 | 🟢 LOW | Feature Envy | Method 'PluginInstaller._install_from_github' accesses 'metadata' 3 times but 'self' only 1 times | Move Method — consider moving '_install_from_github' to the class that owns 'metadata'. |
| 181 | 🟢 LOW | Missing Type Hint | Function '_install_from_git' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 200 | 🟢 LOW | Long Method | Function '_clone_and_copy_git_repo' has 40 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 200 | 🟢 LOW | Missing Type Hint | Function '_clone_and_copy_git_repo' has incomplete type hints: 1/4 params untyped | Add Type Annotations for all parameters and return type. |
| 200 | 🟢 LOW | Feature Envy | Method 'PluginInstaller._clone_and_copy_git_repo' accesses 'asyncio' 3 times but 'self' only 0 times | Move Method — consider moving '_clone_and_copy_git_repo' to the class that owns 'asyncio'. |
| 200 | 🟢 LOW | Feature Envy | Method 'PluginInstaller._clone_and_copy_git_repo' accesses 'item' 3 times but 'self' only 0 times | Move Method — consider moving '_clone_and_copy_git_repo' to the class that owns 'item'. |

_... and 17 more smells._

### knowledge/store.py — ❌ F (41.7/100)

LOC: 470 | Classes: 1 | Functions: 8 | MI: 46 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 548 | 🟠 HIGH | Feature Envy | Method 'KnowledgeStore.format_entity_for_llm' accesses 'entity' 11 times but 'self' only 1 times | Move Method — consider moving 'format_entity_for_llm' to the class that owns 'entity'. |
| 107 | 🟡 MEDIUM | Duplicate Code | Function '_relation_to_edge_attrs' is 100% similar to '_format_tool_for_anthropic' at providers/anthropic.py:130 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 107 | 🟡 MEDIUM | Duplicate Code | Function '_relation_to_edge_attrs' is 100% similar to 'to_metadata' at rag/chunker.py:42 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 182 | 🟢 LOW | Large Class | Class 'KnowledgeStore' spans 422 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
| 182 | 🟢 LOW | Large Class | Class 'KnowledgeStore' has 23 methods (threshold: 20) | Split Class — group related methods into smaller collaborating classes. |
| 333 | 🟢 LOW | Missing Type Hint | Function 'search_entities' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 333 | 🟢 LOW | Feature Envy | Method 'KnowledgeStore.search_entities' accesses 'entity' 3 times but 'self' only 1 times | Move Method — consider moving 'search_entities' to the class that owns 'entity'. |
| 361 | 🟢 LOW | Missing Type Hint | Function 'add_observation' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 385 | 🟢 LOW | Missing Type Hint | Function 'add_relation' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 385 | 🟢 LOW | Feature Envy | Method 'KnowledgeStore.add_relation' accesses 'relation' 4 times but 'self' only 2 times | Move Method — consider moving 'add_relation' to the class that owns 'relation'. |
| 402 | 🟢 LOW | Missing Type Hint | Function 'get_relations' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 402 | 🟢 LOW | Feature Envy | Method 'KnowledgeStore.get_relations' accesses 'data' 4 times but 'self' only 2 times | Move Method — consider moving 'get_relations' to the class that owns 'data'. |
| 442 | 🟢 LOW | Missing Type Hint | Function 'remove_relation' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 460 | 🟢 LOW | Missing Type Hint | Function 'get_neighbors' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 485 | 🟢 LOW | Deep Nesting | Nesting depth 4 in 'get_neighbors' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |

_... and 8 more smells._

### extensions/manager.py — ❌ F (42.7/100)

LOC: 159 | Classes: 1 | Functions: 0 | MI: 63 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 68 | 🟡 MEDIUM | Duplicate Code | Function 'get' is 95% similar to 'get' at tools/registry.py:108 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 79 | 🟡 MEDIUM | Duplicate Code | Function 'list_extensions' is 100% similar to 'get_server_names' at mcp/manager.py:38 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 79 | 🟡 MEDIUM | Duplicate Code | Function 'list_extensions' is 100% similar to 'list_providers' at providers/registry.py:47 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 79 | 🟡 MEDIUM | Duplicate Code | Function 'list_extensions' is 100% similar to 'list_tools' at tools/registry.py:127 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 87 | 🟡 MEDIUM | Duplicate Code | Function 'get_all_tools' is 100% similar to 'get_all_commands' at extensions/manager.py:98 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 167 | 🟡 MEDIUM | Feature Envy | Method 'ExtensionManager._load_extension_from_file' accesses 'logger' 5 times but 'self' only 1 times | Move Method — consider moving '_load_extension_from_file' to the class that owns 'logger'. |
| 40 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 44 | 🟢 LOW | Missing Type Hint | Function 'register' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 44 | 🟢 LOW | Feature Envy | Method 'ExtensionManager.register' accesses 'extension' 3 times but 'self' only 1 times | Move Method — consider moving 'register' to the class that owns 'extension'. |
| 53 | 🟢 LOW | Missing Type Hint | Function 'unregister' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 68 | 🟢 LOW | Missing Type Hint | Function 'get' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 79 | 🟢 LOW | Missing Type Hint | Function 'list_extensions' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 87 | 🟢 LOW | Missing Type Hint | Function 'get_all_tools' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 98 | 🟢 LOW | Missing Type Hint | Function 'get_all_commands' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 109 | 🟢 LOW | Missing Type Hint | Function 'get_combined_context' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |

_... and 9 more smells._

### cli/textual_widgets.py — ❌ F (43.1/100)

LOC: 956 | Classes: 17 | Functions: 3 | MI: 27 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 923 | 🟠 HIGH | Duplicate Code | Function 'add_user_message' is an exact duplicate of 'add_system_message' at cli/textual_widgets.py:931 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 923 | 🟠 HIGH | Duplicate Code | Function 'add_user_message' is an exact duplicate of 'add_error_message' at cli/textual_widgets.py:939 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 931 | 🟠 HIGH | Duplicate Code | Function 'add_system_message' is an exact duplicate of 'add_error_message' at cli/textual_widgets.py:939 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 914 | 🟡 MEDIUM | Duplicate Code | Function '_add_message_with_prefix' is 100% similar to 'add_user_message' at cli/textual_widgets.py:923 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 914 | 🟡 MEDIUM | Duplicate Code | Function '_add_message_with_prefix' is 100% similar to 'add_system_message' at cli/textual_widgets.py:931 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 914 | 🟡 MEDIUM | Duplicate Code | Function '_add_message_with_prefix' is 100% similar to 'add_error_message' at cli/textual_widgets.py:939 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 1027 | 🟡 MEDIUM | Duplicate Code | Function 'add_thinking_message' is 94% similar to 'save' at core/session_manager_base.py:102 | Extract Shared Function — identify the common logic and parameterise the differences. |

### tools/builtins/grep.py — ❌ F (44.2/100)

LOC: 494 | Classes: 6 | Functions: 0 | MI: 47 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 490 | 🟠 HIGH | Primitive Obsession | Function 'execute' has 10 primitive-typed parameters: pattern: Name(id='str', ctx=Load()), path: Name(id='str', ctx=Load()), ignore_case: Name(id='bool', ctx=Load()), line_numbers: Name(id='bool', ctx=Load()), glob: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), context_before: Name(id='int', ctx=Load()), context_after: Name(id='int', ctx=Load()), invert_match: Name(id='bool', ctx=Load()), whole_word: Name(id='bool', ctx=Load()), count_only: Name(id='bool', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 545 | 🟠 HIGH | Feature Envy | Method 'GrepTool._execute_with_params' accesses 'params' 10 times but 'self' only 3 times | Move Method — consider moving '_execute_with_params' to the class that owns 'params'. |
| 167 | 🟡 MEDIUM | Primitive Obsession | Function '_validate_and_setup' has 5 primitive-typed parameters: pattern: Name(id='str', ctx=Load()), path: Name(id='str', ctx=Load()), ignore_case: Name(id='bool', ctx=Load()), whole_word: Name(id='bool', ctx=Load()), glob: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 238 | 🟡 MEDIUM | Feature Envy | Method 'FileSearcher._search_single_file' accesses 'config' 6 times but 'self' only 3 times | Move Method — consider moving '_search_single_file' to the class that owns 'config'. |
| 428 | 🟡 MEDIUM | Long Method | Function '_build_parameters_schema' has 54 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 54 | 🟢 LOW | Long Method | Function 'format_context_block' has 32 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 54 | 🟢 LOW | Feature Envy | Method 'ResultFormatter.format_context_block' accesses 'config' 4 times but 'self' only 0 times | Move Method — consider moving 'format_context_block' to the class that owns 'config'. |
| 54 | 🟢 LOW | Feature Envy | Method 'ResultFormatter.format_context_block' accesses 'result' 3 times but 'self' only 0 times | Move Method — consider moving 'format_context_block' to the class that owns 'result'. |
| 148 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: missing return type | Add Type Annotations for all parameters and return type. |
| 151 | 🟢 LOW | Feature Envy | Method 'FileSearcher._collect_files' accesses 'target' 3 times but 'self' only 0 times | Move Method — consider moving '_collect_files' to the class that owns 'target'. |
| 167 | 🟢 LOW | Feature Envy | Method 'FileSearcher._validate_and_setup' accesses 're' 4 times but 'self' only 1 times | Move Method — consider moving '_validate_and_setup' to the class that owns 're'. |
| 238 | 🟢 LOW | Long Method | Function '_search_single_file' has 39 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 320 | 🟢 LOW | Deep Nesting | Nesting depth 4 in '_count_matches' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 322 | 🟢 LOW | Deep Nesting | Nesting depth 4 in '_count_matches' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 336 | 🟢 LOW | Long Method | Function 'search_files' has 47 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |

_... and 1 more smells._

### cli/console.py — ❌ F (46.2/100)

LOC: 670 | Classes: 9 | Functions: 4 | MI: 42 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 348 | 🟡 MEDIUM | Duplicate Code | Function 'list_themes' is 100% similar to 'list_auto_approve_policies' at tools/registry.py:171 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 433 | 🟡 MEDIUM | Duplicate Code | Function 'success' is 100% similar to 'info' at cli/console.py:443 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 433 | 🟡 MEDIUM | Duplicate Code | Function 'success' is 100% similar to 'warning' at cli/console.py:453 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 433 | 🟡 MEDIUM | Duplicate Code | Function 'success' is 100% similar to 'error' at cli/console.py:463 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 443 | 🟡 MEDIUM | Duplicate Code | Function 'info' is 100% similar to 'warning' at cli/console.py:453 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 443 | 🟡 MEDIUM | Duplicate Code | Function 'info' is 100% similar to 'error' at cli/console.py:463 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 453 | 🟡 MEDIUM | Duplicate Code | Function 'warning' is 100% similar to 'error' at cli/console.py:463 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 770 | 🟡 MEDIUM | Duplicate Code | Function '__init__' is 93% similar to '__init__' at cli/ui_renderer.py:79 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 377 | 🟢 LOW | Large Class | Class 'OutputRenderer' spans 388 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
| 377 | 🟢 LOW | Large Class | Class 'OutputRenderer' has 26 methods (threshold: 20) | Split Class — group related methods into smaller collaborating classes. |
| 473 | 🟢 LOW | Feature Envy | Method 'OutputRenderer._print_status_message' accesses 'params' 4 times but 'self' only 3 times | Move Method — consider moving '_print_status_message' to the class that owns 'params'. |
| 558 | 🟢 LOW | Primitive Obsession | Function 'tool_result' has 3 primitive-typed parameters: content: Name(id='str', ctx=Load()), success: Name(id='bool', ctx=Load()), error: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 641 | 🟢 LOW | Deep Nesting | Nesting depth 4 in 'tree' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 696 | 🟢 LOW | Feature Envy | Method 'OutputRenderer._render_diff' accesses 'params' 4 times but 'self' only 2 times | Move Method — consider moving '_render_diff' to the class that owns 'params'. |

### tools/builtins/test_gen.py — ❌ F (46.4/100)

LOC: 362 | Classes: 1 | Functions: 0 | MI: 52 | Avg CC: 11.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 34 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 92% similar to 'parameters' at tools/builtins/web_fetch.py:32 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 34 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 92% similar to 'parameters' at tools/builtins/web_search.py:27 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 34 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 96% similar to 'parameters' at tools/security/shell_secure.py:315 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 62 | 🟡 MEDIUM | Long Method | Function 'execute' has 58 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 139 | 🟡 MEDIUM | Feature Envy | Method 'TestGenTool._extract_class_methods' accesses 'ast' 5 times but 'self' only 2 times | Move Method — consider moving '_extract_class_methods' to the class that owns 'ast'. |
| 168 | 🟡 MEDIUM | Feature Envy | Method 'TestGenTool._extract_symbols' accesses 'ast' 5 times but 'self' only 3 times | Move Method — consider moving '_extract_symbols' to the class that owns 'ast'. |
| 272 | 🟡 MEDIUM | Long Method | Function '_generate_class_tests' has 65 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 272 | 🟡 MEDIUM | Complex Function | Function '_generate_class_tests' has cyclomatic complexity 11 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 12 | 🟢 LOW | Large Class | Class 'TestGenTool' spans 413 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
| 62 | 🟢 LOW | Primitive Obsession | Function 'execute' has 3 primitive-typed parameters: path: Name(id='str', ctx=Load()), output_path: Name(id='str', ctx=Load()), style: Name(id='str', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 139 | 🟢 LOW | Feature Envy | Method 'TestGenTool._extract_class_methods' accesses 'item' 3 times but 'self' only 2 times | Move Method — consider moving '_extract_class_methods' to the class that owns 'item'. |
| 168 | 🟢 LOW | Long Method | Function '_extract_symbols' has 31 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 168 | 🟢 LOW | Feature Envy | Method 'TestGenTool._extract_symbols' accesses 'node' 4 times but 'self' only 3 times | Move Method — consider moving '_extract_symbols' to the class that owns 'node'. |
| 197 | 🟢 LOW | Deep Nesting | Nesting depth 4 in '_extract_symbols' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 225 | 🟢 LOW | Feature Envy | Method 'TestGenTool._get_return_annotation' accesses 'ast' 3 times but 'self' only 0 times | Move Method — consider moving '_get_return_annotation' to the class that owns 'ast'. |

_... and 1 more smells._

### cli/commands/theme.py — ❌ F (47.6/100)

LOC: 196 | Classes: 1 | Functions: 0 | MI: 61 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 148 | 🟡 MEDIUM | Feature Envy | Method 'ThemeCommand._update_renderer_theme' accesses 'ctx' 7 times but 'self' only 0 times | Move Method — consider moving '_update_renderer_theme' to the class that owns 'ctx'. |
| 166 | 🟡 MEDIUM | Feature Envy | Method 'ThemeCommand._persist_theme_settings' accesses 'ctx' 6 times but 'self' only 0 times | Move Method — consider moving '_persist_theme_settings' to the class that owns 'ctx'. |
| 188 | 🟡 MEDIUM | Feature Envy | Method 'ThemeCommand._preview_theme' accesses 'console' 6 times but 'self' only 1 times | Move Method — consider moving '_preview_theme' to the class that owns 'console'. |
| 188 | 🟡 MEDIUM | Feature Envy | Method 'ThemeCommand._preview_theme' accesses 'preview_renderer' 6 times but 'self' only 1 times | Move Method — consider moving '_preview_theme' to the class that owns 'preview_renderer'. |
| 25 | 🟢 LOW | Missing Type Hint | Function 'name' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 34 | 🟢 LOW | Missing Type Hint | Function 'description' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 43 | 🟢 LOW | Missing Type Hint | Function 'usage' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 51 | 🟢 LOW | Missing Type Hint | Function 'execute' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 70 | 🟢 LOW | Deep Nesting | Nesting depth 4 in 'execute' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 76 | 🟢 LOW | Missing Type Hint | Function '_list_themes' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 76 | 🟢 LOW | Feature Envy | Method 'ThemeCommand._list_themes' accesses 'console' 4 times but 'self' only 1 times | Move Method — consider moving '_list_themes' to the class that owns 'console'. |
| 96 | 🟢 LOW | Missing Type Hint | Function '_set_theme' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 123 | 🟢 LOW | Missing Type Hint | Function '_print_set_theme_error' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 131 | 🟢 LOW | Missing Type Hint | Function '_validate_theme_name' has incomplete type hints: 1/4 params untyped | Add Type Annotations for all parameters and return type. |
| 148 | 🟢 LOW | Missing Type Hint | Function '_update_renderer_theme' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |

_... and 8 more smells._

### providers/openai_compat.py — ❌ F (47.7/100)

LOC: 303 | Classes: 1 | Functions: 0 | MI: 59 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 69 | 🟡 MEDIUM | Feature Envy | Method 'OpenAICompatibleProvider._format_message' accesses 'message' 5 times but 'self' only 0 times | Move Method — consider moving '_format_message' to the class that owns 'message'. |
| 32 | 🟢 LOW | Large Class | Class 'OpenAICompatibleProvider' spans 346 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
| 35 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/4 params untyped | Add Type Annotations for all parameters and return type. |
| 35 | 🟢 LOW | Primitive Obsession | Function '__init__' has 3 primitive-typed parameters: api_key: Name(id='str', ctx=Load()), base_url: Name(id='str', ctx=Load()), default_model: Name(id='str', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 54 | 🟢 LOW | Missing Type Hint | Function 'name' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 58 | 🟢 LOW | Missing Type Hint | Function '_format_tool' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 58 | 🟢 LOW | Feature Envy | Method 'OpenAICompatibleProvider._format_tool' accesses 'tool' 3 times but 'self' only 0 times | Move Method — consider moving '_format_tool' to the class that owns 'tool'. |
| 69 | 🟢 LOW | Long Method | Function '_format_message' has 30 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 69 | 🟢 LOW | Missing Type Hint | Function '_format_message' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 69 | 🟢 LOW | Feature Envy | Method 'OpenAICompatibleProvider._format_message' accesses 'tc' 3 times but 'self' only 0 times | Move Method — consider moving '_format_message' to the class that owns 'tc'. |
| 102 | 🟢 LOW | Missing Type Hint | Function '_parse_finish_reason' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 107 | 🟢 LOW | Missing Type Hint | Function '_parse_tool_calls' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 107 | 🟢 LOW | Feature Envy | Method 'OpenAICompatibleProvider._parse_tool_calls' accesses 'tc' 3 times but 'self' only 0 times | Move Method — consider moving '_parse_tool_calls' to the class that owns 'tc'. |
| 128 | 🟢 LOW | Missing Type Hint | Function 'chat_completion_stream' has incomplete type hints: 1/4 params untyped | Add Type Annotations for all parameters and return type. |
| 161 | 🟢 LOW | Missing Type Hint | Function '_validate_messages' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |

_... and 12 more smells._

### cli/commands/builtins.py — ❌ F (48.2/100)

LOC: 226 | Classes: 4 | Functions: 1 | MI: 67 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 75 | 🟡 MEDIUM | Feature Envy | Method 'HelpCommand._show_specific_command_help' accesses 'ctx' 5 times but 'self' only 0 times | Move Method — consider moving '_show_specific_command_help' to the class that owns 'ctx'. |
| 234 | 🟡 MEDIUM | Feature Envy | Method 'ToolsCommand.execute' accesses 'ctx' 5 times but 'self' only 0 times | Move Method — consider moving 'execute' to the class that owns 'ctx'. |
| 26 | 🟢 LOW | Missing Type Hint | Function 'name' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 35 | 🟢 LOW | Missing Type Hint | Function 'description' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 44 | 🟢 LOW | Missing Type Hint | Function 'usage' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 52 | 🟢 LOW | Missing Type Hint | Function 'execute' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 67 | 🟢 LOW | Missing Type Hint | Function '_print_header' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 75 | 🟢 LOW | Missing Type Hint | Function '_show_specific_command_help' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 75 | 🟢 LOW | Feature Envy | Method 'HelpCommand._show_specific_command_help' accesses 'cmd' 3 times but 'self' only 0 times | Move Method — consider moving '_show_specific_command_help' to the class that owns 'cmd'. |
| 96 | 🟢 LOW | Missing Type Hint | Function '_list_all_commands' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 96 | 🟢 LOW | Feature Envy | Method 'HelpCommand._list_all_commands' accesses 'ctx' 3 times but 'self' only 0 times | Move Method — consider moving '_list_all_commands' to the class that owns 'ctx'. |
| 96 | 🟢 LOW | Feature Envy | Method 'HelpCommand._list_all_commands' accesses 'console' 4 times but 'self' only 0 times | Move Method — consider moving '_list_all_commands' to the class that owns 'console'. |
| 120 | 🟢 LOW | Missing Type Hint | Function 'name' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 129 | 🟢 LOW | Missing Type Hint | Function 'description' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 138 | 🟢 LOW | Missing Type Hint | Function 'usage' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |

_... and 12 more smells._

### agents/delegation.py — ❌ F (49.6/100)

LOC: 374 | Classes: 2 | Functions: 0 | MI: 56 | Avg CC: 13.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 202 | 🟡 MEDIUM | Feature Envy | Method 'DelegationRunner._prepare_delegation_execution' accesses 'params' 7 times but 'self' only 4 times | Move Method — consider moving '_prepare_delegation_execution' to the class that owns 'params'. |
| 306 | 🟡 MEDIUM | Complex Function | Function '_prepare_delegation_context' has cyclomatic complexity 14 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 404 | 🟡 MEDIUM | Complex Function | Function '_assemble_delegation_input' has cyclomatic complexity 12 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 42 | 🟢 LOW | Missing Type Hint | Function '__call__' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 54 | 🟢 LOW | Large Class | Class 'DelegationRunner' spans 446 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
| 69 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/7 params untyped | Add Type Annotations for all parameters and return type. |
| 88 | 🟢 LOW | Long Method | Function 'run_delegation' has 31 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 88 | 🟢 LOW | Missing Type Hint | Function 'run_delegation' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 141 | 🟢 LOW | Missing Type Hint | Function '_is_delegation_depth_exceeded' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 152 | 🟢 LOW | Missing Type Hint | Function '_yield_depth_exceeded_error' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 169 | 🟢 LOW | Missing Type Hint | Function '_get_target_agent_with_error_handling' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 185 | 🟢 LOW | Missing Type Hint | Function '_yield_agent_not_found_completion' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 202 | 🟢 LOW | Missing Type Hint | Function '_prepare_delegation_execution' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 236 | 🟢 LOW | Missing Type Hint | Function '_execute_delegation_loop' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 236 | 🟢 LOW | Feature Envy | Method 'DelegationRunner._execute_delegation_loop' accesses 'params' 4 times but 'self' only 2 times | Move Method — consider moving '_execute_delegation_loop' to the class that owns 'params'. |

_... and 7 more smells._

### cli/commands/chat.py — ❌ F (50.1/100)

LOC: 193 | Classes: 1 | Functions: 0 | MI: 60 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 57 | 🟡 MEDIUM | Duplicate Code | Function 'execute' is 100% similar to 'execute' at cli/commands/mcp.py:58 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 99 | 🟡 MEDIUM | Feature Envy | Method 'ChatCommand._list' accesses 'console' 5 times but 'self' only 0 times | Move Method — consider moving '_list' to the class that owns 'console'. |
| 31 | 🟢 LOW | Missing Type Hint | Function 'name' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 40 | 🟢 LOW | Missing Type Hint | Function 'description' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 49 | 🟢 LOW | Missing Type Hint | Function 'usage' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 57 | 🟢 LOW | Missing Type Hint | Function 'execute' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 77 | 🟢 LOW | Missing Type Hint | Function '_save' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 77 | 🟢 LOW | Feature Envy | Method 'ChatCommand._save' accesses 'ctx' 3 times but 'self' only 0 times | Move Method — consider moving '_save' to the class that owns 'ctx'. |
| 77 | 🟢 LOW | Feature Envy | Method 'ChatCommand._save' accesses 'console' 3 times but 'self' only 0 times | Move Method — consider moving '_save' to the class that owns 'console'. |
| 77 | 🟢 LOW | Feature Envy | Method 'ChatCommand._save' accesses 'session' 3 times but 'self' only 0 times | Move Method — consider moving '_save' to the class that owns 'session'. |
| 99 | 🟢 LOW | Missing Type Hint | Function '_list' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 99 | 🟢 LOW | Feature Envy | Method 'ChatCommand._list' accesses 'meta' 4 times but 'self' only 0 times | Move Method — consider moving '_list' to the class that owns 'meta'. |
| 118 | 🟢 LOW | Magic Number | Magic number 8 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 120 | 🟢 LOW | Magic Number | Magic number 10 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 124 | 🟢 LOW | Missing Type Hint | Function '_resume' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |

_... and 9 more smells._

### tools/builtins/diff_view.py — ❌ F (52.1/100)

LOC: 195 | Classes: 1 | Functions: 0 | MI: 69 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 79 | 🟠 HIGH | Primitive Obsession | Function 'execute' has 7 primitive-typed parameters: path: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), staged: Name(id='bool', ctx=Load()), compare: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), stat: Name(id='bool', ctx=Load()), name_only: Name(id='bool', ctx=Load()), context_lines: BinOp(left=Name(id='int', ctx=Load()), op=BitOr(), right=Constant(value=None)), cwd: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 79 | 🟠 HIGH | Primitive Obsession | Repeated primitive parameter group appears in: 'execute' (line 79), '_build_command' (line 116) | Replace Data Value with Object — create a shared data structure for this recurring parameter group. |
| 116 | 🟠 HIGH | Primitive Obsession | Function '_build_command' has 6 primitive-typed parameters: path: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), staged: Name(id='bool', ctx=Load()), compare: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), stat: Name(id='bool', ctx=Load()), name_only: Name(id='bool', ctx=Load()), context_lines: BinOp(left=Name(id='int', ctx=Load()), op=BitOr(), right=Constant(value=None)) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 156 | 🟡 MEDIUM | Long Method | Function '_run_git' has 50 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 18 | 🟢 LOW | Missing Type Hint | Function 'name' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 23 | 🟢 LOW | Missing Type Hint | Function 'description' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 33 | 🟢 LOW | Long Method | Function 'parameters' has 38 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 33 | 🟢 LOW | Missing Type Hint | Function 'parameters' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 75 | 🟢 LOW | Missing Type Hint | Function 'kind' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 79 | 🟢 LOW | Missing Type Hint | Function 'execute' has incomplete type hints: 1/9 params untyped | Add Type Annotations for all parameters and return type. |
| 116 | 🟢 LOW | Missing Type Hint | Function '_build_command' has incomplete type hints: 1/7 params untyped | Add Type Annotations for all parameters and return type. |
| 156 | 🟢 LOW | Missing Type Hint | Function '_run_git' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 156 | 🟢 LOW | Feature Envy | Method 'DiffViewTool._run_git' accesses 'asyncio' 4 times but 'self' only 0 times | Move Method — consider moving '_run_git' to the class that owns 'asyncio'. |
| 181 | 🟢 LOW | Magic Number | Magic number 30 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |

### tools/builtins/kg_query.py — ❌ F (52.7/100)

LOC: 223 | Classes: 1 | Functions: 1 | MI: 52 | Avg CC: 12.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 18 | 🟠 HIGH | Duplicate Code | Function '_find_git_root' is an exact duplicate of '_find_git_root' at tools/builtins/kg_update.py:48 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 44 | 🟠 HIGH | Duplicate Code | Function '__init__' is an exact duplicate of '__init__' at tools/builtins/kg_update.py:79 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 69 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 96% similar to 'parameters' at tools/builtins/kg_update.py:105 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 69 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 93% similar to 'parameters' at tools/builtins/test_gen.py:34 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 134 | 🟡 MEDIUM | Complex Function | Function 'execute' has cyclomatic complexity 12 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 69 | 🟢 LOW | Long Method | Function 'parameters' has 38 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 134 | 🟢 LOW | Long Method | Function 'execute' has 33 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 168 | 🟢 LOW | Magic Number | Magic number 10 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 170 | 🟢 LOW | Magic Number | Magic number 10 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 225 | 🟢 LOW | Feature Envy | Method 'KgQueryTool._handle_relations' accesses 'rel' 4 times but 'self' only 0 times | Move Method — consider moving '_handle_relations' to the class that owns 'rel'. |
| 259 | 🟢 LOW | Feature Envy | Method 'KgQueryTool._handle_stats' accesses 'store' 4 times but 'self' only 0 times | Move Method — consider moving '_handle_stats' to the class that owns 'store'. |

### tools/builtins/pytest_run.py — ❌ F (54.0/100)

LOC: 238 | Classes: 2 | Functions: 0 | MI: 52 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 106 | 🟠 HIGH | Primitive Obsession | Function 'execute' has 9 primitive-typed parameters: path: Name(id='str', ctx=Load()), keyword: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), markers: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), verbose: Name(id='bool', ctx=Load()), timeout: Name(id='int', ctx=Load()), coverage: Name(id='bool', ctx=Load()), coverage_source: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), parallel: BinOp(left=Name(id='int', ctx=Load()), op=BitOr(), right=Constant(value=None)), collect_only: Name(id='bool', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 52 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 96% similar to 'parameters' at tools/builtins/python_exec.py:35 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 52 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 92% similar to 'parameters' at tools/builtins/test_gen.py:34 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 52 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/web_fetch.py:32 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 171 | 🟡 MEDIUM | Feature Envy | Method 'PytestRunTool._build_pytest_command' accesses 'config' 8 times but 'self' only 0 times | Move Method — consider moving '_build_pytest_command' to the class that owns 'config'. |
| 204 | 🟡 MEDIUM | Feature Envy | Method 'PytestRunTool._execute_pytest_command' accesses 'process' 5 times but 'self' only 3 times | Move Method — consider moving '_execute_pytest_command' to the class that owns 'process'. |
| 21 | 🟢 LOW | Magic Number | Magic number 300 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 52 | 🟢 LOW | Long Method | Function 'parameters' has 46 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 77 | 🟢 LOW | Magic Number | Magic number 300 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 171 | 🟢 LOW | Long Method | Function '_build_pytest_command' has 30 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 204 | 🟢 LOW | Feature Envy | Method 'PytestRunTool._execute_pytest_command' accesses 'asyncio' 4 times but 'self' only 3 times | Move Method — consider moving '_execute_pytest_command' to the class that owns 'asyncio'. |

### cli/commands/agent.py — ❌ F (54.2/100)

LOC: 126 | Classes: 1 | Functions: 0 | MI: 64 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 85 | 🟡 MEDIUM | Duplicate Code | Function '_print_error' is 100% similar to '_print_formatted_message' at cli/commands/session.py:158 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 114 | 🟡 MEDIUM | Feature Envy | Method 'AgentCommand._list_agents' accesses 'table' 5 times but 'self' only 0 times | Move Method — consider moving '_list_agents' to the class that owns 'table'. |
| 137 | 🟡 MEDIUM | Feature Envy | Method 'AgentCommand._show_config' accesses 'console' 8 times but 'self' only 0 times | Move Method — consider moving '_show_config' to the class that owns 'console'. |
| 137 | 🟡 MEDIUM | Feature Envy | Method 'AgentCommand._show_config' accesses 'config' 9 times but 'self' only 0 times | Move Method — consider moving '_show_config' to the class that owns 'config'. |
| 19 | 🟢 LOW | Missing Type Hint | Function 'name' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 24 | 🟢 LOW | Missing Type Hint | Function 'description' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 29 | 🟢 LOW | Missing Type Hint | Function 'usage' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 33 | 🟢 LOW | Missing Type Hint | Function 'execute' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 60 | 🟢 LOW | Missing Type Hint | Function '_check_multi_agent_initialized' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 60 | 🟢 LOW | Feature Envy | Method 'AgentCommand._check_multi_agent_initialized' accesses 'ctx' 3 times but 'self' only 0 times | Move Method — consider moving '_check_multi_agent_initialized' to the class that owns 'ctx'. |
| 74 | 🟢 LOW | Missing Type Hint | Function '_get_orchestrator' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 85 | 🟢 LOW | Missing Type Hint | Function '_print_error' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 94 | 🟢 LOW | Missing Type Hint | Function '_talk_to_agent_directly' has incomplete type hints: 1/4 params untyped | Add Type Annotations for all parameters and return type. |
| 94 | 🟢 LOW | Feature Envy | Method 'AgentCommand._talk_to_agent_directly' accesses 'ctx' 4 times but 'self' only 0 times | Move Method — consider moving '_talk_to_agent_directly' to the class that owns 'ctx'. |
| 114 | 🟢 LOW | Missing Type Hint | Function '_list_agents' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |

_... and 4 more smells._

### utils/compaction.py — ❌ F (54.3/100)

LOC: 770 | Classes: 9 | Functions: 7 | MI: 29 | Avg CC: 11.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 554 | 🟡 MEDIUM | Duplicate Code | Function '_group_into_sequences' is 95% similar to '_cluster_messages' at utils/intelligent_context.py:445 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 930 | 🟡 MEDIUM | Primitive Obsession | Function 'compact_with_summarization' has 4 primitive-typed parameters: max_tokens: Name(id='int', ctx=Load()), summarize: Name(id='bool', ctx=Load()), protect_from_index: Name(id='int', ctx=Load()), max_protected_ratio: Name(id='float', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 1003 | 🟡 MEDIUM | Complex Function | Function '_attempt_summarization' has cyclomatic complexity 11 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 80 | 🟢 LOW | Magic Number | Magic number 0.3 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 260 | 🟢 LOW | Feature Envy | Method 'ProtectedZoneManager._truncate_protected_zone' accesses 'result' 3 times but 'self' only 0 times | Move Method — consider moving '_truncate_protected_zone' to the class that owns 'result'. |
| 415 | 🟢 LOW | Feature Envy | Method 'MessageSequenceValidator._is_valid_tool_message' accesses 'prev_msg' 3 times but 'self' only 0 times | Move Method — consider moving '_is_valid_tool_message' to the class that owns 'prev_msg'. |
| 441 | 🟢 LOW | Feature Envy | Method 'MessageSequenceValidator._all_tool_calls_have_responses' accesses 'msg' 3 times but 'self' only 0 times | Move Method — consider moving '_all_tool_calls_have_responses' to the class that owns 'msg'. |
| 456 | 🟢 LOW | Deep Nesting | Nesting depth 4 in '_all_tool_calls_have_responses' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 565 | 🟢 LOW | Long Method | Function 'compact' has 40 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 660 | 🟢 LOW | Feature Envy | Method 'ContextCompactor._select_sequences_to_keep' accesses 'last_sequence' 3 times but 'self' only 1 times | Move Method — consider moving '_select_sequences_to_keep' to the class that owns 'last_sequence'. |
| 708 | 🟢 LOW | Feature Envy | Method 'ContextCompactor._reconstruct_result' accesses 'result' 4 times but 'self' only 0 times | Move Method — consider moving '_reconstruct_result' to the class that owns 'result'. |
| 811 | 🟢 LOW | Magic Number | Magic number 200 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 812 | 🟢 LOW | Magic Number | Magic number 500 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |

### cli/commands/session.py — ❌ F (55.7/100)

LOC: 836 | Classes: 17 | Functions: 13 | MI: 34 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 150 | 🟡 MEDIUM | Duplicate Code | Function 'print_usage' is 100% similar to '_add_message_with_prefix' at cli/textual_widgets.py:914 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 150 | 🟡 MEDIUM | Duplicate Code | Function 'print_usage' is 100% similar to 'add_user_message' at cli/textual_widgets.py:923 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 150 | 🟡 MEDIUM | Duplicate Code | Function 'print_usage' is 100% similar to 'add_system_message' at cli/textual_widgets.py:931 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 150 | 🟡 MEDIUM | Duplicate Code | Function 'print_usage' is 100% similar to 'add_error_message' at cli/textual_widgets.py:939 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 261 | 🟡 MEDIUM | Duplicate Code | Function '_ensure_args' is 94% similar to 'add_thinking_message' at cli/textual_widgets.py:1027 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 261 | 🟡 MEDIUM | Duplicate Code | Function '_ensure_args' is 100% similar to 'save' at core/session_manager_base.py:102 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 983 | 🟡 MEDIUM | Duplicate Code | Function '_validate_min_args' is 100% similar to '_enforce_message_safety' at utils/compaction.py:542 | Extract Shared Function — identify the common logic and parameterise the differences. |

### extensions/plugin_manager.py — ❌ F (56.6/100)

LOC: 293 | Classes: 1 | Functions: 0 | MI: 56 | Avg CC: 12.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 113 | 🟡 MEDIUM | Primitive Obsession | Function 'search_plugins' has 4 primitive-typed parameters: query: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), page: Name(id='int', ctx=Load()), page_size: Name(id='int', ctx=Load()), category: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 170 | 🟡 MEDIUM | Long Method | Function 'install_plugin' has 57 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 170 | 🟡 MEDIUM | Complex Function | Function 'install_plugin' has cyclomatic complexity 12 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 30 | 🟢 LOW | Large Class | Class 'PluginManager' spans 380 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
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
| 345 | 🟢 LOW | Missing Type Hint | Function 'scan_security' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |

_... and 2 more smells._

## ✨ Clean Files (58 files with no smells)

<details><summary>Click to expand</summary>

- __init__.py — ✅ A
- __main__.py — ✅ A
- agents/__init__.py — ✅ A
- agents/config.py — ✅ A
- agents/orchestrator_anchoring.py — ✅ A
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
- cli/commands/model.py — 👍 B
- cli/prompts.py — ✅ A
- cli/stream_event_handlers.py — 👍 B
- cli/tool_executor.py — 👍 B
- config/__init__.py — ✅ A
- config/settings.py — 👍 B
- core/__init__.py — ✅ A
- core/agent.py — 👍 B
- core/agent_stall.py — ✅ A
- core/events.py — ✅ A
- core/session.py — ✅ A
- core/session_branch.py — ✅ A
- core/session_data.py — ✅ A
- core/session_export.py — ✅ A
- core/session_helpers.py — ✅ A
- core/session_manager.py — ✅ A
- core/session_manager_base.py — ✅ A
- core/session_merge.py — ✅ A
- core/session_templates.py — ✅ A
- extensions/__init__.py — ✅ A
- extensions/constants.py — ✅ A
- extensions/models.py — 👍 B
- knowledge/__init__.py — ✅ A
- knowledge/models.py — ✅ A
- mcp/__init__.py — ✅ A
- metrics/__init__.py — ✅ A
- metrics/models.py — 👍 B
- providers/__init__.py — ✅ A
- providers/utils.py — ✅ A
- rag/__init__.py — ✅ A
- tools/__init__.py — ✅ A
- tools/builtins/__init__.py — ✅ A
- tools/utils.py — ✅ A
- utils/__init__.py — ✅ A
- utils/lazy_import.py — ✅ A
- version.py — ✅ A

</details>

---

_Report generated by XP Code Smell Detector. Smells are static heuristics — use judgement when prioritising fixes._
