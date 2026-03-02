# Code Smell Report — ❌ F (Score: 42.5/100)

_Scanned: /home/matthew/mlg-cli/src/henchman/cli_  

_Generated: 2026-03-02T13:43:18.440193+00:00_

## Executive Summary

| Metric | Value |
|:-------|------:|
| **Overall Grade** | ❌ F |
| **Overall Score** | 42.5/100 |
| **Files Scanned** | 40 |
| **Total Lines (non-blank)** | 10,207 |
| **Total Smells** | 980 |
| **Avg Maintainability Index** | 63.5 |
| **Avg Cyclomatic Complexity** | 12.7 |

### Smells by Severity

| Severity | Count |
|:---------|------:|
| low | 804 |
| medium | 143 |
| high | 33 |

### Smells by Category

| Category | Count |
|:---------|------:|
| Lint Violation | 369 |
| Missing Type Hint | 358 |
| Feature Envy | 83 |
| Duplicate Code | 69 |
| Long Method | 25 |
| Magic Number | 23 |
| Deep Nesting | 20 |
| Primitive Obsession | 19 |
| Large Class | 8 |
| Complex Function | 6 |

## 🎯 Prioritised Refactoring Queue

These are the highest-impact smells to address first:

1. **app.py:645** — 🟠 HIGH — Primitive Obsession  
   Function 'chat_command' has 8 primitive-typed parameters: prompt: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), agent: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), team: Name(id='bool', ctx=Load()), output_format: Name(id='str', ctx=Load()), plan: Name(id='bool', ctx=Load()), yes: Name(id='bool', ctx=Load()), tui: Name(id='bool', ctx=Load()), debug: Name(id='bool', ctx=Load())  
   → _Introduce Parameter Object — group related primitives into a dataclass or NamedTuple._

2. **commands/agent.py:33** — 🟠 HIGH — Feature Envy  
   Method 'AgentCommand.execute' accesses 'ctx' 10 times but 'self' only 2 times  
   → _Move Method — consider moving 'execute' to the class that owns 'ctx'._

3. **commands/builtins.py:52** — 🟠 HIGH — Feature Envy  
   Method 'HelpCommand.execute' accesses 'ctx' 14 times but 'self' only 0 times  
   → _Move Method — consider moving 'execute' to the class that owns 'ctx'._

4. **commands/chat.py:120** — 🟠 HIGH — Feature Envy  
   Method 'ChatCommand._resume' accesses 'ctx' 12 times but 'self' only 0 times  
   → _Move Method — consider moving '_resume' to the class that owns 'ctx'._

5. **commands/context.py:85** — 🟠 HIGH — Feature Envy  
   Method 'ContextCommand._show_status' accesses 'console' 13 times but 'self' only 0 times  
   → _Move Method — consider moving '_show_status' to the class that owns 'console'._

6. **commands/context.py:273** — 🟠 HIGH — Primitive Obsession  
   Function '_handle_range_parameter' has 6 primitive-typed parameters: value: Name(id='str', ctx=Load()), param_name: Name(id='str', ctx=Load()), min_val: Name(id='float', ctx=Load()), max_val: BinOp(left=Name(id='float', ctx=Load()), op=BitOr(), right=Constant(value=None)), is_int: Name(id='bool', ctx=Load()), label: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None))  
   → _Introduce Parameter Object — group related primitives into a dataclass or NamedTuple._

7. **commands/context.py:304** — 🟠 HIGH — Duplicate Code  
   Function '_handle_importance_parameter' is an exact duplicate of '_handle_similarity_parameter' at commands/context.py:308  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

8. **commands/context.py:322** — 🟠 HIGH — Feature Envy  
   Method 'ContextCommand._show_stats' accesses 'ctx' 10 times but 'self' only 0 times  
   → _Move Method — consider moving '_show_stats' to the class that owns 'ctx'._

9. **commands/context.py:322** — 🟠 HIGH — Feature Envy  
   Method 'ContextCommand._show_stats' accesses 'console' 12 times but 'self' only 0 times  
   → _Move Method — consider moving '_show_stats' to the class that owns 'console'._

10. **commands/mcp.py:121** — 🟠 HIGH — Feature Envy  
   Method 'McpCommand._logging' accesses 'ctx' 15 times but 'self' only 0 times  
   → _Move Method — consider moving '_logging' to the class that owns 'ctx'._

11. **commands/model.py:61** — 🟠 HIGH — Feature Envy  
   Method 'ModelCommand._show_current' accesses 'ctx' 10 times but 'self' only 0 times  
   → _Move Method — consider moving '_show_current' to the class that owns 'ctx'._

12. **commands/model.py:125** — 🟠 HIGH — Feature Envy  
   Method 'ModelCommand._set_provider' accesses 'ctx' 26 times but 'self' only 2 times  
   → _Move Method — consider moving '_set_provider' to the class that owns 'ctx'._

13. **commands/plan.py:32** — 🟠 HIGH — Feature Envy  
   Method 'PlanCommand.execute' accesses 'ctx' 13 times but 'self' only 0 times  
   → _Move Method — consider moving 'execute' to the class that owns 'ctx'._

14. **commands/theme.py:94** — 🟠 HIGH — Feature Envy  
   Method 'ThemeCommand._set_theme' accesses 'ctx' 20 times but 'self' only 1 times  
   → _Move Method — consider moving '_set_theme' to the class that owns 'ctx'._

15. **console.py:55** — 🟠 HIGH — Primitive Obsession  
   Repeated primitive parameter group appears in: 'create_diff_params' (line 55), 'diff' (line 648), 'async_diff' (line 817)  
   → _Replace Data Value with Object — create a shared data structure for this recurring parameter group._


## 📊 Files Ranked by Quality

| Rank | File | Grade | Score | Smells | LOC | MI | Avg CC |
|-----:|:-----|:------|------:|-------:|----:|---:|-------:|
| 1 | textual_widgets.py | ❌ F | 8.7 | 33 | 960 | 27 | 0.0 |
| 2 | console.py | ❌ F | 13.0 | 77 | 630 | 43 | 0.0 |
| 3 | app.py | ❌ F | 13.5 | 69 | 531 | 45 | 0.0 |
| 4 | commands/context.py | ❌ F | 15.3 | 91 | 303 | 51 | 11.0 |
| 5 | repl.py | ❌ F | 15.6 | 45 | 341 | 52 | 16.0 |
| 6 | textual_bridge.py | ❌ F | 15.7 | 65 | 317 | 52 | 0.0 |
| 7 | output_handler.py | ❌ F | 15.9 | 53 | 303 | 53 | 0.0 |
| 8 | commands/model.py | ❌ F | 17.2 | 35 | 215 | 57 | 12.0 |
| 9 | ui_renderer.py | ❌ F | 17.3 | 60 | 299 | 58 | 0.0 |
| 10 | commands/chat.py | ❌ F | 27.0 | 26 | 135 | 60 | 11.0 |

## 📁 Per-File Details

_Showing 20 worst files. 20 additional files omitted._

### textual_widgets.py — ❌ F (8.7/100)

LOC: 960 | Classes: 17 | Functions: 3 | MI: 27 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 924 | 🟠 HIGH | Duplicate Code | Function 'add_user_message' is an exact duplicate of 'add_system_message' at textual_widgets.py:932 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 924 | 🟠 HIGH | Duplicate Code | Function 'add_user_message' is an exact duplicate of 'add_error_message' at textual_widgets.py:940 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 932 | 🟠 HIGH | Duplicate Code | Function 'add_system_message' is an exact duplicate of 'add_error_message' at textual_widgets.py:940 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 915 | 🟡 MEDIUM | Duplicate Code | Function '_add_message_with_prefix' is 100% similar to 'add_user_message' at textual_widgets.py:924 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 915 | 🟡 MEDIUM | Duplicate Code | Function '_add_message_with_prefix' is 100% similar to 'add_system_message' at textual_widgets.py:932 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 915 | 🟡 MEDIUM | Duplicate Code | Function '_add_message_with_prefix' is 100% similar to 'add_error_message' at textual_widgets.py:940 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 15 | 🟢 LOW | Lint Violation | [TC003] Move standard library import `collections.abc.Iterator` into a type-checking block | Fix ruff violation TC003. |
| 364 | 🟢 LOW | Lint Violation | [PLC0415] `import` should be at the top-level of a file | Fix ruff violation PLC0415. |
| 366 | 🟢 LOW | Lint Violation | [TC006] Add quotes to type expression in `typing.cast()` | Fix ruff violation TC006. |
| 387 | 🟢 LOW | Lint Violation | [PLC0415] `import` should be at the top-level of a file | Fix ruff violation PLC0415. |
| 389 | 🟢 LOW | Lint Violation | [TC006] Add quotes to type expression in `typing.cast()` | Fix ruff violation TC006. |
| 390 | 🟢 LOW | Lint Violation | [SLF001] Private member accessed: `_navigate_history` | Fix ruff violation SLF001. |
| 399 | 🟢 LOW | Lint Violation | [PLC0415] `import` should be at the top-level of a file | Fix ruff violation PLC0415. |
| 401 | 🟢 LOW | Lint Violation | [TC006] Add quotes to type expression in `typing.cast()` | Fix ruff violation TC006. |
| 402 | 🟢 LOW | Lint Violation | [SLF001] Private member accessed: `_navigate_history` | Fix ruff violation SLF001. |

_... and 18 more smells._

### console.py — ❌ F (13.0/100)

LOC: 630 | Classes: 9 | Functions: 5 | MI: 43 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 55 | 🟠 HIGH | Primitive Obsession | Repeated primitive parameter group appears in: 'create_diff_params' (line 55), 'diff' (line 648), 'async_diff' (line 817) | Replace Data Value with Object — create a shared data structure for this recurring parameter group. |
| 427 | 🟡 MEDIUM | Duplicate Code | Function 'success' is 100% similar to 'info' at console.py:435 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 427 | 🟡 MEDIUM | Duplicate Code | Function 'success' is 100% similar to 'warning' at console.py:443 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 427 | 🟡 MEDIUM | Duplicate Code | Function 'success' is 100% similar to 'error' at console.py:451 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 435 | 🟡 MEDIUM | Duplicate Code | Function 'info' is 100% similar to 'warning' at console.py:443 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 435 | 🟡 MEDIUM | Duplicate Code | Function 'info' is 100% similar to 'error' at console.py:451 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 443 | 🟡 MEDIUM | Duplicate Code | Function 'warning' is 100% similar to 'error' at console.py:451 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 8 | 🟢 LOW | Lint Violation | [TC003] Move standard library import `collections.abc.Callable` into a type-checking block | Fix ruff violation TC003. |
| 55 | 🟢 LOW | Primitive Obsession | Function 'create_diff_params' has 3 primitive-typed parameters: old: Name(id='str', ctx=Load()), new: Name(id='str', ctx=Load()), filename: Name(id='str', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 88 | 🟢 LOW | Lint Violation | [RUF001] String contains ambiguous `ℹ` (INFORMATION SOURCE). Did you mean `i` (LATIN SMALL LETTER I)? | Fix ruff violation RUF001. |
| 93 | 🟢 LOW | Missing Type Hint | Function 'style' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 98 | 🟢 LOW | Missing Type Hint | Function 'icon' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 103 | 🟢 LOW | Missing Type Hint | Function 'accessible_icon' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 139 | 🟢 LOW | Missing Type Hint | Function 'get_resolved_theme' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 147 | 🟢 LOW | Lint Violation | [RET505] Unnecessary `elif` after `return` statement | Fix ruff violation RET505. |

_... and 62 more smells._

### app.py — ❌ F (13.5/100)

LOC: 531 | Classes: 2 | Functions: 21 | MI: 45 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 645 | 🟠 HIGH | Primitive Obsession | Function 'chat_command' has 8 primitive-typed parameters: prompt: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), agent: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), team: Name(id='bool', ctx=Load()), output_format: Name(id='str', ctx=Load()), plan: Name(id='bool', ctx=Load()), yes: Name(id='bool', ctx=Load()), tui: Name(id='bool', ctx=Load()), debug: Name(id='bool', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 118 | 🟡 MEDIUM | Lint Violation | [BLE001] Do not catch blind exception: `Exception` | Fix ruff violation BLE001. |
| 163 | 🟡 MEDIUM | Lint Violation | [PLR2004] Magic value used in comparison, consider replacing `5` with a constant variable | Fix ruff violation PLR2004. |
| 228 | 🟡 MEDIUM | Long Method | Function '_run_interactive' has 54 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 472 | 🟡 MEDIUM | Duplicate Code | Function '_run_headless_json' is 100% similar to '_run_headless_stream_json' at app.py:508 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 486 | 🟡 MEDIUM | Duplicate Code | Function 'run_and_render' is 100% similar to 'run_and_render_stream' at app.py:522 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 645 | 🟡 MEDIUM | Lint Violation | [PLR0913] Too many arguments in function definition (8 > 5) | Fix ruff violation PLR0913. |
| 8 | 🟢 LOW | Lint Violation | [TC003] Move standard library import `collections.abc.Callable` into a type-checking block | Fix ruff violation TC003. |
| 39 | 🟢 LOW | Lint Violation | [UP045] Use `X | None` for type annotations | Fix ruff violation UP045. |
| 40 | 🟢 LOW | Lint Violation | [UP045] Use `X | None` for type annotations | Fix ruff violation UP045. |
| 75 | 🟢 LOW | Lint Violation | [TRY003] Avoid specifying long messages outside the exception class | Fix ruff violation TRY003. |
| 76 | 🟢 LOW | Lint Violation | [EM101] Exception must not use a string literal, assign to variable first | Fix ruff violation EM101. |
| 76 | 🟢 LOW | Lint Violation | [COM812] Trailing comma missing | Fix ruff violation COM812. |
| 86 | 🟢 LOW | Lint Violation | [PLC0415] `import` should be at the top-level of a file | Fix ruff violation PLC0415. |
| 100 | 🟢 LOW | Lint Violation | [PLC0415] `import` should be at the top-level of a file | Fix ruff violation PLC0415. |

_... and 54 more smells._

### commands/context.py — ❌ F (15.3/100)

LOC: 303 | Classes: 1 | Functions: 0 | MI: 51 | Avg CC: 11.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 85 | 🟠 HIGH | Feature Envy | Method 'ContextCommand._show_status' accesses 'console' 13 times but 'self' only 0 times | Move Method — consider moving '_show_status' to the class that owns 'console'. |
| 273 | 🟠 HIGH | Primitive Obsession | Function '_handle_range_parameter' has 6 primitive-typed parameters: value: Name(id='str', ctx=Load()), param_name: Name(id='str', ctx=Load()), min_val: Name(id='float', ctx=Load()), max_val: BinOp(left=Name(id='float', ctx=Load()), op=BitOr(), right=Constant(value=None)), is_int: Name(id='bool', ctx=Load()), label: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 304 | 🟠 HIGH | Duplicate Code | Function '_handle_importance_parameter' is an exact duplicate of '_handle_similarity_parameter' at commands/context.py:308 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 322 | 🟠 HIGH | Feature Envy | Method 'ContextCommand._show_stats' accesses 'ctx' 10 times but 'self' only 0 times | Move Method — consider moving '_show_stats' to the class that owns 'ctx'. |
| 322 | 🟠 HIGH | Feature Envy | Method 'ContextCommand._show_stats' accesses 'console' 12 times but 'self' only 0 times | Move Method — consider moving '_show_stats' to the class that owns 'console'. |
| 75 | 🟡 MEDIUM | Feature Envy | Method 'ContextCommand._show_help_message' accesses 'ctx' 7 times but 'self' only 1 times | Move Method — consider moving '_show_help_message' to the class that owns 'ctx'. |
| 85 | 🟡 MEDIUM | Feature Envy | Method 'ContextCommand._show_status' accesses 'context_settings' 8 times but 'self' only 0 times | Move Method — consider moving '_show_status' to the class that owns 'context_settings'. |
| 155 | 🟡 MEDIUM | Feature Envy | Method 'ContextCommand._manage_strategy' accesses 'ctx' 8 times but 'self' only 5 times | Move Method — consider moving '_manage_strategy' to the class that owns 'ctx'. |
| 168 | 🟡 MEDIUM | Lint Violation | [PLR2004] Magic value used in comparison, consider replacing `3` with a constant variable | Fix ruff violation PLR2004. |
| 188 | 🟡 MEDIUM | Feature Envy | Method 'ContextCommand._show_strategy_status' accesses 'console' 9 times but 'self' only 0 times | Move Method — consider moving '_show_strategy_status' to the class that owns 'console'. |
| 188 | 🟡 MEDIUM | Feature Envy | Method 'ContextCommand._show_strategy_status' accesses 'context_settings' 6 times but 'self' only 0 times | Move Method — consider moving '_show_strategy_status' to the class that owns 'context_settings'. |
| 273 | 🟡 MEDIUM | Lint Violation | [PLR0913] Too many arguments in function definition (7 > 5) | Fix ruff violation PLR0913. |
| 290 | 🟡 MEDIUM | Lint Violation | [PLR5501] Use `elif` instead of `else` then `if`, to reduce indentation | Fix ruff violation PLR5501. |
| 296 | 🟡 MEDIUM | Duplicate Code | Function '_handle_max_tokens_parameter' is 100% similar to '_handle_threshold_parameter' at commands/context.py:300 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 322 | 🟡 MEDIUM | Complex Function | Function '_show_stats' has cyclomatic complexity 11 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |

_... and 76 more smells._

### repl.py — ❌ F (15.6/100)

LOC: 341 | Classes: 2 | Functions: 0 | MI: 52 | Avg CC: 16.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 78 | 🟠 HIGH | Long Method | Function '__init__' has 105 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 78 | 🟡 MEDIUM | Lint Violation | [PLR0913] Too many arguments in function definition (6 > 5) | Fix ruff violation PLR0913. |
| 78 | 🟡 MEDIUM | Complex Function | Function '__init__' has cyclomatic complexity 16 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 211 | 🟡 MEDIUM | Duplicate Code | Function '_handle_confirmation' is 100% similar to 'confirm_tool_execution' at ui_renderer.py:345 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 243 | 🟡 MEDIUM | Lint Violation | [BLE001] Do not catch blind exception: `Exception` | Fix ruff violation BLE001. |
| 352 | 🟡 MEDIUM | Long Method | Function '_run_agent_with_monitor' has 52 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 352 | 🟡 MEDIUM | Feature Envy | Method 'Repl._run_agent_with_monitor' accesses 'asyncio' 8 times but 'self' only 7 times | Move Method — consider moving '_run_agent_with_monitor' to the class that owns 'asyncio'. |
| 404 | 🟡 MEDIUM | Lint Violation | [BLE001] Do not catch blind exception: `Exception` | Fix ruff violation BLE001. |
| 420 | 🟡 MEDIUM | Feature Envy | Method 'Repl._handle_agent_event' accesses 'event' 5 times but 'self' only 1 times | Move Method — consider moving '_handle_agent_event' to the class that owns 'event'. |
| 28 | 🟢 LOW | Lint Violation | [TC001] Move application import `henchman.core.session.Session` into a type-checking block | Fix ruff violation TC001. |
| 30 | 🟢 LOW | Lint Violation | [TC001] Move application import `henchman.providers.base.ModelProvider` into a type-checking block | Fix ruff violation TC001. |
| 30 | 🟢 LOW | Lint Violation | [TC001] Move application import `henchman.providers.base.ToolCall` into a type-checking block | Fix ruff violation TC001. |
| 31 | 🟢 LOW | Lint Violation | [TC001] Move application import `henchman.tools.base.ConfirmationRequest` into a type-checking block | Fix ruff violation TC001. |
| 56 | 🟢 LOW | Lint Violation | [RUF001] String contains ambiguous `❯` (HEAVY RIGHT-POINTING ANGLE QUOTATION MARK ORNAMENT). Did you mean `>` (GREATER-THAN SIGN)? | Fix ruff violation RUF001. |
| 60 | 🟢 LOW | Magic Number | Magic number 25 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |

_... and 30 more smells._

### textual_bridge.py — ❌ F (15.7/100)

LOC: 317 | Classes: 2 | Functions: 2 | MI: 52 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 199 | 🟠 HIGH | Duplicate Code | Function '_on_content' is an exact duplicate of '_on_thought' at textual_bridge.py:204 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 209 | 🟠 HIGH | Duplicate Code | Function '_on_tool_req' is an exact duplicate of '_on_tool_res' at textual_bridge.py:214 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 209 | 🟠 HIGH | Duplicate Code | Function '_on_tool_req' is an exact duplicate of '_on_tool_confirm' at textual_bridge.py:219 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 214 | 🟠 HIGH | Duplicate Code | Function '_on_tool_res' is an exact duplicate of '_on_tool_confirm' at textual_bridge.py:219 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 246 | 🟠 HIGH | Duplicate Code | Function '_on_turn_summary' is an exact duplicate of '_on_think_start' at textual_bridge.py:312 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 246 | 🟠 HIGH | Duplicate Code | Function '_on_turn_summary' is an exact duplicate of '_on_think_done' at textual_bridge.py:316 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 246 | 🟠 HIGH | Duplicate Code | Function '_on_turn_summary' is an exact duplicate of '_on_think_req' at textual_bridge.py:320 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 312 | 🟠 HIGH | Duplicate Code | Function '_on_think_start' is an exact duplicate of '_on_think_done' at textual_bridge.py:316 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 312 | 🟠 HIGH | Duplicate Code | Function '_on_think_start' is an exact duplicate of '_on_think_req' at textual_bridge.py:320 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 316 | 🟠 HIGH | Duplicate Code | Function '_on_think_done' is an exact duplicate of '_on_think_req' at textual_bridge.py:320 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 329 | 🟠 HIGH | Duplicate Code | Function '_on_deleg_dec' is an exact duplicate of '_on_reflection' at textual_bridge.py:339 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 129 | 🟡 MEDIUM | Lint Violation | [BLE001] Do not catch blind exception: `Exception` | Fix ruff violation BLE001. |
| 255 | 🟡 MEDIUM | Feature Envy | Method 'EventBridge._on_turn_status' accesses 'event' 6 times but 'self' only 2 times | Move Method — consider moving '_on_turn_status' to the class that owns 'event'. |
| 272 | 🟡 MEDIUM | Lint Violation | [BLE001] Do not catch blind exception: `Exception` | Fix ruff violation BLE001. |
| 282 | 🟡 MEDIUM | Feature Envy | Method 'EventBridge._on_agent_done' accesses 'event' 5 times but 'self' only 1 times | Move Method — consider moving '_on_agent_done' to the class that owns 'event'. |

_... and 50 more smells._

### output_handler.py — ❌ F (15.9/100)

LOC: 303 | Classes: 1 | Functions: 0 | MI: 53 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 32 | 🟡 MEDIUM | Lint Violation | [PLR0913] Too many arguments in function definition (7 > 5) | Fix ruff violation PLR0913. |
| 104 | 🟡 MEDIUM | Lint Violation | [BLE001] Do not catch blind exception: `Exception` | Fix ruff violation BLE001. |
| 128 | 🟡 MEDIUM | Lint Violation | [BLE001] Do not catch blind exception: `Exception` | Fix ruff violation BLE001. |
| 180 | 🟡 MEDIUM | Lint Violation | [BLE001] Do not catch blind exception: `Exception` | Fix ruff violation BLE001. |
| 199 | 🟡 MEDIUM | Lint Violation | [BLE001] Do not catch blind exception: `Exception` | Fix ruff violation BLE001. |
| 225 | 🟡 MEDIUM | Duplicate Code | Function 'get_rich_status_message' is 94% similar to 'load' at session_manager.py:126 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 225 | 🟡 MEDIUM | Duplicate Code | Function 'get_rich_status_message' is 94% similar to 'compute_project_hash' at session_manager.py:199 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 298 | 🟡 MEDIUM | Duplicate Code | Function 'create_status' is 100% similar to 'create_status' at ui_renderer.py:183 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 332 | 🟡 MEDIUM | Duplicate Code | Function 'start_task' is 100% similar to 'start_task' at ui_renderer.py:356 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 345 | 🟡 MEDIUM | Duplicate Code | Function 'update_task' is 100% similar to 'tool_result' at ui_renderer.py:318 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 345 | 🟡 MEDIUM | Duplicate Code | Function 'update_task' is 100% similar to 'tool_summary' at ui_renderer.py:322 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 345 | 🟡 MEDIUM | Duplicate Code | Function 'update_task' is 100% similar to 'update_task' at ui_renderer.py:369 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 11 | 🟢 LOW | Lint Violation | [TC002] Move third-party import `rich.status.Status` into a type-checking block | Fix ruff violation TC002. |
| 22 | 🟢 LOW | Large Class | Class 'OutputHandler' spans 362 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
| 22 | 🟢 LOW | Large Class | Class 'OutputHandler' has 28 methods (threshold: 20) | Split Class — group related methods into smaller collaborating classes. |

_... and 38 more smells._

### commands/model.py — ❌ F (17.2/100)

LOC: 215 | Classes: 1 | Functions: 0 | MI: 57 | Avg CC: 12.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 61 | 🟠 HIGH | Feature Envy | Method 'ModelCommand._show_current' accesses 'ctx' 10 times but 'self' only 0 times | Move Method — consider moving '_show_current' to the class that owns 'ctx'. |
| 125 | 🟠 HIGH | Feature Envy | Method 'ModelCommand._set_provider' accesses 'ctx' 26 times but 'self' only 2 times | Move Method — consider moving '_set_provider' to the class that owns 'ctx'. |
| 56 | 🟡 MEDIUM | Lint Violation | [PLR2004] Magic value used in comparison, consider replacing `2` with a constant variable | Fix ruff violation PLR2004. |
| 57 | 🟡 MEDIUM | Lint Violation | [PLR2004] Magic value used in comparison, consider replacing `2` with a constant variable | Fix ruff violation PLR2004. |
| 89 | 🟡 MEDIUM | Feature Envy | Method 'ModelCommand._list_providers' accesses 'ctx' 7 times but 'self' only 2 times | Move Method — consider moving '_list_providers' to the class that owns 'ctx'. |
| 122 | 🟡 MEDIUM | Lint Violation | [BLE001] Do not catch blind exception: `Exception` | Fix ruff violation BLE001. |
| 125 | 🟡 MEDIUM | Long Method | Function '_set_provider' has 69 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 125 | 🟡 MEDIUM | Lint Violation | [C901] `_set_provider` is too complex (11 > 10) | Fix ruff violation C901. |
| 125 | 🟡 MEDIUM | Complex Function | Function '_set_provider' has cyclomatic complexity 12 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 175 | 🟡 MEDIUM | Lint Violation | [BLE001] Do not catch blind exception: `Exception` | Fix ruff violation BLE001. |
| 204 | 🟡 MEDIUM | Lint Violation | [BLE001] Do not catch blind exception: `Exception` | Fix ruff violation BLE001. |
| 293 | 🟡 MEDIUM | Lint Violation | [BLE001] Do not catch blind exception: `Exception` | Fix ruff violation BLE001. |
| 12 | 🟢 LOW | Lint Violation | [TC005] Found empty type-checking block | Fix ruff violation TC005. |
| 19 | 🟢 LOW | Missing Type Hint | Function 'name' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 28 | 🟢 LOW | Missing Type Hint | Function 'description' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |

_... and 20 more smells._

### ui_renderer.py — ❌ F (17.3/100)

LOC: 299 | Classes: 2 | Functions: 0 | MI: 58 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 45 | 🟠 HIGH | Primitive Obsession | Repeated primitive parameter group appears in: 'start_task' (line 45), 'start_task' (line 356) | Replace Data Value with Object — create a shared data structure for this recurring parameter group. |
| 69 | 🟠 HIGH | Primitive Obsession | Repeated primitive parameter group appears in: 'update_task' (line 69), 'update_task' (line 369) | Replace Data Value with Object — create a shared data structure for this recurring parameter group. |
| 96 | 🟡 MEDIUM | Large Class | Class 'UIRenderer' has 31 methods (threshold: 20) | Split Class — group related methods into smaller collaborating classes. |
| 174 | 🟡 MEDIUM | Lint Violation | [BLE001] Do not catch blind exception: `Exception` | Fix ruff violation BLE001. |
| 213 | 🟡 MEDIUM | Lint Violation | [BLE001] Do not catch blind exception: `Exception` | Fix ruff violation BLE001. |
| 318 | 🟡 MEDIUM | Duplicate Code | Function 'tool_result' is 100% similar to 'tool_summary' at ui_renderer.py:322 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 318 | 🟡 MEDIUM | Duplicate Code | Function 'tool_result' is 100% similar to 'update_task' at ui_renderer.py:369 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 322 | 🟡 MEDIUM | Duplicate Code | Function 'tool_summary' is 100% similar to 'update_task' at ui_renderer.py:369 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 10 | 🟢 LOW | Lint Violation | [TC003] Move standard library import `collections.abc.Generator` into a type-checking block | Fix ruff violation TC003. |
| 23 | 🟢 LOW | Lint Violation | [TC002] Move third-party import `rich.status.Status` into a type-checking block | Fix ruff violation TC002. |
| 26 | 🟢 LOW | Lint Violation | [TC001] Move application import `henchman.core.session.Session` into a type-checking block | Fix ruff violation TC001. |
| 36 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: missing return type | Add Type Annotations for all parameters and return type. |
| 45 | 🟢 LOW | Missing Type Hint | Function 'start_task' has incomplete type hints: 1/4 params untyped | Add Type Annotations for all parameters and return type. |
| 45 | 🟢 LOW | Primitive Obsession | Function 'start_task' has 3 primitive-typed parameters: task_id: Name(id='str', ctx=Load()), description: Name(id='str', ctx=Load()), total: Name(id='int', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 69 | 🟢 LOW | Missing Type Hint | Function 'update_task' has incomplete type hints: 1/4 params untyped | Add Type Annotations for all parameters and return type. |

_... and 45 more smells._

### commands/chat.py — ❌ F (27.0/100)

LOC: 135 | Classes: 1 | Functions: 0 | MI: 60 | Avg CC: 11.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 120 | 🟠 HIGH | Feature Envy | Method 'ChatCommand._resume' accesses 'ctx' 12 times but 'self' only 0 times | Move Method — consider moving '_resume' to the class that owns 'ctx'. |
| 55 | 🟡 MEDIUM | Duplicate Code | Function 'execute' is 100% similar to 'execute' at commands/mcp.py:54 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 55 | 🟡 MEDIUM | Duplicate Code | Function 'execute' is 96% similar to 'execute' at commands/rag.py:56 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 77 | 🟡 MEDIUM | Feature Envy | Method 'ChatCommand._save' accesses 'ctx' 5 times but 'self' only 0 times | Move Method — consider moving '_save' to the class that owns 'ctx'. |
| 98 | 🟡 MEDIUM | Feature Envy | Method 'ChatCommand._list' accesses 'ctx' 5 times but 'self' only 0 times | Move Method — consider moving '_list' to the class that owns 'ctx'. |
| 98 | 🟡 MEDIUM | Feature Envy | Method 'ChatCommand._list' accesses 'meta' 5 times but 'self' only 0 times | Move Method — consider moving '_list' to the class that owns 'meta'. |
| 120 | 🟡 MEDIUM | Long Method | Function '_resume' has 61 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 120 | 🟡 MEDIUM | Feature Envy | Method 'ChatCommand._resume' accesses 'session_msg' 5 times but 'self' only 0 times | Move Method — consider moving '_resume' to the class that owns 'session_msg'. |
| 120 | 🟡 MEDIUM | Complex Function | Function '_resume' has cyclomatic complexity 11 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 127 | 🟡 MEDIUM | Lint Violation | [PLR2004] Magic value used in comparison, consider replacing `2` with a constant variable | Fix ruff violation PLR2004. |
| 22 | 🟢 LOW | Lint Violation | [RUF012] Mutable class attributes should be annotated with `typing.ClassVar` | Fix ruff violation RUF012. |
| 29 | 🟢 LOW | Missing Type Hint | Function 'name' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 38 | 🟢 LOW | Missing Type Hint | Function 'description' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 47 | 🟢 LOW | Missing Type Hint | Function 'usage' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 55 | 🟢 LOW | Missing Type Hint | Function 'execute' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |

_... and 11 more smells._

### commands/rag.py — ❌ F (28.7/100)

LOC: 169 | Classes: 1 | Functions: 0 | MI: 56 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 75 | 🟡 MEDIUM | Deep Nesting | Nesting depth 5 in 'execute' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 97 | 🟡 MEDIUM | Feature Envy | Method 'RagCommand._status' accesses 'ctx' 9 times but 'self' only 1 times | Move Method — consider moving '_status' to the class that owns 'ctx'. |
| 97 | 🟡 MEDIUM | Feature Envy | Method 'RagCommand._status' accesses 'rag_system' 5 times but 'self' only 1 times | Move Method — consider moving '_status' to the class that owns 'rag_system'. |
| 118 | 🟡 MEDIUM | Feature Envy | Method 'RagCommand._reindex' accesses 'ctx' 5 times but 'self' only 1 times | Move Method — consider moving '_reindex' to the class that owns 'ctx'. |
| 155 | 🟡 MEDIUM | Feature Envy | Method 'RagCommand._clear_all' accesses 'ctx' 6 times but 'self' only 0 times | Move Method — consider moving '_clear_all' to the class that owns 'ctx'. |
| 177 | 🟡 MEDIUM | Lint Violation | [BLE001] Do not catch blind exception: `Exception` | Fix ruff violation BLE001. |
| 182 | 🟡 MEDIUM | Feature Envy | Method 'RagCommand._cleanup' accesses 'ctx' 6 times but 'self' only 0 times | Move Method — consider moving '_cleanup' to the class that owns 'ctx'. |
| 201 | 🟡 MEDIUM | Lint Violation | [BLE001] Do not catch blind exception: `Exception` | Fix ruff violation BLE001. |
| 208 | 🟡 MEDIUM | Lint Violation | [BLE001] Do not catch blind exception: `Exception` | Fix ruff violation BLE001. |
| 21 | 🟢 LOW | Lint Violation | [RUF012] Mutable class attributes should be annotated with `typing.ClassVar` | Fix ruff violation RUF012. |
| 30 | 🟢 LOW | Missing Type Hint | Function 'name' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 39 | 🟢 LOW | Missing Type Hint | Function 'description' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 48 | 🟢 LOW | Missing Type Hint | Function 'usage' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 56 | 🟢 LOW | Missing Type Hint | Function 'execute' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 73 | 🟢 LOW | Deep Nesting | Nesting depth 4 in 'execute' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |

_... and 13 more smells._

### textual_messages.py — ❌ F (31.4/100)

LOC: 129 | Classes: 9 | Functions: 0 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 22 | 🟡 MEDIUM | Duplicate Code | Function '__init__' is 100% similar to '__init__' at textual_messages.py:41 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 22 | 🟡 MEDIUM | Duplicate Code | Function '__init__' is 100% similar to '__init__' at textual_messages.py:60 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 22 | 🟡 MEDIUM | Duplicate Code | Function '__init__' is 100% similar to '__init__' at textual_messages.py:79 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 22 | 🟡 MEDIUM | Duplicate Code | Function '__init__' is 100% similar to '__init__' at textual_messages.py:98 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 22 | 🟡 MEDIUM | Duplicate Code | Function '__init__' is 100% similar to '__init__' at textual_messages.py:117 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 41 | 🟡 MEDIUM | Duplicate Code | Function '__init__' is 100% similar to '__init__' at textual_messages.py:60 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 41 | 🟡 MEDIUM | Duplicate Code | Function '__init__' is 100% similar to '__init__' at textual_messages.py:79 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 41 | 🟡 MEDIUM | Duplicate Code | Function '__init__' is 100% similar to '__init__' at textual_messages.py:98 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 41 | 🟡 MEDIUM | Duplicate Code | Function '__init__' is 100% similar to '__init__' at textual_messages.py:117 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 60 | 🟡 MEDIUM | Duplicate Code | Function '__init__' is 100% similar to '__init__' at textual_messages.py:79 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 60 | 🟡 MEDIUM | Duplicate Code | Function '__init__' is 100% similar to '__init__' at textual_messages.py:98 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 60 | 🟡 MEDIUM | Duplicate Code | Function '__init__' is 100% similar to '__init__' at textual_messages.py:117 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 79 | 🟡 MEDIUM | Duplicate Code | Function '__init__' is 100% similar to '__init__' at textual_messages.py:98 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 79 | 🟡 MEDIUM | Duplicate Code | Function '__init__' is 100% similar to '__init__' at textual_messages.py:117 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 98 | 🟡 MEDIUM | Duplicate Code | Function '__init__' is 100% similar to '__init__' at textual_messages.py:117 | Extract Shared Function — identify the common logic and parameterise the differences. |

_... and 10 more smells._

### commands/theme.py — ❌ F (35.0/100)

LOC: 156 | Classes: 1 | Functions: 0 | MI: 63 | Avg CC: 11.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 94 | 🟠 HIGH | Feature Envy | Method 'ThemeCommand._set_theme' accesses 'ctx' 20 times but 'self' only 1 times | Move Method — consider moving '_set_theme' to the class that owns 'ctx'. |
| 75 | 🟡 MEDIUM | Feature Envy | Method 'ThemeCommand._list_themes' accesses 'ctx' 5 times but 'self' only 1 times | Move Method — consider moving '_list_themes' to the class that owns 'ctx'. |
| 94 | 🟡 MEDIUM | Complex Function | Function '_set_theme' has cyclomatic complexity 11 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 143 | 🟡 MEDIUM | Lint Violation | [BLE001] Do not catch blind exception: `Exception` | Fix ruff violation BLE001. |
| 146 | 🟡 MEDIUM | Feature Envy | Method 'ThemeCommand._preview_theme' accesses 'ctx' 8 times but 'self' only 1 times | Move Method — consider moving '_preview_theme' to the class that owns 'ctx'. |
| 146 | 🟡 MEDIUM | Feature Envy | Method 'ThemeCommand._preview_theme' accesses 'preview_renderer' 6 times but 'self' only 1 times | Move Method — consider moving '_preview_theme' to the class that owns 'preview_renderer'. |
| 24 | 🟢 LOW | Missing Type Hint | Function 'name' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 33 | 🟢 LOW | Missing Type Hint | Function 'description' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 42 | 🟢 LOW | Missing Type Hint | Function 'usage' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 48 | 🟢 LOW | Lint Violation | [E501] Line too long (218 > 100) | Fix ruff violation E501. |
| 50 | 🟢 LOW | Missing Type Hint | Function 'execute' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 69 | 🟢 LOW | Deep Nesting | Nesting depth 4 in 'execute' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 75 | 🟢 LOW | Missing Type Hint | Function '_list_themes' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 94 | 🟢 LOW | Long Method | Function '_set_theme' has 44 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 94 | 🟢 LOW | Missing Type Hint | Function '_set_theme' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |

_... and 12 more smells._

### textual_config.py — ❌ F (40.8/100)

LOC: 217 | Classes: 3 | Functions: 0 | MI: 59 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 184 | 🟡 MEDIUM | Duplicate Code | Function '_initialize_output_handler' is 94% similar to '_initialize_tool_executor' at textual_config.py:216 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 21 | 🟢 LOW | Lint Violation | [TC001] Move application import `henchman.providers.base.ModelProvider` into a type-checking block | Fix ruff violation TC001. |
| 48 | 🟢 LOW | Lint Violation | [PIE790] Unnecessary `pass` statement | Fix ruff violation PIE790. |
| 77 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 111 | 🟢 LOW | Missing Type Hint | Function 'initialize_all' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 129 | 🟢 LOW | Missing Type Hint | Function '_initialize_tui_adapter' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 131 | 🟢 LOW | Lint Violation | [PLC0415] `import` should be at the top-level of a file | Fix ruff violation PLC0415. |
| 135 | 🟢 LOW | Missing Type Hint | Function '_initialize_core_context' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 147 | 🟢 LOW | Lint Violation | [Q000] Single quotes found but double quotes preferred | Fix ruff violation Q000. |
| 150 | 🟢 LOW | Missing Type Hint | Function '_initialize_renderer' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 152 | 🟢 LOW | Lint Violation | [PLC0415] `import` should be at the top-level of a file | Fix ruff violation PLC0415. |
| 155 | 🟢 LOW | Lint Violation | [TRY003] Avoid specifying long messages outside the exception class | Fix ruff violation TRY003. |
| 155 | 🟢 LOW | Lint Violation | [EM101] Exception must not use a string literal, assign to variable first | Fix ruff violation EM101. |
| 163 | 🟢 LOW | Lint Violation | [COM812] Trailing comma missing | Fix ruff violation COM812. |
| 166 | 🟢 LOW | Missing Type Hint | Function '_resolve_theme_name' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |

_... and 17 more smells._

### textual_screens.py — ❌ F (41.0/100)

LOC: 373 | Classes: 4 | Functions: 0 | MI: 53 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 14 | 🟢 LOW | Lint Violation | [TC002] Move third-party import `textual.app.ComposeResult` into a type-checking block | Fix ruff violation TC002. |
| 80 | 🟢 LOW | Lint Violation | [RUF012] Mutable class attributes should be annotated with `typing.ClassVar` | Fix ruff violation RUF012. |
| 86 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 95 | 🟢 LOW | Long Method | Function 'compose' has 35 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 95 | 🟢 LOW | Missing Type Hint | Function 'compose' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 101 | 🟢 LOW | Lint Violation | [PLC0415] `import` should be at the top-level of a file | Fix ruff violation PLC0415. |
| 119 | 🟢 LOW | Lint Violation | [ISC001] Implicitly concatenated string literals on one line | Fix ruff violation ISC001. |
| 119 | 🟢 LOW | Lint Violation | [COM812] Trailing comma missing | Fix ruff violation COM812. |
| 137 | 🟢 LOW | Missing Type Hint | Function '_build_params_label' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 143 | 🟢 LOW | Lint Violation | [PLC0415] `import` should be at the top-level of a file | Fix ruff violation PLC0415. |
| 152 | 🟢 LOW | Lint Violation | [ISC001] Implicitly concatenated string literals on one line | Fix ruff violation ISC001. |
| 154 | 🟢 LOW | Missing Type Hint | Function 'on_button_pressed' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 162 | 🟢 LOW | Missing Type Hint | Function 'action_approve' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 164 | 🟢 LOW | Lint Violation | [FBT003] Boolean positional value in function call | Fix ruff violation FBT003. |
| 166 | 🟢 LOW | Missing Type Hint | Function 'action_deny' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |

_... and 17 more smells._

### input.py — ❌ F (42.4/100)

LOC: 269 | Classes: 3 | Functions: 5 | MI: 53 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 18 | 🟢 LOW | Lint Violation | [TC002] Move third-party import `rich.console.Console` into a type-checking block | Fix ruff violation TC002. |
| 76 | 🟢 LOW | Long Method | Function 'expand_at_references' has 42 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 110 | 🟢 LOW | Deep Nesting | Nesting depth 4 in 'expand_at_references' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 112 | 🟢 LOW | Lint Violation | [E501] Line too long (138 > 100) | Fix ruff violation E501. |
| 121 | 🟢 LOW | Deep Nesting | Nesting depth 4 in 'expand_at_references' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 129 | 🟢 LOW | Long Method | Function 'create_session' has 45 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 151 | 🟢 LOW | Lint Violation | [RSE102] Unnecessary parentheses on raised exception | Fix ruff violation RSE102. |
| 177 | 🟢 LOW | Deep Nesting | Nesting depth 4 in 'create_session' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 201 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 204 | 🟢 LOW | Lint Violation | [RUF001] String contains ambiguous `❯` (HEAVY RIGHT-POINTING ANGLE QUOTATION MARK ORNAMENT). Did you mean `>` (GREATER-THAN SIGN)? | Fix ruff violation RUF001. |
| 215 | 🟢 LOW | Missing Type Hint | Function 'get_prompt' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 227 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: missing return type | Add Type Annotations for all parameters and return type. |
| 235 | 🟢 LOW | Long Method | Function 'prompt_for_parameters' has 39 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 235 | 🟢 LOW | Missing Type Hint | Function 'prompt_for_parameters' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 292 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |

_... and 16 more smells._

### commands/mcp.py — ❌ F (44.3/100)

LOC: 118 | Classes: 1 | Functions: 0 | MI: 61 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 121 | 🟠 HIGH | Feature Envy | Method 'McpCommand._logging' accesses 'ctx' 15 times but 'self' only 0 times | Move Method — consider moving '_logging' to the class that owns 'ctx'. |
| 54 | 🟡 MEDIUM | Duplicate Code | Function 'execute' is 96% similar to 'execute' at commands/rag.py:56 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 76 | 🟡 MEDIUM | Feature Envy | Method 'McpCommand._list' accesses 'ctx' 5 times but 'self' only 0 times | Move Method — consider moving '_list' to the class that owns 'ctx'. |
| 99 | 🟡 MEDIUM | Feature Envy | Method 'McpCommand._status' accesses 'ctx' 7 times but 'self' only 0 times | Move Method — consider moving '_status' to the class that owns 'ctx'. |
| 117 | 🟡 MEDIUM | Lint Violation | [PLR2004] Magic value used in comparison, consider replacing `10` with a constant variable | Fix ruff violation PLR2004. |
| 127 | 🟡 MEDIUM | Lint Violation | [PLR2004] Magic value used in comparison, consider replacing `2` with a constant variable | Fix ruff violation PLR2004. |
| 21 | 🟢 LOW | Lint Violation | [RUF012] Mutable class attributes should be annotated with `typing.ClassVar` | Fix ruff violation RUF012. |
| 28 | 🟢 LOW | Missing Type Hint | Function 'name' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 37 | 🟢 LOW | Missing Type Hint | Function 'description' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 46 | 🟢 LOW | Missing Type Hint | Function 'usage' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 54 | 🟢 LOW | Missing Type Hint | Function 'execute' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 76 | 🟢 LOW | Missing Type Hint | Function '_list' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 76 | 🟢 LOW | Feature Envy | Method 'McpCommand._list' accesses 'manager' 3 times but 'self' only 0 times | Move Method — consider moving '_list' to the class that owns 'manager'. |
| 99 | 🟢 LOW | Missing Type Hint | Function '_status' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 99 | 🟢 LOW | Feature Envy | Method 'McpCommand._status' accesses 'manager' 3 times but 'self' only 0 times | Move Method — consider moving '_status' to the class that owns 'manager'. |

_... and 5 more smells._

### commands/agent.py — ❌ F (45.2/100)

LOC: 87 | Classes: 1 | Functions: 0 | MI: 57 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 33 | 🟠 HIGH | Feature Envy | Method 'AgentCommand.execute' accesses 'ctx' 10 times but 'self' only 2 times | Move Method — consider moving 'execute' to the class that owns 'ctx'. |
| 68 | 🟡 MEDIUM | Lint Violation | [BLE001] Do not catch blind exception: `Exception` | Fix ruff violation BLE001. |
| 71 | 🟡 MEDIUM | Feature Envy | Method 'AgentCommand._list_agents' accesses 'table' 5 times but 'self' only 0 times | Move Method — consider moving '_list_agents' to the class that owns 'table'. |
| 93 | 🟡 MEDIUM | Feature Envy | Method 'AgentCommand._show_config' accesses 'ctx' 8 times but 'self' only 0 times | Move Method — consider moving '_show_config' to the class that owns 'ctx'. |
| 93 | 🟡 MEDIUM | Feature Envy | Method 'AgentCommand._show_config' accesses 'config' 9 times but 'self' only 0 times | Move Method — consider moving '_show_config' to the class that owns 'config'. |
| 19 | 🟢 LOW | Missing Type Hint | Function 'name' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 24 | 🟢 LOW | Missing Type Hint | Function 'description' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 29 | 🟢 LOW | Missing Type Hint | Function 'usage' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 33 | 🟢 LOW | Long Method | Function 'execute' has 31 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 33 | 🟢 LOW | Missing Type Hint | Function 'execute' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 62 | 🟢 LOW | Deep Nesting | Nesting depth 4 in 'execute' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 63 | 🟢 LOW | Lint Violation | [SLF001] Private member accessed: `_run_agent_direct` | Fix ruff violation SLF001. |
| 66 | 🟢 LOW | Lint Violation | [COM812] Trailing comma missing | Fix ruff violation COM812. |
| 68 | 🟢 LOW | Deep Nesting | Nesting depth 4 in 'execute' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 71 | 🟢 LOW | Missing Type Hint | Function '_list_agents' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |

_... and 5 more smells._

### session_manager.py — ❌ F (47.1/100)

LOC: 198 | Classes: 1 | Functions: 0 | MI: 66 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 67 | 🟡 MEDIUM | Feature Envy | Method 'ReplSessionManager._sync_session_to_agent' accesses 'session_msg' 5 times but 'self' only 0 times | Move Method — consider moving '_sync_session_to_agent' to the class that owns 'session_msg'. |
| 126 | 🟡 MEDIUM | Duplicate Code | Function 'load' is 100% similar to 'compute_project_hash' at session_manager.py:199 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 210 | 🟡 MEDIUM | Duplicate Code | Function 'record_user_message' is 100% similar to 'record_tool_result' at session_manager.py:242 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 10 | 🟢 LOW | Lint Violation | [TC003] Move standard library import `pathlib.Path` into a type-checking block | Fix ruff violation TC003. |
| 33 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 36 | 🟢 LOW | Lint Violation | [FBT001] Boolean-typed positional argument in function definition | Fix ruff violation FBT001. |
| 36 | 🟢 LOW | Lint Violation | [FBT002] Boolean default positional argument in function definition | Fix ruff violation FBT002. |
| 50 | 🟢 LOW | Missing Type Hint | Function 'current' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 54 | 🟢 LOW | Missing Type Hint | Function 'set_session' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 67 | 🟢 LOW | Missing Type Hint | Function '_sync_session_to_agent' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 67 | 🟢 LOW | Feature Envy | Method 'ReplSessionManager._sync_session_to_agent' accesses 'tc' 3 times but 'self' only 0 times | Move Method — consider moving '_sync_session_to_agent' to the class that owns 'tc'. |
| 99 | 🟢 LOW | Missing Type Hint | Function 'auto_save_session' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 110 | 🟢 LOW | Missing Type Hint | Function 'create_session' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 126 | 🟢 LOW | Missing Type Hint | Function 'load' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 140 | 🟢 LOW | Missing Type Hint | Function 'load_by_tag' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |

_... and 11 more smells._

### commands/builtins.py — ❌ F (50.7/100)

LOC: 202 | Classes: 4 | Functions: 1 | MI: 71 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 52 | 🟠 HIGH | Feature Envy | Method 'HelpCommand.execute' accesses 'ctx' 14 times but 'self' only 0 times | Move Method — consider moving 'execute' to the class that owns 'ctx'. |
| 52 | 🟡 MEDIUM | Feature Envy | Method 'HelpCommand.execute' accesses 'cmd' 5 times but 'self' only 0 times | Move Method — consider moving 'execute' to the class that owns 'cmd'. |
| 204 | 🟡 MEDIUM | Feature Envy | Method 'ToolsCommand.execute' accesses 'ctx' 7 times but 'self' only 0 times | Move Method — consider moving 'execute' to the class that owns 'ctx'. |
| 26 | 🟢 LOW | Missing Type Hint | Function 'name' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 35 | 🟢 LOW | Missing Type Hint | Function 'description' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 44 | 🟢 LOW | Missing Type Hint | Function 'usage' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 52 | 🟢 LOW | Missing Type Hint | Function 'execute' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 90 | 🟢 LOW | Missing Type Hint | Function 'name' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 99 | 🟢 LOW | Missing Type Hint | Function 'description' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 108 | 🟢 LOW | Missing Type Hint | Function 'usage' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 116 | 🟢 LOW | Missing Type Hint | Function 'execute' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 133 | 🟢 LOW | Missing Type Hint | Function 'name' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 142 | 🟢 LOW | Missing Type Hint | Function 'description' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 151 | 🟢 LOW | Missing Type Hint | Function 'usage' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 159 | 🟢 LOW | Missing Type Hint | Function 'execute' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |

_... and 7 more smells._

## ✨ Clean Files (3 files with no smells)

<details><summary>Click to expand</summary>

- __init__.py — ✅ A
- stream_event_handlers.py — 👍 B
- tool_executor.py — 👍 B

</details>

---

_Report generated by XP Code Smell Detector. Smells are static heuristics — use judgement when prioritising fixes._
