# Code Smell Report — 🔶 D (Score: 61.2/100)

_Scanned: /home/matthew/mlg-cli/src/henchman_  

_Generated: 2026-03-03T15:00:21.979758+00:00_

## Executive Summary

| Metric | Value |
|:-------|------:|
| **Overall Grade** | 🔶 D |
| **Overall Score** | 61.2/100 |
| **Files Scanned** | 188 |
| **Total Lines (non-blank)** | 34,695 |
| **Total Smells** | 1622 |
| **Avg Maintainability Index** | 71.7 |
| **Avg Cyclomatic Complexity** | 13.6 |

### Smells by Severity

| Severity | Count |
|:---------|------:|
| low | 1206 |
| medium | 386 |
| high | 30 |

### Smells by Category

| Category | Count |
|:---------|------:|
| Missing Type Hint | 729 |
| Feature Envy | 279 |
| Duplicate Code | 231 |
| Long Method | 106 |
| Magic Number | 94 |
| Deep Nesting | 69 |
| Primitive Obsession | 63 |
| Complex Function | 28 |
| Large Class | 23 |

## 🎯 Prioritised Refactoring Queue

These are the highest-impact smells to address first:

1. **cli/app.py:650** — 🟠 HIGH — Primitive Obsession  
   Function 'chat_command' has 8 primitive-typed parameters: prompt: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), agent: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), team: Name(id='bool', ctx=Load()), output_format: Name(id='str', ctx=Load()), plan: Name(id='bool', ctx=Load()), yes: Name(id='bool', ctx=Load()), tui: Name(id='bool', ctx=Load()), debug: Name(id='bool', ctx=Load())  
   → _Introduce Parameter Object — group related primitives into a dataclass or NamedTuple._

2. **cli/commands/plan.py:39** — 🟠 HIGH — Feature Envy  
   Method 'PlanCommand.execute' accesses 'ctx' 13 times but 'self' only 0 times  
   → _Move Method — consider moving 'execute' to the class that owns 'ctx'._

3. **cli/json_output.py:38** — 🟠 HIGH — Duplicate Code  
   Function 'render' is an exact duplicate of 'render_stream_json' at cli/json_output.py:72  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

4. **cli/repl.py:78** — 🟠 HIGH — Long Method  
   Function '__init__' has 105 lines (threshold: 30)  
   → _Extract Method — break this function into smaller, intention-revealing helper functions._

5. **cli/textual_widgets.py:923** — 🟠 HIGH — Duplicate Code  
   Function 'add_user_message' is an exact duplicate of 'add_system_message' at cli/textual_widgets.py:931  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

6. **cli/textual_widgets.py:923** — 🟠 HIGH — Duplicate Code  
   Function 'add_user_message' is an exact duplicate of 'add_error_message' at cli/textual_widgets.py:939  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

7. **cli/textual_widgets.py:931** — 🟠 HIGH — Duplicate Code  
   Function 'add_system_message' is an exact duplicate of 'add_error_message' at cli/textual_widgets.py:939  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

8. **cli/ui_renderer.py:49** — 🟠 HIGH — Primitive Obsession  
   Repeated primitive parameter group appears in: 'start_task' (line 49), 'start_task' (line 360)  
   → _Replace Data Value with Object — create a shared data structure for this recurring parameter group._

9. **cli/ui_renderer.py:73** — 🟠 HIGH — Primitive Obsession  
   Repeated primitive parameter group appears in: 'update_task' (line 73), 'update_task' (line 373)  
   → _Replace Data Value with Object — create a shared data structure for this recurring parameter group._

10. **knowledge/scanner.py:199** — 🟠 HIGH — Long Method  
   Function 'scan_repository' has 94 lines (threshold: 30)  
   → _Extract Method — break this function into smaller, intention-revealing helper functions._

11. **knowledge/store.py:459** — 🟠 HIGH — Feature Envy  
   Method 'KnowledgeStore.format_entity_for_llm' accesses 'entity' 13 times but 'self' only 1 times  
   → _Move Method — consider moving 'format_entity_for_llm' to the class that owns 'entity'._

12. **metrics/collector.py:146** — 🟠 HIGH — Feature Envy  
   Method 'MetricsCollector.record_token_usage' accesses 'usage' 13 times but 'self' only 6 times  
   → _Move Method — consider moving 'record_token_usage' to the class that owns 'usage'._

13. **metrics/collector.py:187** — 🟠 HIGH — Feature Envy  
   Method 'MetricsCollector.record_cost' accesses 'cost' 12 times but 'self' only 6 times  
   → _Move Method — consider moving 'record_cost' to the class that owns 'cost'._

14. **metrics/exporter.py:79** — 🟠 HIGH — Duplicate Code  
   Function 'export_to_csv' is an exact duplicate of 'export_to_prometheus' at metrics/exporter.py:93  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

15. **tools/builtins/code_format.py:49** — 🟠 HIGH — Long Method  
   Function 'execute' has 93 lines (threshold: 30)  
   → _Extract Method — break this function into smaller, intention-revealing helper functions._


## 📊 Files Ranked by Quality

| Rank | File | Grade | Score | Smells | LOC | MI | Avg CC |
|-----:|:-----|:------|------:|-------:|----:|---:|-------:|
| 1 | cli/textual_bridge.py | ❌ F | 15.2 | 46 | 405 | 51 | 0.0 |
| 2 | tools/builtins/python_ast.py | ❌ F | 15.7 | 32 | 357 | 52 | 11.0 |
| 3 | cli/output_handler.py | ❌ F | 15.9 | 40 | 303 | 53 | 0.0 |
| 4 | cli/commands/context.py | ❌ F | 16.4 | 47 | 471 | 48 | 0.0 |
| 5 | tools/builtins/git_ops.py | ❌ F | 17.0 | 21 | 278 | 54 | 0.0 |
| 6 | cli/ui_renderer.py | ❌ F | 17.3 | 49 | 300 | 58 | 0.0 |
| 7 | metrics/dashboard.py | ❌ F | 17.4 | 40 | 270 | 58 | 14.0 |
| 8 | cli/repl.py | ❌ F | 21.2 | 30 | 341 | 52 | 16.0 |
| 9 | providers/anthropic.py | ❌ F | 22.7 | 38 | 469 | 41 | 0.0 |
| 10 | metrics/storage.py | ❌ F | 23.1 | 39 | 659 | 47 | 0.0 |

## 📁 Per-File Details

_Showing 20 worst files. 168 additional files omitted._

### cli/textual_bridge.py — ❌ F (15.2/100)

LOC: 405 | Classes: 3 | Functions: 2 | MI: 51 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 172 | 🟡 MEDIUM | Duplicate Code | Function 'post_tool_message' is 100% similar to '_add_message_with_prefix' at cli/textual_widgets.py:914 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 172 | 🟡 MEDIUM | Duplicate Code | Function 'post_tool_message' is 100% similar to 'add_user_message' at cli/textual_widgets.py:923 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 172 | 🟡 MEDIUM | Duplicate Code | Function 'post_tool_message' is 100% similar to 'add_system_message' at cli/textual_widgets.py:931 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 172 | 🟡 MEDIUM | Duplicate Code | Function 'post_tool_message' is 100% similar to 'add_error_message' at cli/textual_widgets.py:939 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 181 | 🟡 MEDIUM | Duplicate Code | Function 'post_status_message' is 94% similar to '_on_finished' at cli/textual_bridge.py:431 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 390 | 🟡 MEDIUM | Duplicate Code | Function '_create_status_message_handler' is 100% similar to '_create_prefixed_message_handler' at cli/textual_bridge.py:401 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 414 | 🟡 MEDIUM | Duplicate Code | Function '_on_thought' is 94% similar to 'code' at cli/ui_renderer.py:306 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 414 | 🟡 MEDIUM | Duplicate Code | Function '_on_thought' is 100% similar to 'add_auto_approve_policy' at tools/registry.py:147 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 414 | 🟡 MEDIUM | Duplicate Code | Function '_on_thought' is 100% similar to 'remove_auto_approve_policy' at tools/registry.py:158 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 53 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 70 | 🟢 LOW | Missing Type Hint | Function 'console' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 78 | 🟢 LOW | Missing Type Hint | Function 'flush_to_chat' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 86 | 🟢 LOW | Missing Type Hint | Function 'print' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 108 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 116 | 🟢 LOW | Missing Type Hint | Function 'post' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |

_... and 31 more smells._

### tools/builtins/python_ast.py — ❌ F (15.7/100)

LOC: 357 | Classes: 1 | Functions: 0 | MI: 52 | Avg CC: 11.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 34 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 96% similar to 'parameters' at tools/builtins/python_exec.py:35 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 34 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/shell.py:329 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 34 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 92% similar to 'parameters' at tools/builtins/test_gen.py:33 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 34 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 96% similar to 'parameters' at tools/builtins/traceback_parse.py:45 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 34 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/web_fetch.py:24 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 34 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/web_search.py:24 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 57 | 🟡 MEDIUM | Feature Envy | Method 'PythonAstTool._get_docstring' accesses 'ast' 6 times but 'self' only 0 times | Move Method — consider moving '_get_docstring' to the class that owns 'ast'. |
| 125 | 🟡 MEDIUM | Feature Envy | Method 'PythonAstTool._format_function' accesses 'node' 7 times but 'self' only 3 times | Move Method — consider moving '_format_function' to the class that owns 'node'. |
| 125 | 🟡 MEDIUM | Complex Function | Function '_format_function' has cyclomatic complexity 11 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 182 | 🟡 MEDIUM | Feature Envy | Method 'PythonAstTool._format_class' accesses 'ast' 6 times but 'self' only 4 times | Move Method — consider moving '_format_class' to the class that owns 'ast'. |
| 182 | 🟡 MEDIUM | Feature Envy | Method 'PythonAstTool._format_class' accesses 'node' 5 times but 'self' only 4 times | Move Method — consider moving '_format_class' to the class that owns 'node'. |
| 310 | 🟡 MEDIUM | Duplicate Code | Function '_validate_path' is 98% similar to 'validate_file_path' at tools/utils.py:9 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 395 | 🟡 MEDIUM | Feature Envy | Method 'PythonAstTool._add_assignments_section' accesses 'ast' 5 times but 'self' only 0 times | Move Method — consider moving '_add_assignments_section' to the class that owns 'ast'. |
| 395 | 🟡 MEDIUM | Feature Envy | Method 'PythonAstTool._add_assignments_section' accesses 'a' 6 times but 'self' only 0 times | Move Method — consider moving '_add_assignments_section' to the class that owns 'a'. |
| 420 | 🟡 MEDIUM | Feature Envy | Method 'PythonAstTool._add_functions_and_classes_sections' accesses 'ast' 5 times but 'self' only 2 times | Move Method — consider moving '_add_functions_and_classes_sections' to the class that owns 'ast'. |

_... and 17 more smells._

### cli/output_handler.py — ❌ F (15.9/100)

LOC: 303 | Classes: 1 | Functions: 0 | MI: 53 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 225 | 🟡 MEDIUM | Duplicate Code | Function 'get_rich_status_message' is 94% similar to 'load' at cli/session_manager.py:127 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 225 | 🟡 MEDIUM | Duplicate Code | Function 'get_rich_status_message' is 94% similar to 'compute_project_hash' at cli/session_manager.py:201 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 298 | 🟡 MEDIUM | Duplicate Code | Function 'create_status' is 100% similar to 'create_status' at cli/ui_renderer.py:187 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 332 | 🟡 MEDIUM | Duplicate Code | Function 'start_task' is 100% similar to 'start_task' at cli/ui_renderer.py:360 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 345 | 🟡 MEDIUM | Duplicate Code | Function 'update_task' is 100% similar to 'tool_result' at cli/ui_renderer.py:322 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 345 | 🟡 MEDIUM | Duplicate Code | Function 'update_task' is 100% similar to 'tool_summary' at cli/ui_renderer.py:326 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 345 | 🟡 MEDIUM | Duplicate Code | Function 'update_task' is 100% similar to 'update_task' at cli/ui_renderer.py:373 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 22 | 🟢 LOW | Large Class | Class 'OutputHandler' spans 362 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
| 22 | 🟢 LOW | Large Class | Class 'OutputHandler' has 28 methods (threshold: 20) | Split Class — group related methods into smaller collaborating classes. |
| 32 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/8 params untyped | Add Type Annotations for all parameters and return type. |
| 61 | 🟢 LOW | Missing Type Hint | Function 'get_toolbar_status' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 81 | 🟢 LOW | Missing Type Hint | Function '_add_plan_mode_status' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 94 | 🟢 LOW | Missing Type Hint | Function '_add_provider_status' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 107 | 🟢 LOW | Missing Type Hint | Function '_add_token_status' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 131 | 🟢 LOW | Missing Type Hint | Function '_get_max_tokens' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |

_... and 25 more smells._

### cli/commands/context.py — ❌ F (16.4/100)

LOC: 471 | Classes: 6 | Functions: 0 | MI: 48 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 112 | 🟡 MEDIUM | Duplicate Code | Function '__init__' is 100% similar to '__init__' at cli/json_output.py:30 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 66 | 🟢 LOW | Missing Type Hint | Function 'get_display_label' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 74 | 🟢 LOW | Missing Type Hint | Function 'validate_value' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 94 | 🟢 LOW | Missing Type Hint | Function 'parse_value' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 112 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 120 | 🟢 LOW | Missing Type Hint | Function 'print_status_info' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 131 | 🟢 LOW | Missing Type Hint | Function 'print_strategy_usage' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 142 | 🟢 LOW | Missing Type Hint | Function 'print_strategy_status' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 157 | 🟢 LOW | Missing Type Hint | Function '_print_context_settings' has incomplete type hints: 1/4 params untyped | Add Type Annotations for all parameters and return type. |
| 190 | 🟢 LOW | Missing Type Hint | Function '_print_available_commands' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 207 | 🟢 LOW | Missing Type Hint | Function '_print_strategy_parameters' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 231 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 252 | 🟢 LOW | Missing Type Hint | Function 'manage_strategy' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 265 | 🟢 LOW | Magic Number | Magic number 3 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 275 | 🟢 LOW | Missing Type Hint | Function '_show_strategy_status' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |

_... and 32 more smells._

### tools/builtins/git_ops.py — ❌ F (17.0/100)

LOC: 278 | Classes: 1 | Functions: 0 | MI: 54 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 142 | 🟠 HIGH | Primitive Obsession | Function 'execute' has 9 primitive-typed parameters: action: Name(id='str', ctx=Load()), path: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), ref: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), ref2: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), max_count: Name(id='int', ctx=Load()), start_line: BinOp(left=Name(id='int', ctx=Load()), op=BitOr(), right=Constant(value=None)), end_line: BinOp(left=Name(id='int', ctx=Load()), op=BitOr(), right=Constant(value=None)), stat: Name(id='bool', ctx=Load()), cwd: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 218 | 🟠 HIGH | Duplicate Code | Function '_status' is an exact duplicate of '_branch_list' at tools/builtins/git_ops.py:277 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 258 | 🟠 HIGH | Primitive Obsession | Repeated primitive parameter group appears in: '_show' (line 258), '_diff_branches' (line 292) | Replace Data Value with Object — create a shared data structure for this recurring parameter group. |
| 46 | 🟡 MEDIUM | Long Method | Function 'parameters' has 53 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 46 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 93% similar to 'parameters' at tools/builtins/kg_query.py:69 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 46 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 96% similar to 'parameters' at tools/builtins/lint_check.py:35 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 46 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 92% similar to 'parameters' at tools/builtins/pytest_run.py:51 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 46 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 92% similar to 'parameters' at tools/builtins/shell.py:329 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 46 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/test_gen.py:33 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 46 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 92% similar to 'parameters' at tools/builtins/web_fetch.py:24 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 222 | 🟡 MEDIUM | Primitive Obsession | Function '_log' has 5 primitive-typed parameters: path: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), ref: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), max_count: Name(id='int', ctx=Load()), stat: Name(id='bool', ctx=Load()), cwd: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 241 | 🟡 MEDIUM | Primitive Obsession | Function '_blame' has 4 primitive-typed parameters: path: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), start_line: BinOp(left=Name(id='int', ctx=Load()), op=BitOr(), right=Constant(value=None)), end_line: BinOp(left=Name(id='int', ctx=Load()), op=BitOr(), right=Constant(value=None)), cwd: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 258 | 🟡 MEDIUM | Primitive Obsession | Function '_show' has 4 primitive-typed parameters: ref: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), path: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), stat: Name(id='bool', ctx=Load()), cwd: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 292 | 🟡 MEDIUM | Primitive Obsession | Function '_diff_branches' has 5 primitive-typed parameters: ref: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), ref2: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), stat: Name(id='bool', ctx=Load()), path: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), cwd: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 79 | 🟢 LOW | Magic Number | Magic number 20 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |

_... and 6 more smells._

### cli/ui_renderer.py — ❌ F (17.3/100)

LOC: 300 | Classes: 2 | Functions: 0 | MI: 58 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 49 | 🟠 HIGH | Primitive Obsession | Repeated primitive parameter group appears in: 'start_task' (line 49), 'start_task' (line 360) | Replace Data Value with Object — create a shared data structure for this recurring parameter group. |
| 73 | 🟠 HIGH | Primitive Obsession | Repeated primitive parameter group appears in: 'update_task' (line 73), 'update_task' (line 373) | Replace Data Value with Object — create a shared data structure for this recurring parameter group. |
| 100 | 🟡 MEDIUM | Large Class | Class 'UIRenderer' has 31 methods (threshold: 20) | Split Class — group related methods into smaller collaborating classes. |
| 306 | 🟡 MEDIUM | Duplicate Code | Function 'code' is 94% similar to 'add_auto_approve_policy' at tools/registry.py:147 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 306 | 🟡 MEDIUM | Duplicate Code | Function 'code' is 94% similar to 'remove_auto_approve_policy' at tools/registry.py:158 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 322 | 🟡 MEDIUM | Duplicate Code | Function 'tool_result' is 100% similar to 'tool_summary' at cli/ui_renderer.py:326 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 322 | 🟡 MEDIUM | Duplicate Code | Function 'tool_result' is 100% similar to 'update_task' at cli/ui_renderer.py:373 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 326 | 🟡 MEDIUM | Duplicate Code | Function 'tool_summary' is 100% similar to 'update_task' at cli/ui_renderer.py:373 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 40 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: missing return type | Add Type Annotations for all parameters and return type. |
| 49 | 🟢 LOW | Missing Type Hint | Function 'start_task' has incomplete type hints: 1/4 params untyped | Add Type Annotations for all parameters and return type. |
| 49 | 🟢 LOW | Primitive Obsession | Function 'start_task' has 3 primitive-typed parameters: task_id: Name(id='str', ctx=Load()), description: Name(id='str', ctx=Load()), total: Name(id='int', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 73 | 🟢 LOW | Missing Type Hint | Function 'update_task' has incomplete type hints: 1/4 params untyped | Add Type Annotations for all parameters and return type. |
| 73 | 🟢 LOW | Primitive Obsession | Function 'update_task' has 3 primitive-typed parameters: task_id: Name(id='str', ctx=Load()), advance: Name(id='int', ctx=Load()), description: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 88 | 🟢 LOW | Missing Type Hint | Function 'complete_task' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 112 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/6 params untyped | Add Type Annotations for all parameters and return type. |

_... and 34 more smells._

### metrics/dashboard.py — ❌ F (17.4/100)

LOC: 270 | Classes: 1 | Functions: 0 | MI: 58 | Avg CC: 14.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 74 | 🟡 MEDIUM | Long Method | Function 'get_summary_stats' has 77 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 74 | 🟡 MEDIUM | Feature Envy | Method 'Dashboard.get_summary_stats' accesses 'stat' 6 times but 'self' only 4 times | Move Method — consider moving 'get_summary_stats' to the class that owns 'stat'. |
| 74 | 🟡 MEDIUM | Complex Function | Function 'get_summary_stats' has cyclomatic complexity 14 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 260 | 🟡 MEDIUM | Duplicate Code | Function '_create_token_panel' is 96% similar to '_create_cost_panel' at metrics/dashboard.py:283 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 260 | 🟡 MEDIUM | Duplicate Code | Function '_create_token_panel' is 98% similar to '_create_tool_panel' at metrics/dashboard.py:306 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 260 | 🟡 MEDIUM | Duplicate Code | Function '_create_token_panel' is 100% similar to '_create_usage_panel' at metrics/dashboard.py:329 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 283 | 🟡 MEDIUM | Duplicate Code | Function '_create_cost_panel' is 94% similar to '_create_tool_panel' at metrics/dashboard.py:306 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 283 | 🟡 MEDIUM | Duplicate Code | Function '_create_cost_panel' is 96% similar to '_create_usage_panel' at metrics/dashboard.py:329 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 306 | 🟡 MEDIUM | Duplicate Code | Function '_create_tool_panel' is 98% similar to '_create_usage_panel' at metrics/dashboard.py:329 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 22 | 🟢 LOW | Large Class | Class 'Dashboard' spans 329 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
| 35 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/4 params untyped | Add Type Annotations for all parameters and return type. |
| 54 | 🟢 LOW | Missing Type Hint | Function 'display' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 69 | 🟢 LOW | Missing Type Hint | Function 'refresh' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 74 | 🟢 LOW | Missing Type Hint | Function 'get_summary_stats' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 81 | 🟢 LOW | Magic Number | Magic number 7 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |

_... and 25 more smells._

### cli/repl.py — ❌ F (21.2/100)

LOC: 341 | Classes: 2 | Functions: 0 | MI: 52 | Avg CC: 16.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 78 | 🟠 HIGH | Long Method | Function '__init__' has 105 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 78 | 🟡 MEDIUM | Complex Function | Function '__init__' has cyclomatic complexity 16 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 203 | 🟡 MEDIUM | Duplicate Code | Function 'set_session' is 94% similar to '_on_thought' at cli/textual_bridge.py:414 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 203 | 🟡 MEDIUM | Duplicate Code | Function 'set_session' is 94% similar to 'add_auto_approve_policy' at tools/registry.py:147 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 203 | 🟡 MEDIUM | Duplicate Code | Function 'set_session' is 94% similar to 'remove_auto_approve_policy' at tools/registry.py:158 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 211 | 🟡 MEDIUM | Duplicate Code | Function '_handle_confirmation' is 100% similar to 'confirm_tool_execution' at cli/ui_renderer.py:349 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 352 | 🟡 MEDIUM | Long Method | Function '_run_agent_with_monitor' has 52 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 352 | 🟡 MEDIUM | Feature Envy | Method 'Repl._run_agent_with_monitor' accesses 'asyncio' 8 times but 'self' only 7 times | Move Method — consider moving '_run_agent_with_monitor' to the class that owns 'asyncio'. |
| 420 | 🟡 MEDIUM | Feature Envy | Method 'Repl._handle_agent_event' accesses 'event' 5 times but 'self' only 1 times | Move Method — consider moving '_handle_agent_event' to the class that owns 'event'. |
| 60 | 🟢 LOW | Magic Number | Magic number 25 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 61 | 🟢 LOW | Magic Number | Magic number 100 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 66 | 🟢 LOW | Large Class | Class 'Repl' spans 378 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
| 78 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/7 params untyped | Add Type Annotations for all parameters and return type. |
| 203 | 🟢 LOW | Missing Type Hint | Function 'set_session' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 211 | 🟢 LOW | Missing Type Hint | Function '_handle_confirmation' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |

_... and 15 more smells._

### providers/anthropic.py — ❌ F (22.7/100)

LOC: 469 | Classes: 5 | Functions: 0 | MI: 41 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 121 | 🟡 MEDIUM | Feature Envy | Method '_AnthropicStreamProcessor.process_stream' accesses 'chunk' 8 times but 'self' only 3 times | Move Method — consider moving 'process_stream' to the class that owns 'chunk'. |
| 203 | 🟡 MEDIUM | Feature Envy | Method '_AnthropicStreamProcessor._handle_content_block_delta' accesses 'delta' 5 times but 'self' only 3 times | Move Method — consider moving '_handle_content_block_delta' to the class that owns 'delta'. |
| 338 | 🟡 MEDIUM | Duplicate Code | Function '_format_tool' is 95% similar to 'to_metadata' at rag/chunker.py:42 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 61 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 75 | 🟢 LOW | Missing Type Hint | Function '_should_yield' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 112 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 121 | 🟢 LOW | Missing Type Hint | Function 'process_stream' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 163 | 🟢 LOW | Missing Type Hint | Function '_process_event' has incomplete type hints: 1/5 params untyped | Add Type Annotations for all parameters and return type. |
| 183 | 🟢 LOW | Missing Type Hint | Function '_handle_content_block_start' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 183 | 🟢 LOW | Feature Envy | Method '_AnthropicStreamProcessor._handle_content_block_start' accesses 'block' 3 times but 'self' only 0 times | Move Method — consider moving '_handle_content_block_start' to the class that owns 'block'. |
| 203 | 🟢 LOW | Missing Type Hint | Function '_handle_content_block_delta' has incomplete type hints: 1/5 params untyped | Add Type Annotations for all parameters and return type. |
| 236 | 🟢 LOW | Missing Type Hint | Function '_handle_content_block_stop' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 241 | 🟢 LOW | Missing Type Hint | Function '_handle_message_delta' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 259 | 🟢 LOW | Missing Type Hint | Function '_build_tool_calls_from_pending' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 293 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |

_... and 23 more smells._

### metrics/storage.py — ❌ F (23.1/100)

LOC: 659 | Classes: 5 | Functions: 0 | MI: 47 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 515 | 🟡 MEDIUM | Feature Envy | Method 'MetricsStorage._create_base_metric_dict' accesses 'metric' 7 times but 'self' only 0 times | Move Method — consider moving '_create_base_metric_dict' to the class that owns 'metric'. |
| 708 | 🟡 MEDIUM | Feature Envy | Method 'MetricsStorage._build_metrics_query' accesses 'query_params' 6 times but 'self' only 0 times | Move Method — consider moving '_build_metrics_query' to the class that owns 'query_params'. |
| 708 | 🟡 MEDIUM | Feature Envy | Method 'MetricsStorage._build_metrics_query' accesses 'params' 6 times but 'self' only 0 times | Move Method — consider moving '_build_metrics_query' to the class that owns 'params'. |
| 41 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 49 | 🟢 LOW | Missing Type Hint | Function 'get_session_metrics' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 74 | 🟢 LOW | Missing Type Hint | Function '_get_session_metrics_by_type' has incomplete type hints: 1/5 params untyped | Add Type Annotations for all parameters and return type. |
| 74 | 🟢 LOW | Primitive Obsession | Function '_get_session_metrics_by_type' has 3 primitive-typed parameters: session_id: Name(id='str', ctx=Load()), metric_type: Name(id='str', ctx=Load()), select_clause: Name(id='str', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 96 | 🟢 LOW | Missing Type Hint | Function '_get_session_aggregated_metrics' has incomplete type hints: 1/4 params untyped | Add Type Annotations for all parameters and return type. |
| 137 | 🟢 LOW | Missing Type Hint | Function '_get_session_metric_by_type' has incomplete type hints: 1/4 params untyped | Add Type Annotations for all parameters and return type. |
| 152 | 🟢 LOW | Missing Type Hint | Function '_get_session_usage_patterns' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 223 | 🟢 LOW | Missing Type Hint | Function 'create_metrics_table' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 232 | 🟢 LOW | Missing Type Hint | Function 'create_indexes' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 251 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 259 | 🟢 LOW | Missing Type Hint | Function 'get_aggregated_stats' has incomplete type hints: 1/5 params untyped | Add Type Annotations for all parameters and return type. |
| 283 | 🟢 LOW | Missing Type Hint | Function '_get_time_format_for_grouping' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |

_... and 24 more smells._

### metrics/collector.py — ❌ F (23.8/100)

LOC: 323 | Classes: 1 | Functions: 0 | MI: 51 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 146 | 🟠 HIGH | Feature Envy | Method 'MetricsCollector.record_token_usage' accesses 'usage' 13 times but 'self' only 6 times | Move Method — consider moving 'record_token_usage' to the class that owns 'usage'. |
| 187 | 🟠 HIGH | Feature Envy | Method 'MetricsCollector.record_cost' accesses 'cost' 12 times but 'self' only 6 times | Move Method — consider moving 'record_cost' to the class that owns 'cost'. |
| 40 | 🟡 MEDIUM | Primitive Obsession | Function '__init__' has 5 primitive-typed parameters: enabled: Name(id='bool', ctx=Load()), anonymize: Name(id='bool', ctx=Load()), sampling_rate: Name(id='float', ctx=Load()), session_id: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), user_id: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 228 | 🟡 MEDIUM | Primitive Obsession | Function 'track_tool_execution' has 4 primitive-typed parameters: tool_name: Name(id='str', ctx=Load()), tool_category: Name(id='str', ctx=Load()), input_size: BinOp(left=Name(id='int', ctx=Load()), op=BitOr(), right=Constant(value=None)), agent_id: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 292 | 🟡 MEDIUM | Feature Envy | Method 'MetricsCollector.record_performance_event' accesses 'event' 6 times but 'self' only 5 times | Move Method — consider moving 'record_performance_event' to the class that owns 'event'. |
| 391 | 🟡 MEDIUM | Deep Nesting | Nesting depth 5 in 'process_agent_event' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 28 | 🟢 LOW | Large Class | Class 'MetricsCollector' spans 365 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
| 40 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/7 params untyped | Add Type Annotations for all parameters and return type. |
| 76 | 🟢 LOW | Missing Type Hint | Function '_generate_session_id' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 81 | 🟢 LOW | Missing Type Hint | Function '_hash_user_id' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 83 | 🟢 LOW | Magic Number | Magic number 16 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 85 | 🟢 LOW | Missing Type Hint | Function 'should_sample' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 94 | 🟢 LOW | Missing Type Hint | Function 'start_command' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 110 | 🟢 LOW | Missing Type Hint | Function 'end_command' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 122 | 🟢 LOW | Magic Number | Magic number 1000 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |

_... and 15 more smells._

### tools/builtins/file_edit.py — ❌ F (25.0/100)

LOC: 228 | Classes: 1 | Functions: 0 | MI: 62 | Avg CC: 13.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 72 | 🟠 HIGH | Primitive Obsession | Function 'execute' has 6 primitive-typed parameters: path: Name(id='str', ctx=Load()), old_str: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), new_str: Name(id='str', ctx=Load()), start_line: BinOp(left=Name(id='int', ctx=Load()), op=BitOr(), right=Constant(value=None)), end_line: BinOp(left=Name(id='int', ctx=Load()), op=BitOr(), right=Constant(value=None)), dry_run: Name(id='bool', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 33 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/file_write.py:27 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 33 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 92% similar to 'parameters' at tools/builtins/git_ops.py:46 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 33 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/glob_tool.py:30 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 33 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/pytest_run.py:51 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 33 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/python_ast.py:34 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 33 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 96% similar to 'parameters' at tools/builtins/python_exec.py:35 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 33 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/shell.py:329 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 33 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 92% similar to 'parameters' at tools/builtins/test_gen.py:33 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 33 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 96% similar to 'parameters' at tools/builtins/traceback_parse.py:45 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 33 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/web_fetch.py:24 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 33 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/web_search.py:24 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 72 | 🟡 MEDIUM | Long Method | Function 'execute' has 51 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 72 | 🟡 MEDIUM | Complex Function | Function 'execute' has cyclomatic complexity 13 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 148 | 🟡 MEDIUM | Primitive Obsession | Function '_edit_string' has 4 primitive-typed parameters: content: Name(id='str', ctx=Load()), old_str: Name(id='str', ctx=Load()), new_str: Name(id='str', ctx=Load()), dry_run: Name(id='bool', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |

_... and 4 more smells._

### cli/commands/__init__.py — ❌ F (27.9/100)

LOC: 157 | Classes: 4 | Functions: 2 | MI: 63 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 138 | 🟡 MEDIUM | Duplicate Code | Function '__init__' is 100% similar to '__init__' at extensions/manager.py:40 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 142 | 🟡 MEDIUM | Duplicate Code | Function 'register' is 100% similar to 'register_theme' at cli/console.py:356 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 150 | 🟡 MEDIUM | Duplicate Code | Function 'get' is 100% similar to 'get' at extensions/manager.py:68 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 150 | 🟡 MEDIUM | Duplicate Code | Function 'get' is 95% similar to 'get' at tools/registry.py:103 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 161 | 🟡 MEDIUM | Duplicate Code | Function 'get_commands' is 100% similar to 'list_commands' at cli/commands/__init__.py:169 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 161 | 🟡 MEDIUM | Duplicate Code | Function 'get_commands' is 100% similar to 'list_extensions' at extensions/manager.py:79 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 161 | 🟡 MEDIUM | Duplicate Code | Function 'get_commands' is 100% similar to 'get_server_names' at mcp/manager.py:38 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 161 | 🟡 MEDIUM | Duplicate Code | Function 'get_commands' is 100% similar to 'list_providers' at providers/registry.py:47 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 161 | 🟡 MEDIUM | Duplicate Code | Function 'get_commands' is 100% similar to 'list_tools' at tools/registry.py:122 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 169 | 🟡 MEDIUM | Duplicate Code | Function 'list_commands' is 100% similar to 'list_extensions' at extensions/manager.py:79 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 169 | 🟡 MEDIUM | Duplicate Code | Function 'list_commands' is 100% similar to 'get_server_names' at mcp/manager.py:38 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 169 | 🟡 MEDIUM | Duplicate Code | Function 'list_commands' is 100% similar to 'list_providers' at providers/registry.py:47 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 169 | 🟡 MEDIUM | Duplicate Code | Function 'list_commands' is 100% similar to 'list_tools' at tools/registry.py:122 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 76 | 🟢 LOW | Missing Type Hint | Function 'name' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 85 | 🟢 LOW | Missing Type Hint | Function 'description' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |

_... and 9 more smells._

### cli/textual_messages.py — ❌ F (30.0/100)

LOC: 129 | Classes: 9 | Functions: 0 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 22 | 🟡 MEDIUM | Duplicate Code | Function '__init__' is 100% similar to '__init__' at cli/textual_messages.py:41 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 22 | 🟡 MEDIUM | Duplicate Code | Function '__init__' is 100% similar to '__init__' at cli/textual_messages.py:60 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 22 | 🟡 MEDIUM | Duplicate Code | Function '__init__' is 100% similar to '__init__' at cli/textual_messages.py:79 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 22 | 🟡 MEDIUM | Duplicate Code | Function '__init__' is 100% similar to '__init__' at cli/textual_messages.py:98 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 22 | 🟡 MEDIUM | Duplicate Code | Function '__init__' is 100% similar to '__init__' at cli/textual_messages.py:117 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 41 | 🟡 MEDIUM | Duplicate Code | Function '__init__' is 100% similar to '__init__' at cli/textual_messages.py:60 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 41 | 🟡 MEDIUM | Duplicate Code | Function '__init__' is 100% similar to '__init__' at cli/textual_messages.py:79 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 41 | 🟡 MEDIUM | Duplicate Code | Function '__init__' is 100% similar to '__init__' at cli/textual_messages.py:98 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 41 | 🟡 MEDIUM | Duplicate Code | Function '__init__' is 100% similar to '__init__' at cli/textual_messages.py:117 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 60 | 🟡 MEDIUM | Duplicate Code | Function '__init__' is 100% similar to '__init__' at cli/textual_messages.py:79 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 60 | 🟡 MEDIUM | Duplicate Code | Function '__init__' is 100% similar to '__init__' at cli/textual_messages.py:98 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 60 | 🟡 MEDIUM | Duplicate Code | Function '__init__' is 100% similar to '__init__' at cli/textual_messages.py:117 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 79 | 🟡 MEDIUM | Duplicate Code | Function '__init__' is 100% similar to '__init__' at cli/textual_messages.py:98 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 79 | 🟡 MEDIUM | Duplicate Code | Function '__init__' is 100% similar to '__init__' at cli/textual_messages.py:117 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 98 | 🟡 MEDIUM | Duplicate Code | Function '__init__' is 100% similar to '__init__' at cli/textual_messages.py:117 | Extract Shared Function — identify the common logic and parameterise the differences. |

_... and 12 more smells._

### knowledge/store.py — ❌ F (30.0/100)

LOC: 390 | Classes: 1 | Functions: 4 | MI: 49 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 459 | 🟠 HIGH | Feature Envy | Method 'KnowledgeStore.format_entity_for_llm' accesses 'entity' 13 times but 'self' only 1 times | Move Method — consider moving 'format_entity_for_llm' to the class that owns 'entity'. |
| 459 | 🟡 MEDIUM | Feature Envy | Method 'KnowledgeStore.format_entity_for_llm' accesses 'parts' 7 times but 'self' only 1 times | Move Method — consider moving 'format_entity_for_llm' to the class that owns 'parts'. |
| 459 | 🟡 MEDIUM | Feature Envy | Method 'KnowledgeStore.format_entity_for_llm' accesses 'rel' 5 times but 'self' only 1 times | Move Method — consider moving 'format_entity_for_llm' to the class that owns 'rel'. |
| 93 | 🟢 LOW | Large Class | Class 'KnowledgeStore' spans 415 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
| 93 | 🟢 LOW | Large Class | Class 'KnowledgeStore' has 23 methods (threshold: 20) | Split Class — group related methods into smaller collaborating classes. |
| 104 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 130 | 🟢 LOW | Missing Type Hint | Function 'store_dir' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 135 | 🟢 LOW | Missing Type Hint | Function 'graph' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 140 | 🟢 LOW | Missing Type Hint | Function 'meta' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 146 | 🟢 LOW | Missing Type Hint | Function 'load' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 166 | 🟢 LOW | Missing Type Hint | Function 'save' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 181 | 🟢 LOW | Missing Type Hint | Function 'add_entity' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 190 | 🟢 LOW | Missing Type Hint | Function 'get_entity' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 203 | 🟢 LOW | Missing Type Hint | Function 'remove_entity' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 218 | 🟢 LOW | Missing Type Hint | Function 'list_entities' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |

_... and 17 more smells._

### agents/metrics_reporter.py — ❌ F (31.7/100)

LOC: 184 | Classes: 1 | Functions: 0 | MI: 50 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 29 | 🟡 MEDIUM | Feature Envy | Method 'MetricsReporter.get_metrics_report' accesses 'report_lines' 7 times but 'self' only 4 times | Move Method — consider moving 'get_metrics_report' to the class that owns 'report_lines'. |
| 52 | 🟡 MEDIUM | Duplicate Code | Function '_generate_efficiency_metrics' is 100% similar to '_generate_quality_metrics' at agents/metrics_reporter.py:61 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 52 | 🟡 MEDIUM | Duplicate Code | Function '_generate_efficiency_metrics' is 100% similar to '_generate_target_metrics' at agents/metrics_reporter.py:70 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 61 | 🟡 MEDIUM | Duplicate Code | Function '_generate_quality_metrics' is 100% similar to '_generate_target_metrics' at agents/metrics_reporter.py:70 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 174 | 🟡 MEDIUM | Duplicate Code | Function '_format_code_coverage' is 100% similar to '_format_documentation_coverage' at agents/metrics_reporter.py:186 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 216 | 🟡 MEDIUM | Duplicate Code | Function '_format_error_rate_target' is 100% similar to '_format_context_window_target' at agents/metrics_reporter.py:225 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 26 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 29 | 🟢 LOW | Missing Type Hint | Function 'get_metrics_report' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 52 | 🟢 LOW | Missing Type Hint | Function '_generate_efficiency_metrics' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 61 | 🟢 LOW | Missing Type Hint | Function '_generate_quality_metrics' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 70 | 🟢 LOW | Missing Type Hint | Function '_generate_target_metrics' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 79 | 🟢 LOW | Missing Type Hint | Function '_generate_detailed_statistics' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 99 | 🟢 LOW | Missing Type Hint | Function '_format_tool_call_statistics' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 99 | 🟢 LOW | Feature Envy | Method 'MetricsReporter._format_tool_call_statistics' accesses 'lines' 4 times but 'self' only 1 times | Move Method — consider moving '_format_tool_call_statistics' to the class that owns 'lines'. |
| 99 | 🟢 LOW | Feature Envy | Method 'MetricsReporter._format_tool_call_statistics' accesses 'tools' 4 times but 'self' only 1 times | Move Method — consider moving '_format_tool_call_statistics' to the class that owns 'tools'. |

_... and 14 more smells._

### tools/builtins/shell.py — ❌ F (33.4/100)

LOC: 498 | Classes: 2 | Functions: 12 | MI: 48 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 116 | 🟡 MEDIUM | Primitive Obsession | Function '_make_result' has 4 primitive-typed parameters: output: Name(id='str', ctx=Load()), returncode: BinOp(left=Name(id='int', ctx=Load()), op=BitOr(), right=Constant(value=None)), timed_out: Name(id='bool', ctx=Load()), timeout_value: BinOp(left=Name(id='float', ctx=Load()), op=BitOr(), right=Constant(value=None)) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 329 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 92% similar to 'parameters' at tools/builtins/test_gen.py:33 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 329 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 96% similar to 'parameters' at tools/builtins/traceback_parse.py:45 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 329 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/web_fetch.py:24 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 329 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/web_search.py:24 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 499 | 🟡 MEDIUM | Long Method | Function '_execute_interactive_sudo' has 73 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 499 | 🟡 MEDIUM | Feature Envy | Method 'ShellTool._execute_interactive_sudo' accesses 'process' 6 times but 'self' only 2 times | Move Method — consider moving '_execute_interactive_sudo' to the class that owns 'process'. |
| 279 | 🟢 LOW | Large Class | Class 'ShellTool' spans 369 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
| 329 | 🟢 LOW | Long Method | Function 'parameters' has 31 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 369 | 🟢 LOW | Primitive Obsession | Function 'execute' has 3 primitive-typed parameters: command: Name(id='str', ctx=Load()), timeout: BinOp(left=Name(id='int', ctx=Load()), op=BitOr(), right=Constant(value=None)), cwd: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 418 | 🟢 LOW | Primitive Obsession | Function '_create_process' has 3 primitive-typed parameters: command: Name(id='str', ctx=Load()), cwd: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), is_sudo: Name(id='bool', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 418 | 🟢 LOW | Feature Envy | Method 'ShellTool._create_process' accesses 'asyncio' 4 times but 'self' only 0 times | Move Method — consider moving '_create_process' to the class that owns 'asyncio'. |
| 442 | 🟢 LOW | Magic Number | Magic number 5 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 452 | 🟢 LOW | Feature Envy | Method 'ShellTool._run_and_collect' accesses 'asyncio' 3 times but 'self' only 0 times | Move Method — consider moving '_run_and_collect' to the class that owns 'asyncio'. |
| 452 | 🟢 LOW | Feature Envy | Method 'ShellTool._run_and_collect' accesses 'process' 3 times but 'self' only 0 times | Move Method — consider moving '_run_and_collect' to the class that owns 'process'. |

_... and 11 more smells._

### extensions/plugin_installer.py — ❌ F (34.3/100)

LOC: 316 | Classes: 1 | Functions: 0 | MI: 54 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 34 | 🟡 MEDIUM | Feature Envy | Method 'PluginInstaller.install_plugin_package' accesses 'metadata' 7 times but 'self' only 6 times | Move Method — consider moving 'install_plugin_package' to the class that owns 'metadata'. |
| 242 | 🟡 MEDIUM | Deep Nesting | Nesting depth 5 in '_clone_and_copy_git_repo' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 23 | 🟢 LOW | Large Class | Class 'PluginInstaller' spans 401 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
| 26 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 34 | 🟢 LOW | Missing Type Hint | Function 'install_plugin_package' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 64 | 🟢 LOW | Missing Type Hint | Function '_install_from_pypi' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 93 | 🟢 LOW | Missing Type Hint | Function '_install_package_with_pip' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 93 | 🟢 LOW | Feature Envy | Method 'PluginInstaller._install_package_with_pip' accesses 'asyncio' 3 times but 'self' only 0 times | Move Method — consider moving '_install_package_with_pip' to the class that owns 'asyncio'. |
| 128 | 🟢 LOW | Missing Type Hint | Function '_copy_installed_files' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 128 | 🟢 LOW | Feature Envy | Method 'PluginInstaller._copy_installed_files' accesses 'item' 4 times but 'self' only 0 times | Move Method — consider moving '_copy_installed_files' to the class that owns 'item'. |
| 144 | 🟢 LOW | Missing Type Hint | Function '_install_from_github' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 144 | 🟢 LOW | Feature Envy | Method 'PluginInstaller._install_from_github' accesses 'metadata' 3 times but 'self' only 1 times | Move Method — consider moving '_install_from_github' to the class that owns 'metadata'. |
| 177 | 🟢 LOW | Missing Type Hint | Function '_install_from_git' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 196 | 🟢 LOW | Long Method | Function '_clone_and_copy_git_repo' has 39 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 196 | 🟢 LOW | Missing Type Hint | Function '_clone_and_copy_git_repo' has incomplete type hints: 1/4 params untyped | Add Type Annotations for all parameters and return type. |

_... and 19 more smells._

### agents/metrics.py — ❌ F (37.6/100)

LOC: 322 | Classes: 5 | Functions: 1 | MI: 51 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 59 | 🟡 MEDIUM | Duplicate Code | Function '__init__' is 92% similar to '__init__' at agents/metrics.py:111 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 91 | 🟡 MEDIUM | Duplicate Code | Function 'track_file_access' is 100% similar to 'track_tool_usage' at agents/metrics.py:99 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 148 | 🟡 MEDIUM | Duplicate Code | Function 'reset' is 93% similar to '__init__' at cli/textual_mixins.py:109 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 184 | 🟡 MEDIUM | Deep Nesting | Nesting depth 5 in 'track_tool_call' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 59 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 71 | 🟢 LOW | Missing Type Hint | Function 'reset' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 83 | 🟢 LOW | Missing Type Hint | Function 'calculate_file_re_reads' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 91 | 🟢 LOW | Missing Type Hint | Function 'track_file_access' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 99 | 🟢 LOW | Missing Type Hint | Function 'track_tool_usage' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 111 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 118 | 🟢 LOW | Missing Type Hint | Function 'reset' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 125 | 🟢 LOW | Missing Type Hint | Function 'calculate_test_percentage' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 136 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 148 | 🟢 LOW | Missing Type Hint | Function 'reset' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 160 | 🟢 LOW | Missing Type Hint | Function 'track_tool_call' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |

_... and 13 more smells._

### agents/delegation.py — ❌ F (40.5/100)

LOC: 367 | Classes: 2 | Functions: 0 | MI: 56 | Avg CC: 13.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 202 | 🟡 MEDIUM | Feature Envy | Method 'DelegationRunner._prepare_delegation_execution' accesses 'params' 7 times but 'self' only 4 times | Move Method — consider moving '_prepare_delegation_execution' to the class that owns 'params'. |
| 259 | 🟡 MEDIUM | Feature Envy | Method 'DelegationRunner._finalize_delegation' accesses 'params' 6 times but 'self' only 2 times | Move Method — consider moving '_finalize_delegation' to the class that owns 'params'. |
| 302 | 🟡 MEDIUM | Complex Function | Function '_prepare_delegation_context' has cyclomatic complexity 14 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 399 | 🟡 MEDIUM | Feature Envy | Method 'DelegationRunner._assemble_delegation_input' accesses 'sections' 8 times but 'self' only 0 times | Move Method — consider moving '_assemble_delegation_input' to the class that owns 'sections'. |
| 399 | 🟡 MEDIUM | Feature Envy | Method 'DelegationRunner._assemble_delegation_input' accesses 'brief' 6 times but 'self' only 0 times | Move Method — consider moving '_assemble_delegation_input' to the class that owns 'brief'. |
| 399 | 🟡 MEDIUM | Complex Function | Function '_assemble_delegation_input' has cyclomatic complexity 12 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 42 | 🟢 LOW | Missing Type Hint | Function '__call__' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 54 | 🟢 LOW | Large Class | Class 'DelegationRunner' spans 439 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
| 69 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/7 params untyped | Add Type Annotations for all parameters and return type. |
| 88 | 🟢 LOW | Long Method | Function 'run_delegation' has 31 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 88 | 🟢 LOW | Missing Type Hint | Function 'run_delegation' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 141 | 🟢 LOW | Missing Type Hint | Function '_is_delegation_depth_exceeded' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 152 | 🟢 LOW | Missing Type Hint | Function '_yield_depth_exceeded_error' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 169 | 🟢 LOW | Missing Type Hint | Function '_get_target_agent_with_error_handling' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 185 | 🟢 LOW | Missing Type Hint | Function '_yield_agent_not_found_completion' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |

_... and 9 more smells._

## ✨ Clean Files (60 files with no smells)

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
- agents/orchestrator_metrics_ctrl.py — ✅ A
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
- cli/prompts.py — ✅ A
- cli/stream_event_handlers.py — 👍 B
- cli/tool_executor.py — 👍 B
- config/__init__.py — ✅ A
- config/settings.py — ✅ A
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
- core/session_models.py — ✅ A
- core/session_templates.py — ✅ A
- core/turn.py — 👍 B
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
