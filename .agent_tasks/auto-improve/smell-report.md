# Code Smell Report — ❌ F (Score: 50.0/100)

_Scanned: /home/matthew/mlg-cli/src/henchman_  

_Generated: 2026-02-26T20:13:27.762937+00:00_

## Executive Summary

| Metric | Value |
|:-------|------:|
| **Overall Grade** | ❌ F |
| **Overall Score** | 50.0/100 |
| **Files Scanned** | 144 |
| **Total Lines (non-blank)** | 27,884 |
| **Total Smells** | 2627 |
| **Avg Maintainability Index** | 100.0 |
| **Avg Cyclomatic Complexity** | 0.0 |

### Smells by Severity

| Severity | Count |
|:---------|------:|
| low | 1751 |
| medium | 612 |
| high | 236 |
| critical | 28 |

### Smells by Category

| Category | Count |
|:---------|------:|
| Missing Type Hint | 1172 |
| Feature Envy | 348 |
| Duplicate Code | 316 |
| Deep Nesting | 274 |
| Magic Number | 218 |
| Long Method | 181 |
| Primitive Obsession | 83 |
| Large Class | 35 |

## 🎯 Prioritised Refactoring Queue

These are the highest-impact smells to address first:

1. **agents/orchestrator.py:1261** — 🔴 CRITICAL — Long Method  
   Function '_run_delegation' has 129 lines (threshold: 30)  
   → _Extract Method — break this function into smaller, intention-revealing helper functions._

2. **agents/presets.py:6** — 🔴 CRITICAL — Long Method  
   Function 'get_default_team' has 121 lines (threshold: 30)  
   → _Extract Method — break this function into smaller, intention-revealing helper functions._

3. **api/endpoints/chat.py:75** — 🔴 CRITICAL — Long Method  
   Function 'chat_completion' has 149 lines (threshold: 30)  
   → _Extract Method — break this function into smaller, intention-revealing helper functions._

4. **api/endpoints/chat.py:191** — 🔴 CRITICAL — Deep Nesting  
   Nesting depth 8 in 'chat_completion' (threshold: 4)  
   → _Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return._

5. **api/endpoints/chat.py:242** — 🔴 CRITICAL — Long Method  
   Function 'chat_completion_stream' has 154 lines (threshold: 30)  
   → _Extract Method — break this function into smaller, intention-revealing helper functions._

6. **api/server.py:71** — 🔴 CRITICAL — Deep Nesting  
   Nesting depth 8 in 'lifespan' (threshold: 4)  
   → _Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return._

7. **api/server.py:73** — 🔴 CRITICAL — Deep Nesting  
   Nesting depth 9 in 'lifespan' (threshold: 4)  
   → _Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return._

8. **api/server.py:75** — 🔴 CRITICAL — Deep Nesting  
   Nesting depth 10 in 'lifespan' (threshold: 4)  
   → _Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return._

9. **cli/app.py:290** — 🔴 CRITICAL — Long Method  
   Function '_run_headless' has 218 lines (threshold: 30)  
   → _Extract Method — break this function into smaller, intention-revealing helper functions._

10. **cli/commands/context.py:253** — 🔴 CRITICAL — Deep Nesting  
   Nesting depth 8 in '_set_strategy_parameter' (threshold: 4)  
   → _Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return._

11. **cli/input.py:335** — 🔴 CRITICAL — Deep Nesting  
   Nesting depth 8 in 'monitor' (threshold: 4)  
   → _Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return._

12. **cli/tool_executor.py:577** — 🔴 CRITICAL — Deep Nesting  
   Nesting depth 8 in 'process_agent_stream' (threshold: 4)  
   → _Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return._

13. **cli/tool_executor.py:580** — 🔴 CRITICAL — Deep Nesting  
   Nesting depth 9 in 'process_agent_stream' (threshold: 4)  
   → _Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return._

14. **cli/tool_executor.py:583** — 🔴 CRITICAL — Deep Nesting  
   Nesting depth 10 in 'process_agent_stream' (threshold: 4)  
   → _Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return._

15. **cli/tool_executor.py:586** — 🔴 CRITICAL — Deep Nesting  
   Nesting depth 11 in 'process_agent_stream' (threshold: 4)  
   → _Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return._


## 📊 Files Ranked by Quality

| Rank | File | Grade | Score | Smells | LOC | MI | Avg CC |
|-----:|:-----|:------|------:|-------:|----:|---:|-------:|
| 1 | agents/orchestrator.py | ❌ F | 30.0 | 128 | 1379 | 100 | 0.0 |
| 2 | api/endpoints/chat.py | ❌ F | 30.0 | 12 | 352 | 100 | 0.0 |
| 3 | cli/app.py | ❌ F | 30.0 | 19 | 463 | 100 | 0.0 |
| 4 | cli/commands/context.py | ❌ F | 30.0 | 39 | 272 | 100 | 0.0 |
| 5 | cli/commands/session.py | ❌ F | 30.0 | 66 | 296 | 100 | 0.0 |
| 6 | cli/console.py | ❌ F | 30.0 | 72 | 462 | 100 | 0.0 |
| 7 | cli/textual_app.py | ❌ F | 30.0 | 121 | 1439 | 100 | 0.0 |
| 8 | cli/textual_bridge.py | ❌ F | 30.0 | 54 | 317 | 100 | 0.0 |
| 9 | cli/textual_messages.py | ❌ F | 30.0 | 27 | 129 | 100 | 0.0 |
| 10 | cli/textual_widgets.py | ❌ F | 30.0 | 87 | 897 | 100 | 0.0 |

## 📁 Per-File Details

_Showing 20 worst files. 124 additional files omitted._

### agents/orchestrator.py — ❌ F (30.0/100)

LOC: 1379 | Classes: 8 | Functions: 1 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 1261 | 🔴 CRITICAL | Long Method | Function '_run_delegation' has 129 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 189 | 🟠 HIGH | Magic Number | Magic number 100.0 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 247 | 🟠 HIGH | Magic Number | Magic number 100.0 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 304 | 🟠 HIGH | Magic Number | Magic number 60.0 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 309 | 🟠 HIGH | Magic Number | Magic number 100.0 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 523 | 🟠 HIGH | Large Class | Class 'Orchestrator' spans 1284 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
| 526 | 🟠 HIGH | Long Method | Function '__init__' has 88 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 646 | 🟠 HIGH | Magic Number | Magic number 500 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 903 | 🟠 HIGH | Magic Number | Magic number 200 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 1036 | 🟠 HIGH | Primitive Obsession | Repeated primitive parameter group appears in: '_run_agent_loop' (line 1036), '_run_delegation' (line 1261) | Replace Data Value with Object — create a shared data structure for this recurring parameter group. |
| 1335 | 🟠 HIGH | Magic Number | Magic number 5 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 1336 | 🟠 HIGH | Magic Number | Magic number 200 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 1394 | 🟠 HIGH | Magic Number | Magic number 10 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 1409 | 🟠 HIGH | Magic Number | Magic number 800 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 1553 | 🟠 HIGH | Magic Number | Magic number 200 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |

_... and 113 more smells._

### api/endpoints/chat.py — ❌ F (30.0/100)

LOC: 352 | Classes: 4 | Functions: 5 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 75 | 🔴 CRITICAL | Long Method | Function 'chat_completion' has 149 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 191 | 🔴 CRITICAL | Deep Nesting | Nesting depth 8 in 'chat_completion' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 242 | 🔴 CRITICAL | Long Method | Function 'chat_completion_stream' has 154 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 186 | 🟠 HIGH | Deep Nesting | Nesting depth 6 in 'chat_completion' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 188 | 🟠 HIGH | Deep Nesting | Nesting depth 7 in 'chat_completion' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 193 | 🟠 HIGH | Deep Nesting | Nesting depth 7 in 'chat_completion' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 358 | 🟠 HIGH | Deep Nesting | Nesting depth 6 in 'event_generator' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 181 | 🟡 MEDIUM | Deep Nesting | Nesting depth 5 in 'chat_completion' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 335 | 🟡 MEDIUM | Long Method | Function 'event_generator' has 65 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 355 | 🟡 MEDIUM | Deep Nesting | Nesting depth 5 in 'event_generator' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 179 | 🟢 LOW | Deep Nesting | Nesting depth 4 in 'chat_completion' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 348 | 🟢 LOW | Deep Nesting | Nesting depth 4 in 'event_generator' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |

### cli/app.py — ❌ F (30.0/100)

LOC: 463 | Classes: 0 | Functions: 12 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 290 | 🔴 CRITICAL | Long Method | Function '_run_headless' has 218 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 145 | 🟠 HIGH | Long Method | Function '_run_interactive' has 85 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 145 | 🟠 HIGH | Primitive Obsession | Repeated primitive parameter group appears in: '_run_interactive' (line 145), '_run_textual_tui' (line 243), '_run_headless' (line 290), 'chat_command' (line 574) | Replace Data Value with Object — create a shared data structure for this recurring parameter group. |
| 574 | 🟠 HIGH | Primitive Obsession | Function 'chat_command' has 8 primitive-typed parameters: prompt: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), agent: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), team: Name(id='bool', ctx=Load()), output_format: Name(id='str', ctx=Load()), plan: Name(id='bool', ctx=Load()), yes: Name(id='bool', ctx=Load()), tui: Name(id='bool', ctx=Load()), debug: Name(id='bool', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 145 | 🟡 MEDIUM | Primitive Obsession | Function '_run_interactive' has 4 primitive-typed parameters: output_format: Name(id='str', ctx=Load()), plan_mode: Name(id='bool', ctx=Load()), yes: Name(id='bool', ctx=Load()), agent_role: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 243 | 🟡 MEDIUM | Primitive Obsession | Function '_run_textual_tui' has 4 primitive-typed parameters: output_format: Name(id='str', ctx=Load()), plan_mode: Name(id='bool', ctx=Load()), yes: Name(id='bool', ctx=Load()), agent_role: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 290 | 🟡 MEDIUM | Primitive Obsession | Function '_run_headless' has 5 primitive-typed parameters: prompt: Name(id='str', ctx=Load()), output_format: Name(id='str', ctx=Load()), plan_mode: Name(id='bool', ctx=Load()), yes: Name(id='bool', ctx=Load()), agent_role: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 386 | 🟡 MEDIUM | Duplicate Code | Function 'run_single_prompt_json' is 100% similar to 'run_single_prompt_stream_json' at cli/app.py:427 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 402 | 🟡 MEDIUM | Duplicate Code | Function 'run_and_render' is 100% similar to 'run_and_render_stream' at cli/app.py:441 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 402 | 🟡 MEDIUM | Duplicate Code | Function 'run_and_render' is 100% similar to 'run_and_collect' at cli/app.py:480 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 441 | 🟡 MEDIUM | Duplicate Code | Function 'run_and_render_stream' is 100% similar to 'run_and_collect' at cli/app.py:480 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 139 | 🟢 LOW | Magic Number | Magic number 5 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 139 | 🟢 LOW | Magic Number | Magic number 5 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 243 | 🟢 LOW | Long Method | Function '_run_textual_tui' has 34 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 386 | 🟢 LOW | Long Method | Function 'run_single_prompt_json' has 38 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |

_... and 4 more smells._

### cli/commands/context.py — ❌ F (30.0/100)

LOC: 272 | Classes: 1 | Functions: 0 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 253 | 🔴 CRITICAL | Deep Nesting | Nesting depth 8 in '_set_strategy_parameter' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 71 | 🟠 HIGH | Feature Envy | Method 'ContextCommand._show_status' accesses 'ctx' 13 times but 'self' only 0 times | Move Method — consider moving '_show_status' to the class that owns 'ctx'. |
| 195 | 🟠 HIGH | Feature Envy | Method 'ContextCommand._set_strategy_parameter' accesses 'ctx' 11 times but 'self' only 0 times | Move Method — consider moving '_set_strategy_parameter' to the class that owns 'ctx'. |
| 242 | 🟠 HIGH | Deep Nesting | Nesting depth 6 in '_set_strategy_parameter' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 248 | 🟠 HIGH | Deep Nesting | Nesting depth 6 in '_set_strategy_parameter' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 249 | 🟠 HIGH | Deep Nesting | Nesting depth 7 in '_set_strategy_parameter' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 268 | 🟠 HIGH | Feature Envy | Method 'ContextCommand._show_stats' accesses 'ctx' 21 times but 'self' only 0 times | Move Method — consider moving '_show_stats' to the class that owns 'ctx'. |
| 45 | 🟡 MEDIUM | Feature Envy | Method 'ContextCommand.execute' accesses 'ctx' 8 times but 'self' only 6 times | Move Method — consider moving 'execute' to the class that owns 'ctx'. |
| 60 | 🟡 MEDIUM | Deep Nesting | Nesting depth 5 in 'execute' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 71 | 🟡 MEDIUM | Feature Envy | Method 'ContextCommand._show_status' accesses 'context_settings' 8 times but 'self' only 0 times | Move Method — consider moving '_show_status' to the class that owns 'context_settings'. |
| 138 | 🟡 MEDIUM | Feature Envy | Method 'ContextCommand._manage_strategy' accesses 'ctx' 8 times but 'self' only 2 times | Move Method — consider moving '_manage_strategy' to the class that owns 'ctx'. |
| 165 | 🟡 MEDIUM | Feature Envy | Method 'ContextCommand._show_strategy_status' accesses 'ctx' 9 times but 'self' only 0 times | Move Method — consider moving '_show_strategy_status' to the class that owns 'ctx'. |
| 165 | 🟡 MEDIUM | Feature Envy | Method 'ContextCommand._show_strategy_status' accesses 'context_settings' 6 times but 'self' only 0 times | Move Method — consider moving '_show_strategy_status' to the class that owns 'context_settings'. |
| 195 | 🟡 MEDIUM | Long Method | Function '_set_strategy_parameter' has 59 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 195 | 🟡 MEDIUM | Feature Envy | Method 'ContextCommand._set_strategy_parameter' accesses 'context_settings' 6 times but 'self' only 0 times | Move Method — consider moving '_set_strategy_parameter' to the class that owns 'context_settings'. |

_... and 24 more smells._

### cli/commands/session.py — ❌ F (30.0/100)

LOC: 296 | Classes: 1 | Functions: 0 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 70 | 🟠 HIGH | Deep Nesting | Nesting depth 6 in 'execute' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 75 | 🟠 HIGH | Feature Envy | Method 'SessionCommand._show_help' accesses 'ctx' 14 times but 'self' only 0 times | Move Method — consider moving '_show_help' to the class that owns 'ctx'. |
| 92 | 🟠 HIGH | Feature Envy | Method 'SessionCommand._branch' accesses 'ctx' 12 times but 'self' only 0 times | Move Method — consider moving '_branch' to the class that owns 'ctx'. |
| 99 | 🟠 HIGH | Magic Number | Magic number 3 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 110 | 🟠 HIGH | Magic Number | Magic number 3 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 110 | 🟠 HIGH | Magic Number | Magic number 3 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 122 | 🟠 HIGH | Feature Envy | Method 'SessionCommand._merge' accesses 'ctx' 16 times but 'self' only 0 times | Move Method — consider moving '_merge' to the class that owns 'ctx'. |
| 129 | 🟠 HIGH | Magic Number | Magic number 3 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 138 | 🟠 HIGH | Magic Number | Magic number 3 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 139 | 🟠 HIGH | Magic Number | Magic number 3 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 140 | 🟠 HIGH | Magic Number | Magic number 3 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 141 | 🟠 HIGH | Magic Number | Magic number 4 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 142 | 🟠 HIGH | Magic Number | Magic number 4 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 144 | 🟠 HIGH | Magic Number | Magic number 3 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 180 | 🟠 HIGH | Feature Envy | Method 'SessionCommand._template_save' accesses 'ctx' 10 times but 'self' only 0 times | Move Method — consider moving '_template_save' to the class that owns 'ctx'. |

_... and 51 more smells._

### cli/console.py — ❌ F (30.0/100)

LOC: 462 | Classes: 4 | Functions: 2 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 476 | 🟠 HIGH | Primitive Obsession | Repeated primitive parameter group appears in: 'diff' (line 476), 'diff' (line 590) | Replace Data Value with Object — create a shared data structure for this recurring parameter group. |
| 512 | 🟠 HIGH | Duplicate Code | Function 'agent_content' is an exact duplicate of 'print_agent_content' at cli/ui_renderer.py:257 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 169 | 🟡 MEDIUM | Duplicate Code | Function 'get_theme' is 94% similar to 'start_task' at cli/output_handler.py:252 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 169 | 🟡 MEDIUM | Duplicate Code | Function 'get_theme' is 94% similar to 'load' at cli/session_manager.py:126 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 169 | 🟡 MEDIUM | Duplicate Code | Function 'get_theme' is 94% similar to 'compute_project_hash' at cli/session_manager.py:199 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 169 | 🟡 MEDIUM | Duplicate Code | Function 'get_theme' is 94% similar to 'start_task' at cli/ui_renderer.py:350 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 169 | 🟡 MEDIUM | Duplicate Code | Function 'get_theme' is 94% similar to 'count_tokens' at rag/chunker.py:86 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 188 | 🟡 MEDIUM | Duplicate Code | Function 'list_themes' is 100% similar to 'list_extensions' at extensions/manager.py:78 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 188 | 🟡 MEDIUM | Duplicate Code | Function 'list_themes' is 100% similar to 'get_server_names' at mcp/manager.py:38 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 188 | 🟡 MEDIUM | Duplicate Code | Function 'list_themes' is 100% similar to 'list_providers' at providers/registry.py:46 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 188 | 🟡 MEDIUM | Duplicate Code | Function 'list_themes' is 100% similar to 'list_tools' at tools/registry.py:121 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 271 | 🟡 MEDIUM | Duplicate Code | Function 'success' is 100% similar to 'info' at cli/console.py:280 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 271 | 🟡 MEDIUM | Duplicate Code | Function 'success' is 100% similar to 'warning' at cli/console.py:289 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 271 | 🟡 MEDIUM | Duplicate Code | Function 'success' is 100% similar to 'error' at cli/console.py:298 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 280 | 🟡 MEDIUM | Duplicate Code | Function 'info' is 100% similar to 'warning' at cli/console.py:289 | Extract Shared Function — identify the common logic and parameterise the differences. |

_... and 57 more smells._

### cli/textual_app.py — ❌ F (30.0/100)

LOC: 1439 | Classes: 1 | Functions: 2 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 158 | 🟠 HIGH | Large Class | Class 'HenchmanTextualApp' spans 1507 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
| 158 | 🟠 HIGH | Large Class | Class 'HenchmanTextualApp' has 86 methods (threshold: 20) | Split Class — group related methods into smaller collaborating classes. |
| 253 | 🟠 HIGH | Long Method | Function '_resolve_provider_from_env' has 115 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 1519 | 🟠 HIGH | Duplicate Code | Function 'action_toggle_thinking_pane' is an exact duplicate of 'action_toggle_tool_pane' at cli/textual_app.py:1529 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 407 | 🟡 MEDIUM | Duplicate Code | Function 'orchestrator' is 100% similar to 'tool_registry' at cli/textual_app.py:422 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 407 | 🟡 MEDIUM | Duplicate Code | Function 'orchestrator' is 100% similar to 'session_manager' at cli/textual_app.py:437 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 407 | 🟡 MEDIUM | Duplicate Code | Function 'orchestrator' is 100% similar to 'agent' at cli/textual_app.py:452 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 422 | 🟡 MEDIUM | Duplicate Code | Function 'tool_registry' is 100% similar to 'session_manager' at cli/textual_app.py:437 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 422 | 🟡 MEDIUM | Duplicate Code | Function 'tool_registry' is 100% similar to 'agent' at cli/textual_app.py:452 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 437 | 🟡 MEDIUM | Duplicate Code | Function 'session_manager' is 100% similar to 'agent' at cli/textual_app.py:452 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 1003 | 🟡 MEDIUM | Feature Envy | Method 'HenchmanTextualApp.on_tool_call_request_message' accesses 'tc' 6 times but 'self' only 3 times | Move Method — consider moving 'on_tool_call_request_message' to the class that owns 'tc'. |
| 1226 | 🟡 MEDIUM | Feature Envy | Method 'HenchmanTextualApp._show_command_palette' accesses 'palette' 5 times but 'self' only 3 times | Move Method — consider moving '_show_command_palette' to the class that owns 'palette'. |
| 1572 | 🟡 MEDIUM | Feature Envy | Method 'HenchmanTextualApp.on_tree_node_selected' accesses 'path' 5 times but 'self' only 1 times | Move Method — consider moving 'on_tree_node_selected' to the class that owns 'path'. |
| 204 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/6 params untyped | Add Type Annotations for all parameters and return type. |
| 229 | 🟢 LOW | Missing Type Hint | Function '_init_provider_and_settings' has incomplete type hints: 1/5 params untyped | Add Type Annotations for all parameters and return type. |

_... and 106 more smells._

### cli/textual_bridge.py — ❌ F (30.0/100)

LOC: 317 | Classes: 2 | Functions: 2 | MI: 100 | Avg CC: 0.0

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

### cli/textual_widgets.py — ❌ F (30.0/100)

LOC: 897 | Classes: 13 | Functions: 3 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 316 | 🟠 HIGH | Duplicate Code | Function '__init__' is an exact duplicate of '__init__' at cli/textual_widgets.py:336 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 316 | 🟠 HIGH | Duplicate Code | Function '__init__' is an exact duplicate of '__init__' at cli/textual_widgets.py:514 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 316 | 🟠 HIGH | Duplicate Code | Function '__init__' is an exact duplicate of '__init__' at cli/textual_widgets.py:534 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 336 | 🟠 HIGH | Duplicate Code | Function '__init__' is an exact duplicate of '__init__' at cli/textual_widgets.py:514 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 336 | 🟠 HIGH | Duplicate Code | Function '__init__' is an exact duplicate of '__init__' at cli/textual_widgets.py:534 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 397 | 🟠 HIGH | Duplicate Code | Function 'content' is an exact duplicate of 'content' at cli/textual_widgets.py:606 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 457 | 🟠 HIGH | Duplicate Code | Function 'toggle_expansion' is an exact duplicate of 'toggle_expansion' at cli/textual_widgets.py:728 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 473 | 🟠 HIGH | Duplicate Code | Function 'set_highlight' is an exact duplicate of 'set_highlight' at cli/textual_widgets.py:744 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 514 | 🟠 HIGH | Duplicate Code | Function '__init__' is an exact duplicate of '__init__' at cli/textual_widgets.py:534 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 831 | 🟠 HIGH | Duplicate Code | Function 'add_user_message' is an exact duplicate of 'add_system_message' at cli/textual_widgets.py:841 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 831 | 🟠 HIGH | Duplicate Code | Function 'add_user_message' is an exact duplicate of 'add_error_message' at cli/textual_widgets.py:851 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 841 | 🟠 HIGH | Duplicate Code | Function 'add_system_message' is an exact duplicate of 'add_error_message' at cli/textual_widgets.py:851 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 1002 | 🟠 HIGH | Duplicate Code | Function '__init__' is an exact duplicate of '__init__' at cli/textual_widgets.py:1020 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 147 | 🟡 MEDIUM | Feature Envy | Method 'HenchmanTextArea.on_key' accesses 'event' 6 times but 'self' only 2 times | Move Method — consider moving 'on_key' to the class that owns 'event'. |
| 283 | 🟡 MEDIUM | Duplicate Code | Function 'append' is 100% similar to 'append' at cli/textual_widgets.py:753 | Extract Shared Function — identify the common logic and parameterise the differences. |

_... and 72 more smells._

### cli/tool_executor.py — ❌ F (30.0/100)

LOC: 545 | Classes: 1 | Functions: 0 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 577 | 🔴 CRITICAL | Deep Nesting | Nesting depth 8 in 'process_agent_stream' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 580 | 🔴 CRITICAL | Deep Nesting | Nesting depth 9 in 'process_agent_stream' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 583 | 🔴 CRITICAL | Deep Nesting | Nesting depth 10 in 'process_agent_stream' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 586 | 🔴 CRITICAL | Deep Nesting | Nesting depth 11 in 'process_agent_stream' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 589 | 🔴 CRITICAL | Deep Nesting | Nesting depth 12 in 'process_agent_stream' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 251 | 🟠 HIGH | Feature Envy | Method 'ToolExecutor._execute_and_record_tool_call' accesses 'tc' 10 times but 'self' only 5 times | Move Method — consider moving '_execute_and_record_tool_call' to the class that owns 'tc'. |
| 486 | 🟠 HIGH | Long Method | Function 'process_agent_stream' has 97 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 486 | 🟠 HIGH | Feature Envy | Method 'ToolExecutor.process_agent_stream' accesses 'event' 16 times but 'self' only 14 times | Move Method — consider moving 'process_agent_stream' to the class that owns 'event'. |
| 563 | 🟠 HIGH | Deep Nesting | Nesting depth 6 in 'process_agent_stream' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 574 | 🟠 HIGH | Deep Nesting | Nesting depth 7 in 'process_agent_stream' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 666 | 🟠 HIGH | Feature Envy | Method 'ToolExecutor.handle_confirmation' accesses 'request' 13 times but 'self' only 1 times | Move Method — consider moving 'handle_confirmation' to the class that owns 'request'. |
| 36 | 🟡 MEDIUM | Large Class | Class 'ToolExecutor' spans 675 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
| 114 | 🟡 MEDIUM | Feature Envy | Method 'ToolExecutor._handle_content_event' accesses 'event' 5 times but 'self' only 1 times | Move Method — consider moving '_handle_content_event' to the class that owns 'event'. |
| 331 | 🟡 MEDIUM | Duplicate Code | Function '_handle_agent_delegated_event' is 100% similar to '_handle_agent_message_event' at cli/tool_executor.py:382 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 560 | 🟡 MEDIUM | Deep Nesting | Nesting depth 5 in 'process_agent_stream' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |

_... and 37 more smells._

### cli/ui_renderer.py — ❌ F (30.0/100)

LOC: 296 | Classes: 2 | Functions: 0 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 45 | 🟠 HIGH | Primitive Obsession | Repeated primitive parameter group appears in: 'start_task' (line 45), 'start_task' (line 350) | Replace Data Value with Object — create a shared data structure for this recurring parameter group. |
| 69 | 🟠 HIGH | Primitive Obsession | Repeated primitive parameter group appears in: 'update_task' (line 69), 'update_task' (line 363) | Replace Data Value with Object — create a shared data structure for this recurring parameter group. |
| 96 | 🟡 MEDIUM | Large Class | Class 'UIRenderer' has 31 methods (threshold: 20) | Split Class — group related methods into smaller collaborating classes. |
| 310 | 🟡 MEDIUM | Duplicate Code | Function 'tool_result' is 100% similar to 'tool_summary' at cli/ui_renderer.py:314 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 310 | 🟡 MEDIUM | Duplicate Code | Function 'tool_result' is 100% similar to 'update_task' at cli/ui_renderer.py:363 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 314 | 🟡 MEDIUM | Duplicate Code | Function 'tool_summary' is 100% similar to 'update_task' at cli/ui_renderer.py:363 | Extract Shared Function — identify the common logic and parameterise the differences. |
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

### core/agent.py — ❌ F (30.0/100)

LOC: 500 | Classes: 1 | Functions: 0 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 360 | 🔴 CRITICAL | Long Method | Function '_process_streaming_response' has 160 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 397 | 🔴 CRITICAL | Long Method | Function 'event_generator' has 135 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 64 | 🟠 HIGH | Primitive Obsession | Function '__init__' has 10 primitive-typed parameters: system_prompt: Name(id='str', ctx=Load()), max_tokens: Name(id='int', ctx=Load()), model: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), summarize_dropped: Name(id='bool', ctx=Load()), base_tool_iterations: Name(id='int', ctx=Load()), max_protected_ratio: Name(id='float', ctx=Load()), intelligent_context: Name(id='bool', ctx=Load()), importance_threshold: Name(id='float', ctx=Load()), cluster_similarity_threshold: Name(id='float', ctx=Load()), adaptive_compression: Name(id='bool', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 360 | 🟠 HIGH | Feature Envy | Method 'Agent._process_streaming_response' accesses 'chunk' 19 times but 'self' only 18 times | Move Method — consider moving '_process_streaming_response' to the class that owns 'chunk'. |
| 493 | 🟠 HIGH | Deep Nesting | Nesting depth 6 in 'event_generator' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 504 | 🟠 HIGH | Deep Nesting | Nesting depth 6 in 'event_generator' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 28 | 🟡 MEDIUM | Large Class | Class 'Agent' spans 628 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
| 472 | 🟡 MEDIUM | Deep Nesting | Nesting depth 5 in 'event_generator' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 479 | 🟡 MEDIUM | Deep Nesting | Nesting depth 5 in 'event_generator' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 537 | 🟡 MEDIUM | Long Method | Function 'run' has 69 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 64 | 🟢 LOW | Long Method | Function '__init__' has 38 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 64 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/14 params untyped | Add Type Annotations for all parameters and return type. |
| 137 | 🟢 LOW | Missing Type Hint | Function 'history' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 142 | 🟢 LOW | Missing Type Hint | Function 'tools' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 146 | 🟢 LOW | Missing Type Hint | Function '_emit' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |

_... and 19 more smells._

### core/session.py — ❌ F (30.0/100)

LOC: 725 | Classes: 5 | Functions: 0 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 241 | 🟠 HIGH | Feature Envy | Method 'Session.from_dict' accesses 'data' 11 times but 'self' only 0 times | Move Method — consider moving 'from_dict' to the class that owns 'data'. |
| 503 | 🟠 HIGH | Feature Envy | Method 'SessionManager.branch_session' accesses 'parent' 12 times but 'self' only 3 times | Move Method — consider moving 'branch_session' to the class that owns 'parent'. |
| 545 | 🟠 HIGH | Long Method | Function 'merge_sessions' has 97 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 632 | 🟠 HIGH | Deep Nesting | Nesting depth 6 in 'merge_sessions' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 662 | 🟠 HIGH | Feature Envy | Method 'SessionManager.export_session' accesses 'session' 17 times but 'self' only 1 times | Move Method — consider moving 'export_session' to the class that owns 'session'. |
| 662 | 🟠 HIGH | Feature Envy | Method 'SessionManager.export_session' accesses 'lines' 31 times but 'self' only 1 times | Move Method — consider moving 'export_session' to the class that owns 'lines'. |
| 56 | 🟡 MEDIUM | Feature Envy | Method 'SessionMessage.from_dict' accesses 'data' 5 times but 'self' only 0 times | Move Method — consider moving 'from_dict' to the class that owns 'data'. |
| 95 | 🟡 MEDIUM | Duplicate Code | Function 'to_dict' is 100% similar to 'to_dict' at core/session.py:158 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 95 | 🟡 MEDIUM | Duplicate Code | Function 'to_dict' is 100% similar to 'to_dict' at mcp/config.py:28 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 95 | 🟡 MEDIUM | Duplicate Code | Function 'to_dict' is 100% similar to 'to_metadata' at rag/chunker.py:42 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 158 | 🟡 MEDIUM | Duplicate Code | Function 'to_dict' is 100% similar to 'to_dict' at mcp/config.py:28 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 158 | 🟡 MEDIUM | Duplicate Code | Function 'to_dict' is 100% similar to 'to_metadata' at rag/chunker.py:42 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 306 | 🟡 MEDIUM | Large Class | Class 'SessionManager' spans 621 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
| 545 | 🟡 MEDIUM | Feature Envy | Method 'SessionManager.merge_sessions' accesses 'session' 7 times but 'self' only 3 times | Move Method — consider moving 'merge_sessions' to the class that owns 'session'. |
| 545 | 🟡 MEDIUM | Feature Envy | Method 'SessionManager.merge_sessions' accesses 'merged' 8 times but 'self' only 3 times | Move Method — consider moving 'merge_sessions' to the class that owns 'merged'. |

_... and 59 more smells._

### core/turn.py — ❌ F (30.0/100)

LOC: 187 | Classes: 2 | Functions: 1 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 19 | 🟠 HIGH | Magic Number | Magic number 8 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 76 | 🟠 HIGH | Magic Number | Magic number 5 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 87 | 🟠 HIGH | Magic Number | Magic number 10 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 113 | 🟠 HIGH | Magic Number | Magic number 3 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 114 | 🟠 HIGH | Magic Number | Magic number 5 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 115 | 🟠 HIGH | Magic Number | Magic number 3 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 127 | 🟠 HIGH | Magic Number | Magic number 3 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 131 | 🟠 HIGH | Magic Number | Magic number 6 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 132 | 🟠 HIGH | Magic Number | Magic number 6 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 134 | 🟠 HIGH | Magic Number | Magic number 4 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 138 | 🟠 HIGH | Magic Number | Magic number 7 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 138 | 🟠 HIGH | Magic Number | Magic number 15 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 152 | 🟠 HIGH | Magic Number | Magic number 10 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 208 | 🟠 HIGH | Magic Number | Magic number 100 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 213 | 🟠 HIGH | Magic Number | Magic number 1000 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |

_... and 11 more smells._

### extensions/plugin_manager.py — ❌ F (30.0/100)

LOC: 656 | Classes: 1 | Functions: 0 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 790 | 🔴 CRITICAL | Deep Nesting | Nesting depth 8 in '_install_from_url' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 36 | 🟠 HIGH | Large Class | Class 'PluginManager' spans 870 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
| 784 | 🟠 HIGH | Deep Nesting | Nesting depth 6 in '_install_from_url' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 786 | 🟠 HIGH | Deep Nesting | Nesting depth 6 in '_install_from_url' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 787 | 🟠 HIGH | Deep Nesting | Nesting depth 7 in '_install_from_url' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 789 | 🟠 HIGH | Deep Nesting | Nesting depth 7 in '_install_from_url' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 92 | 🟡 MEDIUM | Magic Number | Magic number 30 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 106 | 🟡 MEDIUM | Primitive Obsession | Function 'search_plugins' has 4 primitive-typed parameters: query: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), page: Name(id='int', ctx=Load()), page_size: Name(id='int', ctx=Load()), category: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 151 | 🟡 MEDIUM | Magic Number | Magic number 20 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 188 | 🟡 MEDIUM | Magic Number | Magic number 404 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 449 | 🟡 MEDIUM | Magic Number | Magic number 3 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 450 | 🟡 MEDIUM | Magic Number | Magic number 4 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 451 | 🟡 MEDIUM | Magic Number | Magic number 5 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 452 | 🟡 MEDIUM | Magic Number | Magic number 6 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 452 | 🟡 MEDIUM | Magic Number | Magic number 6 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |

_... and 71 more smells._

### metrics/collector.py — ❌ F (30.0/100)

LOC: 341 | Classes: 1 | Functions: 0 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 145 | 🟠 HIGH | Primitive Obsession | Function 'record_token_usage' has 7 primitive-typed parameters: model: Name(id='str', ctx=Load()), provider: Name(id='str', ctx=Load()), prompt_tokens: Name(id='int', ctx=Load()), completion_tokens: Name(id='int', ctx=Load()), cached_tokens: Subscript(value=Name(id='Optional', ctx=Load()), slice=Name(id='int', ctx=Load()), ctx=Load()), token_limit: Subscript(value=Name(id='Optional', ctx=Load()), slice=Name(id='int', ctx=Load()), ctx=Load()), agent_id: Subscript(value=Name(id='Optional', ctx=Load()), slice=Name(id='str', ctx=Load()), ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 198 | 🟠 HIGH | Primitive Obsession | Function 'record_cost' has 8 primitive-typed parameters: model: Name(id='str', ctx=Load()), provider: Name(id='str', ctx=Load()), prompt_cost: Name(id='float', ctx=Load()), completion_cost: Name(id='float', ctx=Load()), currency: Name(id='str', ctx=Load()), cost_per_token: Subscript(value=Name(id='Optional', ctx=Load()), slice=Name(id='float', ctx=Load()), ctx=Load()), estimated_cost: Subscript(value=Name(id='Optional', ctx=Load()), slice=Name(id='float', ctx=Load()), ctx=Load()), agent_id: Subscript(value=Name(id='Optional', ctx=Load()), slice=Name(id='str', ctx=Load()), ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 317 | 🟠 HIGH | Primitive Obsession | Function 'record_performance_event' has 6 primitive-typed parameters: event_type: Name(id='str', ctx=Load()), latency_ms: Name(id='float', ctx=Load()), memory_usage_mb: Subscript(value=Name(id='Optional', ctx=Load()), slice=Name(id='float', ctx=Load()), ctx=Load()), cpu_usage_percent: Subscript(value=Name(id='Optional', ctx=Load()), slice=Name(id='float', ctx=Load()), ctx=Load()), concurrent_operations: Name(id='int', ctx=Load()), queue_depth: Subscript(value=Name(id='Optional', ctx=Load()), slice=Name(id='int', ctx=Load()), ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 373 | 🟠 HIGH | Feature Envy | Method 'MetricsCollector.process_agent_event' accesses 'event' 12 times but 'self' only 9 times | Move Method — consider moving 'process_agent_event' to the class that owns 'event'. |
| 39 | 🟡 MEDIUM | Primitive Obsession | Function '__init__' has 5 primitive-typed parameters: enabled: Name(id='bool', ctx=Load()), anonymize: Name(id='bool', ctx=Load()), sampling_rate: Name(id='float', ctx=Load()), session_id: Subscript(value=Name(id='Optional', ctx=Load()), slice=Name(id='str', ctx=Load()), ctx=Load()), user_id: Subscript(value=Name(id='Optional', ctx=Load()), slice=Name(id='str', ctx=Load()), ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 253 | 🟡 MEDIUM | Primitive Obsession | Function 'track_tool_execution' has 4 primitive-typed parameters: tool_name: Name(id='str', ctx=Load()), tool_category: Name(id='str', ctx=Load()), input_size: Subscript(value=Name(id='Optional', ctx=Load()), slice=Name(id='int', ctx=Load()), ctx=Load()), agent_id: Subscript(value=Name(id='Optional', ctx=Load()), slice=Name(id='str', ctx=Load()), ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 391 | 🟡 MEDIUM | Deep Nesting | Nesting depth 5 in 'process_agent_event' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 396 | 🟡 MEDIUM | Deep Nesting | Nesting depth 5 in 'process_agent_event' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 405 | 🟡 MEDIUM | Deep Nesting | Nesting depth 5 in 'process_agent_event' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 27 | 🟢 LOW | Large Class | Class 'MetricsCollector' spans 380 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
| 39 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/7 params untyped | Add Type Annotations for all parameters and return type. |
| 75 | 🟢 LOW | Missing Type Hint | Function '_generate_session_id' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 80 | 🟢 LOW | Missing Type Hint | Function '_hash_user_id' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 82 | 🟢 LOW | Magic Number | Magic number 16 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 84 | 🟢 LOW | Missing Type Hint | Function 'should_sample' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |

_... and 17 more smells._

### metrics/dashboard.py — ❌ F (30.0/100)

LOC: 265 | Classes: 1 | Functions: 0 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 74 | 🟡 MEDIUM | Long Method | Function 'get_summary_stats' has 77 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 74 | 🟡 MEDIUM | Feature Envy | Method 'Dashboard.get_summary_stats' accesses 'stat' 6 times but 'self' only 4 times | Move Method — consider moving 'get_summary_stats' to the class that owns 'stat'. |
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
| 35 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/4 params untyped | Add Type Annotations for all parameters and return type. |

_... and 24 more smells._

### providers/anthropic.py — ❌ F (30.0/100)

LOC: 268 | Classes: 1 | Functions: 0 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 171 | 🔴 CRITICAL | Long Method | Function 'chat_completion_stream' has 153 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 265 | 🔴 CRITICAL | Deep Nesting | Nesting depth 8 in 'chat_completion_stream' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 270 | 🔴 CRITICAL | Deep Nesting | Nesting depth 9 in 'chat_completion_stream' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 283 | 🔴 CRITICAL | Deep Nesting | Nesting depth 8 in 'chat_completion_stream' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 287 | 🔴 CRITICAL | Deep Nesting | Nesting depth 9 in 'chat_completion_stream' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 289 | 🔴 CRITICAL | Deep Nesting | Nesting depth 10 in 'chat_completion_stream' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 290 | 🔴 CRITICAL | Deep Nesting | Nesting depth 11 in 'chat_completion_stream' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 296 | 🔴 CRITICAL | Deep Nesting | Nesting depth 12 in 'chat_completion_stream' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 98 | 🟠 HIGH | Feature Envy | Method 'AnthropicProvider._format_messages' accesses 'msg' 13 times but 'self' only 0 times | Move Method — consider moving '_format_messages' to the class that owns 'msg'. |
| 250 | 🟠 HIGH | Deep Nesting | Nesting depth 6 in 'chat_completion_stream' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 258 | 🟠 HIGH | Deep Nesting | Nesting depth 6 in 'chat_completion_stream' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 260 | 🟠 HIGH | Deep Nesting | Nesting depth 7 in 'chat_completion_stream' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 280 | 🟠 HIGH | Deep Nesting | Nesting depth 7 in 'chat_completion_stream' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 52 | 🟡 MEDIUM | Primitive Obsession | Function '__init__' has 5 primitive-typed parameters: api_key: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), model: Name(id='str', ctx=Load()), max_tokens: Name(id='int', ctx=Load()), tokens_per_minute: Name(id='int', ctx=Load()), max_retries: Name(id='int', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 159 | 🟡 MEDIUM | Feature Envy | Method 'AnthropicProvider._parse_finish_reason' accesses 'FinishReason' 5 times but 'self' only 0 times | Move Method — consider moving '_parse_finish_reason' to the class that owns 'FinishReason'. |

_... and 16 more smells._

### providers/openai_compat.py — ❌ F (30.0/100)

LOC: 215 | Classes: 1 | Functions: 0 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 127 | 🔴 CRITICAL | Long Method | Function 'chat_completion_stream' has 138 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 231 | 🟠 HIGH | Deep Nesting | Nesting depth 6 in 'chat_completion_stream' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 233 | 🟠 HIGH | Deep Nesting | Nesting depth 6 in 'chat_completion_stream' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 245 | 🟠 HIGH | Deep Nesting | Nesting depth 6 in 'chat_completion_stream' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 66 | 🟡 MEDIUM | Feature Envy | Method 'OpenAICompatibleProvider._format_message' accesses 'message' 8 times but 'self' only 0 times | Move Method — consider moving '_format_message' to the class that owns 'message'. |
| 94 | 🟡 MEDIUM | Feature Envy | Method 'OpenAICompatibleProvider._parse_finish_reason' accesses 'FinishReason' 5 times but 'self' only 0 times | Move Method — consider moving '_parse_finish_reason' to the class that owns 'FinishReason'. |
| 127 | 🟡 MEDIUM | Feature Envy | Method 'OpenAICompatibleProvider.chat_completion_stream' accesses 'chunk' 6 times but 'self' only 5 times | Move Method — consider moving 'chat_completion_stream' to the class that owns 'chunk'. |
| 127 | 🟡 MEDIUM | Feature Envy | Method 'OpenAICompatibleProvider.chat_completion_stream' accesses 'tc_delta' 9 times but 'self' only 5 times | Move Method — consider moving 'chat_completion_stream' to the class that owns 'tc_delta'. |
| 221 | 🟡 MEDIUM | Deep Nesting | Nesting depth 5 in 'chat_completion_stream' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 228 | 🟡 MEDIUM | Deep Nesting | Nesting depth 5 in 'chat_completion_stream' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 230 | 🟡 MEDIUM | Deep Nesting | Nesting depth 5 in 'chat_completion_stream' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 243 | 🟡 MEDIUM | Deep Nesting | Nesting depth 5 in 'chat_completion_stream' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 32 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/4 params untyped | Add Type Annotations for all parameters and return type. |
| 32 | 🟢 LOW | Primitive Obsession | Function '__init__' has 3 primitive-typed parameters: api_key: Name(id='str', ctx=Load()), base_url: Name(id='str', ctx=Load()), default_model: Name(id='str', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 51 | 🟢 LOW | Missing Type Hint | Function 'name' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |

_... and 12 more smells._

## ✨ Clean Files (25 files with no smells)

<details><summary>Click to expand</summary>

- __main__.py — ✅ A
- agents/__init__.py — ✅ A
- agents/config.py — ✅ A
- api/__init__.py — ✅ A
- api/auth.py — ✅ A
- api/endpoints/__init__.py — ✅ A
- cli/__init__.py — ✅ A
- cli/prompts.py — ✅ A
- config/__init__.py — ✅ A
- config/settings.py — ✅ A
- core/__init__.py — ✅ A
- core/events.py — ✅ A
- extensions/__init__.py — ✅ A
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
- utils/__init__.py — ✅ A
- version.py — ✅ A

</details>

---

_Report generated by XP Code Smell Detector. Smells are static heuristics — use judgement when prioritising fixes._
