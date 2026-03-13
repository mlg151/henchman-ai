# Code Smell Report — ✅ A (Score: 96.8/100)

_Scanned: /home/matthew/mlg-cli/src/henchman/cli_  

_Generated: 2026-03-05T14:51:36.572033+00:00_

## Executive Summary

| Metric | Value |
|:-------|------:|
| **Overall Grade** | ✅ A |
| **Overall Score** | 96.8/100 |
| **Files Scanned** | 41 |
| **Total Lines (non-blank)** | 11,563 |
| **Total Smells** | 68 |
| **Avg Maintainability Index** | 100.0 |
| **Avg Cyclomatic Complexity** | 0.0 |

### Smells by Severity

| Severity | Count |
|:---------|------:|
| low | 51 |
| medium | 16 |
| high | 1 |

### Smells by Category

| Category | Count |
|:---------|------:|
| Missing Type Hint | 29 |
| Duplicate Code | 13 |
| Feature Envy | 8 |
| Long Method | 6 |
| Primitive Obsession | 6 |
| Large Class | 3 |
| Magic Number | 2 |
| Deep Nesting | 1 |

## 🎯 Prioritised Refactoring Queue

These are the highest-impact smells to address first:

1. **textual_messages.py:38** — 🟠 HIGH — Duplicate Code  
   Function '_str_payload' is an exact duplicate of 'request' at textual_messages.py:83  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

2. **command_processor.py:62** — 🟡 MEDIUM — Long Method  
   Function 'handle_command' has 50 lines (threshold: 30)  
   → _Extract Method — break this function into smaller, intention-revealing helper functions._

3. **commands/__init__.py:142** — 🟡 MEDIUM — Duplicate Code  
   Function 'register' is 100% similar to 'register_theme' at console.py:372  
   → _Extract Shared Function — identify the common logic and parameterise the differences._

4. **commands/agent.py:218** — 🟡 MEDIUM — Duplicate Code  
   Function '_list_agents' is 94% similar to 'post_status_message' at textual_bridge.py:201  
   → _Extract Shared Function — identify the common logic and parameterise the differences._

5. **commands/builtins.py:205** — 🟡 MEDIUM — Duplicate Code  
   Function '_list_all_commands' is 94% similar to 'on_switch_provider_message' at textual_mixins.py:1394  
   → _Extract Shared Function — identify the common logic and parameterise the differences._

6. **commands/chat.py:319** — 🟡 MEDIUM — Duplicate Code  
   Function '_restore_session' is 100% similar to '_sync_session_to_agent' at session_manager.py:131  
   → _Extract Shared Function — identify the common logic and parameterise the differences._

7. **commands/context.py:127** — 🟡 MEDIUM — Duplicate Code  
   Function '__init__' is 100% similar to '__init__' at json_output.py:69  
   → _Extract Shared Function — identify the common logic and parameterise the differences._

8. **commands/context.py:518** — 🟡 MEDIUM — Duplicate Code  
   Function '_show_help_message' is 94% similar to '_list_themes' at commands/theme.py:203  
   → _Extract Shared Function — identify the common logic and parameterise the differences._

9. **commands/unlimited.py:76** — 🟡 MEDIUM — Feature Envy  
   Method 'UnlimitedCommand.execute' accesses 'ctx' 5 times but 'self' only 1 times  
   → _Move Method — consider moving 'execute' to the class that owns 'ctx'._

10. **console.py:660** — 🟡 MEDIUM — Duplicate Code  
   Function '_render_diff' is 94% similar to '_add_message_with_prefix' at textual_widgets.py:919  
   → _Extract Shared Function — identify the common logic and parameterise the differences._

11. **console_helpers.py:118** — 🟡 MEDIUM — Duplicate Code  
   Function 'print_usage_help' is 100% similar to 'print_parameter_list' at console_helpers.py:135  
   → _Extract Shared Function — identify the common logic and parameterise the differences._

12. **output_handler.py:272** — 🟡 MEDIUM — Duplicate Code  
   Function 'get_rich_status_message' is 94% similar to 'compute_project_hash' at session_manager.py:250  
   → _Extract Shared Function — identify the common logic and parameterise the differences._

13. **repl.py:291** — 🟡 MEDIUM — Duplicate Code  
   Function 'set_session' is 100% similar to 'post' at textual_bridge.py:174  
   → _Extract Shared Function — identify the common logic and parameterise the differences._

14. **serve.py:39** — 🟡 MEDIUM — Primitive Obsession  
   Function 'serve_command' has 4 primitive-typed parameters: host: Name(id='str', ctx=Load()), port: Name(id='int', ctx=Load()), reload: Name(id='bool', ctx=Load()), workers: Name(id='int', ctx=Load())  
   → _Introduce Parameter Object — group related primitives into a dataclass or NamedTuple._

15. **textual_config.py:191** — 🟡 MEDIUM — Duplicate Code  
   Function '_initialize_output_handler' is 95% similar to '_initialize_tool_executor' at textual_config.py:225  
   → _Extract Shared Function — identify the common logic and parameterise the differences._


## 📊 Files Ranked by Quality

| Rank | File | Grade | Score | Smells | LOC | MI | Avg CC |
|-----:|:-----|:------|------:|-------:|----:|---:|-------:|
| 1 | textual_screens.py | ⚠️ C | 77.6 | 16 | 373 | 100 | 0.0 |
| 2 | textual_messages.py | 👍 B | 89.5 | 2 | 112 | 100 | 0.0 |
| 3 | commands/extensions.py | ✅ A | 90.2 | 7 | 49 | 100 | 0.0 |
| 4 | command_processor.py | ✅ A | 92.3 | 4 | 100 | 100 | 0.0 |
| 5 | output_handler.py | ✅ A | 92.3 | 4 | 267 | 100 | 0.0 |
| 6 | commands/context.py | ✅ A | 93.0 | 2 | 535 | 100 | 0.0 |
| 7 | repl.py | ✅ A | 93.7 | 3 | 436 | 100 | 0.0 |
| 8 | serve.py | ✅ A | 93.7 | 3 | 84 | 100 | 0.0 |
| 9 | textual_app.py | ✅ A | 94.4 | 4 | 307 | 100 | 0.0 |
| 10 | console.py | ✅ A | 95.1 | 2 | 713 | 100 | 0.0 |

## 📁 Per-File Details

_Showing 20 worst files. 21 additional files omitted._

### textual_screens.py — ⚠️ C (77.6/100)

LOC: 373 | Classes: 4 | Functions: 0 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
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
| 451 | 🟢 LOW | Missing Type Hint | Function 'on_button_pressed' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |

_... and 1 more smells._

### textual_messages.py — 👍 B (89.5/100)

LOC: 112 | Classes: 10 | Functions: 0 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 38 | 🟠 HIGH | Duplicate Code | Function '_str_payload' is an exact duplicate of 'request' at textual_messages.py:83 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 119 | 🟡 MEDIUM | Duplicate Code | Function '__init__' is 95% similar to '__init__' at textual_screens.py:87 | Extract Shared Function — identify the common logic and parameterise the differences. |

### commands/extensions.py — ✅ A (90.2/100)

LOC: 49 | Classes: 1 | Functions: 0 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 14 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 23 | 🟢 LOW | Missing Type Hint | Function 'name' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 32 | 🟢 LOW | Missing Type Hint | Function 'description' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 41 | 🟢 LOW | Missing Type Hint | Function 'usage' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 49 | 🟢 LOW | Missing Type Hint | Function 'execute' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 49 | 🟢 LOW | Feature Envy | Method 'ExtensionsCommand.execute' accesses 'ctx' 3 times but 'self' only 2 times | Move Method — consider moving 'execute' to the class that owns 'ctx'. |
| 49 | 🟢 LOW | Feature Envy | Method 'ExtensionsCommand.execute' accesses 'ext' 3 times but 'self' only 2 times | Move Method — consider moving 'execute' to the class that owns 'ext'. |

### command_processor.py — ✅ A (92.3/100)

LOC: 100 | Classes: 1 | Functions: 0 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 62 | 🟡 MEDIUM | Long Method | Function 'handle_command' has 50 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 34 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/6 params untyped | Add Type Annotations for all parameters and return type. |
| 62 | 🟢 LOW | Missing Type Hint | Function 'handle_command' has incomplete type hints: 1/4 params untyped | Add Type Annotations for all parameters and return type. |
| 124 | 🟢 LOW | Missing Type Hint | Function 'get_command_registry' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |

### output_handler.py — ✅ A (92.3/100)

LOC: 267 | Classes: 1 | Functions: 0 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 272 | 🟡 MEDIUM | Duplicate Code | Function 'get_rich_status_message' is 94% similar to 'compute_project_hash' at session_manager.py:250 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 26 | 🟢 LOW | Large Class | Class 'OutputHandler' spans 307 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
| 206 | 🟢 LOW | Magic Number | Magic number 100 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 315 | 🟢 LOW | Feature Envy | Method 'OutputHandler._safe_create_task' accesses 't' 3 times but 'self' only 0 times | Move Method — consider moving '_safe_create_task' to the class that owns 't'. |

### commands/context.py — ✅ A (93.0/100)

LOC: 535 | Classes: 7 | Functions: 11 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 127 | 🟡 MEDIUM | Duplicate Code | Function '__init__' is 100% similar to '__init__' at json_output.py:69 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 518 | 🟡 MEDIUM | Duplicate Code | Function '_show_help_message' is 94% similar to '_list_themes' at commands/theme.py:203 | Extract Shared Function — identify the common logic and parameterise the differences. |

### repl.py — ✅ A (93.7/100)

LOC: 436 | Classes: 2 | Functions: 3 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 291 | 🟡 MEDIUM | Duplicate Code | Function 'set_session' is 100% similar to 'post' at textual_bridge.py:174 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 143 | 🟢 LOW | Large Class | Class 'Repl' spans 381 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
| 143 | 🟢 LOW | Large Class | Class 'Repl' has 22 methods (threshold: 20) | Split Class — group related methods into smaller collaborating classes. |

### serve.py — ✅ A (93.7/100)

LOC: 84 | Classes: 0 | Functions: 1 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 39 | 🟡 MEDIUM | Primitive Obsession | Function 'serve_command' has 4 primitive-typed parameters: host: Name(id='str', ctx=Load()), port: Name(id='int', ctx=Load()), reload: Name(id='bool', ctx=Load()), workers: Name(id='int', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 21 | 🟢 LOW | Magic Number | Magic number 8000 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 39 | 🟢 LOW | Long Method | Function 'serve_command' has 39 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |

### textual_app.py — ✅ A (94.4/100)

LOC: 307 | Classes: 1 | Functions: 2 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 219 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/6 params untyped | Add Type Annotations for all parameters and return type. |
| 245 | 🟢 LOW | Missing Type Hint | Function 'compose' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 266 | 🟢 LOW | Missing Type Hint | Function 'on_mount' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 281 | 🟢 LOW | Missing Type Hint | Function 'on_unmount' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |

### console.py — ✅ A (95.1/100)

LOC: 713 | Classes: 14 | Functions: 6 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 660 | 🟡 MEDIUM | Duplicate Code | Function '_render_diff' is 94% similar to '_add_message_with_prefix' at textual_widgets.py:919 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 693 | 🟢 LOW | Primitive Obsession | Function 'tool_result' has 3 primitive-typed parameters: content: Name(id='str', ctx=Load()), success: Name(id='bool', ctx=Load()), error: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |

### textual_config.py — ✅ A (95.1/100)

LOC: 224 | Classes: 3 | Functions: 0 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 191 | 🟡 MEDIUM | Duplicate Code | Function '_initialize_output_handler' is 95% similar to '_initialize_tool_executor' at textual_config.py:225 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 173 | 🟢 LOW | Feature Envy | Method 'ComponentInitializer._resolve_theme_name' accesses 'settings' 3 times but 'self' only 1 times | Move Method — consider moving '_resolve_theme_name' to the class that owns 'settings'. |

### commands/__init__.py — ✅ A (96.5/100)

LOC: 161 | Classes: 4 | Functions: 2 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 142 | 🟡 MEDIUM | Duplicate Code | Function 'register' is 100% similar to 'register_theme' at console.py:372 | Extract Shared Function — identify the common logic and parameterise the differences. |

### commands/agent.py — ✅ A (96.5/100)

LOC: 184 | Classes: 1 | Functions: 6 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 218 | 🟡 MEDIUM | Duplicate Code | Function '_list_agents' is 94% similar to 'post_status_message' at textual_bridge.py:201 | Extract Shared Function — identify the common logic and parameterise the differences. |

### commands/builtins.py — ✅ A (96.5/100)

LOC: 268 | Classes: 4 | Functions: 7 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 205 | 🟡 MEDIUM | Duplicate Code | Function '_list_all_commands' is 94% similar to 'on_switch_provider_message' at textual_mixins.py:1394 | Extract Shared Function — identify the common logic and parameterise the differences. |

### commands/chat.py — ✅ A (96.5/100)

LOC: 258 | Classes: 1 | Functions: 6 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 319 | 🟡 MEDIUM | Duplicate Code | Function '_restore_session' is 100% similar to '_sync_session_to_agent' at session_manager.py:131 | Extract Shared Function — identify the common logic and parameterise the differences. |

### commands/unlimited.py — ✅ A (96.5/100)

LOC: 71 | Classes: 1 | Functions: 2 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 76 | 🟡 MEDIUM | Feature Envy | Method 'UnlimitedCommand.execute' accesses 'ctx' 5 times but 'self' only 1 times | Move Method — consider moving 'execute' to the class that owns 'ctx'. |

### console_helpers.py — ✅ A (96.5/100)

LOC: 121 | Classes: 1 | Functions: 3 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 118 | 🟡 MEDIUM | Duplicate Code | Function 'print_usage_help' is 100% similar to 'print_parameter_list' at console_helpers.py:135 | Extract Shared Function — identify the common logic and parameterise the differences. |

### tool_manager.py — ✅ A (96.5/100)

LOC: 137 | Classes: 1 | Functions: 0 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 47 | 🟡 MEDIUM | Long Method | Function '_create_builtin_tools' has 59 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |

### core_init.py — ✅ A (97.2/100)

LOC: 118 | Classes: 1 | Functions: 2 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 58 | 🟢 LOW | Long Method | Function 'create_core_context' has 48 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 58 | 🟢 LOW | Primitive Obsession | Function 'create_core_context' has 3 primitive-typed parameters: system_prompt: Name(id='str', ctx=Load()), environment_context: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), auto_approve_tools: Name(id='bool', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |

### textual_mixins.py — ✅ A (97.2/100)

LOC: 1463 | Classes: 13 | Functions: 3 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 1137 | 🟢 LOW | Feature Envy | Method '_CommandPaletteMixin._fill_input_with_text' accesses 'widget' 3 times but 'self' only 1 times | Move Method — consider moving '_fill_input_with_text' to the class that owns 'widget'. |
| 1723 | 🟢 LOW | Primitive Obsession | Function 'update_status' has 3 primitive-typed parameters: message: Name(id='str', ctx=Load()), tokens: BinOp(left=Name(id='int', ctx=Load()), op=BitOr(), right=Constant(value=None)), cost: BinOp(left=Name(id='float', ctx=Load()), op=BitOr(), right=Constant(value=None)) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |

## ✨ Clean Files (14 files with no smells)

<details><summary>Click to expand</summary>

- __init__.py — ✅ A
- app.py — ✅ A
- commands/model.py — ✅ A
- commands/plan.py — ✅ A
- commands/rag.py — ✅ A
- commands/session.py — ✅ A
- commands/team.py — ✅ A
- input.py — ✅ A
- json_output.py — ✅ A
- prompts.py — ✅ A
- session_manager.py — ✅ A
- stream_event_handlers.py — ✅ A
- textual_bridge.py — ✅ A
- textual_widgets.py — ✅ A

</details>

---

_Report generated by XP Code Smell Detector. Smells are static heuristics — use judgement when prioritising fixes._
