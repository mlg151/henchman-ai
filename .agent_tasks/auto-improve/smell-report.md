# Code Smell Report — ⚠️ C (Score: 75.1/100)

_Scanned: /home/matthew/mlg-cli/src/henchman_  

_Generated: 2026-03-03T18:30:32.655488+00:00_

## Executive Summary

| Metric | Value |
|:-------|------:|
| **Overall Grade** | ⚠️ C |
| **Overall Score** | 75.1/100 |
| **Files Scanned** | 193 |
| **Total Lines (non-blank)** | 36,839 |
| **Total Smells** | 755 |
| **Avg Maintainability Index** | 71.6 |
| **Avg Cyclomatic Complexity** | 13.7 |

### Smells by Severity

| Severity | Count |
|:---------|------:|
| low | 511 |
| medium | 213 |
| high | 31 |

### Smells by Category

| Category | Count |
|:---------|------:|
| Missing Type Hint | 222 |
| Duplicate Code | 158 |
| Feature Envy | 123 |
| Long Method | 83 |
| Magic Number | 53 |
| Primitive Obsession | 44 |
| Deep Nesting | 40 |
| Complex Function | 21 |
| Large Class | 11 |

## 🎯 Prioritised Refactoring Queue

These are the highest-impact smells to address first:

1. **cli/app.py:656** — 🟠 HIGH — Primitive Obsession  
   Function 'chat_command' has 8 primitive-typed parameters: prompt: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), agent: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), team: Name(id='bool', ctx=Load()), output_format: Name(id='str', ctx=Load()), plan: Name(id='bool', ctx=Load()), yes: Name(id='bool', ctx=Load()), tui: Name(id='bool', ctx=Load()), debug: Name(id='bool', ctx=Load())  
   → _Introduce Parameter Object — group related primitives into a dataclass or NamedTuple._

2. **cli/commands/builtins.py:294** — 🟠 HIGH — Duplicate Code  
   Function 'execute' is an exact duplicate of '_list_themes' at cli/commands/theme.py:202  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

3. **cli/commands/plan.py:41** — 🟠 HIGH — Feature Envy  
   Method 'PlanCommand.execute' accesses 'ctx' 11 times but 'self' only 0 times  
   → _Move Method — consider moving 'execute' to the class that owns 'ctx'._

4. **cli/json_output.py:43** — 🟠 HIGH — Duplicate Code  
   Function 'render' is an exact duplicate of 'render_stream_json' at cli/json_output.py:77  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

5. **knowledge/scanner.py:198** — 🟠 HIGH — Long Method  
   Function 'scan_repository' has 94 lines (threshold: 30)  
   → _Extract Method — break this function into smaller, intention-revealing helper functions._

6. **metrics/exporter.py:80** — 🟠 HIGH — Duplicate Code  
   Function 'export_to_csv' is an exact duplicate of 'export_to_prometheus' at metrics/exporter.py:94  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

7. **providers/anthropic.py:427** — 🟠 HIGH — Duplicate Code  
   Function '_format_tool' is an exact duplicate of '_format_tool' at providers/openai_compat.py:129  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

8. **providers/anthropic.py:427** — 🟠 HIGH — Duplicate Code  
   Function '_format_tool' is an exact duplicate of '_format_message' at providers/openai_compat.py:136  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

9. **providers/anthropic.py:582** — 🟠 HIGH — Duplicate Code  
   Function '_validate_messages' is an exact duplicate of '_validate_messages' at providers/openai_compat.py:196  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

10. **providers/openai_compat.py:129** — 🟠 HIGH — Duplicate Code  
   Function '_format_tool' is an exact duplicate of '_format_message' at providers/openai_compat.py:136  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

11. **tools/builtins/code_format.py:49** — 🟠 HIGH — Long Method  
   Function 'execute' has 94 lines (threshold: 30)  
   → _Extract Method — break this function into smaller, intention-revealing helper functions._

12. **tools/builtins/delegate.py:157** — 🟠 HIGH — Duplicate Code  
   Function 'parameters' is an exact duplicate of 'parameters' at tools/builtins/file_edit.py:158  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

13. **tools/builtins/delegate.py:157** — 🟠 HIGH — Duplicate Code  
   Function 'parameters' is an exact duplicate of 'parameters' at tools/builtins/git_ops.py:254  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

14. **tools/builtins/delegate.py:157** — 🟠 HIGH — Duplicate Code  
   Function 'parameters' is an exact duplicate of 'parameters' at tools/builtins/python_ast.py:53  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

15. **tools/builtins/delegate.py:157** — 🟠 HIGH — Duplicate Code  
   Function 'parameters' is an exact duplicate of 'parameters' at tools/builtins/shell.py:639  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._


## 📊 Files Ranked by Quality

| Rank | File | Grade | Score | Smells | LOC | MI | Avg CC |
|-----:|:-----|:------|------:|-------:|----:|---:|-------:|
| 1 | providers/anthropic.py | ❌ F | 53.6 | 5 | 542 | 39 | 0.0 |
| 2 | utils/compaction.py | ❌ F | 54.3 | 13 | 770 | 29 | 11.0 |
| 3 | cli/commands/session.py | ❌ F | 55.7 | 7 | 836 | 34 | 0.0 |
| 4 | tools/builtins/delegate.py | ❌ F | 55.7 | 5 | 158 | 69 | 0.0 |
| 5 | tools/builtins/file_edit.py | ❌ F | 55.9 | 6 | 283 | 56 | 0.0 |
| 6 | extensions/plugin_manager.py | ❌ F | 56.6 | 17 | 293 | 56 | 12.0 |
| 7 | agents/ledger.py | ❌ F | 58.1 | 16 | 167 | 63 | 13.5 |
| 8 | tools/builtins/coverage_map.py | ❌ F | 59.0 | 14 | 492 | 43 | 0.0 |
| 9 | cli/commands/rag.py | ❌ F | 59.2 | 16 | 171 | 60 | 0.0 |
| 10 | tools/builtins/python_exec.py | ❌ F | 59.2 | 13 | 129 | 67 | 12.0 |

## 📁 Per-File Details

_Showing 20 worst files. 173 additional files omitted._

### providers/anthropic.py — ❌ F (53.6/100)

LOC: 542 | Classes: 5 | Functions: 6 | MI: 39 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 427 | 🟠 HIGH | Duplicate Code | Function '_format_tool' is an exact duplicate of '_format_tool' at providers/openai_compat.py:129 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 427 | 🟠 HIGH | Duplicate Code | Function '_format_tool' is an exact duplicate of '_format_message' at providers/openai_compat.py:136 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 582 | 🟠 HIGH | Duplicate Code | Function '_validate_messages' is an exact duplicate of '_validate_messages' at providers/openai_compat.py:196 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 130 | 🟡 MEDIUM | Duplicate Code | Function '_format_tool_for_anthropic' is 100% similar to 'to_metadata' at rag/chunker.py:42 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 538 | 🟡 MEDIUM | Duplicate Code | Function '_parse_finish_reason' is 100% similar to '_parse_finish_reason' at providers/openai_compat.py:143 | Extract Shared Function — identify the common logic and parameterise the differences. |

### utils/compaction.py — ❌ F (54.3/100)

LOC: 770 | Classes: 9 | Functions: 7 | MI: 29 | Avg CC: 11.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 554 | 🟡 MEDIUM | Duplicate Code | Function '_group_into_sequences' is 95% similar to '_cluster_messages' at utils/intelligent_context.py:445 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 930 | 🟡 MEDIUM | Primitive Obsession | Function 'compact_with_summarization' has 4 primitive-typed parameters: max_tokens: Name(id='int', ctx=Load()), summarize: Name(id='bool', ctx=Load()), protect_from_index: Name(id='int', ctx=Load()), max_protected_ratio: Name(id='float', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 1003 | 🟡 MEDIUM | Complex Function | Function '_attempt_summarization' has cyclomatic complexity 11 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 80 | 🟢 LOW | Magic Number | Magic number 0.3 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 260 | 🟢 LOW | Feature Envy | Method 'ProtectedZoneManager._truncate_protected_zone' accesses 'result' 3 times but 'self' only 0 times | Move Method — consider moving '_truncate_protected_zone' to the class that owns 'result'. |
| 415 | 🟢 LOW | Feature Envy | Method 'MessageSequenceValidator._is_valid_tool_message' accesses 'prev_msg' 3 times but 'self' only 0 times | Move Method — consider moving '_is_valid_tool_message' to the class that owns 'prev_msg'. |
| 441 | 🟢 LOW | Feature Envy | Method 'MessageSequenceValidator._all_tool_calls_have_responses' accesses 'msg' 3 times but 'self' only 0 times | Move Method — consider moving '_all_tool_calls_have_responses' to the class that owns 'msg'. |
| 456 | 🟢 LOW | Deep Nesting | Nesting depth 4 in '_all_tool_calls_have_responses' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 565 | 🟢 LOW | Long Method | Function 'compact' has 40 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 660 | 🟢 LOW | Feature Envy | Method 'ContextCompactor._select_sequences_to_keep' accesses 'last_sequence' 3 times but 'self' only 1 times | Move Method — consider moving '_select_sequences_to_keep' to the class that owns 'last_sequence'. |
| 708 | 🟢 LOW | Feature Envy | Method 'ContextCompactor._reconstruct_result' accesses 'result' 4 times but 'self' only 0 times | Move Method — consider moving '_reconstruct_result' to the class that owns 'result'. |
| 811 | 🟢 LOW | Magic Number | Magic number 200 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 812 | 🟢 LOW | Magic Number | Magic number 500 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |

### cli/commands/session.py — ❌ F (55.7/100)

LOC: 836 | Classes: 17 | Functions: 13 | MI: 34 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 142 | 🟡 MEDIUM | Duplicate Code | Function 'print_info' is 94% similar to '_print_set_theme_error' at cli/commands/theme.py:230 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 150 | 🟡 MEDIUM | Duplicate Code | Function 'print_usage' is 94% similar to '_render_diff' at cli/console.py:661 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 150 | 🟡 MEDIUM | Duplicate Code | Function 'print_usage' is 100% similar to '_add_message_with_prefix' at cli/textual_widgets.py:915 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 150 | 🟡 MEDIUM | Duplicate Code | Function 'print_usage' is 100% similar to 'register' at extensions/manager.py:154 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 261 | 🟡 MEDIUM | Duplicate Code | Function '_ensure_args' is 94% similar to 'add_thinking_message' at cli/textual_widgets.py:1012 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 261 | 🟡 MEDIUM | Duplicate Code | Function '_ensure_args' is 100% similar to 'save' at core/session_manager_base.py:102 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 983 | 🟡 MEDIUM | Duplicate Code | Function '_validate_min_args' is 100% similar to '_enforce_message_safety' at utils/compaction.py:542 | Extract Shared Function — identify the common logic and parameterise the differences. |

### tools/builtins/delegate.py — ❌ F (55.7/100)

LOC: 158 | Classes: 2 | Functions: 1 | MI: 69 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 157 | 🟠 HIGH | Duplicate Code | Function 'parameters' is an exact duplicate of 'parameters' at tools/builtins/file_edit.py:158 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 157 | 🟠 HIGH | Duplicate Code | Function 'parameters' is an exact duplicate of 'parameters' at tools/builtins/git_ops.py:254 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 157 | 🟠 HIGH | Duplicate Code | Function 'parameters' is an exact duplicate of 'parameters' at tools/builtins/python_ast.py:53 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 157 | 🟠 HIGH | Duplicate Code | Function 'parameters' is an exact duplicate of 'parameters' at tools/builtins/shell.py:639 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 157 | 🟠 HIGH | Duplicate Code | Function 'parameters' is an exact duplicate of 'parameters' at tools/security/shell_secure.py:506 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |

### tools/builtins/file_edit.py — ❌ F (55.9/100)

LOC: 283 | Classes: 2 | Functions: 6 | MI: 56 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 158 | 🟠 HIGH | Duplicate Code | Function 'parameters' is an exact duplicate of 'parameters' at tools/builtins/git_ops.py:254 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 158 | 🟠 HIGH | Duplicate Code | Function 'parameters' is an exact duplicate of 'parameters' at tools/builtins/python_ast.py:53 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 158 | 🟠 HIGH | Duplicate Code | Function 'parameters' is an exact duplicate of 'parameters' at tools/builtins/shell.py:639 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 158 | 🟠 HIGH | Duplicate Code | Function 'parameters' is an exact duplicate of 'parameters' at tools/security/shell_secure.py:506 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 183 | 🟢 LOW | Long Method | Function '_apply_edit' has 39 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 275 | 🟢 LOW | Long Method | Function '_edit_line_range' has 40 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |

### extensions/plugin_manager.py — ❌ F (56.6/100)

LOC: 293 | Classes: 1 | Functions: 0 | MI: 56 | Avg CC: 12.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 113 | 🟡 MEDIUM | Primitive Obsession | Function 'search_plugins' has 4 primitive-typed parameters: query: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), page: Name(id='int', ctx=Load()), page_size: Name(id='int', ctx=Load()), category: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 170 | 🟡 MEDIUM | Long Method | Function 'install_plugin' has 57 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 170 | 🟡 MEDIUM | Complex Function | Function 'install_plugin' has cyclomatic complexity 12 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 30 | 🟢 LOW | Large Class | Class 'PluginManager' spans 380 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
| 47 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 68 | 🟢 LOW | Missing Type Hint | Function 'initialize' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 104 | 🟢 LOW | Missing Type Hint | Function 'close' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 113 | 🟢 LOW | Missing Type Hint | Function 'search_plugins' has incomplete type hints: 1/5 params untyped | Add Type Annotations for all parameters and return type. |
| 146 | 🟢 LOW | Missing Type Hint | Function 'get_plugin_info' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 170 | 🟢 LOW | Missing Type Hint | Function 'install_plugin' has incomplete type hints: 1/4 params untyped | Add Type Annotations for all parameters and return type. |
| 170 | 🟢 LOW | Primitive Obsession | Function 'install_plugin' has 3 primitive-typed parameters: plugin_name: Name(id='str', ctx=Load()), version: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), confirm_permissions: Name(id='bool', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 249 | 🟢 LOW | Missing Type Hint | Function 'uninstall_plugin' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 284 | 🟢 LOW | Missing Type Hint | Function 'update_plugin' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 323 | 🟢 LOW | Missing Type Hint | Function 'check_updates' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 345 | 🟢 LOW | Missing Type Hint | Function 'scan_security' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |

_... and 2 more smells._

### agents/ledger.py — ❌ F (58.1/100)

LOC: 167 | Classes: 4 | Functions: 0 | MI: 63 | Avg CC: 13.5

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 79 | 🟡 MEDIUM | Duplicate Code | Function 'add_checklist_item' is 92% similar to 'add_delegation' at agents/ledger.py:107 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 121 | 🟡 MEDIUM | Duplicate Code | Function 'complete_delegation' is 100% similar to 'fail_delegation' at agents/ledger.py:131 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 149 | 🟡 MEDIUM | Complex Function | Function 'mission_recap' has cyclomatic complexity 11 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 176 | 🟡 MEDIUM | Complex Function | Function 'render' has cyclomatic complexity 16 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 79 | 🟢 LOW | Missing Type Hint | Function 'add_checklist_item' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 92 | 🟢 LOW | Missing Type Hint | Function 'check_item' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 107 | 🟢 LOW | Missing Type Hint | Function 'add_delegation' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 121 | 🟢 LOW | Missing Type Hint | Function 'complete_delegation' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 129 | 🟢 LOW | Magic Number | Magic number 500 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 131 | 🟢 LOW | Missing Type Hint | Function 'fail_delegation' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 139 | 🟢 LOW | Magic Number | Magic number 500 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 141 | 🟢 LOW | Missing Type Hint | Function 'mark_verified' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 149 | 🟢 LOW | Missing Type Hint | Function 'mission_recap' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 176 | 🟢 LOW | Long Method | Function 'render' has 49 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 176 | 🟢 LOW | Missing Type Hint | Function 'render' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |

_... and 1 more smells._

### tools/builtins/coverage_map.py — ❌ F (59.0/100)

LOC: 492 | Classes: 7 | Functions: 0 | MI: 43 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 530 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/dead_code.py:343 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 530 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/import_graph.py:446 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 83 | 🟢 LOW | Feature Envy | Method 'CoverageFormatter._format_file_entry' accesses 'CoverageFormatter' 3 times but 'self' only 0 times | Move Method — consider moving '_format_file_entry' to the class that owns 'CoverageFormatter'. |
| 97 | 🟢 LOW | Magic Number | Magic number 100 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 144 | 🟢 LOW | Magic Number | Magic number 100 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 165 | 🟢 LOW | Magic Number | Magic number 100 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 201 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: missing return type | Add Type Annotations for all parameters and return type. |
| 331 | 🟢 LOW | Feature Envy | Method 'XmlCoverageParser._parse_class' accesses 'cls' 3 times but 'self' only 2 times | Move Method — consider moving '_parse_class' to the class that owns 'cls'. |
| 331 | 🟢 LOW | Feature Envy | Method 'XmlCoverageParser._parse_class' accesses 'config' 4 times but 'self' only 2 times | Move Method — consider moving '_parse_class' to the class that owns 'config'. |
| 374 | 🟢 LOW | Feature Envy | Method 'XmlCoverageParser._parse_lines' accesses 'line' 3 times but 'self' only 1 times | Move Method — consider moving '_parse_lines' to the class that owns 'line'. |
| 445 | 🟢 LOW | Feature Envy | Method 'JsonCoverageParser._parse_file' accesses 'config' 4 times but 'self' only 2 times | Move Method — consider moving '_parse_file' to the class that owns 'config'. |
| 560 | 🟢 LOW | Long Method | Function 'execute' has 38 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 560 | 🟢 LOW | Feature Envy | Method 'CoverageMapTool.execute' accesses 'params' 4 times but 'self' only 0 times | Move Method — consider moving 'execute' to the class that owns 'params'. |
| 560 | 🟢 LOW | Feature Envy | Method 'CoverageMapTool.execute' accesses 'target' 3 times but 'self' only 0 times | Move Method — consider moving 'execute' to the class that owns 'target'. |

### cli/commands/rag.py — ❌ F (59.2/100)

LOC: 171 | Classes: 1 | Functions: 0 | MI: 60 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 91 | 🟡 MEDIUM | Feature Envy | Method 'RagCommand._status' accesses 'console' 9 times but 'self' only 1 times | Move Method — consider moving '_status' to the class that owns 'console'. |
| 153 | 🟡 MEDIUM | Feature Envy | Method 'RagCommand._clear_all' accesses 'console' 6 times but 'self' only 0 times | Move Method — consider moving '_clear_all' to the class that owns 'console'. |
| 181 | 🟡 MEDIUM | Feature Envy | Method 'RagCommand._cleanup' accesses 'console' 6 times but 'self' only 0 times | Move Method — consider moving '_cleanup' to the class that owns 'console'. |
| 30 | 🟢 LOW | Missing Type Hint | Function 'name' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 39 | 🟢 LOW | Missing Type Hint | Function 'description' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 48 | 🟢 LOW | Missing Type Hint | Function 'usage' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 56 | 🟢 LOW | Missing Type Hint | Function 'execute' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 76 | 🟢 LOW | Missing Type Hint | Function '_get_rag_system' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 91 | 🟢 LOW | Missing Type Hint | Function '_status' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 91 | 🟢 LOW | Feature Envy | Method 'RagCommand._status' accesses 'rag_system' 4 times but 'self' only 1 times | Move Method — consider moving '_status' to the class that owns 'rag_system'. |
| 115 | 🟢 LOW | Missing Type Hint | Function '_reindex' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 115 | 🟢 LOW | Feature Envy | Method 'RagCommand._reindex' accesses 'console' 4 times but 'self' only 1 times | Move Method — consider moving '_reindex' to the class that owns 'console'. |
| 139 | 🟢 LOW | Missing Type Hint | Function '_clear' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 153 | 🟢 LOW | Missing Type Hint | Function '_clear_all' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 181 | 🟢 LOW | Long Method | Function '_cleanup' has 34 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |

_... and 1 more smells._

### tools/builtins/python_exec.py — ❌ F (59.2/100)

LOC: 129 | Classes: 1 | Functions: 0 | MI: 67 | Avg CC: 12.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 35 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 96% similar to 'parameters' at tools/builtins/web_fetch.py:32 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 35 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 96% similar to 'parameters' at tools/builtins/web_search.py:27 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 62 | 🟡 MEDIUM | Long Method | Function 'execute' has 73 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 62 | 🟡 MEDIUM | Feature Envy | Method 'PythonExecTool.execute' accesses 'asyncio' 5 times but 'self' only 0 times | Move Method — consider moving 'execute' to the class that owns 'asyncio'. |
| 62 | 🟡 MEDIUM | Feature Envy | Method 'PythonExecTool.execute' accesses 'process' 6 times but 'self' only 0 times | Move Method — consider moving 'execute' to the class that owns 'process'. |
| 62 | 🟡 MEDIUM | Complex Function | Function 'execute' has cyclomatic complexity 12 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 21 | 🟢 LOW | Missing Type Hint | Function 'name' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 26 | 🟢 LOW | Missing Type Hint | Function 'description' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 35 | 🟢 LOW | Missing Type Hint | Function 'parameters' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 47 | 🟢 LOW | Magic Number | Magic number 30 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 58 | 🟢 LOW | Missing Type Hint | Function 'kind' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 62 | 🟢 LOW | Missing Type Hint | Function 'execute' has incomplete type hints: 1/5 params untyped | Add Type Annotations for all parameters and return type. |
| 62 | 🟢 LOW | Primitive Obsession | Function 'execute' has 3 primitive-typed parameters: code: Name(id='str', ctx=Load()), timeout: Name(id='int', ctx=Load()), cwd: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |

### cli/commands/mcp.py — ❌ F (59.7/100)

LOC: 137 | Classes: 1 | Functions: 0 | MI: 61 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 78 | 🟡 MEDIUM | Feature Envy | Method 'McpCommand._list' accesses 'console' 5 times but 'self' only 0 times | Move Method — consider moving '_list' to the class that owns 'console'. |
| 102 | 🟡 MEDIUM | Feature Envy | Method 'McpCommand._status' accesses 'console' 7 times but 'self' only 3 times | Move Method — consider moving '_status' to the class that owns 'console'. |
| 150 | 🟡 MEDIUM | Feature Envy | Method 'McpCommand._handle_logging_action' accesses 'console' 5 times but 'self' only 0 times | Move Method — consider moving '_handle_logging_action' to the class that owns 'console'. |
| 32 | 🟢 LOW | Missing Type Hint | Function 'name' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 41 | 🟢 LOW | Missing Type Hint | Function 'description' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 50 | 🟢 LOW | Missing Type Hint | Function 'usage' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 58 | 🟢 LOW | Missing Type Hint | Function 'execute' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 78 | 🟢 LOW | Missing Type Hint | Function '_list' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 78 | 🟢 LOW | Feature Envy | Method 'McpCommand._list' accesses 'manager' 3 times but 'self' only 0 times | Move Method — consider moving '_list' to the class that owns 'manager'. |
| 102 | 🟢 LOW | Missing Type Hint | Function '_status' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 125 | 🟢 LOW | Missing Type Hint | Function '_logging' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 138 | 🟢 LOW | Missing Type Hint | Function '_print_logging_help' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 138 | 🟢 LOW | Feature Envy | Method 'McpCommand._print_logging_help' accesses 'console' 4 times but 'self' only 0 times | Move Method — consider moving '_print_logging_help' to the class that owns 'console'. |
| 150 | 🟢 LOW | Missing Type Hint | Function '_handle_logging_action' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 150 | 🟢 LOW | Feature Envy | Method 'McpCommand._handle_logging_action' accesses 'ctx' 4 times but 'self' only 0 times | Move Method — consider moving '_handle_logging_action' to the class that owns 'ctx'. |

_... and 1 more smells._

### tools/builtins/patch_apply.py — ❌ F (59.7/100)

LOC: 466 | Classes: 5 | Functions: 0 | MI: 43 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 131 | 🟡 MEDIUM | Feature Envy | Method 'HunkApplier._apply_hunk_with_context' accesses 'context' 5 times but 'self' only 3 times | Move Method — consider moving '_apply_hunk_with_context' to the class that owns 'context'. |
| 428 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at tools/builtins/pytest_run.py:134 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 462 | 🟡 MEDIUM | Primitive Obsession | Function 'execute' has 4 primitive-typed parameters: patch: Name(id='str', ctx=Load()), path: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), dry_run: Name(id='bool', ctx=Load()), fuzz: Name(id='int', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 99 | 🟢 LOW | Primitive Obsession | Function '_apply_single_hunk' has 3 primitive-typed parameters: hunk_idx: Name(id='int', ctx=Load()), offset: Name(id='int', ctx=Load()), fuzz: Name(id='int', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 168 | 🟢 LOW | Feature Envy | Method 'HunkApplier._extract_old_and_new_lines' accesses 'line' 3 times but 'self' only 0 times | Move Method — consider moving '_extract_old_and_new_lines' to the class that owns 'line'. |
| 178 | 🟢 LOW | Deep Nesting | Nesting depth 4 in '_extract_old_and_new_lines' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 319 | 🟢 LOW | Magic Number | Magic number 4 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 359 | 🟢 LOW | Feature Envy | Method 'PatchParser._parse_hunk_header' accesses 'match' 4 times but 'self' only 0 times | Move Method — consider moving '_parse_hunk_header' to the class that owns 'match'. |
| 373 | 🟢 LOW | Magic Number | Magic number 3 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 374 | 🟢 LOW | Magic Number | Magic number 4 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 525 | 🟢 LOW | Primitive Obsession | Function '_apply_patch_to_single_file' has 3 primitive-typed parameters: file_path: Name(id='str', ctx=Load()), dry_run: Name(id='bool', ctx=Load()), fuzz: Name(id='int', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 525 | 🟢 LOW | Feature Envy | Method 'PatchApplyTool._apply_patch_to_single_file' accesses 'target' 3 times but 'self' only 0 times | Move Method — consider moving '_apply_patch_to_single_file' to the class that owns 'target'. |

### cli/textual_screens.py — ❌ F (59.8/100)

LOC: 373 | Classes: 4 | Functions: 0 | MI: 52 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 87 | 🟡 MEDIUM | Duplicate Code | Function '__init__' is 95% similar to '__init__' at mcp/client.py:33 | Extract Shared Function — identify the common logic and parameterise the differences. |
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

_... and 2 more smells._

### cli/commands/__init__.py — 🔶 D (61.0/100)

LOC: 161 | Classes: 4 | Functions: 2 | MI: 63 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 138 | 🟡 MEDIUM | Duplicate Code | Function '__init__' is 100% similar to '__init__' at extensions/manager.py:150 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 142 | 🟡 MEDIUM | Duplicate Code | Function 'register' is 100% similar to 'register_theme' at cli/console.py:372 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 150 | 🟡 MEDIUM | Duplicate Code | Function 'get' is 100% similar to 'get' at extensions/manager.py:177 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 150 | 🟡 MEDIUM | Duplicate Code | Function 'get' is 100% similar to 'get' at tools/registry.py:108 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 161 | 🟡 MEDIUM | Duplicate Code | Function 'get_commands' is 100% similar to 'list_extensions' at extensions/manager.py:188 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 161 | 🟡 MEDIUM | Duplicate Code | Function 'get_commands' is 100% similar to 'get_server_names' at mcp/manager.py:38 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 161 | 🟡 MEDIUM | Duplicate Code | Function 'get_commands' is 100% similar to 'list_providers' at providers/registry.py:47 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 161 | 🟡 MEDIUM | Duplicate Code | Function 'get_commands' is 100% similar to 'list_tools' at tools/registry.py:127 | Extract Shared Function — identify the common logic and parameterise the differences. |

### mcp/manager.py — 🔶 D (63.0/100)

LOC: 165 | Classes: 1 | Functions: 0 | MI: 65 | Avg CC: 11.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 38 | 🟡 MEDIUM | Duplicate Code | Function 'get_server_names' is 100% similar to 'list_providers' at providers/registry.py:47 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 38 | 🟡 MEDIUM | Duplicate Code | Function 'get_server_names' is 100% similar to 'list_tools' at tools/registry.py:127 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 124 | 🟡 MEDIUM | Feature Envy | Method 'McpManager._build_logging_env' accesses 'command' 5 times but 'self' only 0 times | Move Method — consider moving '_build_logging_env' to the class that owns 'command'. |
| 124 | 🟡 MEDIUM | Complex Function | Function '_build_logging_env' has cyclomatic complexity 11 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 26 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 38 | 🟢 LOW | Missing Type Hint | Function 'get_server_names' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 46 | 🟢 LOW | Missing Type Hint | Function 'is_trusted' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 59 | 🟢 LOW | Missing Type Hint | Function 'connect_all' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 83 | 🟢 LOW | Missing Type Hint | Function 'disconnect_all' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 90 | 🟢 LOW | Missing Type Hint | Function 'get_all_tools' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 98 | 🟢 LOW | Missing Type Hint | Function 'call_tool' has incomplete type hints: 1/4 params untyped | Add Type Annotations for all parameters and return type. |
| 124 | 🟢 LOW | Long Method | Function '_build_logging_env' has 35 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 176 | 🟢 LOW | Feature Envy | Method 'McpManager.create_from_settings' accesses 'server_config' 4 times but 'self' only 0 times | Move Method — consider moving 'create_from_settings' to the class that owns 'server_config'. |

### tools/builtins/git_ops.py — 🔶 D (63.2/100)

LOC: 269 | Classes: 2 | Functions: 8 | MI: 52 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 254 | 🟠 HIGH | Duplicate Code | Function 'parameters' is an exact duplicate of 'parameters' at tools/builtins/python_ast.py:53 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 254 | 🟠 HIGH | Duplicate Code | Function 'parameters' is an exact duplicate of 'parameters' at tools/builtins/shell.py:639 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 254 | 🟠 HIGH | Duplicate Code | Function 'parameters' is an exact duplicate of 'parameters' at tools/security/shell_secure.py:506 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 263 | 🟢 LOW | Feature Envy | Method 'GitOpsTool.execute' accesses 'params' 4 times but 'self' only 1 times | Move Method — consider moving 'execute' to the class that owns 'params'. |

### cli/app.py — 🔶 D (63.6/100)

LOC: 567 | Classes: 2 | Functions: 22 | MI: 46 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 656 | 🟠 HIGH | Primitive Obsession | Function 'chat_command' has 8 primitive-typed parameters: prompt: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), agent: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), team: Name(id='bool', ctx=Load()), output_format: Name(id='str', ctx=Load()), plan: Name(id='bool', ctx=Load()), yes: Name(id='bool', ctx=Load()), tui: Name(id='bool', ctx=Load()), debug: Name(id='bool', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 236 | 🟡 MEDIUM | Long Method | Function '_run_interactive' has 54 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 480 | 🟡 MEDIUM | Duplicate Code | Function '_run_headless_json' is 100% similar to '_run_headless_stream_json' at cli/app.py:515 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 493 | 🟡 MEDIUM | Duplicate Code | Function 'run_and_render' is 100% similar to 'run_and_render_stream' at cli/app.py:528 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 331 | 🟢 LOW | Long Method | Function '_create_headless_repl' has 43 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 402 | 🟢 LOW | Deep Nesting | Nesting depth 4 in '_run_headless' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |

### tools/builtins/shell.py — 🔶 D (64.6/100)

LOC: 537 | Classes: 3 | Functions: 19 | MI: 47 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 478 | 🟠 HIGH | Long Method | Function '_run_sudo_with_pty' has 80 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 639 | 🟠 HIGH | Duplicate Code | Function 'parameters' is an exact duplicate of 'parameters' at tools/security/shell_secure.py:506 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 518 | 🟢 LOW | Deep Nesting | Nesting depth 4 in '_run_sudo_with_pty' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 526 | 🟢 LOW | Deep Nesting | Nesting depth 4 in '_run_sudo_with_pty' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 649 | 🟢 LOW | Long Method | Function 'execute' has 36 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 649 | 🟢 LOW | Primitive Obsession | Function 'execute' has 3 primitive-typed parameters: command: Name(id='str', ctx=Load()), timeout: BinOp(left=Name(id='int', ctx=Load()), op=BitOr(), right=Constant(value=None)), cwd: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |

### tools/builtins/test_gen.py — 🔶 D (64.6/100)

LOC: 400 | Classes: 1 | Functions: 6 | MI: 52 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 172 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 92% similar to 'parameters' at tools/builtins/web_fetch.py:32 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 172 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 92% similar to 'parameters' at tools/builtins/web_search.py:27 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 200 | 🟡 MEDIUM | Long Method | Function 'execute' has 58 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 277 | 🟡 MEDIUM | Duplicate Code | Function '_extract_class_methods' is 100% similar to '_extract_symbols' at tools/builtins/test_gen.py:284 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 112 | 🟢 LOW | Primitive Obsession | Function '_generate_test_method' has 3 primitive-typed parameters: cls_name: Name(id='str', ctx=Load()), method_name: Name(id='str', ctx=Load()), is_async: Name(id='bool', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 150 | 🟢 LOW | Large Class | Class 'TestGenTool' spans 338 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
| 200 | 🟢 LOW | Primitive Obsession | Function 'execute' has 3 primitive-typed parameters: path: Name(id='str', ctx=Load()), output_path: Name(id='str', ctx=Load()), style: Name(id='str', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 200 | 🟢 LOW | Feature Envy | Method 'TestGenTool.execute' accesses 'target' 3 times but 'self' only 2 times | Move Method — consider moving 'execute' to the class that owns 'target'. |
| 415 | 🟢 LOW | Long Method | Function '_generate_function_tests' has 33 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |

### cli/textual_mixins.py — 🔶 D (64.8/100)

LOC: 1472 | Classes: 13 | Functions: 3 | MI: 4 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 1400 | 🟡 MEDIUM | Duplicate Code | Function 'on_switch_provider_message' is 94% similar to '__exit__' at rag/concurrency.py:121 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 1141 | 🟢 LOW | Feature Envy | Method '_CommandPaletteMixin._fill_input_with_text' accesses 'widget' 3 times but 'self' only 1 times | Move Method — consider moving '_fill_input_with_text' to the class that owns 'widget'. |
| 1732 | 🟢 LOW | Primitive Obsession | Function 'update_status' has 3 primitive-typed parameters: message: Name(id='str', ctx=Load()), tokens: BinOp(left=Name(id='int', ctx=Load()), op=BitOr(), right=Constant(value=None)), cost: BinOp(left=Name(id='float', ctx=Load()), op=BitOr(), right=Constant(value=None)) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |

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
- cli/commands/model.py — 👍 B
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
- core/session_templates.py — ✅ A
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
- tools/builtins/kg_common.py — ✅ A
- tools/security/__init__.py — ✅ A
- tools/utils.py — ✅ A
- utils/__init__.py — ✅ A
- utils/lazy_import.py — ✅ A
- version.py — ✅ A

</details>

---

_Report generated by XP Code Smell Detector. Smells are static heuristics — use judgement when prioritising fixes._
