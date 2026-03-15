# Code Smell Report — ⚠️ C (Score: 78.4/100)

_Scanned: /home/matthew/mlg-cli/src/henchman_  

_Generated: 2026-03-15T14:00:29.567441+00:00_

## Executive Summary

| Metric | Value |
|:-------|------:|
| **Overall Grade** | ⚠️ C |
| **Overall Score** | 78.4/100 |
| **Files Scanned** | 215 |
| **Total Lines (non-blank)** | 44,376 |
| **Total Smells** | 597 |
| **Avg Maintainability Index** | 70.0 |
| **Avg Cyclomatic Complexity** | 14.0 |

### Smells by Severity

| Severity | Count |
|:---------|------:|
| low | 405 |
| medium | 187 |
| high | 3 |
| critical | 2 |

### Smells by Category

| Category | Count |
|:---------|------:|
| Missing Type Hint | 143 |
| Duplicate Code | 107 |
| Feature Envy | 82 |
| Long Method | 75 |
| Deep Nesting | 59 |
| Magic Number | 44 |
| Primitive Obsession | 43 |
| Complex Function | 29 |
| Large Class | 15 |

## 🎯 Prioritised Refactoring Queue

These are the highest-impact smells to address first:

1. **/home/matthew/mlg-cli/src/henchman/agents/working_memory.py:361** — 🔴 CRITICAL — Complex Function  
   Function 'should_read_file' has cyclomatic complexity 41 (rank F)  
   → _Extract Method / Replace Conditional with Polymorphism to reduce branching._

2. **agents/working_memory.py:361** — 🔴 CRITICAL — Long Method  
   Function 'should_read_file' has 142 lines (threshold: 30)  
   → _Extract Method — break this function into smaller, intention-revealing helper functions._

3. **agents/working_memory.py:361** — 🟠 HIGH — Feature Envy  
   Method 'WorkingMemory.should_read_file' accesses 'rng' 15 times but 'self' only 5 times  
   → _Move Method — consider moving 'should_read_file' to the class that owns 'rng'._

4. **agents/working_memory.py:439** — 🟠 HIGH — Deep Nesting  
   Nesting depth 6 in 'should_read_file' (threshold: 4)  
   → _Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return._

5. **agents/working_memory.py:473** — 🟠 HIGH — Deep Nesting  
   Nesting depth 6 in 'should_read_file' (threshold: 4)  
   → _Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return._

6. **/home/matthew/mlg-cli/src/henchman/agents/delegation.py:284** — 🟡 MEDIUM — Complex Function  
   Function '_validate_messages_access' has cyclomatic complexity 12 (rank C)  
   → _Extract Method / Replace Conditional with Polymorphism to reduce branching._

7. **/home/matthew/mlg-cli/src/henchman/agents/orchestrator_delegation_ctrl.py:122** — 🟡 MEDIUM — Complex Function  
   Function '_run_delegation' has cyclomatic complexity 18 (rank C)  
   → _Extract Method / Replace Conditional with Polymorphism to reduce branching._

8. **/home/matthew/mlg-cli/src/henchman/agents/working_memory.py:305** — 🟡 MEDIUM — Complex Function  
   Function '_parse_line_ranges' has cyclomatic complexity 12 (rank C)  
   → _Extract Method / Replace Conditional with Polymorphism to reduce branching._

9. **/home/matthew/mlg-cli/src/henchman/config/context.py:132** — 🟡 MEDIUM — Complex Function  
   Function 'discover_files' has cyclomatic complexity 19 (rank C)  
   → _Extract Method / Replace Conditional with Polymorphism to reduce branching._

10. **/home/matthew/mlg-cli/src/henchman/config/environment.py:133** — 🟡 MEDIUM — Complex Function  
   Function '_detect_git_status' has cyclomatic complexity 17 (rank C)  
   → _Extract Method / Replace Conditional with Polymorphism to reduce branching._

11. **/home/matthew/mlg-cli/src/henchman/core/agent.py:198** — 🟡 MEDIUM — Complex Function  
   Function '__getattr__' has cyclomatic complexity 12 (rank C)  
   → _Extract Method / Replace Conditional with Polymorphism to reduce branching._

12. **/home/matthew/mlg-cli/src/henchman/mcp/client.py:42** — 🟡 MEDIUM — Complex Function  
   Function 'write' has cyclomatic complexity 13 (rank C)  
   → _Extract Method / Replace Conditional with Polymorphism to reduce branching._

13. **/home/matthew/mlg-cli/src/henchman/mcp/manager.py:132** — 🟡 MEDIUM — Complex Function  
   Function '_build_logging_env' has cyclomatic complexity 11 (rank C)  
   → _Extract Method / Replace Conditional with Polymorphism to reduce branching._

14. **/home/matthew/mlg-cli/src/henchman/rag/indexer.py:217** — 🟡 MEDIUM — Complex Function  
   Function 'index' has cyclomatic complexity 13 (rank C)  
   → _Extract Method / Replace Conditional with Polymorphism to reduce branching._

15. **/home/matthew/mlg-cli/src/henchman/rag/system.py:250** — 🟡 MEDIUM — Complex Function  
   Function 'initialize_rag' has cyclomatic complexity 19 (rank C)  
   → _Extract Method / Replace Conditional with Polymorphism to reduce branching._


## 📊 Files Ranked by Quality

| Rank | File | Grade | Score | Smells | LOC | MI | Avg CC |
|-----:|:-----|:------|------:|-------:|----:|---:|-------:|
| 1 | agents/working_memory.py | ❌ F | 11.0 | 32 | 464 | 37 | 26.5 |
| 2 | tools/builtins/symbol_trace.py | ❌ F | 51.2 | 16 | 381 | 47 | 13.0 |
| 3 | cli/textual_mixins.py | 🔶 D | 61.3 | 4 | 1463 | 4 | 0.0 |
| 4 | cli/textual_screens.py | 🔶 D | 61.9 | 17 | 398 | 52 | 0.0 |
| 5 | mcp/manager.py | 🔶 D | 63.0 | 13 | 173 | 65 | 11.0 |
| 6 | tools/builtins/file_overview.py | 🔶 D | 63.5 | 11 | 295 | 51 | 11.0 |
| 7 | tools/builtins/pattern_search.py | 🔶 D | 64.1 | 10 | 312 | 55 | 12.0 |
| 8 | utils/compaction.py | 🔶 D | 64.2 | 6 | 855 | 30 | 11.0 |
| 9 | agents/orchestrator_delegation_ctrl.py | 🔶 D | 65.1 | 8 | 179 | 63 | 18.0 |
| 10 | utils/message_compactor.py | 🔶 D | 65.1 | 15 | 235 | 61 | 12.0 |

## 📁 Per-File Details

_Showing 20 worst files. 195 additional files omitted._

### agents/working_memory.py — ❌ F (11.0/100)

LOC: 464 | Classes: 7 | Functions: 1 | MI: 37 | Avg CC: 26.5

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 361 | 🔴 CRITICAL | Long Method | Function 'should_read_file' has 142 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 361 | 🔴 CRITICAL | Complex Function | Function 'should_read_file' has cyclomatic complexity 41 (rank F) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 361 | 🟠 HIGH | Feature Envy | Method 'WorkingMemory.should_read_file' accesses 'rng' 15 times but 'self' only 5 times | Move Method — consider moving 'should_read_file' to the class that owns 'rng'. |
| 439 | 🟠 HIGH | Deep Nesting | Nesting depth 6 in 'should_read_file' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 473 | 🟠 HIGH | Deep Nesting | Nesting depth 6 in 'should_read_file' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 184 | 🟡 MEDIUM | Duplicate Code | Function 'add_decision' is 100% similar to 'set_session' at cli/repl.py:291 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 184 | 🟡 MEDIUM | Duplicate Code | Function 'add_decision' is 100% similar to 'post' at cli/textual_bridge.py:181 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 184 | 🟡 MEDIUM | Duplicate Code | Function 'add_decision' is 100% similar to 'add_auto_approve_policy' at tools/registry.py:170 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 184 | 🟡 MEDIUM | Duplicate Code | Function 'add_decision' is 100% similar to 'remove_auto_approve_policy' at tools/registry.py:184 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 305 | 🟡 MEDIUM | Complex Function | Function '_parse_line_ranges' has cyclomatic complexity 12 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 430 | 🟡 MEDIUM | Deep Nesting | Nesting depth 5 in 'should_read_file' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 437 | 🟡 MEDIUM | Deep Nesting | Nesting depth 5 in 'should_read_file' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 464 | 🟡 MEDIUM | Deep Nesting | Nesting depth 5 in 'should_read_file' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 471 | 🟡 MEDIUM | Deep Nesting | Nesting depth 5 in 'should_read_file' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 95 | 🟢 LOW | Missing Type Hint | Function '__post_init__' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |

_... and 17 more smells._

### tools/builtins/symbol_trace.py — ❌ F (51.2/100)

LOC: 381 | Classes: 5 | Functions: 11 | MI: 47 | Avg CC: 13.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 106 | 🟡 MEDIUM | Complex Function | Function '_find_definitions_in_file' has cyclomatic complexity 12 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 153 | 🟡 MEDIUM | Deep Nesting | Nesting depth 5 in '_find_definitions_in_file' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 166 | 🟡 MEDIUM | Complex Function | Function '_find_imports_in_file' has cyclomatic complexity 14 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 195 | 🟡 MEDIUM | Deep Nesting | Nesting depth 5 in '_find_imports_in_file' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 354 | 🟡 MEDIUM | Complex Function | Function '_execute_symbol_trace' has cyclomatic complexity 13 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 100 | 🟢 LOW | Magic Number | Magic number 120 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 106 | 🟢 LOW | Long Method | Function '_find_definitions_in_file' has 45 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 152 | 🟢 LOW | Deep Nesting | Nesting depth 4 in '_find_definitions_in_file' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 188 | 🟢 LOW | Deep Nesting | Nesting depth 4 in '_find_imports_in_file' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 193 | 🟢 LOW | Deep Nesting | Nesting depth 4 in '_find_imports_in_file' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 251 | 🟢 LOW | Deep Nesting | Nesting depth 4 in '_collect_annotations_from_node' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 277 | 🟢 LOW | Magic Number | Magic number 20 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 300 | 🟢 LOW | Long Method | Function '_build_trace_report' has 43 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 345 | 🟢 LOW | Magic Number | Magic number 20 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 354 | 🟢 LOW | Long Method | Function '_execute_symbol_trace' has 39 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |

_... and 1 more smells._

### cli/textual_mixins.py — 🔶 D (61.3/100)

LOC: 1463 | Classes: 13 | Functions: 3 | MI: 4 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 109 | 🟡 MEDIUM | Duplicate Code | Function '__init__' is 100% similar to '_reset_string_state' at utils/intelligent_context_parser.py:221 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 1394 | 🟡 MEDIUM | Duplicate Code | Function 'on_switch_provider_message' is 94% similar to '__exit__' at rag/concurrency.py:125 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 1137 | 🟢 LOW | Feature Envy | Method '_CommandPaletteMixin._fill_input_with_text' accesses 'widget' 3 times but 'self' only 1 times | Move Method — consider moving '_fill_input_with_text' to the class that owns 'widget'. |
| 1723 | 🟢 LOW | Primitive Obsession | Function 'update_status' has 3 primitive-typed parameters: message: Name(id='str', ctx=Load()), tokens: BinOp(left=Name(id='int', ctx=Load()), op=BitOr(), right=Constant(value=None)), cost: BinOp(left=Name(id='float', ctx=Load()), op=BitOr(), right=Constant(value=None)) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |

### cli/textual_screens.py — 🔶 D (61.9/100)

LOC: 398 | Classes: 4 | Functions: 0 | MI: 52 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 89 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 98 | 🟢 LOW | Missing Type Hint | Function 'compose' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 106 | 🟢 LOW | Long Method | Function '_build_confirmation_dialog' has 35 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 106 | 🟢 LOW | Missing Type Hint | Function '_build_confirmation_dialog' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 148 | 🟢 LOW | Missing Type Hint | Function '_build_params_label' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 165 | 🟢 LOW | Missing Type Hint | Function 'on_button_pressed' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 176 | 🟢 LOW | Missing Type Hint | Function 'action_approve' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 184 | 🟢 LOW | Missing Type Hint | Function 'action_deny' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 216 | 🟢 LOW | Missing Type Hint | Function 'compose' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 250 | 🟢 LOW | Missing Type Hint | Function 'on_button_pressed' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 288 | 🟢 LOW | Missing Type Hint | Function 'compose' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 368 | 🟢 LOW | Missing Type Hint | Function 'on_button_pressed' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 425 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 435 | 🟢 LOW | Missing Type Hint | Function 'compose' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 462 | 🟢 LOW | Missing Type Hint | Function '_build_entries' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |

_... and 2 more smells._

### mcp/manager.py — 🔶 D (63.0/100)

LOC: 173 | Classes: 1 | Functions: 0 | MI: 65 | Avg CC: 11.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 38 | 🟡 MEDIUM | Duplicate Code | Function 'get_server_names' is 100% similar to 'list_providers' at providers/registry.py:50 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 38 | 🟡 MEDIUM | Duplicate Code | Function 'get_server_names' is 100% similar to 'list_tools' at tools/registry.py:142 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 132 | 🟡 MEDIUM | Feature Envy | Method 'McpManager._build_logging_env' accesses 'command' 5 times but 'self' only 0 times | Move Method — consider moving '_build_logging_env' to the class that owns 'command'. |
| 132 | 🟡 MEDIUM | Complex Function | Function '_build_logging_env' has cyclomatic complexity 11 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 26 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 38 | 🟢 LOW | Missing Type Hint | Function 'get_server_names' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 46 | 🟢 LOW | Missing Type Hint | Function 'is_trusted' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 59 | 🟢 LOW | Missing Type Hint | Function 'connect_all' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 87 | 🟢 LOW | Missing Type Hint | Function 'disconnect_all' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 98 | 🟢 LOW | Missing Type Hint | Function 'get_all_tools' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 106 | 🟢 LOW | Missing Type Hint | Function 'call_tool' has incomplete type hints: 1/4 params untyped | Add Type Annotations for all parameters and return type. |
| 132 | 🟢 LOW | Long Method | Function '_build_logging_env' has 35 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 184 | 🟢 LOW | Feature Envy | Method 'McpManager.create_from_settings' accesses 'server_config' 4 times but 'self' only 0 times | Move Method — consider moving 'create_from_settings' to the class that owns 'server_config'. |

### tools/builtins/file_overview.py — 🔶 D (63.5/100)

LOC: 295 | Classes: 1 | Functions: 10 | MI: 51 | Avg CC: 11.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 35 | 🟡 MEDIUM | Complex Function | Function '_format_function_sig' has cyclomatic complexity 11 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 136 | 🟡 MEDIUM | Complex Function | Function '_summarize_python' has cyclomatic complexity 11 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 349 | 🟡 MEDIUM | Duplicate Code | Function 'execute' is 96% similar to 'execute' at tools/builtins/pattern_search.py:363 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 35 | 🟢 LOW | Long Method | Function '_format_function_sig' has 33 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 136 | 🟢 LOW | Primitive Obsession | Function '_summarize_python' has 3 primitive-typed parameters: source: Name(id='str', ctx=Load()), depth: Name(id='int', ctx=Load()), include_docs: Name(id='bool', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 165 | 🟢 LOW | Magic Number | Magic number 200 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 205 | 🟢 LOW | Magic Number | Magic number 20 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 228 | 🟢 LOW | Magic Number | Magic number 20 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 253 | 🟢 LOW | Magic Number | Magic number 15 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 255 | 🟢 LOW | Magic Number | Magic number 15 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 259 | 🟢 LOW | Long Method | Function '_execute_file_overview' has 35 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |

### tools/builtins/pattern_search.py — 🔶 D (64.1/100)

LOC: 312 | Classes: 3 | Functions: 7 | MI: 55 | Avg CC: 12.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 73 | 🟡 MEDIUM | Complex Function | Function '_extract_structural_patterns' has cyclomatic complexity 13 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 234 | 🟡 MEDIUM | Long Method | Function '_execute_pattern_search' has 52 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 234 | 🟡 MEDIUM | Complex Function | Function '_execute_pattern_search' has cyclomatic complexity 11 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 363 | 🟡 MEDIUM | Primitive Obsession | Function 'execute' has 4 primitive-typed parameters: description: Name(id='str', ctx=Load()), path: Name(id='str', ctx=Load()), top_k: Name(id='int', ctx=Load()), strategy: Name(id='str', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 70 | 🟢 LOW | Magic Number | Magic number 3 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 73 | 🟢 LOW | Long Method | Function '_extract_structural_patterns' has 35 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 96 | 🟢 LOW | Magic Number | Magic number 3 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 168 | 🟢 LOW | Deep Nesting | Nesting depth 4 in '_search_file_structural' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 226 | 🟢 LOW | Magic Number | Magic number 5 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 328 | 🟢 LOW | Magic Number | Magic number 10 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |

### utils/compaction.py — 🔶 D (64.2/100)

LOC: 855 | Classes: 11 | Functions: 11 | MI: 30 | Avg CC: 11.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 55 | 🟡 MEDIUM | Duplicate Code | Function 'token_count' is 94% similar to '_truncate_with_marker' at utils/intelligent_context_formatter.py:379 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 747 | 🟡 MEDIUM | Duplicate Code | Function 'validate_compacted_sequence' is 100% similar to '_detect_conversation_type' at utils/message_analyzer.py:95 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 1049 | 🟡 MEDIUM | Complex Function | Function '_attempt_summarization' has cyclomatic complexity 11 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 555 | 🟢 LOW | Feature Envy | Method '_ContextCompactorHelpersMixin._select_sequences_to_keep' accesses 'last_sequence' 3 times but 'self' only 1 times | Move Method — consider moving '_select_sequences_to_keep' to the class that owns 'last_sequence'. |
| 598 | 🟢 LOW | Feature Envy | Method '_ContextCompactorHelpersMixin._reconstruct_result' accesses 'result' 4 times but 'self' only 0 times | Move Method — consider moving '_reconstruct_result' to the class that owns 'result'. |
| 699 | 🟢 LOW | Long Method | Function '_perform_compaction' has 33 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |

### agents/orchestrator_delegation_ctrl.py — 🔶 D (65.1/100)

LOC: 179 | Classes: 2 | Functions: 0 | MI: 63 | Avg CC: 18.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 122 | 🟡 MEDIUM | Long Method | Function '_run_delegation' has 70 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 122 | 🟡 MEDIUM | Feature Envy | Method 'DelegationController._run_delegation' accesses 'params' 6 times but 'self' only 5 times | Move Method — consider moving '_run_delegation' to the class that owns 'params'. |
| 122 | 🟡 MEDIUM | Feature Envy | Method 'DelegationController._run_delegation' accesses 'state' 8 times but 'self' only 5 times | Move Method — consider moving '_run_delegation' to the class that owns 'state'. |
| 122 | 🟡 MEDIUM | Feature Envy | Method 'DelegationController._run_delegation' accesses 'final_state' 8 times but 'self' only 5 times | Move Method — consider moving '_run_delegation' to the class that owns 'final_state'. |
| 122 | 🟡 MEDIUM | Complex Function | Function '_run_delegation' has cyclomatic complexity 18 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 206 | 🟡 MEDIUM | Feature Envy | Method 'DelegationController._stream_delegation' accesses 'state' 5 times but 'self' only 1 times | Move Method — consider moving '_stream_delegation' to the class that owns 'state'. |
| 206 | 🟢 LOW | Feature Envy | Method 'DelegationController._stream_delegation' accesses 'params' 4 times but 'self' only 1 times | Move Method — consider moving '_stream_delegation' to the class that owns 'params'. |
| 206 | 🟢 LOW | Feature Envy | Method 'DelegationController._stream_delegation' accesses 'sub_event' 4 times but 'self' only 1 times | Move Method — consider moving '_stream_delegation' to the class that owns 'sub_event'. |

### utils/message_compactor.py — 🔶 D (65.1/100)

LOC: 235 | Classes: 1 | Functions: 0 | MI: 61 | Avg CC: 12.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 183 | 🟡 MEDIUM | Complex Function | Function '_add_complete_clusters' has cyclomatic complexity 12 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 19 | 🟢 LOW | Large Class | Class 'MessageCompactor' spans 300 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
| 26 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 34 | 🟢 LOW | Long Method | Function 'apply_intelligent_truncation' has 44 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 34 | 🟢 LOW | Missing Type Hint | Function 'apply_intelligent_truncation' has incomplete type hints: 1/5 params untyped | Add Type Annotations for all parameters and return type. |
| 103 | 🟢 LOW | Missing Type Hint | Function '_count_tokens' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 117 | 🟢 LOW | Missing Type Hint | Function '_sort_by_importance' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 131 | 🟢 LOW | Missing Type Hint | Function '_add_protected_messages' has incomplete type hints: 1/6 params untyped | Add Type Annotations for all parameters and return type. |
| 169 | 🟢 LOW | Missing Type Hint | Function 'calculate_cluster_importance' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 183 | 🟢 LOW | Missing Type Hint | Function '_add_complete_clusters' has incomplete type hints: 1/6 params untyped | Add Type Annotations for all parameters and return type. |
| 222 | 🟢 LOW | Deep Nesting | Nesting depth 4 in '_add_complete_clusters' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 230 | 🟢 LOW | Missing Type Hint | Function '_add_individual_messages' has incomplete type hints: 1/5 params untyped | Add Type Annotations for all parameters and return type. |
| 262 | 🟢 LOW | Missing Type Hint | Function '_add_message_if_fits' has incomplete type hints: 1/4 params untyped | Add Type Annotations for all parameters and return type. |
| 281 | 🟢 LOW | Missing Type Hint | Function '_update_tokens_used' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 294 | 🟢 LOW | Missing Type Hint | Function '_sort_messages_to_original_order' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |

### knowledge/store.py — 🔶 D (65.2/100)

LOC: 462 | Classes: 2 | Functions: 9 | MI: 47 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 107 | 🟡 MEDIUM | Duplicate Code | Function '_relation_to_edge_attrs' is 100% similar to '_format_tool_for_anthropic' at providers/anthropic.py:130 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 107 | 🟡 MEDIUM | Duplicate Code | Function '_relation_to_edge_attrs' is 100% similar to 'to_metadata' at rag/chunker.py:42 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 407 | 🟡 MEDIUM | Duplicate Code | Function 'add_entity' is 100% similar to 'add_relation' at knowledge/store.py:499 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 518 | 🟡 MEDIUM | Duplicate Code | Function 'get_relations' is 94% similar to 'extract_imports' at tools/builtins/import_graph.py:267 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 518 | 🟡 MEDIUM | Duplicate Code | Function 'get_relations' is 94% similar to 'extract_critical_sections' at utils/message_analyzer.py:106 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 257 | 🟢 LOW | Deep Nesting | Nesting depth 4 in 'get_neighbors' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |

### utils/compression_strategy.py — 🔶 D (65.5/100)

LOC: 245 | Classes: 4 | Functions: 0 | MI: 57 | Avg CC: 14.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 65 | 🟡 MEDIUM | Long Method | Function 'compress' has 56 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 65 | 🟡 MEDIUM | Complex Function | Function 'compress' has cyclomatic complexity 14 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 274 | 🟡 MEDIUM | Feature Envy | Method 'CompressionStrategyFactory.create_for_conversation_type' accesses 'CSC' 6 times but 'self' only 0 times | Move Method — consider moving 'create_for_conversation_type' to the class that owns 'CSC'. |
| 103 | 🟢 LOW | Deep Nesting | Nesting depth 4 in 'compress' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 117 | 🟢 LOW | Deep Nesting | Nesting depth 4 in 'compress' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 127 | 🟢 LOW | Deep Nesting | Nesting depth 4 in 'compress' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 134 | 🟢 LOW | Deep Nesting | Nesting depth 4 in 'compress' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 199 | 🟢 LOW | Feature Envy | Method 'CompressionStrategy._generate_cluster_summary' accesses 'msg' 4 times but 'self' only 0 times | Move Method — consider moving '_generate_cluster_summary' to the class that owns 'msg'. |
| 245 | 🟢 LOW | Deep Nesting | Nesting depth 4 in '_preserve_tool_sequences_in_cluster' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 248 | 🟢 LOW | Feature Envy | Method 'CompressionStrategy._preserve_code_blocks_in_cluster' accesses 'msg' 4 times but 'self' only 0 times | Move Method — consider moving '_preserve_code_blocks_in_cluster' to the class that owns 'msg'. |
| 274 | 🟢 LOW | Long Method | Function 'create_for_conversation_type' has 42 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |

### agents/delegation.py — 🔶 D (66.7/100)

LOC: 856 | Classes: 3 | Functions: 18 | MI: 33 | Avg CC: 12.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 284 | 🟡 MEDIUM | Complex Function | Function '_validate_messages_access' has cyclomatic complexity 12 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 136 | 🟢 LOW | Magic Number | Magic number 0.3 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 150 | 🟢 LOW | Magic Number | Magic number 0.7 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 284 | 🟢 LOW | Long Method | Function '_validate_messages_access' has 31 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 419 | 🟢 LOW | Primitive Obsession | Function '_append_list_section' has 3 primitive-typed parameters: header: Name(id='str', ctx=Load()), item_format: Name(id='str', ctx=Load()), footer: Name(id='str', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 555 | 🟢 LOW | Long Method | Function '_prepare_execution' has 32 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 688 | 🟢 LOW | Large Class | Class 'DelegationRunner' spans 372 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
| 719 | 🟢 LOW | Long Method | Function 'run_delegation' has 30 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |

### mcp/client.py — 🔶 D (66.9/100)

LOC: 199 | Classes: 4 | Functions: 0 | MI: 62 | Avg CC: 13.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 42 | 🟡 MEDIUM | Complex Function | Function 'write' has cyclomatic complexity 13 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 33 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 42 | 🟢 LOW | Long Method | Function 'write' has 46 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 42 | 🟢 LOW | Missing Type Hint | Function 'write' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 42 | 🟢 LOW | Feature Envy | Method 'FilteredStream.write' accesses 're' 3 times but 'self' only 1 times | Move Method — consider moving 'write' to the class that owns 're'. |
| 42 | 🟢 LOW | Feature Envy | Method 'FilteredStream.write' accesses 'line' 3 times but 'self' only 1 times | Move Method — consider moving 'write' to the class that owns 'line'. |
| 133 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/4 params untyped | Add Type Annotations for all parameters and return type. |
| 149 | 🟢 LOW | Missing Type Hint | Function 'is_connected' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 153 | 🟢 LOW | Long Method | Function 'connect' has 34 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 153 | 🟢 LOW | Missing Type Hint | Function 'connect' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 198 | 🟢 LOW | Missing Type Hint | Function 'disconnect' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 211 | 🟢 LOW | Missing Type Hint | Function 'discover_tools' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 231 | 🟢 LOW | Missing Type Hint | Function 'get_tools' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 239 | 🟢 LOW | Missing Type Hint | Function 'call_tool' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |

### config/context.py — 🔶 D (69.0/100)

LOC: 160 | Classes: 1 | Functions: 0 | MI: 62 | Avg CC: 19.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 132 | 🟡 MEDIUM | Long Method | Function 'discover_files' has 51 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 132 | 🟡 MEDIUM | Complex Function | Function 'discover_files' has cyclomatic complexity 19 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 43 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/4 params untyped | Add Type Annotations for all parameters and return type. |
| 68 | 🟢 LOW | Missing Type Hint | Function 'filename' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 72 | 🟢 LOW | Missing Type Hint | Function '_find_git_root' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 88 | 🟢 LOW | Missing Type Hint | Function '_load_gitignore_patterns' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 88 | 🟢 LOW | Feature Envy | Method 'ContextLoader._load_gitignore_patterns' accesses 'line' 3 times but 'self' only 0 times | Move Method — consider moving '_load_gitignore_patterns' to the class that owns 'line'. |
| 109 | 🟢 LOW | Missing Type Hint | Function '_is_ignored' has incomplete type hints: 1/4 params untyped | Add Type Annotations for all parameters and return type. |
| 132 | 🟢 LOW | Missing Type Hint | Function 'discover_files' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 185 | 🟢 LOW | Deep Nesting | Nesting depth 4 in 'discover_files' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 190 | 🟢 LOW | Missing Type Hint | Function 'load' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |

### utils/intelligent_context_aggregator.py — 🔶 D (69.2/100)

LOC: 418 | Classes: 4 | Functions: 0 | MI: 42 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 209 | 🟡 MEDIUM | Feature Envy | Method 'SequenceValidator.validate_compacted_sequence' accesses 'SequenceValidator' 5 times but 'self' only 0 times | Move Method — consider moving 'validate_compacted_sequence' to the class that owns 'SequenceValidator'. |
| 261 | 🟢 LOW | Feature Envy | Method 'SequenceValidator._is_duplicate_assistant_message' accesses 'current_msg' 3 times but 'self' only 0 times | Move Method — consider moving '_is_duplicate_assistant_message' to the class that owns 'current_msg'. |
| 261 | 🟢 LOW | Feature Envy | Method 'SequenceValidator._is_duplicate_assistant_message' accesses 'prev_msg' 3 times but 'self' only 0 times | Move Method — consider moving '_is_duplicate_assistant_message' to the class that owns 'prev_msg'. |
| 293 | 🟢 LOW | Feature Envy | Method 'SequenceValidator._validate_conversation_flow' accesses 'prev' 3 times but 'self' only 0 times | Move Method — consider moving '_validate_conversation_flow' to the class that owns 'prev'. |
| 354 | 🟢 LOW | Feature Envy | Method 'SequenceValidator._validate_no_duplicate_consecutive_messages' accesses 'curr' 4 times but 'self' only 0 times | Move Method — consider moving '_validate_no_duplicate_consecutive_messages' to the class that owns 'curr'. |
| 354 | 🟢 LOW | Feature Envy | Method 'SequenceValidator._validate_no_duplicate_consecutive_messages' accesses 'prev' 4 times but 'self' only 0 times | Move Method — consider moving '_validate_no_duplicate_consecutive_messages' to the class that owns 'prev'. |
| 510 | 🟢 LOW | Feature Envy | Method 'MessagePreserver._preserve_tool_call_sequences' accesses 'curr_msg' 3 times but 'self' only 0 times | Move Method — consider moving '_preserve_tool_call_sequences' to the class that owns 'curr_msg'. |
| 510 | 🟢 LOW | Feature Envy | Method 'MessagePreserver._preserve_tool_call_sequences' accesses 'next_msg' 3 times but 'self' only 0 times | Move Method — consider moving '_preserve_tool_call_sequences' to the class that owns 'next_msg'. |

### utils/validation.py — 🔶 D (69.7/100)

LOC: 192 | Classes: 0 | Functions: 5 | MI: 60 | Avg CC: 11.5

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 12 | 🟡 MEDIUM | Long Method | Function 'validate_message_sequence' has 62 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 12 | 🟡 MEDIUM | Complex Function | Function 'validate_message_sequence' has cyclomatic complexity 11 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 122 | 🟡 MEDIUM | Long Method | Function 'repair_message_sequence' has 71 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 122 | 🟡 MEDIUM | Complex Function | Function 'repair_message_sequence' has cyclomatic complexity 12 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 43 | 🟢 LOW | Deep Nesting | Nesting depth 4 in 'validate_message_sequence' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 53 | 🟢 LOW | Deep Nesting | Nesting depth 4 in 'validate_message_sequence' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 242 | 🟢 LOW | Magic Number | Magic number 50 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |

### agents/metrics_reporter.py — ⚠️ C (70.1/100)

LOC: 251 | Classes: 2 | Functions: 4 | MI: 56 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 32 | 🟡 MEDIUM | Duplicate Code | Function '_build_metrics_section' is 100% similar to '_format_findings' at tools/builtins/dead_code.py:597 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 257 | 🟡 MEDIUM | Duplicate Code | Function '_format_documentation_coverage' is 94% similar to '_str_payload' at cli/textual_messages.py:38 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 264 | 🟡 MEDIUM | Duplicate Code | Function '_format_tool_call_statistics' is 93% similar to 'list_themes' at cli/console.py:367 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 264 | 🟡 MEDIUM | Duplicate Code | Function '_format_tool_call_statistics' is 93% similar to 'list_auto_approve_policies' at tools/registry.py:195 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 191 | 🟢 LOW | Feature Envy | Method 'MetricsReporter._format_task_completion_time' accesses 'time' 4 times but 'self' only 2 times | Move Method — consider moving '_format_task_completion_time' to the class that owns 'time'. |
| 202 | 🟢 LOW | Magic Number | Magic number 60 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |

### cli/commands/context.py — ⚠️ C (70.1/100)

LOC: 549 | Classes: 7 | Functions: 11 | MI: 47 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 130 | 🟡 MEDIUM | Duplicate Code | Function '__init__' is 100% similar to '__init__' at cli/json_output.py:69 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 130 | 🟡 MEDIUM | Duplicate Code | Function '__init__' is 100% similar to '__init__' at tools/builtins/coverage_map.py:394 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 130 | 🟡 MEDIUM | Duplicate Code | Function '__init__' is 100% similar to '__init__' at tools/security/shell_secure.py:442 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 536 | 🟡 MEDIUM | Duplicate Code | Function '_show_help_message' is 94% similar to '_list_themes' at cli/commands/theme.py:206 | Extract Shared Function — identify the common logic and parameterise the differences. |

### utils/tokens.py — ⚠️ C (70.7/100)

LOC: 125 | Classes: 1 | Functions: 1 | MI: 70 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 139 | 🟡 MEDIUM | Feature Envy | Method 'TokenCounter.count_messages' accesses 'msg' 5 times but 'self' only 0 times | Move Method — consider moving 'count_messages' to the class that owns 'msg'. |
| 70 | 🟢 LOW | Missing Type Hint | Function '_get_encoding' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 70 | 🟢 LOW | Feature Envy | Method 'TokenCounter._get_encoding' accesses 'tiktoken' 3 times but 'self' only 0 times | Move Method — consider moving '_get_encoding' to the class that owns 'tiktoken'. |
| 70 | 🟢 LOW | Feature Envy | Method 'TokenCounter._get_encoding' accesses 'cls' 3 times but 'self' only 0 times | Move Method — consider moving '_get_encoding' to the class that owns 'cls'. |
| 98 | 🟢 LOW | Missing Type Hint | Function 'count_text' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 115 | 🟢 LOW | Missing Type Hint | Function 'truncate_text' has incomplete type hints: 1/4 params untyped | Add Type Annotations for all parameters and return type. |
| 115 | 🟢 LOW | Primitive Obsession | Function 'truncate_text' has 3 primitive-typed parameters: text: Name(id='str', ctx=Load()), max_tokens: Name(id='int', ctx=Load()), model: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 139 | 🟢 LOW | Long Method | Function 'count_messages' has 39 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 139 | 🟢 LOW | Missing Type Hint | Function 'count_messages' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 139 | 🟢 LOW | Feature Envy | Method 'TokenCounter.count_messages' accesses 'encoding' 4 times but 'self' only 0 times | Move Method — consider moving 'count_messages' to the class that owns 'encoding'. |
| 158 | 🟢 LOW | Magic Number | Magic number 3 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 181 | 🟢 LOW | Magic Number | Magic number 10 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 188 | 🟢 LOW | Magic Number | Magic number 3 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |

## ✨ Clean Files (77 files with no smells)

<details><summary>Click to expand</summary>

- __init__.py — ✅ A
- __main__.py — ✅ A
- agents/__init__.py — ✅ A
- agents/config.py — ✅ A
- agents/orchestrator_components.py — ✅ A
- agents/orchestrator_events.py — ✅ A
- agents/orchestrator_init.py — ✅ A
- agents/orchestrator_loop.py — ✅ A
- agents/orchestrator_prompts.py — ✅ A
- agents/orchestrator_run.py — ✅ A
- agents/orchestrator_tech_lead.py — ✅ A
- agents/orchestrator_timeout.py — ✅ A
- agents/orchestrator_tools.py — ✅ A
- agents/orchestrator_turns.py — ✅ A
- agents/orchestrator_types.py — 👍 B
- agents/orchestrator_validation.py — ✅ A
- api/__init__.py — ✅ A
- api/auth.py — ✅ A
- api/endpoints/__init__.py — ✅ A
- cli/__init__.py — ✅ A
- cli/app.py — 👍 B
- cli/commands/__init__.py — 👍 B
- cli/commands/model.py — 👍 B
- cli/commands/plan.py — ✅ A
- cli/commands/rag.py — 👍 B
- cli/commands/team.py — ✅ A
- cli/input.py — 👍 B
- cli/prompts.py — ✅ A
- cli/stream_event_handlers.py — 👍 B
- config/__init__.py — ✅ A
- config/settings.py — 👍 B
- core/__init__.py — ✅ A
- core/agent_stall.py — ✅ A
- core/events.py — ✅ A
- core/session.py — ✅ A
- core/session_branch.py — ✅ A
- core/session_export.py — ✅ A
- core/session_helpers.py — ✅ A
- core/session_manager.py — ✅ A
- core/session_merge.py — ✅ A
- core/session_models.py — ✅ A
- core/session_templates.py — ✅ A
- extensions/__init__.py — ✅ A
- extensions/constants.py — ✅ A
- extensions/models.py — 👍 B
- extensions/plugin_registry_client.py — ✅ A
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
- tools/builtins/dead_code.py — 👍 B
- tools/builtins/delegate.py — ✅ A
- tools/builtins/kg_common.py — ✅ A
- tools/builtins/pytest_run.py — 👍 B
- tools/builtins/python_ast.py — ✅ A
- tools/builtins/test_gen.py — 👍 B
- tools/security/__init__.py — ✅ A
- tools/utils.py — ✅ A
- utils/__init__.py — ✅ A
- utils/cluster_utils.py — ✅ A
- utils/intelligent_context_config.py — ✅ A
- utils/intelligent_context_detector.py — ✅ A
- utils/intelligent_context_extractor.py — 👍 B
- utils/intelligent_context_parser.py — ⚠️ C
- utils/intelligent_context_summarizer.py — ✅ A
- utils/intelligent_context_topic_extractor.py — ✅ A
- utils/intelligent_context_types.py — 👍 B
- utils/lazy_import.py — ✅ A
- utils/message_analyzer.py — ✅ A
- utils/sorting_utils.py — ✅ A
- version.py — ✅ A

</details>

---

_Report generated by XP Code Smell Detector. Smells are static heuristics — use judgement when prioritising fixes._
