# Code Smell Report — ❌ F (Score: 53.5/100)

_Scanned: /home/matthew/mlg-cli/src/henchman_  

_Generated: 2026-03-03T08:30:21.324735+00:00_

## Executive Summary

| Metric | Value |
|:-------|------:|
| **Overall Grade** | ❌ F |
| **Overall Score** | 53.5/100 |
| **Files Scanned** | 189 |
| **Total Lines (non-blank)** | 34,388 |
| **Total Smells** | 2143 |
| **Avg Maintainability Index** | 71.7 |
| **Avg Cyclomatic Complexity** | 14.1 |

### Smells by Severity

| Severity | Count |
|:---------|------:|
| low | 1631 |
| medium | 447 |
| high | 65 |

### Smells by Category

| Category | Count |
|:---------|------:|
| Missing Type Hint | 1143 |
| Feature Envy | 298 |
| Duplicate Code | 238 |
| Magic Number | 129 |
| Long Method | 108 |
| Deep Nesting | 98 |
| Primitive Obsession | 72 |
| Complex Function | 30 |
| Large Class | 27 |

## 🎯 Prioritised Refactoring Queue

These are the highest-impact smells to address first:

1. **cli/app.py:645** — 🟠 HIGH — Primitive Obsession  
   Function 'chat_command' has 8 primitive-typed parameters: prompt: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), agent: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), team: Name(id='bool', ctx=Load()), output_format: Name(id='str', ctx=Load()), plan: Name(id='bool', ctx=Load()), yes: Name(id='bool', ctx=Load()), tui: Name(id='bool', ctx=Load()), debug: Name(id='bool', ctx=Load())  
   → _Introduce Parameter Object — group related primitives into a dataclass or NamedTuple._

2. **cli/commands/plan.py:32** — 🟠 HIGH — Feature Envy  
   Method 'PlanCommand.execute' accesses 'ctx' 13 times but 'self' only 0 times  
   → _Move Method — consider moving 'execute' to the class that owns 'ctx'._

3. **cli/json_output.py:37** — 🟠 HIGH — Duplicate Code  
   Function 'render' is an exact duplicate of 'render_stream_json' at cli/json_output.py:71  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

4. **cli/repl.py:78** — 🟠 HIGH — Long Method  
   Function '__init__' has 105 lines (threshold: 30)  
   → _Extract Method — break this function into smaller, intention-revealing helper functions._

5. **cli/textual_bridge.py:199** — 🟠 HIGH — Duplicate Code  
   Function '_on_content' is an exact duplicate of '_on_thought' at cli/textual_bridge.py:204  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

6. **cli/textual_bridge.py:209** — 🟠 HIGH — Duplicate Code  
   Function '_on_tool_req' is an exact duplicate of '_on_tool_res' at cli/textual_bridge.py:214  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

7. **cli/textual_bridge.py:209** — 🟠 HIGH — Duplicate Code  
   Function '_on_tool_req' is an exact duplicate of '_on_tool_confirm' at cli/textual_bridge.py:219  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

8. **cli/textual_bridge.py:214** — 🟠 HIGH — Duplicate Code  
   Function '_on_tool_res' is an exact duplicate of '_on_tool_confirm' at cli/textual_bridge.py:219  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

9. **cli/textual_bridge.py:246** — 🟠 HIGH — Duplicate Code  
   Function '_on_turn_summary' is an exact duplicate of '_on_think_start' at cli/textual_bridge.py:312  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

10. **cli/textual_bridge.py:246** — 🟠 HIGH — Duplicate Code  
   Function '_on_turn_summary' is an exact duplicate of '_on_think_done' at cli/textual_bridge.py:316  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

11. **cli/textual_bridge.py:246** — 🟠 HIGH — Duplicate Code  
   Function '_on_turn_summary' is an exact duplicate of '_on_think_req' at cli/textual_bridge.py:320  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

12. **cli/textual_bridge.py:312** — 🟠 HIGH — Duplicate Code  
   Function '_on_think_start' is an exact duplicate of '_on_think_done' at cli/textual_bridge.py:316  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

13. **cli/textual_bridge.py:312** — 🟠 HIGH — Duplicate Code  
   Function '_on_think_start' is an exact duplicate of '_on_think_req' at cli/textual_bridge.py:320  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

14. **cli/textual_bridge.py:316** — 🟠 HIGH — Duplicate Code  
   Function '_on_think_done' is an exact duplicate of '_on_think_req' at cli/textual_bridge.py:320  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

15. **cli/textual_bridge.py:329** — 🟠 HIGH — Duplicate Code  
   Function '_on_deleg_dec' is an exact duplicate of '_on_reflection' at cli/textual_bridge.py:339  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._


## 📊 Files Ranked by Quality

| Rank | File | Grade | Score | Smells | LOC | MI | Avg CC |
|-----:|:-----|:------|------:|-------:|----:|---:|-------:|
| 1 | cli/commands/context.py | ❌ F | 14.3 | 55 | 473 | 48 | 0.0 |
| 2 | cli/textual_bridge.py | ❌ F | 15.7 | 54 | 317 | 52 | 0.0 |
| 3 | tools/builtins/grep.py | ❌ F | 15.7 | 32 | 436 | 52 | 0.0 |
| 4 | tools/builtins/python_ast.py | ❌ F | 15.7 | 52 | 335 | 52 | 11.0 |
| 5 | tools/builtins/test_gen.py | ❌ F | 15.8 | 31 | 327 | 53 | 16.0 |
| 6 | cli/output_handler.py | ❌ F | 15.9 | 40 | 303 | 53 | 0.0 |
| 7 | metrics/collector.py | ❌ F | 15.9 | 33 | 341 | 53 | 14.0 |
| 8 | tools/builtins/git_ops.py | ❌ F | 16.5 | 31 | 273 | 55 | 0.0 |
| 9 | extensions/plugin_manager.py | ❌ F | 16.9 | 27 | 282 | 56 | 12.0 |
| 10 | metrics/dashboard.py | ❌ F | 16.9 | 40 | 265 | 56 | 14.0 |

## 📁 Per-File Details

_Showing 20 worst files. 169 additional files omitted._

### cli/commands/context.py — ❌ F (14.3/100)

LOC: 473 | Classes: 5 | Functions: 0 | MI: 48 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 89 | 🟡 MEDIUM | Duplicate Code | Function '__init__' is 100% similar to '__init__' at cli/json_output.py:29 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 97 | 🟡 MEDIUM | Duplicate Code | Function 'print_status_info' is 94% similar to 'print_usage' at cli/commands/session.py:138 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 97 | 🟡 MEDIUM | Duplicate Code | Function 'print_status_info' is 94% similar to '_add_message_with_prefix' at cli/textual_widgets.py:915 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 97 | 🟡 MEDIUM | Duplicate Code | Function 'print_status_info' is 94% similar to 'add_user_message' at cli/textual_widgets.py:924 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 97 | 🟡 MEDIUM | Duplicate Code | Function 'print_status_info' is 94% similar to 'add_system_message' at cli/textual_widgets.py:932 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 97 | 🟡 MEDIUM | Duplicate Code | Function 'print_status_info' is 94% similar to 'add_error_message' at cli/textual_widgets.py:940 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 108 | 🟡 MEDIUM | Duplicate Code | Function '_print_status_header' is 100% similar to 'unregister' at tools/registry.py:93 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 45 | 🟢 LOW | Missing Type Hint | Function 'get_display_label' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 53 | 🟢 LOW | Missing Type Hint | Function 'validate_value' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 71 | 🟢 LOW | Missing Type Hint | Function 'parse_value' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 89 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 97 | 🟢 LOW | Missing Type Hint | Function 'print_status_info' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 108 | 🟢 LOW | Missing Type Hint | Function '_print_status_header' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 116 | 🟢 LOW | Missing Type Hint | Function '_print_status_values' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 131 | 🟢 LOW | Magic Number | Magic number 100 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |

_... and 40 more smells._

### cli/textual_bridge.py — ❌ F (15.7/100)

LOC: 317 | Classes: 2 | Functions: 2 | MI: 52 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 199 | 🟠 HIGH | Duplicate Code | Function '_on_content' is an exact duplicate of '_on_thought' at cli/textual_bridge.py:204 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 209 | 🟠 HIGH | Duplicate Code | Function '_on_tool_req' is an exact duplicate of '_on_tool_res' at cli/textual_bridge.py:214 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 209 | 🟠 HIGH | Duplicate Code | Function '_on_tool_req' is an exact duplicate of '_on_tool_confirm' at cli/textual_bridge.py:219 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 214 | 🟠 HIGH | Duplicate Code | Function '_on_tool_res' is an exact duplicate of '_on_tool_confirm' at cli/textual_bridge.py:219 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 246 | 🟠 HIGH | Duplicate Code | Function '_on_turn_summary' is an exact duplicate of '_on_think_start' at cli/textual_bridge.py:312 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 246 | 🟠 HIGH | Duplicate Code | Function '_on_turn_summary' is an exact duplicate of '_on_think_done' at cli/textual_bridge.py:316 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 246 | 🟠 HIGH | Duplicate Code | Function '_on_turn_summary' is an exact duplicate of '_on_think_req' at cli/textual_bridge.py:320 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 312 | 🟠 HIGH | Duplicate Code | Function '_on_think_start' is an exact duplicate of '_on_think_done' at cli/textual_bridge.py:316 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 312 | 🟠 HIGH | Duplicate Code | Function '_on_think_start' is an exact duplicate of '_on_think_req' at cli/textual_bridge.py:320 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 316 | 🟠 HIGH | Duplicate Code | Function '_on_think_done' is an exact duplicate of '_on_think_req' at cli/textual_bridge.py:320 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 329 | 🟠 HIGH | Duplicate Code | Function '_on_deleg_dec' is an exact duplicate of '_on_reflection' at cli/textual_bridge.py:339 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 255 | 🟡 MEDIUM | Feature Envy | Method 'EventBridge._on_turn_status' accesses 'event' 6 times but 'self' only 2 times | Move Method — consider moving '_on_turn_status' to the class that owns 'event'. |
| 282 | 🟡 MEDIUM | Feature Envy | Method 'EventBridge._on_agent_done' accesses 'event' 5 times but 'self' only 1 times | Move Method — consider moving '_on_agent_done' to the class that owns 'event'. |
| 293 | 🟡 MEDIUM | Feature Envy | Method 'EventBridge._on_delegated' accesses 'event' 6 times but 'self' only 2 times | Move Method — consider moving '_on_delegated' to the class that owns 'event'. |
| 48 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |

_... and 39 more smells._

### tools/builtins/grep.py — ❌ F (15.7/100)

LOC: 436 | Classes: 1 | Functions: 0 | MI: 52 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 160 | 🟠 HIGH | Primitive Obsession | Function 'execute' has 10 primitive-typed parameters: pattern: Name(id='str', ctx=Load()), path: Name(id='str', ctx=Load()), ignore_case: Name(id='bool', ctx=Load()), line_numbers: Name(id='bool', ctx=Load()), glob: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), context_before: Name(id='int', ctx=Load()), context_after: Name(id='int', ctx=Load()), invert_match: Name(id='bool', ctx=Load()), whole_word: Name(id='bool', ctx=Load()), count_only: Name(id='bool', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 318 | 🟠 HIGH | Primitive Obsession | Function '_search_files_with_results' has 6 primitive-typed parameters: invert_match: Name(id='bool', ctx=Load()), has_context: Name(id='bool', ctx=Load()), context_before: Name(id='int', ctx=Load()), context_after: Name(id='int', ctx=Load()), line_numbers: Name(id='bool', ctx=Load()), multi_file: Name(id='bool', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 318 | 🟠 HIGH | Primitive Obsession | Repeated primitive parameter group appears in: '_search_files_with_results' (line 318), '_search_single_file' (line 395) | Replace Data Value with Object — create a shared data structure for this recurring parameter group. |
| 395 | 🟠 HIGH | Primitive Obsession | Function '_search_single_file' has 6 primitive-typed parameters: invert_match: Name(id='bool', ctx=Load()), has_context: Name(id='bool', ctx=Load()), context_before: Name(id='int', ctx=Load()), context_after: Name(id='int', ctx=Load()), line_numbers: Name(id='bool', ctx=Load()), multi_file: Name(id='bool', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 9 | 🟡 MEDIUM | Large Class | Class 'GrepTool' spans 509 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
| 31 | 🟡 MEDIUM | Long Method | Function 'parameters' has 54 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 31 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/pytest_run.py:50 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 31 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/shell.py:333 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 109 | 🟡 MEDIUM | Primitive Obsession | Function '_format_context_block' has 4 primitive-typed parameters: context_before: Name(id='int', ctx=Load()), context_after: Name(id='int', ctx=Load()), line_numbers: Name(id='bool', ctx=Load()), file_prefix: Name(id='str', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 272 | 🟡 MEDIUM | Primitive Obsession | Function '_validate_and_setup' has 5 primitive-typed parameters: pattern: Name(id='str', ctx=Load()), path: Name(id='str', ctx=Load()), ignore_case: Name(id='bool', ctx=Load()), whole_word: Name(id='bool', ctx=Load()), glob: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 318 | 🟡 MEDIUM | Long Method | Function '_search_files_with_results' has 50 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 21 | 🟢 LOW | Missing Type Hint | Function 'name' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 26 | 🟢 LOW | Missing Type Hint | Function 'description' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 31 | 🟢 LOW | Missing Type Hint | Function 'parameters' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 89 | 🟢 LOW | Missing Type Hint | Function 'kind' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |

_... and 17 more smells._

### tools/builtins/python_ast.py — ❌ F (15.7/100)

LOC: 335 | Classes: 1 | Functions: 0 | MI: 52 | Avg CC: 11.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 91 | 🟠 HIGH | Deep Nesting | Nesting depth 6 in '_classify_method' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 33 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/python_exec.py:35 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 33 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/shell.py:333 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 33 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 95% similar to 'parameters' at tools/builtins/traceback_parse.py:44 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 33 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/web_fetch.py:23 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 33 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/web_search.py:23 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 56 | 🟡 MEDIUM | Feature Envy | Method 'PythonAstTool._get_docstring' accesses 'ast' 6 times but 'self' only 0 times | Move Method — consider moving '_get_docstring' to the class that owns 'ast'. |
| 72 | 🟡 MEDIUM | Feature Envy | Method 'PythonAstTool._classify_method' accesses 'ast' 7 times but 'self' only 0 times | Move Method — consider moving '_classify_method' to the class that owns 'ast'. |
| 72 | 🟡 MEDIUM | Feature Envy | Method 'PythonAstTool._classify_method' accesses 'd' 6 times but 'self' only 0 times | Move Method — consider moving '_classify_method' to the class that owns 'd'. |
| 89 | 🟡 MEDIUM | Deep Nesting | Nesting depth 5 in '_classify_method' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 114 | 🟡 MEDIUM | Feature Envy | Method 'PythonAstTool._format_function' accesses 'ast' 5 times but 'self' only 3 times | Move Method — consider moving '_format_function' to the class that owns 'ast'. |
| 114 | 🟡 MEDIUM | Feature Envy | Method 'PythonAstTool._format_function' accesses 'node' 8 times but 'self' only 3 times | Move Method — consider moving '_format_function' to the class that owns 'node'. |
| 114 | 🟡 MEDIUM | Complex Function | Function '_format_function' has cyclomatic complexity 11 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 168 | 🟡 MEDIUM | Feature Envy | Method 'PythonAstTool._format_class' accesses 'ast' 6 times but 'self' only 4 times | Move Method — consider moving '_format_class' to the class that owns 'ast'. |
| 168 | 🟡 MEDIUM | Feature Envy | Method 'PythonAstTool._format_class' accesses 'node' 6 times but 'self' only 4 times | Move Method — consider moving '_format_class' to the class that owns 'node'. |

_... and 37 more smells._

### tools/builtins/test_gen.py — ❌ F (15.8/100)

LOC: 327 | Classes: 1 | Functions: 0 | MI: 53 | Avg CC: 16.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 137 | 🟠 HIGH | Feature Envy | Method 'TestGenTool._extract_symbols' accesses 'ast' 10 times but 'self' only 4 times | Move Method — consider moving '_extract_symbols' to the class that owns 'ast'. |
| 167 | 🟠 HIGH | Deep Nesting | Nesting depth 6 in '_extract_symbols' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 217 | 🟠 HIGH | Long Method | Function '_generate_class_tests' has 81 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 272 | 🟠 HIGH | Deep Nesting | Nesting depth 6 in '_generate_class_tests' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 275 | 🟠 HIGH | Deep Nesting | Nesting depth 7 in '_generate_class_tests' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 60 | 🟡 MEDIUM | Long Method | Function 'execute' has 58 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 166 | 🟡 MEDIUM | Deep Nesting | Nesting depth 5 in '_extract_symbols' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 217 | 🟡 MEDIUM | Complex Function | Function '_generate_class_tests' has cyclomatic complexity 16 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 271 | 🟡 MEDIUM | Deep Nesting | Nesting depth 5 in '_generate_class_tests' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 10 | 🟢 LOW | Large Class | Class 'TestGenTool' spans 376 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
| 19 | 🟢 LOW | Missing Type Hint | Function 'name' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 24 | 🟢 LOW | Missing Type Hint | Function 'description' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 32 | 🟢 LOW | Missing Type Hint | Function 'parameters' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 56 | 🟢 LOW | Missing Type Hint | Function 'kind' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 60 | 🟢 LOW | Missing Type Hint | Function 'execute' has incomplete type hints: 1/5 params untyped | Add Type Annotations for all parameters and return type. |

_... and 16 more smells._

### cli/output_handler.py — ❌ F (15.9/100)

LOC: 303 | Classes: 1 | Functions: 0 | MI: 53 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 225 | 🟡 MEDIUM | Duplicate Code | Function 'get_rich_status_message' is 94% similar to 'load' at cli/session_manager.py:126 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 225 | 🟡 MEDIUM | Duplicate Code | Function 'get_rich_status_message' is 94% similar to 'compute_project_hash' at cli/session_manager.py:199 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 298 | 🟡 MEDIUM | Duplicate Code | Function 'create_status' is 100% similar to 'create_status' at cli/ui_renderer.py:183 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 332 | 🟡 MEDIUM | Duplicate Code | Function 'start_task' is 100% similar to 'start_task' at cli/ui_renderer.py:356 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 345 | 🟡 MEDIUM | Duplicate Code | Function 'update_task' is 100% similar to 'tool_result' at cli/ui_renderer.py:318 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 345 | 🟡 MEDIUM | Duplicate Code | Function 'update_task' is 100% similar to 'tool_summary' at cli/ui_renderer.py:322 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 345 | 🟡 MEDIUM | Duplicate Code | Function 'update_task' is 100% similar to 'update_task' at cli/ui_renderer.py:369 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 22 | 🟢 LOW | Large Class | Class 'OutputHandler' spans 362 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
| 22 | 🟢 LOW | Large Class | Class 'OutputHandler' has 28 methods (threshold: 20) | Split Class — group related methods into smaller collaborating classes. |
| 32 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/8 params untyped | Add Type Annotations for all parameters and return type. |
| 61 | 🟢 LOW | Missing Type Hint | Function 'get_toolbar_status' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 81 | 🟢 LOW | Missing Type Hint | Function '_add_plan_mode_status' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 94 | 🟢 LOW | Missing Type Hint | Function '_add_provider_status' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 107 | 🟢 LOW | Missing Type Hint | Function '_add_token_status' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 131 | 🟢 LOW | Missing Type Hint | Function '_get_max_tokens' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |

_... and 25 more smells._

### metrics/collector.py — ❌ F (15.9/100)

LOC: 341 | Classes: 1 | Functions: 0 | MI: 53 | Avg CC: 14.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 145 | 🟠 HIGH | Primitive Obsession | Function 'record_token_usage' has 7 primitive-typed parameters: model: Name(id='str', ctx=Load()), provider: Name(id='str', ctx=Load()), prompt_tokens: Name(id='int', ctx=Load()), completion_tokens: Name(id='int', ctx=Load()), cached_tokens: Subscript(value=Name(id='Optional', ctx=Load()), slice=Name(id='int', ctx=Load()), ctx=Load()), token_limit: Subscript(value=Name(id='Optional', ctx=Load()), slice=Name(id='int', ctx=Load()), ctx=Load()), agent_id: Subscript(value=Name(id='Optional', ctx=Load()), slice=Name(id='str', ctx=Load()), ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 198 | 🟠 HIGH | Primitive Obsession | Function 'record_cost' has 8 primitive-typed parameters: model: Name(id='str', ctx=Load()), provider: Name(id='str', ctx=Load()), prompt_cost: Name(id='float', ctx=Load()), completion_cost: Name(id='float', ctx=Load()), currency: Name(id='str', ctx=Load()), cost_per_token: Subscript(value=Name(id='Optional', ctx=Load()), slice=Name(id='float', ctx=Load()), ctx=Load()), estimated_cost: Subscript(value=Name(id='Optional', ctx=Load()), slice=Name(id='float', ctx=Load()), ctx=Load()), agent_id: Subscript(value=Name(id='Optional', ctx=Load()), slice=Name(id='str', ctx=Load()), ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 317 | 🟠 HIGH | Primitive Obsession | Function 'record_performance_event' has 6 primitive-typed parameters: event_type: Name(id='str', ctx=Load()), latency_ms: Name(id='float', ctx=Load()), memory_usage_mb: Subscript(value=Name(id='Optional', ctx=Load()), slice=Name(id='float', ctx=Load()), ctx=Load()), cpu_usage_percent: Subscript(value=Name(id='Optional', ctx=Load()), slice=Name(id='float', ctx=Load()), ctx=Load()), concurrent_operations: Name(id='int', ctx=Load()), queue_depth: Subscript(value=Name(id='Optional', ctx=Load()), slice=Name(id='int', ctx=Load()), ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 373 | 🟠 HIGH | Feature Envy | Method 'MetricsCollector.process_agent_event' accesses 'event' 12 times but 'self' only 9 times | Move Method — consider moving 'process_agent_event' to the class that owns 'event'. |
| 39 | 🟡 MEDIUM | Primitive Obsession | Function '__init__' has 5 primitive-typed parameters: enabled: Name(id='bool', ctx=Load()), anonymize: Name(id='bool', ctx=Load()), sampling_rate: Name(id='float', ctx=Load()), session_id: Subscript(value=Name(id='Optional', ctx=Load()), slice=Name(id='str', ctx=Load()), ctx=Load()), user_id: Subscript(value=Name(id='Optional', ctx=Load()), slice=Name(id='str', ctx=Load()), ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 253 | 🟡 MEDIUM | Primitive Obsession | Function 'track_tool_execution' has 4 primitive-typed parameters: tool_name: Name(id='str', ctx=Load()), tool_category: Name(id='str', ctx=Load()), input_size: Subscript(value=Name(id='Optional', ctx=Load()), slice=Name(id='int', ctx=Load()), ctx=Load()), agent_id: Subscript(value=Name(id='Optional', ctx=Load()), slice=Name(id='str', ctx=Load()), ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 373 | 🟡 MEDIUM | Complex Function | Function 'process_agent_event' has cyclomatic complexity 14 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 391 | 🟡 MEDIUM | Deep Nesting | Nesting depth 5 in 'process_agent_event' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 396 | 🟡 MEDIUM | Deep Nesting | Nesting depth 5 in 'process_agent_event' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 405 | 🟡 MEDIUM | Deep Nesting | Nesting depth 5 in 'process_agent_event' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 27 | 🟢 LOW | Large Class | Class 'MetricsCollector' spans 380 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
| 39 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/7 params untyped | Add Type Annotations for all parameters and return type. |
| 75 | 🟢 LOW | Missing Type Hint | Function '_generate_session_id' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 80 | 🟢 LOW | Missing Type Hint | Function '_hash_user_id' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 82 | 🟢 LOW | Magic Number | Magic number 16 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |

_... and 18 more smells._

### tools/builtins/git_ops.py — ❌ F (16.5/100)

LOC: 273 | Classes: 1 | Functions: 0 | MI: 55 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 135 | 🟠 HIGH | Primitive Obsession | Function 'execute' has 9 primitive-typed parameters: action: Name(id='str', ctx=Load()), path: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), ref: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), ref2: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), max_count: Name(id='int', ctx=Load()), start_line: BinOp(left=Name(id='int', ctx=Load()), op=BitOr(), right=Constant(value=None)), end_line: BinOp(left=Name(id='int', ctx=Load()), op=BitOr(), right=Constant(value=None)), stat: Name(id='bool', ctx=Load()), cwd: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 212 | 🟠 HIGH | Duplicate Code | Function '_status' is an exact duplicate of '_branch_list' at tools/builtins/git_ops.py:271 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 252 | 🟠 HIGH | Primitive Obsession | Repeated primitive parameter group appears in: '_show' (line 252), '_diff_branches' (line 286) | Replace Data Value with Object — create a shared data structure for this recurring parameter group. |
| 41 | 🟡 MEDIUM | Long Method | Function 'parameters' has 53 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 41 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 92% similar to 'parameters' at tools/builtins/kg_query.py:69 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 41 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/lint_check.py:35 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 41 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/test_gen.py:32 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 102 | 🟡 MEDIUM | Feature Envy | Method 'GitOpsTool._run_git' accesses 'asyncio' 5 times but 'self' only 0 times | Move Method — consider moving '_run_git' to the class that owns 'asyncio'. |
| 216 | 🟡 MEDIUM | Primitive Obsession | Function '_log' has 5 primitive-typed parameters: path: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), ref: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), max_count: Name(id='int', ctx=Load()), stat: Name(id='bool', ctx=Load()), cwd: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 235 | 🟡 MEDIUM | Primitive Obsession | Function '_blame' has 4 primitive-typed parameters: path: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), start_line: BinOp(left=Name(id='int', ctx=Load()), op=BitOr(), right=Constant(value=None)), end_line: BinOp(left=Name(id='int', ctx=Load()), op=BitOr(), right=Constant(value=None)), cwd: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 252 | 🟡 MEDIUM | Primitive Obsession | Function '_show' has 4 primitive-typed parameters: ref: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), path: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), stat: Name(id='bool', ctx=Load()), cwd: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 286 | 🟡 MEDIUM | Primitive Obsession | Function '_diff_branches' has 5 primitive-typed parameters: ref: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), ref2: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), stat: Name(id='bool', ctx=Load()), path: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), cwd: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 27 | 🟢 LOW | Missing Type Hint | Function 'name' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 32 | 🟢 LOW | Missing Type Hint | Function 'description' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 41 | 🟢 LOW | Missing Type Hint | Function 'parameters' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |

_... and 16 more smells._

### extensions/plugin_manager.py — ❌ F (16.9/100)

LOC: 282 | Classes: 1 | Functions: 0 | MI: 56 | Avg CC: 12.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 47 | 🟠 HIGH | Duplicate Code | Function '__init__' is an exact duplicate of '__init__' at extensions/plugin_manager_refactored.py:48 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 68 | 🟠 HIGH | Duplicate Code | Function 'initialize' is an exact duplicate of 'initialize' at extensions/plugin_manager_refactored.py:69 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 104 | 🟠 HIGH | Duplicate Code | Function 'close' is an exact duplicate of 'close' at extensions/plugin_manager_refactored.py:105 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 113 | 🟠 HIGH | Duplicate Code | Function 'search_plugins' is an exact duplicate of 'search_plugins' at extensions/plugin_manager_refactored.py:114 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 145 | 🟠 HIGH | Duplicate Code | Function 'get_plugin_info' is an exact duplicate of 'get_plugin_info' at extensions/plugin_manager_refactored.py:146 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 168 | 🟠 HIGH | Duplicate Code | Function 'install_plugin' is an exact duplicate of 'install_plugin' at extensions/plugin_manager_refactored.py:169 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 241 | 🟠 HIGH | Duplicate Code | Function 'uninstall_plugin' is an exact duplicate of 'uninstall_plugin' at extensions/plugin_manager_refactored.py:242 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 275 | 🟠 HIGH | Duplicate Code | Function 'update_plugin' is an exact duplicate of 'update_plugin' at extensions/plugin_manager_refactored.py:276 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 313 | 🟠 HIGH | Duplicate Code | Function 'check_updates' is an exact duplicate of 'check_updates' at extensions/plugin_manager_refactored.py:314 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 378 | 🟠 HIGH | Duplicate Code | Function '_load_plugin_extension' is an exact duplicate of '_load_plugin_extension' at extensions/plugin_manager_refactored.py:379 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 113 | 🟡 MEDIUM | Primitive Obsession | Function 'search_plugins' has 4 primitive-typed parameters: query: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), page: Name(id='int', ctx=Load()), page_size: Name(id='int', ctx=Load()), category: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 168 | 🟡 MEDIUM | Long Method | Function 'install_plugin' has 52 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 168 | 🟡 MEDIUM | Complex Function | Function 'install_plugin' has cyclomatic complexity 12 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 30 | 🟢 LOW | Large Class | Class 'PluginManager' spans 369 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
| 47 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |

_... and 12 more smells._

### metrics/dashboard.py — ❌ F (16.9/100)

LOC: 265 | Classes: 1 | Functions: 0 | MI: 56 | Avg CC: 14.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 74 | 🟡 MEDIUM | Long Method | Function 'get_summary_stats' has 77 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 74 | 🟡 MEDIUM | Feature Envy | Method 'Dashboard.get_summary_stats' accesses 'stat' 6 times but 'self' only 4 times | Move Method — consider moving 'get_summary_stats' to the class that owns 'stat'. |
| 74 | 🟡 MEDIUM | Complex Function | Function 'get_summary_stats' has cyclomatic complexity 14 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 158 | 🟡 MEDIUM | Feature Envy | Method 'Dashboard.export_data' accesses 'writer' 7 times but 'self' only 1 times | Move Method — consider moving 'export_data' to the class that owns 'writer'. |
| 259 | 🟡 MEDIUM | Feature Envy | Method 'Dashboard._create_token_panel' accesses 'table' 5 times but 'self' only 1 times | Move Method — consider moving '_create_token_panel' to the class that owns 'table'. |
| 259 | 🟡 MEDIUM | Duplicate Code | Function '_create_token_panel' is 96% similar to '_create_cost_panel' at metrics/dashboard.py:281 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 259 | 🟡 MEDIUM | Duplicate Code | Function '_create_token_panel' is 98% similar to '_create_tool_panel' at metrics/dashboard.py:303 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 259 | 🟡 MEDIUM | Duplicate Code | Function '_create_token_panel' is 98% similar to '_create_usage_panel' at metrics/dashboard.py:325 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 281 | 🟡 MEDIUM | Feature Envy | Method 'Dashboard._create_cost_panel' accesses 'table' 5 times but 'self' only 1 times | Move Method — consider moving '_create_cost_panel' to the class that owns 'table'. |
| 281 | 🟡 MEDIUM | Duplicate Code | Function '_create_cost_panel' is 94% similar to '_create_tool_panel' at metrics/dashboard.py:303 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 281 | 🟡 MEDIUM | Duplicate Code | Function '_create_cost_panel' is 94% similar to '_create_usage_panel' at metrics/dashboard.py:325 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 303 | 🟡 MEDIUM | Feature Envy | Method 'Dashboard._create_tool_panel' accesses 'table' 5 times but 'self' only 1 times | Move Method — consider moving '_create_tool_panel' to the class that owns 'table'. |
| 303 | 🟡 MEDIUM | Duplicate Code | Function '_create_tool_panel' is 96% similar to '_create_usage_panel' at metrics/dashboard.py:325 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 325 | 🟡 MEDIUM | Feature Envy | Method 'Dashboard._create_usage_panel' accesses 'table' 5 times but 'self' only 1 times | Move Method — consider moving '_create_usage_panel' to the class that owns 'table'. |
| 22 | 🟢 LOW | Large Class | Class 'Dashboard' spans 324 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |

_... and 25 more smells._

### tools/builtins/kg_query.py — ❌ F (17.0/100)

LOC: 220 | Classes: 1 | Functions: 1 | MI: 52 | Avg CC: 12.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 18 | 🟠 HIGH | Duplicate Code | Function '_find_git_root' is an exact duplicate of '_find_git_root' at tools/builtins/kg_update.py:48 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 44 | 🟠 HIGH | Duplicate Code | Function '__init__' is an exact duplicate of '__init__' at tools/builtins/kg_update.py:79 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 184 | 🟠 HIGH | Deep Nesting | Nesting depth 6 in 'execute' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 69 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 93% similar to 'parameters' at tools/builtins/kg_update.py:105 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 69 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 92% similar to 'parameters' at tools/builtins/lint_check.py:35 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 69 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 92% similar to 'parameters' at tools/builtins/test_gen.py:32 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 134 | 🟡 MEDIUM | Complex Function | Function 'execute' has cyclomatic complexity 12 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 182 | 🟡 MEDIUM | Deep Nesting | Nesting depth 5 in 'execute' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 226 | 🟡 MEDIUM | Feature Envy | Method 'KgQueryTool._handle_relations' accesses 'rel' 7 times but 'self' only 0 times | Move Method — consider moving '_handle_relations' to the class that owns 'rel'. |
| 44 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 55 | 🟢 LOW | Missing Type Hint | Function 'name' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 60 | 🟢 LOW | Missing Type Hint | Function 'description' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 69 | 🟢 LOW | Long Method | Function 'parameters' has 38 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 69 | 🟢 LOW | Missing Type Hint | Function 'parameters' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 111 | 🟢 LOW | Missing Type Hint | Function 'kind' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |

_... and 13 more smells._

### cli/ui_renderer.py — ❌ F (17.3/100)

LOC: 299 | Classes: 2 | Functions: 0 | MI: 58 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 45 | 🟠 HIGH | Primitive Obsession | Repeated primitive parameter group appears in: 'start_task' (line 45), 'start_task' (line 356) | Replace Data Value with Object — create a shared data structure for this recurring parameter group. |
| 69 | 🟠 HIGH | Primitive Obsession | Repeated primitive parameter group appears in: 'update_task' (line 69), 'update_task' (line 369) | Replace Data Value with Object — create a shared data structure for this recurring parameter group. |
| 96 | 🟡 MEDIUM | Large Class | Class 'UIRenderer' has 31 methods (threshold: 20) | Split Class — group related methods into smaller collaborating classes. |
| 318 | 🟡 MEDIUM | Duplicate Code | Function 'tool_result' is 100% similar to 'tool_summary' at cli/ui_renderer.py:322 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 318 | 🟡 MEDIUM | Duplicate Code | Function 'tool_result' is 100% similar to 'update_task' at cli/ui_renderer.py:369 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 322 | 🟡 MEDIUM | Duplicate Code | Function 'tool_summary' is 100% similar to 'update_task' at cli/ui_renderer.py:369 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 36 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: missing return type | Add Type Annotations for all parameters and return type. |
| 45 | 🟢 LOW | Missing Type Hint | Function 'start_task' has incomplete type hints: 1/4 params untyped | Add Type Annotations for all parameters and return type. |
| 45 | 🟢 LOW | Primitive Obsession | Function 'start_task' has 3 primitive-typed parameters: task_id: Name(id='str', ctx=Load()), description: Name(id='str', ctx=Load()), total: Name(id='int', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 69 | 🟢 LOW | Missing Type Hint | Function 'update_task' has incomplete type hints: 1/4 params untyped | Add Type Annotations for all parameters and return type. |
| 69 | 🟢 LOW | Primitive Obsession | Function 'update_task' has 3 primitive-typed parameters: task_id: Name(id='str', ctx=Load()), advance: Name(id='int', ctx=Load()), description: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 84 | 🟢 LOW | Missing Type Hint | Function 'complete_task' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 108 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/6 params untyped | Add Type Annotations for all parameters and return type. |
| 136 | 🟢 LOW | Missing Type Hint | Function 'print_welcome' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 140 | 🟢 LOW | Missing Type Hint | Function 'print_goodbye' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |

_... and 32 more smells._

### providers/anthropic.py — ❌ F (17.9/100)

LOC: 477 | Classes: 5 | Functions: 0 | MI: 41 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 121 | 🟡 MEDIUM | Feature Envy | Method '_AnthropicStreamProcessor.process_stream' accesses 'chunk' 9 times but 'self' only 3 times | Move Method — consider moving 'process_stream' to the class that owns 'chunk'. |
| 183 | 🟡 MEDIUM | Feature Envy | Method '_AnthropicStreamProcessor._handle_content_block_start' accesses 'block' 5 times but 'self' only 0 times | Move Method — consider moving '_handle_content_block_start' to the class that owns 'block'. |
| 202 | 🟡 MEDIUM | Feature Envy | Method '_AnthropicStreamProcessor._handle_content_block_delta' accesses 'delta' 7 times but 'self' only 3 times | Move Method — consider moving '_handle_content_block_delta' to the class that owns 'delta'. |
| 291 | 🟡 MEDIUM | Primitive Obsession | Function '__init__' has 5 primitive-typed parameters: api_key: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), model: Name(id='str', ctx=Load()), max_tokens: Name(id='int', ctx=Load()), tokens_per_minute: Name(id='int', ctx=Load()), max_retries: Name(id='int', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 61 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 75 | 🟢 LOW | Missing Type Hint | Function '_should_yield' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 112 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 121 | 🟢 LOW | Missing Type Hint | Function 'process_stream' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 162 | 🟢 LOW | Missing Type Hint | Function '_process_event' has incomplete type hints: 1/5 params untyped | Add Type Annotations for all parameters and return type. |
| 178 | 🟢 LOW | Deep Nesting | Nesting depth 4 in '_process_event' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 183 | 🟢 LOW | Missing Type Hint | Function '_handle_content_block_start' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 202 | 🟢 LOW | Missing Type Hint | Function '_handle_content_block_delta' has incomplete type hints: 1/5 params untyped | Add Type Annotations for all parameters and return type. |
| 234 | 🟢 LOW | Missing Type Hint | Function '_handle_content_block_stop' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 239 | 🟢 LOW | Missing Type Hint | Function '_handle_message_delta' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 257 | 🟢 LOW | Missing Type Hint | Function '_build_tool_calls_from_pending' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |

_... and 25 more smells._

### tools/builtins/file_edit.py — ❌ F (18.6/100)

LOC: 227 | Classes: 1 | Functions: 0 | MI: 62 | Avg CC: 12.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 71 | 🟠 HIGH | Primitive Obsession | Function 'execute' has 6 primitive-typed parameters: path: Name(id='str', ctx=Load()), old_str: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), new_str: Name(id='str', ctx=Load()), start_line: BinOp(left=Name(id='int', ctx=Load()), op=BitOr(), right=Constant(value=None)), end_line: BinOp(left=Name(id='int', ctx=Load()), op=BitOr(), right=Constant(value=None)), dry_run: Name(id='bool', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 32 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/file_write.py:26 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 32 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/glob_tool.py:29 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 32 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/grep.py:31 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 32 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/pytest_run.py:50 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 32 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/python_ast.py:33 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 32 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/python_exec.py:35 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 32 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/shell.py:333 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 32 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 95% similar to 'parameters' at tools/builtins/traceback_parse.py:44 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 32 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/web_fetch.py:23 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 32 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/web_search.py:23 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 71 | 🟡 MEDIUM | Long Method | Function 'execute' has 51 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 71 | 🟡 MEDIUM | Complex Function | Function 'execute' has cyclomatic complexity 12 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 147 | 🟡 MEDIUM | Primitive Obsession | Function '_edit_string' has 4 primitive-typed parameters: content: Name(id='str', ctx=Load()), old_str: Name(id='str', ctx=Load()), new_str: Name(id='str', ctx=Load()), dry_run: Name(id='bool', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 191 | 🟡 MEDIUM | Primitive Obsession | Function '_edit_line_range' has 5 primitive-typed parameters: content: Name(id='str', ctx=Load()), start_line: Name(id='int', ctx=Load()), end_line: Name(id='int', ctx=Load()), new_str: Name(id='str', ctx=Load()), dry_run: Name(id='bool', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |

_... and 11 more smells._

### tools/builtins/import_graph.py — ❌ F (18.8/100)

LOC: 650 | Classes: 5 | Functions: 5 | MI: 39 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 115 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 123 | 🟢 LOW | Missing Type Hint | Function 'extract_imports' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 134 | 🟢 LOW | Missing Type Hint | Function 'classify_import' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 149 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 157 | 🟢 LOW | Missing Type Hint | Function 'build_graph' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 177 | 🟢 LOW | Missing Type Hint | Function '_collect_local_modules' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 188 | 🟢 LOW | Missing Type Hint | Function '_extract_dependencies_from_file' has incomplete type hints: 1/4 params untyped | Add Type Annotations for all parameters and return type. |
| 216 | 🟢 LOW | Missing Type Hint | Function '_extract_dependencies_from_node' has incomplete type hints: 1/5 params untyped | Add Type Annotations for all parameters and return type. |
| 216 | 🟢 LOW | Feature Envy | Method 'ImportGraphBuilder._extract_dependencies_from_node' accesses 'ast' 3 times but 'self' only 2 times | Move Method — consider moving '_extract_dependencies_from_node' to the class that owns 'ast'. |
| 236 | 🟢 LOW | Missing Type Hint | Function '_extract_dependencies_from_import' has incomplete type hints: 1/5 params untyped | Add Type Annotations for all parameters and return type. |
| 255 | 🟢 LOW | Missing Type Hint | Function '_extract_dependencies_from_import_from' has incomplete type hints: 1/5 params untyped | Add Type Annotations for all parameters and return type. |
| 277 | 🟢 LOW | Missing Type Hint | Function '_add_dependency_if_local' has incomplete type hints: 1/5 params untyped | Add Type Annotations for all parameters and return type. |
| 295 | 🟢 LOW | Missing Type Hint | Function 'detect_cycles' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 304 | 🟢 LOW | Missing Type Hint | Function '_find_cycles_in_graph' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 320 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |

_... and 30 more smells._

### rag/store.py — ❌ F (19.2/100)

LOC: 203 | Classes: 2 | Functions: 0 | MI: 64 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 124 | 🟡 MEDIUM | Magic Number | Magic number 3 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 124 | 🟡 MEDIUM | Magic Number | Magic number 0.1 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 125 | 🟡 MEDIUM | Feature Envy | Method 'VectorStore.add_chunks' accesses 'chunk' 6 times but 'self' only 1 times | Move Method — consider moving 'add_chunks' to the class that owns 'chunk'. |
| 150 | 🟡 MEDIUM | Magic Number | Magic number 3 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 150 | 🟡 MEDIUM | Magic Number | Magic number 0.1 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 204 | 🟡 MEDIUM | Magic Number | Magic number 3 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 204 | 🟡 MEDIUM | Magic Number | Magic number 0.1 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 220 | 🟡 MEDIUM | Magic Number | Magic number 3 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 220 | 🟡 MEDIUM | Magic Number | Magic number 0.1 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 230 | 🟡 MEDIUM | Magic Number | Magic number 3 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 230 | 🟡 MEDIUM | Magic Number | Magic number 0.1 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 245 | 🟡 MEDIUM | Magic Number | Magic number 3 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 245 | 🟡 MEDIUM | Magic Number | Magic number 0.1 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 254 | 🟡 MEDIUM | Magic Number | Magic number 3 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 254 | 🟡 MEDIUM | Magic Number | Magic number 0.1 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |

_... and 13 more smells._

### metrics/storage.py — ❌ F (19.8/100)

LOC: 646 | Classes: 5 | Functions: 0 | MI: 47 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 701 | 🟠 HIGH | Feature Envy | Method 'MetricsStorage._build_metrics_query' accesses 'query_params' 12 times but 'self' only 0 times | Move Method — consider moving '_build_metrics_query' to the class that owns 'query_params'. |
| 514 | 🟡 MEDIUM | Feature Envy | Method 'MetricsStorage._create_base_metric_dict' accesses 'metric' 8 times but 'self' only 0 times | Move Method — consider moving '_create_base_metric_dict' to the class that owns 'metric'. |
| 701 | 🟡 MEDIUM | Feature Envy | Method 'MetricsStorage._build_metrics_query' accesses 'params' 6 times but 'self' only 0 times | Move Method — consider moving '_build_metrics_query' to the class that owns 'params'. |
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

### tools/builtins/patch_apply.py — ❌ F (21.1/100)

LOC: 459 | Classes: 5 | Functions: 0 | MI: 42 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 129 | 🟡 MEDIUM | Feature Envy | Method 'HunkApplier._apply_hunk_with_context' accesses 'context' 8 times but 'self' only 3 times | Move Method — consider moving '_apply_hunk_with_context' to the class that owns 'context'. |
| 456 | 🟡 MEDIUM | Primitive Obsession | Function 'execute' has 4 primitive-typed parameters: patch: Name(id='str', ctx=Load()), path: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), dry_run: Name(id='bool', ctx=Load()), fuzz: Name(id='int', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 39 | 🟢 LOW | Missing Type Hint | Function 'apply_hunks' has incomplete type hints: 1/4 params untyped | Add Type Annotations for all parameters and return type. |
| 66 | 🟢 LOW | Missing Type Hint | Function '_split_original_content' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 82 | 🟢 LOW | Missing Type Hint | Function '_reconstruct_content' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 97 | 🟢 LOW | Missing Type Hint | Function '_apply_single_hunk' has incomplete type hints: 1/6 params untyped | Add Type Annotations for all parameters and return type. |
| 97 | 🟢 LOW | Primitive Obsession | Function '_apply_single_hunk' has 3 primitive-typed parameters: hunk_idx: Name(id='int', ctx=Load()), offset: Name(id='int', ctx=Load()), fuzz: Name(id='int', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 129 | 🟢 LOW | Missing Type Hint | Function '_apply_hunk_with_context' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 154 | 🟢 LOW | Missing Type Hint | Function '_extract_hunk_lines' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 161 | 🟢 LOW | Missing Type Hint | Function '_extract_old_and_new_lines' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 161 | 🟢 LOW | Feature Envy | Method 'HunkApplier._extract_old_and_new_lines' accesses 'line' 3 times but 'self' only 0 times | Move Method — consider moving '_extract_old_and_new_lines' to the class that owns 'line'. |
| 171 | 🟢 LOW | Deep Nesting | Nesting depth 4 in '_extract_old_and_new_lines' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 177 | 🟢 LOW | Missing Type Hint | Function '_find_match' has incomplete type hints: 1/5 params untyped | Add Type Annotations for all parameters and return type. |
| 221 | 🟢 LOW | Missing Type Hint | Function '_lines_match' has incomplete type hints: 1/4 params untyped | Add Type Annotations for all parameters and return type. |
| 245 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |

_... and 26 more smells._

### utils/compaction.py — ❌ F (21.4/100)

LOC: 766 | Classes: 9 | Functions: 7 | MI: 29 | Avg CC: 11.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 926 | 🟡 MEDIUM | Primitive Obsession | Function 'compact_with_summarization' has 4 primitive-typed parameters: max_tokens: Name(id='int', ctx=Load()), summarize: Name(id='bool', ctx=Load()), protect_from_index: Name(id='int', ctx=Load()), max_protected_ratio: Name(id='float', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 998 | 🟡 MEDIUM | Complex Function | Function '_attempt_summarization' has cyclomatic complexity 11 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 40 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 49 | 🟢 LOW | Missing Type Hint | Function 'token_count' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 54 | 🟢 LOW | Missing Type Hint | Function 'is_tool_sequence' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 58 | 🟢 LOW | Missing Type Hint | Function '__repr__' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 78 | 🟢 LOW | Magic Number | Magic number 0.3 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 212 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 220 | 🟢 LOW | Missing Type Hint | Function 'separate_protected_messages' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 241 | 🟢 LOW | Missing Type Hint | Function 'truncate_if_needed' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 258 | 🟢 LOW | Missing Type Hint | Function '_truncate_protected_zone' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 258 | 🟢 LOW | Feature Envy | Method 'ProtectedZoneManager._truncate_protected_zone' accesses 'result' 3 times but 'self' only 0 times | Move Method — consider moving '_truncate_protected_zone' to the class that owns 'result'. |
| 332 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 340 | 🟢 LOW | Missing Type Hint | Function 'calculate_budget' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 356 | 🟢 LOW | Missing Type Hint | Function 'handle_edge_cases' has incomplete type hints: 1/6 params untyped | Add Type Annotations for all parameters and return type. |

_... and 23 more smells._

### tools/builtins/dead_code.py — ❌ F (21.7/100)

LOC: 475 | Classes: 6 | Functions: 0 | MI: 44 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 53 | 🟡 MEDIUM | Feature Envy | Method 'ASTAnalyzer.is_import_context' accesses 'ast' 5 times but 'self' only 0 times | Move Method — consider moving 'is_import_context' to the class that owns 'ast'. |
| 73 | 🟡 MEDIUM | Feature Envy | Method 'ASTAnalyzer.collect_top_level_definitions' accesses 'ast' 5 times but 'self' only 0 times | Move Method — consider moving 'collect_top_level_definitions' to the class that owns 'ast'. |
| 73 | 🟡 MEDIUM | Feature Envy | Method 'ASTAnalyzer.collect_top_level_definitions' accesses 'node' 6 times but 'self' only 0 times | Move Method — consider moving 'collect_top_level_definitions' to the class that owns 'node'. |
| 92 | 🟡 MEDIUM | Feature Envy | Method 'ASTAnalyzer.find_all_assignment' accesses 'ast' 6 times but 'self' only 0 times | Move Method — consider moving 'find_all_assignment' to the class that owns 'ast'. |
| 438 | 🟡 MEDIUM | Duplicate Code | Function '_format_import_findings' is 100% similar to '_format_definition_findings' at tools/builtins/dead_code.py:452 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 540 | 🟡 MEDIUM | Duplicate Code | Function '_identify_unused_items' is 93% similar to '_identify_unused_definitions' at tools/builtins/dead_code.py:562 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 92 | 🟢 LOW | Feature Envy | Method 'ASTAnalyzer.find_all_assignment' accesses 'node' 3 times but 'self' only 0 times | Move Method — consider moving 'find_all_assignment' to the class that owns 'node'. |
| 119 | 🟢 LOW | Feature Envy | Method 'ImportAnalyzer.collect_imported_names' accesses 'ast' 4 times but 'self' only 0 times | Move Method — consider moving 'collect_imported_names' to the class that owns 'ast'. |
| 149 | 🟢 LOW | Feature Envy | Method 'ImportAnalyzer._collect_import_from_names' accesses 'alias' 3 times but 'self' only 0 times | Move Method — consider moving '_collect_import_from_names' to the class that owns 'alias'. |
| 163 | 🟢 LOW | Feature Envy | Method 'ImportAnalyzer.collect_used_names' accesses 'ast' 4 times but 'self' only 0 times | Move Method — consider moving 'collect_used_names' to the class that owns 'ast'. |
| 178 | 🟢 LOW | Deep Nesting | Nesting depth 4 in 'collect_used_names' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 183 | 🟢 LOW | Feature Envy | Method 'ImportAnalyzer._extract_attribute_root_name' accesses 'ast' 4 times but 'self' only 0 times | Move Method — consider moving '_extract_attribute_root_name' to the class that owns 'ast'. |
| 202 | 🟢 LOW | Feature Envy | Method 'DefinitionAnalyzer.collect_all_references' accesses 'ast' 4 times but 'self' only 0 times | Move Method — consider moving 'collect_all_references' to the class that owns 'ast'. |
| 236 | 🟢 LOW | Feature Envy | Method 'DefinitionAnalyzer._extract_names_from_all' accesses 'ast' 4 times but 'self' only 0 times | Move Method — consider moving '_extract_names_from_all' to the class that owns 'ast'. |
| 255 | 🟢 LOW | Large Class | Class 'DeadCodeTool' spans 328 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |

_... and 20 more smells._

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
- tools/utils.py — ✅ A
- utils/__init__.py — ✅ A
- utils/lazy_import.py — ✅ A
- version.py — ✅ A

</details>

---

_Report generated by XP Code Smell Detector. Smells are static heuristics — use judgement when prioritising fixes._
