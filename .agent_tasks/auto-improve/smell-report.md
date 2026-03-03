# Code Smell Report — 🔶 D (Score: 62.2/100)

_Scanned: /home/matthew/mlg-cli/src/henchman_  

_Generated: 2026-03-03T16:00:33.375817+00:00_

## Executive Summary

| Metric | Value |
|:-------|------:|
| **Overall Grade** | 🔶 D |
| **Overall Score** | 62.2/100 |
| **Files Scanned** | 188 |
| **Total Lines (non-blank)** | 34,988 |
| **Total Smells** | 1572 |
| **Avg Maintainability Index** | 71.7 |
| **Avg Cyclomatic Complexity** | 13.6 |

### Smells by Severity

| Severity | Count |
|:---------|------:|
| low | 1083 |
| medium | 462 |
| high | 27 |

### Smells by Category

| Category | Count |
|:---------|------:|
| Missing Type Hint | 602 |
| Duplicate Code | 331 |
| Feature Envy | 279 |
| Long Method | 111 |
| Magic Number | 79 |
| Primitive Obsession | 63 |
| Deep Nesting | 57 |
| Complex Function | 27 |
| Large Class | 23 |

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

4. **cli/repl.py:83** — 🟠 HIGH — Long Method  
   Function '__init__' has 107 lines (threshold: 30)  
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
   Repeated primitive parameter group appears in: 'start_task' (line 49), 'start_task' (line 361)  
   → _Replace Data Value with Object — create a shared data structure for this recurring parameter group._

9. **cli/ui_renderer.py:73** — 🟠 HIGH — Primitive Obsession  
   Repeated primitive parameter group appears in: 'update_task' (line 73), 'update_task' (line 374)  
   → _Replace Data Value with Object — create a shared data structure for this recurring parameter group._

10. **knowledge/scanner.py:198** — 🟠 HIGH — Long Method  
   Function 'scan_repository' has 94 lines (threshold: 30)  
   → _Extract Method — break this function into smaller, intention-revealing helper functions._

11. **knowledge/store.py:459** — 🟠 HIGH — Feature Envy  
   Method 'KnowledgeStore.format_entity_for_llm' accesses 'entity' 11 times but 'self' only 1 times  
   → _Move Method — consider moving 'format_entity_for_llm' to the class that owns 'entity'._

12. **metrics/exporter.py:79** — 🟠 HIGH — Duplicate Code  
   Function 'export_to_csv' is an exact duplicate of 'export_to_prometheus' at metrics/exporter.py:93  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

13. **tools/builtins/code_format.py:49** — 🟠 HIGH — Long Method  
   Function 'execute' has 94 lines (threshold: 30)  
   → _Extract Method — break this function into smaller, intention-revealing helper functions._

14. **tools/builtins/delegate.py:115** — 🟠 HIGH — Primitive Obsession  
   Function 'execute' has 7 primitive-typed parameters: agent: Name(id='str', ctx=Load()), task: Name(id='str', ctx=Load()), done_when: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), context: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), background: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), requirements: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), depends_on: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None))  
   → _Introduce Parameter Object — group related primitives into a dataclass or NamedTuple._

15. **tools/builtins/diff_view.py:79** — 🟠 HIGH — Primitive Obsession  
   Function 'execute' has 7 primitive-typed parameters: path: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), staged: Name(id='bool', ctx=Load()), compare: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), stat: Name(id='bool', ctx=Load()), name_only: Name(id='bool', ctx=Load()), context_lines: BinOp(left=Name(id='int', ctx=Load()), op=BitOr(), right=Constant(value=None)), cwd: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None))  
   → _Introduce Parameter Object — group related primitives into a dataclass or NamedTuple._


## 📊 Files Ranked by Quality

| Rank | File | Grade | Score | Smells | LOC | MI | Avg CC |
|-----:|:-----|:------|------:|-------:|----:|---:|-------:|
| 1 | cli/textual_bridge.py | ❌ F | 15.1 | 25 | 409 | 50 | 0.0 |
| 2 | tools/builtins/python_ast.py | ❌ F | 15.5 | 33 | 373 | 52 | 11.0 |
| 3 | cli/output_handler.py | ❌ F | 15.7 | 92 | 307 | 52 | 0.0 |
| 4 | cli/ui_renderer.py | ❌ F | 17.2 | 47 | 301 | 57 | 0.0 |
| 5 | tools/builtins/git_ops.py | ❌ F | 17.3 | 21 | 279 | 55 | 0.0 |
| 6 | metrics/dashboard.py | ❌ F | 17.6 | 40 | 270 | 59 | 14.0 |
| 7 | cli/commands/context.py | ❌ F | 21.3 | 45 | 475 | 48 | 0.0 |
| 8 | providers/anthropic.py | ❌ F | 22.9 | 38 | 471 | 41 | 0.0 |
| 9 | cli/repl.py | ❌ F | 23.9 | 22 | 347 | 52 | 16.0 |
| 10 | tools/builtins/file_edit.py | ❌ F | 25.0 | 19 | 231 | 62 | 13.0 |

## 📁 Per-File Details

_Showing 20 worst files. 168 additional files omitted._

### cli/textual_bridge.py — ❌ F (15.1/100)

LOC: 409 | Classes: 3 | Functions: 2 | MI: 50 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 121 | 🟡 MEDIUM | Duplicate Code | Function 'post' is 100% similar to '_post' at cli/textual_bridge.py:261 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 121 | 🟡 MEDIUM | Duplicate Code | Function 'post' is 100% similar to '_on_thought' at cli/textual_bridge.py:419 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 121 | 🟡 MEDIUM | Duplicate Code | Function 'post' is 94% similar to 'code' at cli/ui_renderer.py:307 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 121 | 🟡 MEDIUM | Duplicate Code | Function 'post' is 100% similar to 'add_auto_approve_policy' at tools/registry.py:151 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 121 | 🟡 MEDIUM | Duplicate Code | Function 'post' is 100% similar to 'remove_auto_approve_policy' at tools/registry.py:162 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 177 | 🟡 MEDIUM | Duplicate Code | Function 'post_tool_message' is 100% similar to '_add_message_with_prefix' at cli/textual_widgets.py:914 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 177 | 🟡 MEDIUM | Duplicate Code | Function 'post_tool_message' is 100% similar to 'add_user_message' at cli/textual_widgets.py:923 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 177 | 🟡 MEDIUM | Duplicate Code | Function 'post_tool_message' is 100% similar to 'add_system_message' at cli/textual_widgets.py:931 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 177 | 🟡 MEDIUM | Duplicate Code | Function 'post_tool_message' is 100% similar to 'add_error_message' at cli/textual_widgets.py:939 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 186 | 🟡 MEDIUM | Duplicate Code | Function 'post_status_message' is 100% similar to '_on_finished' at cli/textual_bridge.py:436 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 261 | 🟡 MEDIUM | Duplicate Code | Function '_post' is 100% similar to '_on_thought' at cli/textual_bridge.py:419 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 261 | 🟡 MEDIUM | Duplicate Code | Function '_post' is 94% similar to 'code' at cli/ui_renderer.py:307 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 261 | 🟡 MEDIUM | Duplicate Code | Function '_post' is 100% similar to 'add_auto_approve_policy' at tools/registry.py:151 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 261 | 🟡 MEDIUM | Duplicate Code | Function '_post' is 100% similar to 'remove_auto_approve_policy' at tools/registry.py:162 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 395 | 🟡 MEDIUM | Duplicate Code | Function '_create_status_message_handler' is 100% similar to '_create_prefixed_message_handler' at cli/textual_bridge.py:406 | Extract Shared Function — identify the common logic and parameterise the differences. |

_... and 10 more smells._

### tools/builtins/python_ast.py — ❌ F (15.5/100)

LOC: 373 | Classes: 1 | Functions: 0 | MI: 52 | Avg CC: 11.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 35 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 96% similar to 'parameters' at tools/builtins/python_exec.py:35 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 35 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/shell.py:330 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 35 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 92% similar to 'parameters' at tools/builtins/test_gen.py:34 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 35 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 96% similar to 'parameters' at tools/builtins/traceback_parse.py:46 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 35 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/web_fetch.py:27 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 35 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/web_search.py:27 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 58 | 🟡 MEDIUM | Feature Envy | Method 'PythonAstTool._get_docstring' accesses 'ast' 6 times but 'self' only 0 times | Move Method — consider moving '_get_docstring' to the class that owns 'ast'. |
| 130 | 🟡 MEDIUM | Feature Envy | Method 'PythonAstTool._format_function' accesses 'node' 6 times but 'self' only 3 times | Move Method — consider moving '_format_function' to the class that owns 'node'. |
| 130 | 🟡 MEDIUM | Complex Function | Function '_format_function' has cyclomatic complexity 11 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 190 | 🟡 MEDIUM | Feature Envy | Method 'PythonAstTool._format_class' accesses 'ast' 6 times but 'self' only 4 times | Move Method — consider moving '_format_class' to the class that owns 'ast'. |
| 190 | 🟡 MEDIUM | Feature Envy | Method 'PythonAstTool._format_class' accesses 'node' 5 times but 'self' only 4 times | Move Method — consider moving '_format_class' to the class that owns 'node'. |
| 325 | 🟡 MEDIUM | Duplicate Code | Function '_validate_path' is 98% similar to 'validate_file_path' at tools/utils.py:9 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 409 | 🟡 MEDIUM | Feature Envy | Method 'PythonAstTool._add_assignments_section' accesses 'ast' 5 times but 'self' only 0 times | Move Method — consider moving '_add_assignments_section' to the class that owns 'ast'. |
| 409 | 🟡 MEDIUM | Complex Function | Function '_add_assignments_section' has cyclomatic complexity 11 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 437 | 🟡 MEDIUM | Feature Envy | Method 'PythonAstTool._add_functions_and_classes_sections' accesses 'ast' 5 times but 'self' only 2 times | Move Method — consider moving '_add_functions_and_classes_sections' to the class that owns 'ast'. |

_... and 18 more smells._

### cli/output_handler.py — ❌ F (15.7/100)

LOC: 307 | Classes: 1 | Functions: 0 | MI: 52 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 230 | 🟡 MEDIUM | Duplicate Code | Function 'get_rich_status_message' is 94% similar to 'load' at cli/session_manager.py:133 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 230 | 🟡 MEDIUM | Duplicate Code | Function 'get_rich_status_message' is 94% similar to 'compute_project_hash' at cli/session_manager.py:207 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 255 | 🟡 MEDIUM | Duplicate Code | Function 'success' is 100% similar to 'error' at cli/output_handler.py:263 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 255 | 🟡 MEDIUM | Duplicate Code | Function 'success' is 100% similar to 'warning' at cli/output_handler.py:271 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 255 | 🟡 MEDIUM | Duplicate Code | Function 'success' is 100% similar to 'muted' at cli/output_handler.py:279 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 255 | 🟡 MEDIUM | Duplicate Code | Function 'success' is 100% similar to 'thinking' at cli/output_handler.py:287 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 255 | 🟡 MEDIUM | Duplicate Code | Function 'success' is 100% similar to 'print_agent_content' at cli/output_handler.py:295 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 255 | 🟡 MEDIUM | Duplicate Code | Function 'success' is 100% similar to 'complete_task' at cli/output_handler.py:360 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 255 | 🟡 MEDIUM | Duplicate Code | Function 'success' is 100% similar to 'set_session' at cli/repl.py:210 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 255 | 🟡 MEDIUM | Duplicate Code | Function 'success' is 100% similar to 'delete' at cli/session_manager.py:196 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 255 | 🟡 MEDIUM | Duplicate Code | Function 'success' is 100% similar to 'post' at cli/textual_bridge.py:121 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 255 | 🟡 MEDIUM | Duplicate Code | Function 'success' is 100% similar to '_post' at cli/textual_bridge.py:261 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 255 | 🟡 MEDIUM | Duplicate Code | Function 'success' is 100% similar to '_on_thought' at cli/textual_bridge.py:419 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 255 | 🟡 MEDIUM | Duplicate Code | Function 'success' is 94% similar to 'code' at cli/ui_renderer.py:307 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 255 | 🟡 MEDIUM | Duplicate Code | Function 'success' is 100% similar to 'add_auto_approve_policy' at tools/registry.py:151 | Extract Shared Function — identify the common logic and parameterise the differences. |

_... and 77 more smells._

### cli/ui_renderer.py — ❌ F (17.2/100)

LOC: 301 | Classes: 2 | Functions: 0 | MI: 57 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 49 | 🟠 HIGH | Primitive Obsession | Repeated primitive parameter group appears in: 'start_task' (line 49), 'start_task' (line 361) | Replace Data Value with Object — create a shared data structure for this recurring parameter group. |
| 73 | 🟠 HIGH | Primitive Obsession | Repeated primitive parameter group appears in: 'update_task' (line 73), 'update_task' (line 374) | Replace Data Value with Object — create a shared data structure for this recurring parameter group. |
| 100 | 🟡 MEDIUM | Large Class | Class 'UIRenderer' has 31 methods (threshold: 20) | Split Class — group related methods into smaller collaborating classes. |
| 307 | 🟡 MEDIUM | Duplicate Code | Function 'code' is 94% similar to 'add_auto_approve_policy' at tools/registry.py:151 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 307 | 🟡 MEDIUM | Duplicate Code | Function 'code' is 94% similar to 'remove_auto_approve_policy' at tools/registry.py:162 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 327 | 🟡 MEDIUM | Duplicate Code | Function 'tool_summary' is 100% similar to 'update_task' at cli/ui_renderer.py:374 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 40 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: missing return type | Add Type Annotations for all parameters and return type. |
| 49 | 🟢 LOW | Missing Type Hint | Function 'start_task' has incomplete type hints: 1/4 params untyped | Add Type Annotations for all parameters and return type. |
| 49 | 🟢 LOW | Primitive Obsession | Function 'start_task' has 3 primitive-typed parameters: task_id: Name(id='str', ctx=Load()), description: Name(id='str', ctx=Load()), total: Name(id='int', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 73 | 🟢 LOW | Missing Type Hint | Function 'update_task' has incomplete type hints: 1/4 params untyped | Add Type Annotations for all parameters and return type. |
| 73 | 🟢 LOW | Primitive Obsession | Function 'update_task' has 3 primitive-typed parameters: task_id: Name(id='str', ctx=Load()), advance: Name(id='int', ctx=Load()), description: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 88 | 🟢 LOW | Missing Type Hint | Function 'complete_task' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 112 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/6 params untyped | Add Type Annotations for all parameters and return type. |
| 141 | 🟢 LOW | Missing Type Hint | Function 'print_welcome' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 145 | 🟢 LOW | Missing Type Hint | Function 'print_goodbye' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |

_... and 32 more smells._

### tools/builtins/git_ops.py — ❌ F (17.3/100)

LOC: 279 | Classes: 1 | Functions: 0 | MI: 55 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 144 | 🟠 HIGH | Primitive Obsession | Function 'execute' has 9 primitive-typed parameters: action: Name(id='str', ctx=Load()), path: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), ref: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), ref2: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), max_count: Name(id='int', ctx=Load()), start_line: BinOp(left=Name(id='int', ctx=Load()), op=BitOr(), right=Constant(value=None)), end_line: BinOp(left=Name(id='int', ctx=Load()), op=BitOr(), right=Constant(value=None)), stat: Name(id='bool', ctx=Load()), cwd: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 220 | 🟠 HIGH | Duplicate Code | Function '_status' is an exact duplicate of '_branch_list' at tools/builtins/git_ops.py:279 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 260 | 🟠 HIGH | Primitive Obsession | Repeated primitive parameter group appears in: '_show' (line 260), '_diff_branches' (line 294) | Replace Data Value with Object — create a shared data structure for this recurring parameter group. |
| 47 | 🟡 MEDIUM | Long Method | Function 'parameters' has 53 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 47 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 93% similar to 'parameters' at tools/builtins/kg_query.py:69 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 47 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 96% similar to 'parameters' at tools/builtins/lint_check.py:35 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 47 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 92% similar to 'parameters' at tools/builtins/pytest_run.py:52 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 47 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 92% similar to 'parameters' at tools/builtins/shell.py:330 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 47 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/test_gen.py:34 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 47 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 92% similar to 'parameters' at tools/builtins/web_fetch.py:27 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 224 | 🟡 MEDIUM | Primitive Obsession | Function '_log' has 5 primitive-typed parameters: path: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), ref: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), max_count: Name(id='int', ctx=Load()), stat: Name(id='bool', ctx=Load()), cwd: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 243 | 🟡 MEDIUM | Primitive Obsession | Function '_blame' has 4 primitive-typed parameters: path: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), start_line: BinOp(left=Name(id='int', ctx=Load()), op=BitOr(), right=Constant(value=None)), end_line: BinOp(left=Name(id='int', ctx=Load()), op=BitOr(), right=Constant(value=None)), cwd: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 260 | 🟡 MEDIUM | Primitive Obsession | Function '_show' has 4 primitive-typed parameters: ref: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), path: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), stat: Name(id='bool', ctx=Load()), cwd: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 294 | 🟡 MEDIUM | Primitive Obsession | Function '_diff_branches' has 5 primitive-typed parameters: ref: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), ref2: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), stat: Name(id='bool', ctx=Load()), path: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), cwd: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 80 | 🟢 LOW | Magic Number | Magic number 20 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |

_... and 6 more smells._

### metrics/dashboard.py — ❌ F (17.6/100)

LOC: 270 | Classes: 1 | Functions: 0 | MI: 59 | Avg CC: 14.0

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

### cli/commands/context.py — ❌ F (21.3/100)

LOC: 475 | Classes: 6 | Functions: 0 | MI: 48 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 66 | 🟢 LOW | Missing Type Hint | Function 'get_display_label' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 74 | 🟢 LOW | Missing Type Hint | Function 'validate_value' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 94 | 🟢 LOW | Missing Type Hint | Function 'parse_value' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 112 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 120 | 🟢 LOW | Missing Type Hint | Function 'print_status_info' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 131 | 🟢 LOW | Missing Type Hint | Function 'print_strategy_usage' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 142 | 🟢 LOW | Missing Type Hint | Function 'print_strategy_status' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 157 | 🟢 LOW | Missing Type Hint | Function '_print_context_settings' has incomplete type hints: 1/4 params untyped | Add Type Annotations for all parameters and return type. |
| 191 | 🟢 LOW | Missing Type Hint | Function '_print_available_commands' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 208 | 🟢 LOW | Missing Type Hint | Function '_print_strategy_parameters' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 233 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 254 | 🟢 LOW | Missing Type Hint | Function 'manage_strategy' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 277 | 🟢 LOW | Missing Type Hint | Function '_show_strategy_status' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 286 | 🟢 LOW | Missing Type Hint | Function '_load_context_settings' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 295 | 🟢 LOW | Missing Type Hint | Function '_set_strategy_parameter' has incomplete type hints: 1/4 params untyped | Add Type Annotations for all parameters and return type. |

_... and 30 more smells._

### providers/anthropic.py — ❌ F (22.9/100)

LOC: 471 | Classes: 5 | Functions: 0 | MI: 41 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 121 | 🟡 MEDIUM | Feature Envy | Method '_AnthropicStreamProcessor.process_stream' accesses 'chunk' 7 times but 'self' only 3 times | Move Method — consider moving 'process_stream' to the class that owns 'chunk'. |
| 204 | 🟡 MEDIUM | Feature Envy | Method '_AnthropicStreamProcessor._handle_content_block_delta' accesses 'delta' 5 times but 'self' only 3 times | Move Method — consider moving '_handle_content_block_delta' to the class that owns 'delta'. |
| 340 | 🟡 MEDIUM | Duplicate Code | Function '_format_tool' is 95% similar to 'to_metadata' at rag/chunker.py:42 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 61 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 75 | 🟢 LOW | Missing Type Hint | Function '_should_yield' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 112 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 121 | 🟢 LOW | Missing Type Hint | Function 'process_stream' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 164 | 🟢 LOW | Missing Type Hint | Function '_process_event' has incomplete type hints: 1/5 params untyped | Add Type Annotations for all parameters and return type. |
| 184 | 🟢 LOW | Missing Type Hint | Function '_handle_content_block_start' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 184 | 🟢 LOW | Feature Envy | Method '_AnthropicStreamProcessor._handle_content_block_start' accesses 'block' 3 times but 'self' only 0 times | Move Method — consider moving '_handle_content_block_start' to the class that owns 'block'. |
| 204 | 🟢 LOW | Missing Type Hint | Function '_handle_content_block_delta' has incomplete type hints: 1/5 params untyped | Add Type Annotations for all parameters and return type. |
| 238 | 🟢 LOW | Missing Type Hint | Function '_handle_content_block_stop' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 243 | 🟢 LOW | Missing Type Hint | Function '_handle_message_delta' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 261 | 🟢 LOW | Missing Type Hint | Function '_build_tool_calls_from_pending' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 295 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |

_... and 23 more smells._

### cli/repl.py — ❌ F (23.9/100)

LOC: 347 | Classes: 2 | Functions: 0 | MI: 52 | Avg CC: 16.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 83 | 🟠 HIGH | Long Method | Function '__init__' has 107 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 83 | 🟡 MEDIUM | Complex Function | Function '__init__' has cyclomatic complexity 16 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 210 | 🟡 MEDIUM | Duplicate Code | Function 'set_session' is 100% similar to 'delete' at cli/session_manager.py:196 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 210 | 🟡 MEDIUM | Duplicate Code | Function 'set_session' is 100% similar to 'post' at cli/textual_bridge.py:121 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 210 | 🟡 MEDIUM | Duplicate Code | Function 'set_session' is 100% similar to '_post' at cli/textual_bridge.py:261 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 210 | 🟡 MEDIUM | Duplicate Code | Function 'set_session' is 100% similar to '_on_thought' at cli/textual_bridge.py:419 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 210 | 🟡 MEDIUM | Duplicate Code | Function 'set_session' is 94% similar to 'code' at cli/ui_renderer.py:307 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 210 | 🟡 MEDIUM | Duplicate Code | Function 'set_session' is 100% similar to 'add_auto_approve_policy' at tools/registry.py:151 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 210 | 🟡 MEDIUM | Duplicate Code | Function 'set_session' is 100% similar to 'remove_auto_approve_policy' at tools/registry.py:162 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 218 | 🟡 MEDIUM | Duplicate Code | Function '_handle_confirmation' is 95% similar to 'confirm_tool_execution' at cli/ui_renderer.py:350 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 359 | 🟡 MEDIUM | Long Method | Function '_run_agent_with_monitor' has 52 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 359 | 🟡 MEDIUM | Feature Envy | Method 'Repl._run_agent_with_monitor' accesses 'asyncio' 8 times but 'self' only 7 times | Move Method — consider moving '_run_agent_with_monitor' to the class that owns 'asyncio'. |
| 427 | 🟡 MEDIUM | Feature Envy | Method 'Repl._handle_agent_event' accesses 'event' 5 times but 'self' only 1 times | Move Method — consider moving '_handle_agent_event' to the class that owns 'event'. |
| 65 | 🟢 LOW | Magic Number | Magic number 25 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 66 | 🟢 LOW | Magic Number | Magic number 100 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |

_... and 7 more smells._

### tools/builtins/file_edit.py — ❌ F (25.0/100)

LOC: 231 | Classes: 1 | Functions: 0 | MI: 62 | Avg CC: 13.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 73 | 🟠 HIGH | Primitive Obsession | Function 'execute' has 6 primitive-typed parameters: path: Name(id='str', ctx=Load()), old_str: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), new_str: Name(id='str', ctx=Load()), start_line: BinOp(left=Name(id='int', ctx=Load()), op=BitOr(), right=Constant(value=None)), end_line: BinOp(left=Name(id='int', ctx=Load()), op=BitOr(), right=Constant(value=None)), dry_run: Name(id='bool', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 34 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/file_write.py:28 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 34 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 92% similar to 'parameters' at tools/builtins/git_ops.py:47 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 34 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/glob_tool.py:31 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 34 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/pytest_run.py:52 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 34 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/python_ast.py:35 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 34 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 96% similar to 'parameters' at tools/builtins/python_exec.py:35 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 34 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/shell.py:330 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 34 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 92% similar to 'parameters' at tools/builtins/test_gen.py:34 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 34 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 96% similar to 'parameters' at tools/builtins/traceback_parse.py:46 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 34 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/web_fetch.py:27 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 34 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/web_search.py:27 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 73 | 🟡 MEDIUM | Long Method | Function 'execute' has 51 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 73 | 🟡 MEDIUM | Complex Function | Function 'execute' has cyclomatic complexity 13 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 150 | 🟡 MEDIUM | Primitive Obsession | Function '_edit_string' has 4 primitive-typed parameters: content: Name(id='str', ctx=Load()), old_str: Name(id='str', ctx=Load()), new_str: Name(id='str', ctx=Load()), dry_run: Name(id='bool', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |

_... and 4 more smells._

### metrics/storage.py — ❌ F (26.7/100)

LOC: 660 | Classes: 5 | Functions: 0 | MI: 47 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 515 | 🟡 MEDIUM | Feature Envy | Method 'MetricsStorage._create_base_metric_dict' accesses 'metric' 7 times but 'self' only 0 times | Move Method — consider moving '_create_base_metric_dict' to the class that owns 'metric'. |
| 708 | 🟡 MEDIUM | Feature Envy | Method 'MetricsStorage._build_metrics_query' accesses 'query_params' 6 times but 'self' only 0 times | Move Method — consider moving '_build_metrics_query' to the class that owns 'query_params'. |
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
| 340 | 🟢 LOW | Missing Type Hint | Function '_build_aggregation_query' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |

_... and 23 more smells._

### cli/commands/__init__.py — ❌ F (27.9/100)

LOC: 157 | Classes: 4 | Functions: 2 | MI: 63 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 138 | 🟡 MEDIUM | Duplicate Code | Function '__init__' is 100% similar to '__init__' at extensions/manager.py:40 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 142 | 🟡 MEDIUM | Duplicate Code | Function 'register' is 100% similar to 'register_theme' at cli/console.py:356 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 150 | 🟡 MEDIUM | Duplicate Code | Function 'get' is 100% similar to 'get' at extensions/manager.py:68 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 150 | 🟡 MEDIUM | Duplicate Code | Function 'get' is 95% similar to 'get' at tools/registry.py:107 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 161 | 🟡 MEDIUM | Duplicate Code | Function 'get_commands' is 100% similar to 'list_commands' at cli/commands/__init__.py:169 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 161 | 🟡 MEDIUM | Duplicate Code | Function 'get_commands' is 100% similar to 'list_extensions' at extensions/manager.py:79 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 161 | 🟡 MEDIUM | Duplicate Code | Function 'get_commands' is 100% similar to 'get_server_names' at mcp/manager.py:38 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 161 | 🟡 MEDIUM | Duplicate Code | Function 'get_commands' is 100% similar to 'list_providers' at providers/registry.py:47 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 161 | 🟡 MEDIUM | Duplicate Code | Function 'get_commands' is 100% similar to 'list_tools' at tools/registry.py:126 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 169 | 🟡 MEDIUM | Duplicate Code | Function 'list_commands' is 100% similar to 'list_extensions' at extensions/manager.py:79 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 169 | 🟡 MEDIUM | Duplicate Code | Function 'list_commands' is 100% similar to 'get_server_names' at mcp/manager.py:38 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 169 | 🟡 MEDIUM | Duplicate Code | Function 'list_commands' is 100% similar to 'list_providers' at providers/registry.py:47 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 169 | 🟡 MEDIUM | Duplicate Code | Function 'list_commands' is 100% similar to 'list_tools' at tools/registry.py:126 | Extract Shared Function — identify the common logic and parameterise the differences. |
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

### metrics/collector.py — ❌ F (31.5/100)

LOC: 345 | Classes: 1 | Functions: 0 | MI: 51 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 40 | 🟡 MEDIUM | Primitive Obsession | Function '__init__' has 5 primitive-typed parameters: enabled: Name(id='bool', ctx=Load()), anonymize: Name(id='bool', ctx=Load()), sampling_rate: Name(id='float', ctx=Load()), session_id: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), user_id: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 147 | 🟡 MEDIUM | Feature Envy | Method 'MetricsCollector.record_token_usage' accesses 'usage' 7 times but 'self' only 6 times | Move Method — consider moving 'record_token_usage' to the class that owns 'usage'. |
| 195 | 🟡 MEDIUM | Feature Envy | Method 'MetricsCollector.record_cost' accesses 'cost' 8 times but 'self' only 6 times | Move Method — consider moving 'record_cost' to the class that owns 'cost'. |
| 244 | 🟡 MEDIUM | Primitive Obsession | Function 'track_tool_execution' has 4 primitive-typed parameters: tool_name: Name(id='str', ctx=Load()), tool_category: Name(id='str', ctx=Load()), input_size: BinOp(left=Name(id='int', ctx=Load()), op=BitOr(), right=Constant(value=None)), agent_id: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 308 | 🟡 MEDIUM | Feature Envy | Method 'MetricsCollector.record_performance_event' accesses 'event' 6 times but 'self' only 5 times | Move Method — consider moving 'record_performance_event' to the class that owns 'event'. |
| 28 | 🟢 LOW | Large Class | Class 'MetricsCollector' spans 388 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
| 40 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/7 params untyped | Add Type Annotations for all parameters and return type. |
| 77 | 🟢 LOW | Missing Type Hint | Function '_generate_session_id' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 82 | 🟢 LOW | Missing Type Hint | Function '_hash_user_id' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 84 | 🟢 LOW | Magic Number | Magic number 16 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 86 | 🟢 LOW | Missing Type Hint | Function 'should_sample' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 95 | 🟢 LOW | Missing Type Hint | Function 'start_command' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 111 | 🟢 LOW | Missing Type Hint | Function 'end_command' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 123 | 🟢 LOW | Magic Number | Magic number 1000 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 147 | 🟢 LOW | Long Method | Function 'record_token_usage' has 35 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |

_... and 16 more smells._

### tools/builtins/shell.py — ❌ F (33.4/100)

LOC: 500 | Classes: 2 | Functions: 12 | MI: 48 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 116 | 🟡 MEDIUM | Primitive Obsession | Function '_make_result' has 4 primitive-typed parameters: output: Name(id='str', ctx=Load()), returncode: BinOp(left=Name(id='int', ctx=Load()), op=BitOr(), right=Constant(value=None)), timed_out: Name(id='bool', ctx=Load()), timeout_value: BinOp(left=Name(id='float', ctx=Load()), op=BitOr(), right=Constant(value=None)) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 330 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 92% similar to 'parameters' at tools/builtins/test_gen.py:34 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 330 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 96% similar to 'parameters' at tools/builtins/traceback_parse.py:46 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 330 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/web_fetch.py:27 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 330 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/web_search.py:27 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 501 | 🟡 MEDIUM | Long Method | Function '_execute_interactive_sudo' has 73 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 501 | 🟡 MEDIUM | Feature Envy | Method 'ShellTool._execute_interactive_sudo' accesses 'process' 6 times but 'self' only 2 times | Move Method — consider moving '_execute_interactive_sudo' to the class that owns 'process'. |
| 280 | 🟢 LOW | Large Class | Class 'ShellTool' spans 370 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
| 330 | 🟢 LOW | Long Method | Function 'parameters' has 31 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 370 | 🟢 LOW | Primitive Obsession | Function 'execute' has 3 primitive-typed parameters: command: Name(id='str', ctx=Load()), timeout: BinOp(left=Name(id='int', ctx=Load()), op=BitOr(), right=Constant(value=None)), cwd: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 419 | 🟢 LOW | Primitive Obsession | Function '_create_process' has 3 primitive-typed parameters: command: Name(id='str', ctx=Load()), cwd: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), is_sudo: Name(id='bool', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 419 | 🟢 LOW | Feature Envy | Method 'ShellTool._create_process' accesses 'asyncio' 4 times but 'self' only 0 times | Move Method — consider moving '_create_process' to the class that owns 'asyncio'. |
| 444 | 🟢 LOW | Magic Number | Magic number 5 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 454 | 🟢 LOW | Feature Envy | Method 'ShellTool._run_and_collect' accesses 'asyncio' 3 times but 'self' only 0 times | Move Method — consider moving '_run_and_collect' to the class that owns 'asyncio'. |
| 454 | 🟢 LOW | Feature Envy | Method 'ShellTool._run_and_collect' accesses 'process' 3 times but 'self' only 0 times | Move Method — consider moving '_run_and_collect' to the class that owns 'process'. |

_... and 11 more smells._

### knowledge/store.py — ❌ F (35.5/100)

LOC: 397 | Classes: 1 | Functions: 4 | MI: 48 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 459 | 🟠 HIGH | Feature Envy | Method 'KnowledgeStore.format_entity_for_llm' accesses 'entity' 11 times but 'self' only 1 times | Move Method — consider moving 'format_entity_for_llm' to the class that owns 'entity'. |
| 93 | 🟢 LOW | Large Class | Class 'KnowledgeStore' spans 422 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
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
| 244 | 🟢 LOW | Missing Type Hint | Function 'search_entities' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 244 | 🟢 LOW | Feature Envy | Method 'KnowledgeStore.search_entities' accesses 'entity' 3 times but 'self' only 1 times | Move Method — consider moving 'search_entities' to the class that owns 'entity'. |

_... and 16 more smells._

### agents/metrics_reporter.py — ❌ F (35.6/100)

LOC: 186 | Classes: 1 | Functions: 0 | MI: 51 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 54 | 🟡 MEDIUM | Duplicate Code | Function '_generate_efficiency_metrics' is 100% similar to '_generate_quality_metrics' at agents/metrics_reporter.py:63 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 54 | 🟡 MEDIUM | Duplicate Code | Function '_generate_efficiency_metrics' is 100% similar to '_generate_target_metrics' at agents/metrics_reporter.py:72 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 63 | 🟡 MEDIUM | Duplicate Code | Function '_generate_quality_metrics' is 100% similar to '_generate_target_metrics' at agents/metrics_reporter.py:72 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 176 | 🟡 MEDIUM | Duplicate Code | Function '_format_code_coverage' is 100% similar to '_format_documentation_coverage' at agents/metrics_reporter.py:188 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 218 | 🟡 MEDIUM | Duplicate Code | Function '_format_error_rate_target' is 100% similar to '_format_context_window_target' at agents/metrics_reporter.py:227 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 26 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 29 | 🟢 LOW | Missing Type Hint | Function 'get_metrics_report' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 54 | 🟢 LOW | Missing Type Hint | Function '_generate_efficiency_metrics' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 63 | 🟢 LOW | Missing Type Hint | Function '_generate_quality_metrics' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 72 | 🟢 LOW | Missing Type Hint | Function '_generate_target_metrics' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 81 | 🟢 LOW | Missing Type Hint | Function '_generate_detailed_statistics' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 101 | 🟢 LOW | Missing Type Hint | Function '_format_tool_call_statistics' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 101 | 🟢 LOW | Feature Envy | Method 'MetricsReporter._format_tool_call_statistics' accesses 'lines' 4 times but 'self' only 1 times | Move Method — consider moving '_format_tool_call_statistics' to the class that owns 'lines'. |
| 101 | 🟢 LOW | Feature Envy | Method 'MetricsReporter._format_tool_call_statistics' accesses 'tools' 4 times but 'self' only 1 times | Move Method — consider moving '_format_tool_call_statistics' to the class that owns 'tools'. |
| 122 | 🟢 LOW | Missing Type Hint | Function '_format_task_completion_time' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |

_... and 13 more smells._

### cli/commands/model.py — ❌ F (39.5/100)

LOC: 288 | Classes: 1 | Functions: 0 | MI: 55 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 77 | 🟡 MEDIUM | Feature Envy | Method 'ModelCommand._print_current_configuration' accesses 'console' 7 times but 'self' only 0 times | Move Method — consider moving '_print_current_configuration' to the class that owns 'console'. |
| 100 | 🟡 MEDIUM | Feature Envy | Method 'ModelCommand._list_providers' accesses 'console' 7 times but 'self' only 2 times | Move Method — consider moving '_list_providers' to the class that owns 'console'. |
| 215 | 🟡 MEDIUM | Feature Envy | Method 'ModelCommand._test_provider_connection' accesses 'console' 7 times but 'self' only 0 times | Move Method — consider moving '_test_provider_connection' to the class that owns 'console'. |
| 242 | 🟡 MEDIUM | Feature Envy | Method 'ModelCommand._update_agent_provider' accesses 'ctx' 6 times but 'self' only 0 times | Move Method — consider moving '_update_agent_provider' to the class that owns 'ctx'. |
| 269 | 🟡 MEDIUM | Feature Envy | Method 'ModelCommand._show_configuration_warnings' accesses 'console' 6 times but 'self' only 1 times | Move Method — consider moving '_show_configuration_warnings' to the class that owns 'console'. |
| 12 | 🟢 LOW | Large Class | Class 'ModelCommand' spans 373 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
| 18 | 🟢 LOW | Missing Type Hint | Function 'name' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 27 | 🟢 LOW | Missing Type Hint | Function 'description' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 36 | 🟢 LOW | Missing Type Hint | Function 'usage' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 44 | 🟢 LOW | Missing Type Hint | Function 'execute' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 60 | 🟢 LOW | Missing Type Hint | Function '_show_current' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 60 | 🟢 LOW | Feature Envy | Method 'ModelCommand._show_current' accesses 'ctx' 4 times but 'self' only 1 times | Move Method — consider moving '_show_current' to the class that owns 'ctx'. |
| 77 | 🟢 LOW | Missing Type Hint | Function '_print_current_configuration' has incomplete type hints: 1/4 params untyped | Add Type Annotations for all parameters and return type. |
| 100 | 🟢 LOW | Long Method | Function '_list_providers' has 30 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 100 | 🟢 LOW | Missing Type Hint | Function '_list_providers' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |

_... and 11 more smells._

### agents/metrics.py — ❌ F (39.7/100)

LOC: 320 | Classes: 5 | Functions: 1 | MI: 53 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 59 | 🟡 MEDIUM | Duplicate Code | Function '__init__' is 92% similar to '__init__' at agents/metrics.py:111 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 91 | 🟡 MEDIUM | Duplicate Code | Function 'track_file_access' is 100% similar to 'track_tool_usage' at agents/metrics.py:99 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 148 | 🟡 MEDIUM | Duplicate Code | Function 'reset' is 93% similar to '__init__' at cli/textual_mixins.py:109 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 160 | 🟡 MEDIUM | Feature Envy | Method 'ToolMetrics.track_tool_call' accesses 'TC' 5 times but 'self' only 3 times | Move Method — consider moving 'track_tool_call' to the class that owns 'TC'. |
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

_... and 12 more smells._

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

## ✨ Clean Files (59 files with no smells)

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
