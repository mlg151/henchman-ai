# Code Smell Report — ❌ F (Score: 49.3/100)

_Scanned: /home/matthew/mlg-cli/src/henchman_  

_Generated: 2026-03-01T01:30:19.607365+00:00_

## Executive Summary

| Metric | Value |
|:-------|------:|
| **Overall Grade** | ❌ F |
| **Overall Score** | 49.3/100 |
| **Files Scanned** | 180 |
| **Total Lines (non-blank)** | 31,469 |
| **Total Smells** | 2377 |
| **Avg Maintainability Index** | 71.3 |
| **Avg Cyclomatic Complexity** | 13.6 |

### Smells by Severity

| Severity | Count |
|:---------|------:|
| low | 1703 |
| medium | 588 |
| high | 86 |

### Smells by Category

| Category | Count |
|:---------|------:|
| Missing Type Hint | 1165 |
| Feature Envy | 322 |
| Duplicate Code | 294 |
| Magic Number | 149 |
| Long Method | 146 |
| Deep Nesting | 140 |
| Primitive Obsession | 80 |
| Complex Function | 47 |
| Large Class | 34 |

## 🎯 Prioritised Refactoring Queue

These are the highest-impact smells to address first:

1. **cli/app.py:645** — 🟠 HIGH — Primitive Obsession  
   Function 'chat_command' has 8 primitive-typed parameters: prompt: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), agent: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), team: Name(id='bool', ctx=Load()), output_format: Name(id='str', ctx=Load()), plan: Name(id='bool', ctx=Load()), yes: Name(id='bool', ctx=Load()), tui: Name(id='bool', ctx=Load()), debug: Name(id='bool', ctx=Load())  
   → _Introduce Parameter Object — group related primitives into a dataclass or NamedTuple._

2. **cli/commands/agent.py:33** — 🟠 HIGH — Feature Envy  
   Method 'AgentCommand.execute' accesses 'ctx' 10 times but 'self' only 2 times  
   → _Move Method — consider moving 'execute' to the class that owns 'ctx'._

3. **cli/commands/builtins.py:52** — 🟠 HIGH — Feature Envy  
   Method 'HelpCommand.execute' accesses 'ctx' 14 times but 'self' only 0 times  
   → _Move Method — consider moving 'execute' to the class that owns 'ctx'._

4. **cli/commands/chat.py:120** — 🟠 HIGH — Feature Envy  
   Method 'ChatCommand._resume' accesses 'ctx' 12 times but 'self' only 0 times  
   → _Move Method — consider moving '_resume' to the class that owns 'ctx'._

5. **cli/commands/context.py:85** — 🟠 HIGH — Feature Envy  
   Method 'ContextCommand._show_status' accesses 'console' 13 times but 'self' only 0 times  
   → _Move Method — consider moving '_show_status' to the class that owns 'console'._

6. **cli/commands/context.py:273** — 🟠 HIGH — Primitive Obsession  
   Function '_handle_range_parameter' has 6 primitive-typed parameters: value: Name(id='str', ctx=Load()), param_name: Name(id='str', ctx=Load()), min_val: Name(id='float', ctx=Load()), max_val: BinOp(left=Name(id='float', ctx=Load()), op=BitOr(), right=Constant(value=None)), is_int: Name(id='bool', ctx=Load()), label: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None))  
   → _Introduce Parameter Object — group related primitives into a dataclass or NamedTuple._

7. **cli/commands/context.py:304** — 🟠 HIGH — Duplicate Code  
   Function '_handle_importance_parameter' is an exact duplicate of '_handle_similarity_parameter' at cli/commands/context.py:308  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

8. **cli/commands/context.py:322** — 🟠 HIGH — Feature Envy  
   Method 'ContextCommand._show_stats' accesses 'ctx' 10 times but 'self' only 0 times  
   → _Move Method — consider moving '_show_stats' to the class that owns 'ctx'._

9. **cli/commands/context.py:322** — 🟠 HIGH — Feature Envy  
   Method 'ContextCommand._show_stats' accesses 'console' 12 times but 'self' only 0 times  
   → _Move Method — consider moving '_show_stats' to the class that owns 'console'._

10. **cli/commands/mcp.py:121** — 🟠 HIGH — Feature Envy  
   Method 'McpCommand._logging' accesses 'ctx' 15 times but 'self' only 0 times  
   → _Move Method — consider moving '_logging' to the class that owns 'ctx'._

11. **cli/commands/model.py:61** — 🟠 HIGH — Feature Envy  
   Method 'ModelCommand._show_current' accesses 'ctx' 10 times but 'self' only 0 times  
   → _Move Method — consider moving '_show_current' to the class that owns 'ctx'._

12. **cli/commands/model.py:125** — 🟠 HIGH — Feature Envy  
   Method 'ModelCommand._set_provider' accesses 'ctx' 26 times but 'self' only 2 times  
   → _Move Method — consider moving '_set_provider' to the class that owns 'ctx'._

13. **cli/commands/plan.py:32** — 🟠 HIGH — Feature Envy  
   Method 'PlanCommand.execute' accesses 'ctx' 13 times but 'self' only 0 times  
   → _Move Method — consider moving 'execute' to the class that owns 'ctx'._

14. **cli/commands/session.py:149** — 🟠 HIGH — Feature Envy  
   Method 'SessionCommand._merge' accesses 'ctx' 13 times but 'self' only 10 times  
   → _Move Method — consider moving '_merge' to the class that owns 'ctx'._

15. **cli/commands/session.py:323** — 🟠 HIGH — Feature Envy  
   Method 'SessionCommand._import' accesses 'ctx' 10 times but 'self' only 7 times  
   → _Move Method — consider moving '_import' to the class that owns 'ctx'._


## 📊 Files Ranked by Quality

| Rank | File | Grade | Score | Smells | LOC | MI | Avg CC |
|-----:|:-----|:------|------:|-------:|----:|---:|-------:|
| 1 | cli/textual_widgets.py | ❌ F | 8.1 | 83 | 1010 | 27 | 0.0 |
| 2 | utils/compaction.py | ❌ F | 10.3 | 58 | 546 | 34 | 14.8 |
| 3 | extensions/plugin_manager.py | ❌ F | 10.5 | 82 | 689 | 35 | 0.0 |
| 4 | cli/commands/session.py | ❌ F | 11.5 | 35 | 324 | 38 | 11.0 |
| 5 | providers/anthropic.py | ❌ F | 11.8 | 37 | 396 | 39 | 11.0 |
| 6 | cli/tool_executor.py | ❌ F | 12.1 | 60 | 688 | 40 | 11.0 |
| 7 | tools/builtins/import_graph.py | ❌ F | 12.9 | 61 | 450 | 43 | 13.0 |
| 8 | tools/builtins/patch_apply.py | ❌ F | 14.1 | 39 | 339 | 47 | 13.0 |
| 9 | tools/builtins/coverage_map.py | ❌ F | 14.3 | 47 | 301 | 48 | 12.3 |
| 10 | cli/console.py | ❌ F | 14.6 | 72 | 462 | 49 | 0.0 |

## 📁 Per-File Details

_Showing 20 worst files. 160 additional files omitted._

### cli/textual_widgets.py — ❌ F (8.1/100)

LOC: 1010 | Classes: 17 | Functions: 3 | MI: 27 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 1081 | 🟡 MEDIUM | Duplicate Code | Function 'add_thinking_message' is 94% similar to 'save' at core/session_manager_base.py:102 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 1123 | 🟡 MEDIUM | Duplicate Code | Function 'add_tool_message' is 95% similar to '_handle_thought_event_with_state' at cli/tool_executor.py:703 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 1123 | 🟡 MEDIUM | Duplicate Code | Function 'add_tool_message' is 95% similar to '_handle_finished_event_with_state' at cli/tool_executor.py:752 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 114 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 127 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 137 | 🟢 LOW | Missing Type Hint | Function 'append' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 148 | 🟢 LOW | Missing Type Hint | Function 'set_content' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 158 | 🟢 LOW | Missing Type Hint | Function '_content' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 163 | 🟢 LOW | Missing Type Hint | Function '_update_renderable' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 210 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 225 | 🟢 LOW | Missing Type Hint | Function 'content' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 230 | 🟢 LOW | Missing Type Hint | Function 'content' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 235 | 🟢 LOW | Missing Type Hint | Function 'compose' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 245 | 🟢 LOW | Missing Type Hint | Function '_update_renderable' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 249 | 🟢 LOW | Missing Type Hint | Function 'toggle_expansion' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |

_... and 68 more smells._

### utils/compaction.py — ❌ F (10.3/100)

LOC: 546 | Classes: 4 | Functions: 1 | MI: 34 | Avg CC: 14.8

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 465 | 🟠 HIGH | Feature Envy | Method 'ContextCompactor._truncate_protected_zone' accesses 'msg' 11 times but 'self' only 0 times | Move Method — consider moving '_truncate_protected_zone' to the class that owns 'msg'. |
| 63 | 🟡 MEDIUM | Large Class | Class 'ContextCompactor' spans 528 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
| 86 | 🟡 MEDIUM | Feature Envy | Method 'ContextCompactor.enforce_safety_limits' accesses 'msg' 7 times but 'self' only 1 times | Move Method — consider moving 'enforce_safety_limits' to the class that owns 'msg'. |
| 102 | 🟡 MEDIUM | Magic Number | Magic number 0.75 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 142 | 🟡 MEDIUM | Long Method | Function '_group_into_sequences' has 51 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 142 | 🟡 MEDIUM | Complex Function | Function '_group_into_sequences' has cyclomatic complexity 16 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 186 | 🟡 MEDIUM | Deep Nesting | Nesting depth 5 in '_group_into_sequences' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 189 | 🟡 MEDIUM | Deep Nesting | Nesting depth 5 in '_group_into_sequences' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 191 | 🟡 MEDIUM | Deep Nesting | Nesting depth 5 in '_group_into_sequences' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 496 | 🟡 MEDIUM | Magic Number | Magic number 500 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 498 | 🟡 MEDIUM | Magic Number | Magic number 4 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 499 | 🟡 MEDIUM | Magic Number | Magic number 200 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 503 | 🟡 MEDIUM | Magic Number | Magic number 200 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 505 | 🟡 MEDIUM | Magic Number | Magic number 4 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 521 | 🟡 MEDIUM | Feature Envy | Method 'ContextCompactor.validate_compacted_sequence' accesses 'msg' 5 times but 'self' only 0 times | Move Method — consider moving 'validate_compacted_sequence' to the class that owns 'msg'. |

_... and 43 more smells._

### extensions/plugin_manager.py — ❌ F (10.5/100)

LOC: 689 | Classes: 1 | Functions: 0 | MI: 35 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 35 | 🟠 HIGH | Large Class | Class 'PluginManager' spans 912 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
| 91 | 🟡 MEDIUM | Magic Number | Magic number 30 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 105 | 🟡 MEDIUM | Primitive Obsession | Function 'search_plugins' has 4 primitive-typed parameters: query: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), page: Name(id='int', ctx=Load()), page_size: Name(id='int', ctx=Load()), category: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 150 | 🟡 MEDIUM | Magic Number | Magic number 20 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 187 | 🟡 MEDIUM | Magic Number | Magic number 404 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 448 | 🟡 MEDIUM | Magic Number | Magic number 3 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 449 | 🟡 MEDIUM | Magic Number | Magic number 4 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 450 | 🟡 MEDIUM | Magic Number | Magic number 5 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 451 | 🟡 MEDIUM | Magic Number | Magic number 6 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 451 | 🟡 MEDIUM | Magic Number | Magic number 6 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 465 | 🟡 MEDIUM | Feature Envy | Method 'PluginManager._save_installation' accesses 'installation' 8 times but 'self' only 1 times | Move Method — consider moving '_save_installation' to the class that owns 'installation'. |
| 501 | 🟡 MEDIUM | Feature Envy | Method 'PluginManager._check_compatibility' accesses 'sys' 5 times but 'self' only 0 times | Move Method — consider moving '_check_compatibility' to the class that owns 'sys'. |
| 544 | 🟡 MEDIUM | Feature Envy | Method 'PluginManager._install_plugin_package' accesses 'metadata' 7 times but 'self' only 6 times | Move Method — consider moving '_install_plugin_package' to the class that owns 'metadata'. |
| 569 | 🟡 MEDIUM | Deep Nesting | Nesting depth 5 in '_install_plugin_package' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 574 | 🟡 MEDIUM | Long Method | Function '_install_from_pypi' has 51 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |

_... and 67 more smells._

### cli/commands/session.py — ❌ F (11.5/100)

LOC: 324 | Classes: 1 | Functions: 0 | MI: 38 | Avg CC: 11.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 149 | 🟠 HIGH | Feature Envy | Method 'SessionCommand._merge' accesses 'ctx' 13 times but 'self' only 10 times | Move Method — consider moving '_merge' to the class that owns 'ctx'. |
| 323 | 🟠 HIGH | Feature Envy | Method 'SessionCommand._import' accesses 'ctx' 10 times but 'self' only 7 times | Move Method — consider moving '_import' to the class that owns 'ctx'. |
| 352 | 🟠 HIGH | Feature Envy | Method 'SessionCommand._list' accesses 'meta' 11 times but 'self' only 7 times | Move Method — consider moving '_list' to the class that owns 'meta'. |
| 121 | 🟡 MEDIUM | Feature Envy | Method 'SessionCommand._branch' accesses 'ctx' 9 times but 'self' only 6 times | Move Method — consider moving '_branch' to the class that owns 'ctx'. |
| 230 | 🟡 MEDIUM | Feature Envy | Method 'SessionCommand._template_save' accesses 'ctx' 8 times but 'self' only 5 times | Move Method — consider moving '_template_save' to the class that owns 'ctx'. |
| 248 | 🟡 MEDIUM | Feature Envy | Method 'SessionCommand._template_create' accesses 'ctx' 7 times but 'self' only 4 times | Move Method — consider moving '_template_create' to the class that owns 'ctx'. |
| 266 | 🟡 MEDIUM | Feature Envy | Method 'SessionCommand._template_list' accesses 'ctx' 8 times but 'self' only 0 times | Move Method — consider moving '_template_list' to the class that owns 'ctx'. |
| 299 | 🟡 MEDIUM | Feature Envy | Method 'SessionCommand._export' accesses 'ctx' 6 times but 'self' only 5 times | Move Method — consider moving '_export' to the class that owns 'ctx'. |
| 352 | 🟡 MEDIUM | Complex Function | Function '_list' has cyclomatic complexity 11 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 19 | 🟢 LOW | Large Class | Class 'SessionCommand' spans 380 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
| 39 | 🟢 LOW | Missing Type Hint | Function 'name' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 48 | 🟢 LOW | Missing Type Hint | Function 'description' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 57 | 🟢 LOW | Missing Type Hint | Function 'usage' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 65 | 🟢 LOW | Missing Type Hint | Function 'execute' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 91 | 🟢 LOW | Missing Type Hint | Function '_get_manager' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |

_... and 20 more smells._

### providers/anthropic.py — ❌ F (11.8/100)

LOC: 396 | Classes: 2 | Functions: 0 | MI: 39 | Avg CC: 11.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 138 | 🟠 HIGH | Feature Envy | Method 'AnthropicProvider._format_messages' accesses 'msg' 13 times but 'self' only 0 times | Move Method — consider moving '_format_messages' to the class that owns 'msg'. |
| 241 | 🟠 HIGH | Duplicate Code | Function '_validate_messages' is an exact duplicate of '_validate_messages' at providers/openai_compat.py:160 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 42 | 🟡 MEDIUM | Primitive Obsession | Function '__init__' has 4 primitive-typed parameters: content: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), thinking: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), current_tool_id: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), total_output_tokens_delta: Name(id='int', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 92 | 🟡 MEDIUM | Primitive Obsession | Function '__init__' has 5 primitive-typed parameters: api_key: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), model: Name(id='str', ctx=Load()), max_tokens: Name(id='int', ctx=Load()), tokens_per_minute: Name(id='int', ctx=Load()), max_retries: Name(id='int', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 138 | 🟡 MEDIUM | Complex Function | Function '_format_messages' has cyclomatic complexity 11 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 199 | 🟡 MEDIUM | Feature Envy | Method 'AnthropicProvider._parse_finish_reason' accesses 'FinishReason' 5 times but 'self' only 0 times | Move Method — consider moving '_parse_finish_reason' to the class that owns 'FinishReason'. |
| 199 | 🟡 MEDIUM | Duplicate Code | Function '_parse_finish_reason' is 100% similar to '_parse_finish_reason' at providers/openai_compat.py:94 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 332 | 🟡 MEDIUM | Feature Envy | Method 'AnthropicProvider._process_stream' accesses 'chunk' 9 times but 'self' only 3 times | Move Method — consider moving '_process_stream' to the class that owns 'chunk'. |
| 386 | 🟡 MEDIUM | Feature Envy | Method 'AnthropicProvider._handle_content_block_start' accesses 'block' 5 times but 'self' only 0 times | Move Method — consider moving '_handle_content_block_start' to the class that owns 'block'. |
| 404 | 🟡 MEDIUM | Feature Envy | Method 'AnthropicProvider._handle_content_block_delta' accesses 'delta' 7 times but 'self' only 3 times | Move Method — consider moving '_handle_content_block_delta' to the class that owns 'delta'. |
| 42 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/7 params untyped | Add Type Annotations for all parameters and return type. |
| 59 | 🟢 LOW | Missing Type Hint | Function '_should_yield' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 81 | 🟢 LOW | Large Class | Class 'AnthropicProvider' spans 400 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
| 92 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/6 params untyped | Add Type Annotations for all parameters and return type. |
| 117 | 🟢 LOW | Missing Type Hint | Function 'name' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |

_... and 22 more smells._

### cli/tool_executor.py — ❌ F (12.1/100)

LOC: 688 | Classes: 1 | Functions: 0 | MI: 40 | Avg CC: 11.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 36 | 🟠 HIGH | Large Class | Class 'ToolExecutor' spans 838 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
| 190 | 🟠 HIGH | Primitive Obsession | Repeated primitive parameter group appears in: '_handle_tool_call_result_event' (line 190), '_handle_tool_call_result_event_with_state' (line 718) | Replace Data Value with Object — create a shared data structure for this recurring parameter group. |
| 281 | 🟠 HIGH | Feature Envy | Method 'ToolExecutor._execute_and_record_tool_call' accesses 'tc' 10 times but 'self' only 5 times | Move Method — consider moving '_execute_and_record_tool_call' to the class that owns 'tc'. |
| 630 | 🟠 HIGH | Feature Envy | Method 'ToolExecutor._process_event_by_type' accesses 'EventType' 24 times but 'self' only 12 times | Move Method — consider moving '_process_event_by_type' to the class that owns 'EventType'. |
| 689 | 🟠 HIGH | Deep Nesting | Nesting depth 6 in '_process_event_by_type' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 693 | 🟠 HIGH | Deep Nesting | Nesting depth 6 in '_process_event_by_type' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 697 | 🟠 HIGH | Deep Nesting | Nesting depth 7 in '_process_event_by_type' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 829 | 🟠 HIGH | Feature Envy | Method 'ToolExecutor.handle_confirmation' accesses 'request' 13 times but 'self' only 1 times | Move Method — consider moving 'handle_confirmation' to the class that owns 'request'. |
| 36 | 🟡 MEDIUM | Large Class | Class 'ToolExecutor' has 30 methods (threshold: 20) | Split Class — group related methods into smaller collaborating classes. |
| 114 | 🟡 MEDIUM | Feature Envy | Method 'ToolExecutor._handle_content_event' accesses 'event' 5 times but 'self' only 1 times | Move Method — consider moving '_handle_content_event' to the class that owns 'event'. |
| 361 | 🟡 MEDIUM | Duplicate Code | Function '_handle_agent_delegated_event' is 100% similar to '_handle_agent_message_event' at cli/tool_executor.py:412 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 461 | 🟡 MEDIUM | Complex Function | Function '_handle_post_stream_processing' has cyclomatic complexity 11 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 630 | 🟡 MEDIUM | Long Method | Function '_process_event_by_type' has 54 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 687 | 🟡 MEDIUM | Deep Nesting | Nesting depth 5 in '_process_event_by_type' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 703 | 🟡 MEDIUM | Duplicate Code | Function '_handle_thought_event_with_state' is 100% similar to '_handle_finished_event_with_state' at cli/tool_executor.py:752 | Extract Shared Function — identify the common logic and parameterise the differences. |

_... and 45 more smells._

### tools/builtins/import_graph.py — ❌ F (12.9/100)

LOC: 450 | Classes: 1 | Functions: 0 | MI: 43 | Avg CC: 13.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 131 | 🟠 HIGH | Duplicate Code | Function '_validate_input' is an exact duplicate of '_validate_path' at tools/builtins/python_ast.py:292 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 12 | 🟡 MEDIUM | Large Class | Class 'ImportGraphTool' spans 534 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
| 36 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/patch_apply.py:32 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 36 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/pytest_run.py:50 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 36 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/python_ast.py:33 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 36 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/python_exec.py:35 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 36 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/shell.py:333 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 36 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 95% similar to 'parameters' at tools/builtins/traceback_parse.py:44 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 36 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/web_fetch.py:23 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 36 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/web_search.py:23 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 74 | 🟡 MEDIUM | Primitive Obsession | Function 'execute' has 4 primitive-typed parameters: path: Name(id='str', ctx=Load()), scan_dir: Name(id='str', ctx=Load()), detect_cycles: Name(id='bool', ctx=Load()), classify: Name(id='bool', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 74 | 🟡 MEDIUM | Complex Function | Function 'execute' has cyclomatic complexity 12 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 282 | 🟡 MEDIUM | Complex Function | Function '_find_reverse_imports' has cyclomatic complexity 14 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 313 | 🟡 MEDIUM | Deep Nesting | Nesting depth 5 in '_find_reverse_imports' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 321 | 🟡 MEDIUM | Deep Nesting | Nesting depth 5 in '_find_reverse_imports' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |

_... and 46 more smells._

### tools/builtins/patch_apply.py — ❌ F (14.1/100)

LOC: 339 | Classes: 2 | Functions: 0 | MI: 47 | Avg CC: 13.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 32 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/pytest_run.py:50 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 32 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/python_ast.py:33 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 32 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/python_exec.py:35 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 32 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/shell.py:333 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 32 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 95% similar to 'parameters' at tools/builtins/traceback_parse.py:44 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 32 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/web_fetch.py:23 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 32 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/web_search.py:23 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 67 | 🟡 MEDIUM | Long Method | Function 'execute' has 52 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 67 | 🟡 MEDIUM | Primitive Obsession | Function 'execute' has 4 primitive-typed parameters: patch: Name(id='str', ctx=Load()), path: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), dry_run: Name(id='bool', ctx=Load()), fuzz: Name(id='int', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 67 | 🟡 MEDIUM | Feature Envy | Method 'PatchApplyTool.execute' accesses 'results' 5 times but 'self' only 2 times | Move Method — consider moving 'execute' to the class that owns 'results'. |
| 160 | 🟡 MEDIUM | Complex Function | Function '_apply_hunks' has cyclomatic complexity 13 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 202 | 🟡 MEDIUM | Deep Nesting | Nesting depth 5 in '_apply_hunks' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 372 | 🟡 MEDIUM | Feature Envy | Method 'PatchParser._handle_hunk_header' accesses 'match' 6 times but 'self' only 4 times | Move Method — consider moving '_handle_hunk_header' to the class that owns 'match'. |
| 18 | 🟢 LOW | Missing Type Hint | Function 'name' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 23 | 🟢 LOW | Missing Type Hint | Function 'description' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |

_... and 24 more smells._

### tools/builtins/coverage_map.py — ❌ F (14.3/100)

LOC: 301 | Classes: 1 | Functions: 0 | MI: 48 | Avg CC: 12.3

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 34 | 🟠 HIGH | Duplicate Code | Function 'parameters' is an exact duplicate of 'parameters' at tools/builtins/import_graph.py:36 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 68 | 🟠 HIGH | Primitive Obsession | Repeated primitive parameter group appears in: 'execute' (line 68), '_parse_xml' (line 108), '_parse_json' (line 196), '_format_results' (line 268) | Replace Data Value with Object — create a shared data structure for this recurring parameter group. |
| 165 | 🟠 HIGH | Deep Nesting | Nesting depth 6 in '_parse_xml' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 34 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/dead_code.py:48 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 34 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/delegate.py:33 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 34 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/file_edit.py:32 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 34 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/file_write.py:26 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 34 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/glob_tool.py:29 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 34 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/grep.py:31 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 34 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/patch_apply.py:32 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 34 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/pytest_run.py:50 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 34 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/python_ast.py:33 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 34 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/python_exec.py:35 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 34 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/shell.py:333 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 34 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 95% similar to 'parameters' at tools/builtins/traceback_parse.py:44 | Extract Shared Function — identify the common logic and parameterise the differences. |

_... and 32 more smells._

### cli/console.py — ❌ F (14.6/100)

LOC: 462 | Classes: 4 | Functions: 2 | MI: 49 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 476 | 🟠 HIGH | Primitive Obsession | Repeated primitive parameter group appears in: 'diff' (line 476), 'diff' (line 590) | Replace Data Value with Object — create a shared data structure for this recurring parameter group. |
| 512 | 🟠 HIGH | Duplicate Code | Function 'agent_content' is an exact duplicate of 'print_agent_content' at cli/ui_renderer.py:257 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 169 | 🟡 MEDIUM | Duplicate Code | Function 'get_theme' is 94% similar to 'start_task' at cli/output_handler.py:332 | Extract Shared Function — identify the common logic and parameterise the differences. |
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

### metrics/storage.py — ❌ F (14.6/100)

LOC: 432 | Classes: 1 | Functions: 0 | MI: 49 | Avg CC: 12.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 175 | 🟠 HIGH | Feature Envy | Method 'MetricsStorage._metric_to_dict' accesses 'metric' 46 times but 'self' only 0 times | Move Method — consider moving '_metric_to_dict' to the class that owns 'metric'. |
| 79 | 🟡 MEDIUM | Long Method | Function '_init_database' has 62 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 79 | 🟡 MEDIUM | Feature Envy | Method 'MetricsStorage._init_database' accesses 'cursor' 8 times but 'self' only 1 times | Move Method — consider moving '_init_database' to the class that owns 'cursor'. |
| 175 | 🟡 MEDIUM | Long Method | Function '_metric_to_dict' has 66 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 175 | 🟡 MEDIUM | Feature Envy | Method 'MetricsStorage._metric_to_dict' accesses 'base_dict' 5 times but 'self' only 0 times | Move Method — consider moving '_metric_to_dict' to the class that owns 'base_dict'. |
| 239 | 🟡 MEDIUM | Deep Nesting | Nesting depth 5 in '_metric_to_dict' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 283 | 🟡 MEDIUM | Feature Envy | Method 'MetricsStorage.get_metrics' accesses 'params' 6 times but 'self' only 1 times | Move Method — consider moving 'get_metrics' to the class that owns 'params'. |
| 341 | 🟡 MEDIUM | Long Method | Function 'get_aggregated_stats' has 75 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 341 | 🟡 MEDIUM | Complex Function | Function 'get_aggregated_stats' has cyclomatic complexity 12 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 435 | 🟡 MEDIUM | Long Method | Function 'get_session_metrics' has 59 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 435 | 🟡 MEDIUM | Feature Envy | Method 'MetricsStorage.get_session_metrics' accesses 'cursor' 8 times but 'self' only 1 times | Move Method — consider moving 'get_session_metrics' to the class that owns 'cursor'. |
| 24 | 🟢 LOW | Large Class | Class 'MetricsStorage' spans 496 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
| 33 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/4 params untyped | Add Type Annotations for all parameters and return type. |
| 66 | 🟢 LOW | Missing Type Hint | Function '_get_connection' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 66 | 🟢 LOW | Feature Envy | Method 'MetricsStorage._get_connection' accesses 'sqlite3' 3 times but 'self' only 1 times | Move Method — consider moving '_get_connection' to the class that owns 'sqlite3'. |

_... and 16 more smells._

### tools/builtins/dead_code.py — ❌ F (15.0/100)

LOC: 301 | Classes: 1 | Functions: 0 | MI: 50 | Avg CC: 15.5

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 355 | 🟠 HIGH | Deep Nesting | Nesting depth 6 in '_get_all_names' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 48 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/delegate.py:33 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 48 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/file_edit.py:32 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 48 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/file_write.py:26 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 48 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/glob_tool.py:29 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 48 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/grep.py:31 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 48 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/import_graph.py:36 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 48 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/patch_apply.py:32 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 48 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/pytest_run.py:50 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 48 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/python_ast.py:33 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 48 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/python_exec.py:35 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 48 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/shell.py:333 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 48 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 95% similar to 'parameters' at tools/builtins/traceback_parse.py:44 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 48 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/web_fetch.py:23 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 48 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/web_search.py:23 | Extract Shared Function — identify the common logic and parameterise the differences. |

_... and 34 more smells._

### cli/commands/context.py — ❌ F (15.3/100)

LOC: 303 | Classes: 1 | Functions: 0 | MI: 51 | Avg CC: 11.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 85 | 🟠 HIGH | Feature Envy | Method 'ContextCommand._show_status' accesses 'console' 13 times but 'self' only 0 times | Move Method — consider moving '_show_status' to the class that owns 'console'. |
| 273 | 🟠 HIGH | Primitive Obsession | Function '_handle_range_parameter' has 6 primitive-typed parameters: value: Name(id='str', ctx=Load()), param_name: Name(id='str', ctx=Load()), min_val: Name(id='float', ctx=Load()), max_val: BinOp(left=Name(id='float', ctx=Load()), op=BitOr(), right=Constant(value=None)), is_int: Name(id='bool', ctx=Load()), label: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 304 | 🟠 HIGH | Duplicate Code | Function '_handle_importance_parameter' is an exact duplicate of '_handle_similarity_parameter' at cli/commands/context.py:308 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 322 | 🟠 HIGH | Feature Envy | Method 'ContextCommand._show_stats' accesses 'ctx' 10 times but 'self' only 0 times | Move Method — consider moving '_show_stats' to the class that owns 'ctx'. |
| 322 | 🟠 HIGH | Feature Envy | Method 'ContextCommand._show_stats' accesses 'console' 12 times but 'self' only 0 times | Move Method — consider moving '_show_stats' to the class that owns 'console'. |
| 75 | 🟡 MEDIUM | Feature Envy | Method 'ContextCommand._show_help_message' accesses 'ctx' 7 times but 'self' only 1 times | Move Method — consider moving '_show_help_message' to the class that owns 'ctx'. |
| 85 | 🟡 MEDIUM | Feature Envy | Method 'ContextCommand._show_status' accesses 'context_settings' 8 times but 'self' only 0 times | Move Method — consider moving '_show_status' to the class that owns 'context_settings'. |
| 155 | 🟡 MEDIUM | Feature Envy | Method 'ContextCommand._manage_strategy' accesses 'ctx' 8 times but 'self' only 5 times | Move Method — consider moving '_manage_strategy' to the class that owns 'ctx'. |
| 188 | 🟡 MEDIUM | Feature Envy | Method 'ContextCommand._show_strategy_status' accesses 'console' 9 times but 'self' only 0 times | Move Method — consider moving '_show_strategy_status' to the class that owns 'console'. |
| 188 | 🟡 MEDIUM | Feature Envy | Method 'ContextCommand._show_strategy_status' accesses 'context_settings' 6 times but 'self' only 0 times | Move Method — consider moving '_show_strategy_status' to the class that owns 'context_settings'. |
| 296 | 🟡 MEDIUM | Duplicate Code | Function '_handle_max_tokens_parameter' is 100% similar to '_handle_threshold_parameter' at cli/commands/context.py:300 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 322 | 🟡 MEDIUM | Complex Function | Function '_show_stats' has cyclomatic complexity 11 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 15 | 🟢 LOW | Large Class | Class 'ContextCommand' spans 356 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
| 25 | 🟢 LOW | Missing Type Hint | Function 'name' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 34 | 🟢 LOW | Missing Type Hint | Function 'description' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |

_... and 26 more smells._

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
| 31 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/import_graph.py:36 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 31 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/patch_apply.py:32 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 31 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/pytest_run.py:50 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 31 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/shell.py:333 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 109 | 🟡 MEDIUM | Primitive Obsession | Function '_format_context_block' has 4 primitive-typed parameters: context_before: Name(id='int', ctx=Load()), context_after: Name(id='int', ctx=Load()), line_numbers: Name(id='bool', ctx=Load()), file_prefix: Name(id='str', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 272 | 🟡 MEDIUM | Primitive Obsession | Function '_validate_and_setup' has 5 primitive-typed parameters: pattern: Name(id='str', ctx=Load()), path: Name(id='str', ctx=Load()), ignore_case: Name(id='bool', ctx=Load()), whole_word: Name(id='bool', ctx=Load()), glob: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 318 | 🟡 MEDIUM | Long Method | Function '_search_files_with_results' has 50 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 21 | 🟢 LOW | Missing Type Hint | Function 'name' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 26 | 🟢 LOW | Missing Type Hint | Function 'description' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |

_... and 19 more smells._

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

_... and 36 more smells._

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
| 332 | 🟡 MEDIUM | Duplicate Code | Function 'start_task' is 100% similar to 'start_task' at cli/ui_renderer.py:350 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 345 | 🟡 MEDIUM | Duplicate Code | Function 'update_task' is 100% similar to 'tool_result' at cli/ui_renderer.py:310 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 345 | 🟡 MEDIUM | Duplicate Code | Function 'update_task' is 100% similar to 'tool_summary' at cli/ui_renderer.py:314 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 345 | 🟡 MEDIUM | Duplicate Code | Function 'update_task' is 100% similar to 'update_task' at cli/ui_renderer.py:363 | Extract Shared Function — identify the common logic and parameterise the differences. |
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

### tools/builtins/kg_query.py — ❌ F (16.0/100)

LOC: 209 | Classes: 1 | Functions: 1 | MI: 49 | Avg CC: 12.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 18 | 🟠 HIGH | Duplicate Code | Function '_find_git_root' is an exact duplicate of '_find_git_root' at tools/builtins/kg_update.py:48 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 44 | 🟠 HIGH | Duplicate Code | Function '__init__' is an exact duplicate of '__init__' at tools/builtins/kg_update.py:79 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 173 | 🟠 HIGH | Deep Nesting | Nesting depth 6 in 'execute' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 69 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 93% similar to 'parameters' at tools/builtins/kg_update.py:105 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 69 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 92% similar to 'parameters' at tools/builtins/lint_check.py:35 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 69 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 92% similar to 'parameters' at tools/builtins/test_gen.py:32 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 134 | 🟡 MEDIUM | Complex Function | Function 'execute' has cyclomatic complexity 12 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 171 | 🟡 MEDIUM | Deep Nesting | Nesting depth 5 in 'execute' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 215 | 🟡 MEDIUM | Feature Envy | Method 'KgQueryTool._handle_relations' accesses 'rel' 7 times but 'self' only 0 times | Move Method — consider moving '_handle_relations' to the class that owns 'rel'. |
| 44 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 55 | 🟢 LOW | Missing Type Hint | Function 'name' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 60 | 🟢 LOW | Missing Type Hint | Function 'description' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 69 | 🟢 LOW | Long Method | Function 'parameters' has 38 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 69 | 🟢 LOW | Missing Type Hint | Function 'parameters' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 111 | 🟢 LOW | Missing Type Hint | Function 'kind' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |

_... and 13 more smells._

## ✨ Clean Files (55 files with no smells)

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
- utils/lazy_import.py — ✅ A
- version.py — ✅ A

</details>

---

_Report generated by XP Code Smell Detector. Smells are static heuristics — use judgement when prioritising fixes._
