# Code Smell Report — ❌ F (Score: 35.1/100)

_Scanned: /home/matthew/mlg-cli/src/henchman_  

_Generated: 2026-02-27T14:30:13.456964+00:00_

## Executive Summary

| Metric | Value |
|:-------|------:|
| **Overall Grade** | ❌ F |
| **Overall Score** | 35.1/100 |
| **Files Scanned** | 146 |
| **Total Lines (non-blank)** | 30,268 |
| **Total Smells** | 2768 |
| **Avg Maintainability Index** | 70.0 |
| **Avg Cyclomatic Complexity** | 13.6 |

### Smells by Severity

| Severity | Count |
|:---------|------:|
| low | 1924 |
| medium | 679 |
| high | 165 |

### Smells by Category

| Category | Count |
|:---------|------:|
| Missing Type Hint | 1338 |
| Feature Envy | 371 |
| Duplicate Code | 324 |
| Magic Number | 204 |
| Long Method | 171 |
| Deep Nesting | 167 |
| Primitive Obsession | 93 |
| Complex Function | 60 |
| Large Class | 40 |

## 🎯 Prioritised Refactoring Queue

These are the highest-impact smells to address first:

1. **agents/delegation_manager.py:46** — 🟠 HIGH — Duplicate Code  
   Function '_prepare_delegation_brief' is an exact duplicate of '_prepare_delegation_brief' at agents/orchestrator.py:1073  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

2. **agents/delegation_manager.py:192** — 🟠 HIGH — Duplicate Code  
   Function '_is_delegation_depth_exceeded' is an exact duplicate of '_is_delegation_depth_exceeded' at agents/orchestrator.py:1721  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

3. **agents/orchestrator.py:627** — 🟠 HIGH — Large Class  
   Class 'Orchestrator' spans 1647 lines (threshold: 300)  
   → _Extract Class — split into smaller, cohesive classes with single responsibilities._

4. **agents/orchestrator.py:627** — 🟠 HIGH — Large Class  
   Class 'Orchestrator' has 68 methods (threshold: 20)  
   → _Split Class — group related methods into smaller collaborating classes._

5. **agents/orchestrator.py:1655** — 🟠 HIGH — Primitive Obsession  
   Repeated primitive parameter group appears in: '_run_delegation' (line 1655), '_execute_delegation_loop' (line 1821)  
   → _Replace Data Value with Object — create a shared data structure for this recurring parameter group._

6. **agents/presets.py:30** — 🟠 HIGH — Primitive Obsession  
   Function '_create_agent_config' has 10 primitive-typed parameters: name: Name(id='str', ctx=Load()), role: Name(id='str', ctx=Load()), description: Name(id='str', ctx=Load()), basic_file_tools: Name(id='bool', ctx=Load()), file_edit_tools: Name(id='bool', ctx=Load()), git_tools: Name(id='bool', ctx=Load()), web_tools: Name(id='bool', ctx=Load()), knowledge_tools: Name(id='bool', ctx=Load()), shell_tools: Name(id='bool', ctx=Load()), python_dev_tools: Name(id='bool', ctx=Load())  
   → _Introduce Parameter Object — group related primitives into a dataclass or NamedTuple._

7. **cli/app.py:143** — 🟠 HIGH — Long Method  
   Function '_run_interactive' has 85 lines (threshold: 30)  
   → _Extract Method — break this function into smaller, intention-revealing helper functions._

8. **cli/app.py:143** — 🟠 HIGH — Primitive Obsession  
   Repeated primitive parameter group appears in: '_run_interactive' (line 143), '_run_textual_tui' (line 241), '_run_headless' (line 369), 'chat_command' (line 644)  
   → _Replace Data Value with Object — create a shared data structure for this recurring parameter group._

9. **cli/app.py:644** — 🟠 HIGH — Primitive Obsession  
   Function 'chat_command' has 8 primitive-typed parameters: prompt: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), agent: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), team: Name(id='bool', ctx=Load()), output_format: Name(id='str', ctx=Load()), plan: Name(id='bool', ctx=Load()), yes: Name(id='bool', ctx=Load()), tui: Name(id='bool', ctx=Load()), debug: Name(id='bool', ctx=Load())  
   → _Introduce Parameter Object — group related primitives into a dataclass or NamedTuple._

10. **cli/commands/agent.py:33** — 🟠 HIGH — Feature Envy  
   Method 'AgentCommand.execute' accesses 'ctx' 10 times but 'self' only 2 times  
   → _Move Method — consider moving 'execute' to the class that owns 'ctx'._

11. **cli/commands/builtins.py:52** — 🟠 HIGH — Feature Envy  
   Method 'HelpCommand.execute' accesses 'ctx' 16 times but 'self' only 0 times  
   → _Move Method — consider moving 'execute' to the class that owns 'ctx'._

12. **cli/commands/chat.py:120** — 🟠 HIGH — Feature Envy  
   Method 'ChatCommand._resume' accesses 'ctx' 12 times but 'self' only 0 times  
   → _Move Method — consider moving '_resume' to the class that owns 'ctx'._

13. **cli/commands/context.py:71** — 🟠 HIGH — Feature Envy  
   Method 'ContextCommand._show_status' accesses 'ctx' 13 times but 'self' only 0 times  
   → _Move Method — consider moving '_show_status' to the class that owns 'ctx'._

14. **cli/commands/context.py:348** — 🟠 HIGH — Feature Envy  
   Method 'ContextCommand._show_stats' accesses 'ctx' 21 times but 'self' only 0 times  
   → _Move Method — consider moving '_show_stats' to the class that owns 'ctx'._

15. **cli/commands/mcp.py:121** — 🟠 HIGH — Feature Envy  
   Method 'McpCommand._logging' accesses 'ctx' 15 times but 'self' only 0 times  
   → _Move Method — consider moving '_logging' to the class that owns 'ctx'._


## 📊 Files Ranked by Quality

| Rank | File | Grade | Score | Smells | LOC | MI | Avg CC |
|-----:|:-----|:------|------:|-------:|----:|---:|-------:|
| 1 | cli/textual_app.py | ❌ F | 0.4 | 121 | 1439 | 1 | 0.0 |
| 2 | agents/orchestrator.py | ❌ F | 0.6 | 141 | 1753 | 2 | 13.2 |
| 3 | utils/intelligent_context.py | ❌ F | 6.4 | 88 | 913 | 21 | 14.5 |
| 4 | cli/textual_widgets.py | ❌ F | 8.2 | 89 | 897 | 27 | 12.0 |
| 5 | cli/commands/session.py | ❌ F | 10.0 | 65 | 295 | 33 | 11.0 |
| 6 | utils/compaction.py | ❌ F | 10.3 | 59 | 546 | 34 | 14.8 |
| 7 | core/agent.py | ❌ F | 10.7 | 47 | 586 | 36 | 11.0 |
| 8 | extensions/plugin_manager.py | ❌ F | 10.9 | 79 | 668 | 36 | 0.0 |
| 9 | core/session.py | ❌ F | 11.0 | 76 | 725 | 37 | 17.0 |
| 10 | providers/anthropic.py | ❌ F | 11.8 | 37 | 396 | 39 | 11.0 |

## 📁 Per-File Details

_Showing 20 worst files. 126 additional files omitted._

### cli/textual_app.py — ❌ F (0.4/100)

LOC: 1439 | Classes: 1 | Functions: 2 | MI: 1 | Avg CC: 0.0

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

### agents/orchestrator.py — ❌ F (0.6/100)

LOC: 1753 | Classes: 10 | Functions: 1 | MI: 2 | Avg CC: 13.2

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 627 | 🟠 HIGH | Large Class | Class 'Orchestrator' spans 1647 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
| 627 | 🟠 HIGH | Large Class | Class 'Orchestrator' has 68 methods (threshold: 20) | Split Class — group related methods into smaller collaborating classes. |
| 1655 | 🟠 HIGH | Primitive Obsession | Repeated primitive parameter group appears in: '_run_delegation' (line 1655), '_execute_delegation_loop' (line 1821) | Replace Data Value with Object — create a shared data structure for this recurring parameter group. |
| 221 | 🟡 MEDIUM | Duplicate Code | Function '__init__' is 92% similar to '__init__' at agents/orchestrator.py:265 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 253 | 🟡 MEDIUM | Duplicate Code | Function 'track_file_access' is 100% similar to 'track_tool_usage' at agents/orchestrator.py:257 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 302 | 🟡 MEDIUM | Duplicate Code | Function 'reset' is 100% similar to '__init__' at cli/textual_app.py:277 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 333 | 🟡 MEDIUM | Deep Nesting | Nesting depth 5 in 'track_tool_call' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 779 | 🟡 MEDIUM | Feature Envy | Method 'Orchestrator._create_tech_lead_prompt' accesses 'c' 8 times but 'self' only 0 times | Move Method — consider moving '_create_tech_lead_prompt' to the class that owns 'c'. |
| 1005 | 🟡 MEDIUM | Feature Envy | Method 'Orchestrator._check_stall_failure' accesses 'agent' 5 times but 'self' only 1 times | Move Method — consider moving '_check_stall_failure' to the class that owns 'agent'. |
| 1073 | 🟡 MEDIUM | Feature Envy | Method 'Orchestrator._prepare_delegation_brief' accesses 'tool_call' 6 times but 'self' only 0 times | Move Method — consider moving '_prepare_delegation_brief' to the class that owns 'tool_call'. |
| 1136 | 🟡 MEDIUM | Feature Envy | Method 'Orchestrator._handle_regular_tool' accesses 'tool_call' 6 times but 'self' only 1 times | Move Method — consider moving '_handle_regular_tool' to the class that owns 'tool_call'. |
| 1177 | 🟡 MEDIUM | Primitive Obsession | Function '_enforce_turn_limits' has 4 primitive-typed parameters: max_turns: Name(id='int', ctx=Load()), tool_call_count: Name(id='int', ctx=Load()), msg_start_index: Name(id='int', ctx=Load()), wrapup_warned: Name(id='bool', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 1286 | 🟡 MEDIUM | Long Method | Function '_run_agent_loop' has 60 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 1286 | 🟡 MEDIUM | Complex Function | Function '_run_agent_loop' has cyclomatic complexity 11 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 1462 | 🟡 MEDIUM | Long Method | Function '_execute_delegation_tool' has 53 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |

_... and 126 more smells._

### utils/intelligent_context.py — ❌ F (6.4/100)

LOC: 913 | Classes: 2 | Functions: 0 | MI: 21 | Avg CC: 14.5

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 44 | 🟠 HIGH | Large Class | Class 'IntelligentContextManager' spans 1177 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
| 933 | 🟠 HIGH | Duplicate Code | Function '_apply_research_compression_strategy' is an exact duplicate of '_apply_general_compression_strategy' at utils/intelligent_context.py:993 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 44 | 🟡 MEDIUM | Large Class | Class 'IntelligentContextManager' has 36 methods (threshold: 20) | Split Class — group related methods into smaller collaborating classes. |
| 55 | 🟡 MEDIUM | Primitive Obsession | Function '__init__' has 5 primitive-typed parameters: max_tokens: Name(id='int', ctx=Load()), max_protected_ratio: Name(id='float', ctx=Load()), importance_threshold: Name(id='float', ctx=Load()), cluster_similarity_threshold: Name(id='float', ctx=Load()), adaptive_compression: Name(id='bool', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 83 | 🟡 MEDIUM | Feature Envy | Method 'IntelligentContextManager.enforce_safety_limits' accesses 'msg' 7 times but 'self' only 1 times | Move Method — consider moving 'enforce_safety_limits' to the class that owns 'msg'. |
| 97 | 🟡 MEDIUM | Magic Number | Magic number 0.75 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 529 | 🟡 MEDIUM | Complex Function | Function '_cluster_temporal_proximity' has cyclomatic complexity 11 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 591 | 🟡 MEDIUM | Complex Function | Function '_cluster_topic_similarity' has cyclomatic complexity 14 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 622 | 🟡 MEDIUM | Deep Nesting | Nesting depth 5 in '_cluster_topic_similarity' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 622 | 🟡 MEDIUM | Magic Number | Magic number 3 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 656 | 🟡 MEDIUM | Complex Function | Function '_cluster_role_patterns' has cyclomatic complexity 20 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 696 | 🟡 MEDIUM | Magic Number | Magic number 3 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 699 | 🟡 MEDIUM | Magic Number | Magic number 3 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 811 | 🟡 MEDIUM | Complex Function | Function '_detect_conversation_type' has cyclomatic complexity 13 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 896 | 🟡 MEDIUM | Magic Number | Magic number 0.1 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |

_... and 73 more smells._

### cli/textual_widgets.py — ❌ F (8.2/100)

LOC: 897 | Classes: 13 | Functions: 3 | MI: 27 | Avg CC: 12.0

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

_... and 74 more smells._

### cli/commands/session.py — ❌ F (10.0/100)

LOC: 295 | Classes: 1 | Functions: 0 | MI: 33 | Avg CC: 11.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 86 | 🟠 HIGH | Deep Nesting | Nesting depth 6 in 'execute' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 93 | 🟠 HIGH | Feature Envy | Method 'SessionCommand._branch' accesses 'ctx' 12 times but 'self' only 0 times | Move Method — consider moving '_branch' to the class that owns 'ctx'. |
| 100 | 🟠 HIGH | Magic Number | Magic number 3 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 111 | 🟠 HIGH | Magic Number | Magic number 3 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 111 | 🟠 HIGH | Magic Number | Magic number 3 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 123 | 🟠 HIGH | Feature Envy | Method 'SessionCommand._merge' accesses 'ctx' 16 times but 'self' only 0 times | Move Method — consider moving '_merge' to the class that owns 'ctx'. |
| 130 | 🟠 HIGH | Magic Number | Magic number 3 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 139 | 🟠 HIGH | Magic Number | Magic number 3 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 140 | 🟠 HIGH | Magic Number | Magic number 3 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 141 | 🟠 HIGH | Magic Number | Magic number 3 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 142 | 🟠 HIGH | Magic Number | Magic number 4 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 143 | 🟠 HIGH | Magic Number | Magic number 4 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 145 | 🟠 HIGH | Magic Number | Magic number 3 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 181 | 🟠 HIGH | Feature Envy | Method 'SessionCommand._template_save' accesses 'ctx' 10 times but 'self' only 0 times | Move Method — consider moving '_template_save' to the class that owns 'ctx'. |
| 183 | 🟠 HIGH | Magic Number | Magic number 4 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |

_... and 50 more smells._

### utils/compaction.py — ❌ F (10.3/100)

LOC: 546 | Classes: 4 | Functions: 1 | MI: 34 | Avg CC: 14.8

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 86 | 🟠 HIGH | Duplicate Code | Function 'enforce_safety_limits' is an exact duplicate of 'enforce_safety_limits' at utils/intelligent_context.py:83 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
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

_... and 44 more smells._

### core/agent.py — ❌ F (10.7/100)

LOC: 586 | Classes: 2 | Functions: 0 | MI: 36 | Avg CC: 11.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 78 | 🟠 HIGH | Primitive Obsession | Function '__init__' has 10 primitive-typed parameters: system_prompt: Name(id='str', ctx=Load()), max_tokens: Name(id='int', ctx=Load()), model: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), summarize_dropped: Name(id='bool', ctx=Load()), base_tool_iterations: Name(id='int', ctx=Load()), max_protected_ratio: Name(id='float', ctx=Load()), intelligent_context: Name(id='bool', ctx=Load()), importance_threshold: Name(id='float', ctx=Load()), cluster_similarity_threshold: Name(id='float', ctx=Load()), adaptive_compression: Name(id='bool', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 491 | 🟠 HIGH | Feature Envy | Method 'Agent._process_chunk' accesses 'chunk' 12 times but 'self' only 3 times | Move Method — consider moving '_process_chunk' to the class that owns 'chunk'. |
| 589 | 🟠 HIGH | Duplicate Code | Function '_handle_stop_finish' is an exact duplicate of '_handle_other_finish' at core/agent.py:618 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 42 | 🟡 MEDIUM | Large Class | Class 'Agent' spans 720 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
| 374 | 🟡 MEDIUM | Feature Envy | Method 'Agent._process_streaming_response' accesses 'state' 5 times but 'self' only 2 times | Move Method — consider moving '_process_streaming_response' to the class that owns 'state'. |
| 491 | 🟡 MEDIUM | Feature Envy | Method 'Agent._process_chunk' accesses 'state' 8 times but 'self' only 3 times | Move Method — consider moving '_process_chunk' to the class that owns 'state'. |
| 573 | 🟡 MEDIUM | Feature Envy | Method 'Agent._create_assistant_message' accesses 'state' 5 times but 'self' only 0 times | Move Method — consider moving '_create_assistant_message' to the class that owns 'state'. |
| 646 | 🟡 MEDIUM | Long Method | Function 'run' has 66 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 646 | 🟡 MEDIUM | Complex Function | Function 'run' has cyclomatic complexity 11 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 42 | 🟢 LOW | Large Class | Class 'Agent' has 27 methods (threshold: 20) | Split Class — group related methods into smaller collaborating classes. |
| 78 | 🟢 LOW | Long Method | Function '__init__' has 38 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 78 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/14 params untyped | Add Type Annotations for all parameters and return type. |
| 151 | 🟢 LOW | Missing Type Hint | Function 'history' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 156 | 🟢 LOW | Missing Type Hint | Function 'tools' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 160 | 🟢 LOW | Missing Type Hint | Function '_emit' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |

_... and 32 more smells._

### extensions/plugin_manager.py — ❌ F (10.9/100)

LOC: 668 | Classes: 1 | Functions: 0 | MI: 36 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 35 | 🟠 HIGH | Large Class | Class 'PluginManager' spans 889 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
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
| 521 | 🟡 MEDIUM | Feature Envy | Method 'PluginManager._install_plugin_package' accesses 'metadata' 7 times but 'self' only 6 times | Move Method — consider moving '_install_plugin_package' to the class that owns 'metadata'. |
| 546 | 🟡 MEDIUM | Deep Nesting | Nesting depth 5 in '_install_plugin_package' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 551 | 🟡 MEDIUM | Long Method | Function '_install_from_pypi' has 51 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 604 | 🟡 MEDIUM | Deep Nesting | Nesting depth 5 in '_install_from_pypi' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |

_... and 64 more smells._

### core/session.py — ❌ F (11.0/100)

LOC: 725 | Classes: 5 | Functions: 0 | MI: 37 | Avg CC: 17.0

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

_... and 61 more smells._

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

### cli/commands/context.py — ❌ F (15.2/100)

LOC: 330 | Classes: 1 | Functions: 0 | MI: 51 | Avg CC: 11.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 71 | 🟠 HIGH | Feature Envy | Method 'ContextCommand._show_status' accesses 'ctx' 13 times but 'self' only 0 times | Move Method — consider moving '_show_status' to the class that owns 'ctx'. |
| 348 | 🟠 HIGH | Feature Envy | Method 'ContextCommand._show_stats' accesses 'ctx' 21 times but 'self' only 0 times | Move Method — consider moving '_show_stats' to the class that owns 'ctx'. |
| 45 | 🟡 MEDIUM | Feature Envy | Method 'ContextCommand.execute' accesses 'ctx' 8 times but 'self' only 6 times | Move Method — consider moving 'execute' to the class that owns 'ctx'. |
| 60 | 🟡 MEDIUM | Deep Nesting | Nesting depth 5 in 'execute' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 71 | 🟡 MEDIUM | Feature Envy | Method 'ContextCommand._show_status' accesses 'context_settings' 8 times but 'self' only 0 times | Move Method — consider moving '_show_status' to the class that owns 'context_settings'. |
| 138 | 🟡 MEDIUM | Feature Envy | Method 'ContextCommand._manage_strategy' accesses 'ctx' 8 times but 'self' only 2 times | Move Method — consider moving '_manage_strategy' to the class that owns 'ctx'. |
| 165 | 🟡 MEDIUM | Feature Envy | Method 'ContextCommand._show_strategy_status' accesses 'ctx' 9 times but 'self' only 0 times | Move Method — consider moving '_show_strategy_status' to the class that owns 'ctx'. |
| 165 | 🟡 MEDIUM | Feature Envy | Method 'ContextCommand._show_strategy_status' accesses 'context_settings' 6 times but 'self' only 0 times | Move Method — consider moving '_show_strategy_status' to the class that owns 'context_settings'. |
| 255 | 🟡 MEDIUM | Duplicate Code | Function '_handle_threshold_parameter' is 100% similar to '_handle_importance_parameter' at cli/commands/context.py:277 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 255 | 🟡 MEDIUM | Duplicate Code | Function '_handle_threshold_parameter' is 100% similar to '_handle_similarity_parameter' at cli/commands/context.py:299 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 277 | 🟡 MEDIUM | Duplicate Code | Function '_handle_importance_parameter' is 100% similar to '_handle_similarity_parameter' at cli/commands/context.py:299 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 348 | 🟡 MEDIUM | Complex Function | Function '_show_stats' has cyclomatic complexity 11 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 15 | 🟢 LOW | Large Class | Class 'ContextCommand' spans 387 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
| 19 | 🟢 LOW | Missing Type Hint | Function 'name' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 28 | 🟢 LOW | Missing Type Hint | Function 'description' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |

_... and 22 more smells._

### agents/delegation_manager.py — ❌ F (15.6/100)

LOC: 376 | Classes: 1 | Functions: 0 | MI: 52 | Avg CC: 13.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 46 | 🟠 HIGH | Duplicate Code | Function '_prepare_delegation_brief' is an exact duplicate of '_prepare_delegation_brief' at agents/orchestrator.py:1073 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 192 | 🟠 HIGH | Duplicate Code | Function '_is_delegation_depth_exceeded' is an exact duplicate of '_is_delegation_depth_exceeded' at agents/orchestrator.py:1721 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 46 | 🟡 MEDIUM | Feature Envy | Method 'DelegationManager._prepare_delegation_brief' accesses 'tool_call' 6 times but 'self' only 0 times | Move Method — consider moving '_prepare_delegation_brief' to the class that owns 'tool_call'. |
| 64 | 🟡 MEDIUM | Complex Function | Function '_prepare_delegation_context' has cyclomatic complexity 11 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 80 | 🟡 MEDIUM | Magic Number | Magic number 5 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 84 | 🟡 MEDIUM | Magic Number | Magic number 200 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 100 | 🟡 MEDIUM | Magic Number | Magic number 200 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 100 | 🟡 MEDIUM | Magic Number | Magic number 5 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 108 | 🟡 MEDIUM | Feature Envy | Method 'DelegationManager._assemble_delegation_input' accesses 'parts' 8 times but 'self' only 0 times | Move Method — consider moving '_assemble_delegation_input' to the class that owns 'parts'. |
| 108 | 🟡 MEDIUM | Feature Envy | Method 'DelegationManager._assemble_delegation_input' accesses 'brief' 6 times but 'self' only 0 times | Move Method — consider moving '_assemble_delegation_input' to the class that owns 'brief'. |
| 108 | 🟡 MEDIUM | Complex Function | Function '_assemble_delegation_input' has cyclomatic complexity 15 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 181 | 🟡 MEDIUM | Magic Number | Magic number 3 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 252 | 🟡 MEDIUM | Duplicate Code | Function '_yield_agent_not_found_completion' is 93% similar to '_yield_agent_not_found_completion' at agents/orchestrator.py:1765 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 342 | 🟡 MEDIUM | Feature Envy | Method 'DelegationManager._build_timeout_summary' accesses 'msg' 5 times but 'self' only 0 times | Move Method — consider moving '_build_timeout_summary' to the class that owns 'msg'. |
| 372 | 🟡 MEDIUM | Magic Number | Magic number 3 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |

_... and 22 more smells._

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

## ✨ Clean Files (27 files with no smells)

<details><summary>Click to expand</summary>

- __init__.py — ✅ A
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
- utils/lazy_import.py — ✅ A
- version.py — ✅ A

</details>

---

_Report generated by XP Code Smell Detector. Smells are static heuristics — use judgement when prioritising fixes._
