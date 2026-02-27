# Code Smell Report — ❌ F (Score: 35.8/100)

_Scanned: /home/matthew/mlg-cli/src/henchman_  

_Generated: 2026-02-27T02:04:34.579274+00:00_

## Executive Summary

| Metric | Value |
|:-------|------:|
| **Overall Grade** | ❌ F |
| **Overall Score** | 35.8/100 |
| **Files Scanned** | 144 |
| **Total Lines (non-blank)** | 28,594 |
| **Total Smells** | 2706 |
| **Avg Maintainability Index** | 69.9 |
| **Avg Cyclomatic Complexity** | 15.5 |

### Smells by Severity

| Severity | Count |
|:---------|------:|
| low | 1808 |
| medium | 668 |
| high | 230 |

### Smells by Category

| Category | Count |
|:---------|------:|
| Missing Type Hint | 1226 |
| Feature Envy | 362 |
| Duplicate Code | 326 |
| Magic Number | 218 |
| Deep Nesting | 208 |
| Long Method | 173 |
| Primitive Obsession | 86 |
| Complex Function | 70 |
| Large Class | 37 |

## 🎯 Prioritised Refactoring Queue

These are the highest-impact smells to address first:

1. **/home/matthew/mlg-cli/src/henchman/cli/output_handler.py:61** — 🟠 HIGH — Complex Function  
   Function 'get_toolbar_status' has cyclomatic complexity 24 (rank D)  
   → _Extract Method / Replace Conditional with Polymorphism to reduce branching._

2. **/home/matthew/mlg-cli/src/henchman/tools/builtins/grep.py:160** — 🟠 HIGH — Complex Function  
   Function 'execute' has cyclomatic complexity 23 (rank D)  
   → _Extract Method / Replace Conditional with Polymorphism to reduce branching._

3. **/home/matthew/mlg-cli/src/henchman/tools/builtins/import_graph.py:74** — 🟠 HIGH — Complex Function  
   Function 'execute' has cyclomatic complexity 21 (rank D)  
   → _Extract Method / Replace Conditional with Polymorphism to reduce branching._

4. **/home/matthew/mlg-cli/src/henchman/tools/builtins/kg_query.py:134** — 🟠 HIGH — Complex Function  
   Function 'execute' has cyclomatic complexity 30 (rank D)  
   → _Extract Method / Replace Conditional with Polymorphism to reduce branching._

5. **/home/matthew/mlg-cli/src/henchman/tools/builtins/kg_update.py:186** — 🟠 HIGH — Complex Function  
   Function 'execute' has cyclomatic complexity 26 (rank D)  
   → _Extract Method / Replace Conditional with Polymorphism to reduce branching._

6. **/home/matthew/mlg-cli/src/henchman/tools/builtins/patch_apply.py:140** — 🟠 HIGH — Complex Function  
   Function '_parse_patch' has cyclomatic complexity 23 (rank D)  
   → _Extract Method / Replace Conditional with Polymorphism to reduce branching._

7. **/home/matthew/mlg-cli/src/henchman/tools/builtins/pytest_run.py:89** — 🟠 HIGH — Complex Function  
   Function 'execute' has cyclomatic complexity 21 (rank D)  
   → _Extract Method / Replace Conditional with Polymorphism to reduce branching._

8. **/home/matthew/mlg-cli/src/henchman/tools/builtins/python_ast.py:230** — 🟠 HIGH — Complex Function  
   Function 'execute' has cyclomatic complexity 23 (rank D)  
   → _Extract Method / Replace Conditional with Polymorphism to reduce branching._

9. **/home/matthew/mlg-cli/src/henchman/tools/builtins/traceback_parse.py:52** — 🟠 HIGH — Complex Function  
   Function 'execute' has cyclomatic complexity 23 (rank D)  
   → _Extract Method / Replace Conditional with Polymorphism to reduce branching._

10. **/home/matthew/mlg-cli/src/henchman/utils/compaction.py:209** — 🟠 HIGH — Complex Function  
   Function 'compact' has cyclomatic complexity 22 (rank D)  
   → _Extract Method / Replace Conditional with Polymorphism to reduce branching._

11. **/home/matthew/mlg-cli/src/henchman/utils/intelligent_context.py:199** — 🟠 HIGH — Complex Function  
   Function '_calculate_importance_scores' has cyclomatic complexity 21 (rank D)  
   → _Extract Method / Replace Conditional with Polymorphism to reduce branching._

12. **__init__.py:10** — 🟠 HIGH — Duplicate Code  
   Function '__getattr__' is an exact duplicate of '__getattr__' at cli/app.py:23  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

13. **agents/orchestrator.py:189** — 🟠 HIGH — Magic Number  
   Magic number 100.0 — consider extracting to a named constant  
   → _Extract Constant / Introduce Named Constant._

14. **agents/orchestrator.py:247** — 🟠 HIGH — Magic Number  
   Magic number 100.0 — consider extracting to a named constant  
   → _Extract Constant / Introduce Named Constant._

15. **agents/orchestrator.py:304** — 🟠 HIGH — Magic Number  
   Magic number 60.0 — consider extracting to a named constant  
   → _Extract Constant / Introduce Named Constant._


## 📊 Files Ranked by Quality

| Rank | File | Grade | Score | Smells | LOC | MI | Avg CC |
|-----:|:-----|:------|------:|-------:|----:|---:|-------:|
| 1 | cli/textual_app.py | ❌ F | 0.4 | 121 | 1439 | 1 | 0.0 |
| 2 | agents/orchestrator.py | ❌ F | 2.0 | 139 | 1447 | 7 | 14.6 |
| 3 | utils/intelligent_context.py | ❌ F | 7.6 | 90 | 784 | 25 | 15.8 |
| 4 | cli/textual_widgets.py | ❌ F | 8.2 | 89 | 897 | 27 | 12.0 |
| 5 | cli/commands/session.py | ❌ F | 9.8 | 67 | 296 | 33 | 11.0 |
| 6 | core/agent.py | ❌ F | 10.7 | 47 | 586 | 36 | 11.0 |
| 7 | extensions/plugin_manager.py | ❌ F | 10.9 | 79 | 668 | 36 | 0.0 |
| 8 | utils/compaction.py | ❌ F | 10.9 | 52 | 436 | 36 | 15.3 |
| 9 | core/session.py | ❌ F | 11.0 | 76 | 725 | 37 | 17.0 |
| 10 | providers/anthropic.py | ❌ F | 11.8 | 37 | 396 | 39 | 11.0 |

## 📁 Per-File Details

_Showing 20 worst files. 124 additional files omitted._

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

### agents/orchestrator.py — ❌ F (2.0/100)

LOC: 1447 | Classes: 8 | Functions: 1 | MI: 7 | Avg CC: 14.6

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 189 | 🟠 HIGH | Magic Number | Magic number 100.0 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 247 | 🟠 HIGH | Magic Number | Magic number 100.0 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 304 | 🟠 HIGH | Magic Number | Magic number 60.0 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 309 | 🟠 HIGH | Magic Number | Magic number 100.0 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 533 | 🟠 HIGH | Large Class | Class 'Orchestrator' spans 1363 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
| 536 | 🟠 HIGH | Long Method | Function '__init__' has 88 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 656 | 🟠 HIGH | Magic Number | Magic number 500 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 931 | 🟠 HIGH | Magic Number | Magic number 200 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 1064 | 🟠 HIGH | Long Method | Function '_run_agent_loop' has 82 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 1064 | 🟠 HIGH | Primitive Obsession | Repeated primitive parameter group appears in: '_run_agent_loop' (line 1064), '_run_delegation' (line 1399) | Replace Data Value with Object — create a shared data structure for this recurring parameter group. |
| 1328 | 🟠 HIGH | Magic Number | Magic number 5 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 1329 | 🟠 HIGH | Magic Number | Magic number 200 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 1387 | 🟠 HIGH | Magic Number | Magic number 10 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 1399 | 🟠 HIGH | Long Method | Function '_run_delegation' has 80 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 1498 | 🟠 HIGH | Magic Number | Magic number 800 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |

_... and 124 more smells._

### utils/intelligent_context.py — ❌ F (7.6/100)

LOC: 784 | Classes: 2 | Functions: 0 | MI: 25 | Avg CC: 15.8

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 44 | 🟠 HIGH | Large Class | Class 'IntelligentContextManager' spans 1009 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
| 97 | 🟠 HIGH | Magic Number | Magic number 0.75 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 199 | 🟠 HIGH | Feature Envy | Method 'IntelligentContextManager._calculate_importance_scores' accesses 'message' 15 times but 'self' only 0 times | Move Method — consider moving '_calculate_importance_scores' to the class that owns 'message'. |
| 199 | 🟠 HIGH | Complex Function | Function '_calculate_importance_scores' has cyclomatic complexity 21 (rank D) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 254 | 🟠 HIGH | Deep Nesting | Nesting depth 6 in '_calculate_importance_scores' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 254 | 🟠 HIGH | Magic Number | Magic number 100 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 262 | 🟠 HIGH | Deep Nesting | Nesting depth 6 in '_calculate_importance_scores' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 262 | 🟠 HIGH | Magic Number | Magic number 20 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 269 | 🟠 HIGH | Magic Number | Magic number 0.2 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 275 | 🟠 HIGH | Magic Number | Magic number 500 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 277 | 🟠 HIGH | Magic Number | Magic number 100 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 285 | 🟠 HIGH | Magic Number | Magic number 0.1 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 454 | 🟠 HIGH | Magic Number | Magic number 3 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 528 | 🟠 HIGH | Magic Number | Magic number 3 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 531 | 🟠 HIGH | Magic Number | Magic number 3 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |

_... and 75 more smells._

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

### cli/commands/session.py — ❌ F (9.8/100)

LOC: 296 | Classes: 1 | Functions: 0 | MI: 33 | Avg CC: 11.0

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

_... and 52 more smells._

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

### utils/compaction.py — ❌ F (10.9/100)

LOC: 436 | Classes: 4 | Functions: 1 | MI: 36 | Avg CC: 15.3

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 86 | 🟠 HIGH | Duplicate Code | Function 'enforce_safety_limits' is an exact duplicate of 'enforce_safety_limits' at utils/intelligent_context.py:83 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 209 | 🟠 HIGH | Long Method | Function 'compact' has 98 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 209 | 🟠 HIGH | Complex Function | Function 'compact' has cyclomatic complexity 22 (rank D) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 329 | 🟠 HIGH | Feature Envy | Method 'ContextCompactor._truncate_protected_zone' accesses 'msg' 11 times but 'self' only 0 times | Move Method — consider moving '_truncate_protected_zone' to the class that owns 'msg'. |
| 63 | 🟡 MEDIUM | Complex Function | Function 'ContextCompactor' has cyclomatic complexity 11 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 86 | 🟡 MEDIUM | Feature Envy | Method 'ContextCompactor.enforce_safety_limits' accesses 'msg' 7 times but 'self' only 1 times | Move Method — consider moving 'enforce_safety_limits' to the class that owns 'msg'. |
| 102 | 🟡 MEDIUM | Magic Number | Magic number 0.75 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 142 | 🟡 MEDIUM | Long Method | Function '_group_into_sequences' has 51 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 142 | 🟡 MEDIUM | Complex Function | Function '_group_into_sequences' has cyclomatic complexity 16 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 186 | 🟡 MEDIUM | Deep Nesting | Nesting depth 5 in '_group_into_sequences' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 189 | 🟡 MEDIUM | Deep Nesting | Nesting depth 5 in '_group_into_sequences' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 191 | 🟡 MEDIUM | Deep Nesting | Nesting depth 5 in '_group_into_sequences' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 360 | 🟡 MEDIUM | Magic Number | Magic number 500 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 362 | 🟡 MEDIUM | Magic Number | Magic number 4 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 363 | 🟡 MEDIUM | Magic Number | Magic number 200 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |

_... and 37 more smells._

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

### tools/builtins/import_graph.py — ❌ F (13.0/100)

LOC: 312 | Classes: 1 | Functions: 0 | MI: 43 | Avg CC: 17.3

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 74 | 🟠 HIGH | Complex Function | Function 'execute' has cyclomatic complexity 21 (rank D) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 327 | 🟠 HIGH | Deep Nesting | Nesting depth 6 in '_build_import_graph' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 36 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/patch_apply.py:32 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 36 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/pytest_run.py:35 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 36 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/python_ast.py:33 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 36 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/python_exec.py:35 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 36 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/shell.py:333 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 36 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 95% similar to 'parameters' at tools/builtins/traceback_parse.py:34 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 36 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/web_fetch.py:23 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 36 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/web_search.py:23 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 74 | 🟡 MEDIUM | Long Method | Function 'execute' has 74 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 74 | 🟡 MEDIUM | Primitive Obsession | Function 'execute' has 4 primitive-typed parameters: path: Name(id='str', ctx=Load()), scan_dir: Name(id='str', ctx=Load()), detect_cycles: Name(id='bool', ctx=Load()), classify: Name(id='bool', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 74 | 🟡 MEDIUM | Feature Envy | Method 'ImportGraphTool.execute' accesses 'parts' 9 times but 'self' only 5 times | Move Method — consider moving 'execute' to the class that owns 'parts'. |
| 195 | 🟡 MEDIUM | Complex Function | Function '_find_reverse_imports' has cyclomatic complexity 14 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 226 | 🟡 MEDIUM | Deep Nesting | Nesting depth 5 in '_find_reverse_imports' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |

_... and 43 more smells._

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
| 34 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/pytest_run.py:35 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 34 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/python_ast.py:33 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 34 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/python_exec.py:35 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 34 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/shell.py:333 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 34 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 95% similar to 'parameters' at tools/builtins/traceback_parse.py:34 | Extract Shared Function — identify the common logic and parameterise the differences. |

_... and 32 more smells._

### tools/builtins/patch_apply.py — ❌ F (14.4/100)

LOC: 283 | Classes: 1 | Functions: 0 | MI: 48 | Avg CC: 18.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 140 | 🟠 HIGH | Complex Function | Function '_parse_patch' has cyclomatic complexity 23 (rank D) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 32 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/pytest_run.py:35 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 32 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/python_ast.py:33 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 32 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/python_exec.py:35 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 32 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/shell.py:333 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 32 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 95% similar to 'parameters' at tools/builtins/traceback_parse.py:34 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 32 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/web_fetch.py:23 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 32 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/web_search.py:23 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 67 | 🟡 MEDIUM | Long Method | Function 'execute' has 52 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 67 | 🟡 MEDIUM | Primitive Obsession | Function 'execute' has 4 primitive-typed parameters: patch: Name(id='str', ctx=Load()), path: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), dry_run: Name(id='bool', ctx=Load()), fuzz: Name(id='int', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 67 | 🟡 MEDIUM | Feature Envy | Method 'PatchApplyTool.execute' accesses 'results' 5 times but 'self' only 2 times | Move Method — consider moving 'execute' to the class that owns 'results'. |
| 140 | 🟡 MEDIUM | Long Method | Function '_parse_patch' has 69 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 140 | 🟡 MEDIUM | Feature Envy | Method 'PatchApplyTool._parse_patch' accesses 'line' 5 times but 'self' only 0 times | Move Method — consider moving '_parse_patch' to the class that owns 'line'. |
| 140 | 🟡 MEDIUM | Feature Envy | Method 'PatchApplyTool._parse_patch' accesses 'match' 6 times but 'self' only 0 times | Move Method — consider moving '_parse_patch' to the class that owns 'match'. |
| 211 | 🟡 MEDIUM | Deep Nesting | Nesting depth 5 in '_parse_patch' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |

_... and 22 more smells._

### cli/console.py — ❌ F (14.6/100)

LOC: 462 | Classes: 4 | Functions: 2 | MI: 49 | Avg CC: 0.0

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
| 48 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/pytest_run.py:35 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 48 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/python_ast.py:33 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 48 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/python_exec.py:35 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 48 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/shell.py:333 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 48 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 95% similar to 'parameters' at tools/builtins/traceback_parse.py:34 | Extract Shared Function — identify the common logic and parameterise the differences. |
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

### tools/builtins/kg_query.py — ❌ F (15.4/100)

LOC: 188 | Classes: 1 | Functions: 1 | MI: 51 | Avg CC: 30.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 18 | 🟠 HIGH | Duplicate Code | Function '_find_git_root' is an exact duplicate of '_find_git_root' at tools/builtins/kg_update.py:48 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 44 | 🟠 HIGH | Duplicate Code | Function '__init__' is an exact duplicate of '__init__' at tools/builtins/kg_update.py:79 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 134 | 🟠 HIGH | Long Method | Function 'execute' has 81 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 134 | 🟠 HIGH | Feature Envy | Method 'KgQueryTool.execute' accesses 'store' 12 times but 'self' only 1 times | Move Method — consider moving 'execute' to the class that owns 'store'. |
| 134 | 🟠 HIGH | Complex Function | Function 'execute' has cyclomatic complexity 30 (rank D) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 204 | 🟠 HIGH | Deep Nesting | Nesting depth 6 in 'execute' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 207 | 🟠 HIGH | Deep Nesting | Nesting depth 6 in 'execute' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 211 | 🟠 HIGH | Deep Nesting | Nesting depth 6 in 'execute' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 69 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 93% similar to 'parameters' at tools/builtins/kg_update.py:105 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 69 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 92% similar to 'parameters' at tools/builtins/lint_check.py:35 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 69 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 92% similar to 'parameters' at tools/builtins/test_gen.py:32 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 134 | 🟡 MEDIUM | Feature Envy | Method 'KgQueryTool.execute' accesses 'params' 5 times but 'self' only 1 times | Move Method — consider moving 'execute' to the class that owns 'params'. |
| 134 | 🟡 MEDIUM | Feature Envy | Method 'KgQueryTool.execute' accesses 'rel' 7 times but 'self' only 1 times | Move Method — consider moving 'execute' to the class that owns 'rel'. |
| 189 | 🟡 MEDIUM | Deep Nesting | Nesting depth 5 in 'execute' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 192 | 🟡 MEDIUM | Deep Nesting | Nesting depth 5 in 'execute' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |

_... and 15 more smells._

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
