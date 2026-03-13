# Code Smell Report — 👍 B (Score: 88.0/100)

_Scanned: /home/matthew/mlg-cli/src_  

_Generated: 2026-03-12T19:34:27.298187+00:00_

## Executive Summary

| Metric | Value |
|:-------|------:|
| **Overall Grade** | 👍 B |
| **Overall Score** | 88.0/100 |
| **Files Scanned** | 207 |
| **Total Lines (non-blank)** | 43,821 |
| **Total Smells** | 891 |
| **Avg Maintainability Index** | 100.0 |
| **Avg Cyclomatic Complexity** | 0.0 |

### Smells by Severity

| Severity | Count |
|:---------|------:|
| low | 729 |
| medium | 147 |
| high | 15 |

### Smells by Category

| Category | Count |
|:---------|------:|
| Lint Violation | 294 |
| Missing Type Hint | 165 |
| Duplicate Code | 113 |
| Feature Envy | 92 |
| Long Method | 77 |
| Magic Number | 47 |
| Primitive Obsession | 44 |
| Deep Nesting | 42 |
| Large Class | 17 |

## 🎯 Prioritised Refactoring Queue

These are the highest-impact smells to address first:

1. **henchman/agents/working_memory.py:133** — 🟠 HIGH — Duplicate Code  
   Function 'add_recent_file' is an exact duplicate of 'add_decision' at henchman/agents/working_memory.py:137  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

2. **henchman/agents/working_memory.py:133** — 🟠 HIGH — Duplicate Code  
   Function 'add_recent_file' is an exact duplicate of 'add_completed_step' at henchman/agents/working_memory.py:141  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

3. **henchman/agents/working_memory.py:133** — 🟠 HIGH — Duplicate Code  
   Function 'add_recent_file' is an exact duplicate of 'add_next_action' at henchman/agents/working_memory.py:145  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

4. **henchman/agents/working_memory.py:133** — 🟠 HIGH — Duplicate Code  
   Function 'add_recent_file' is an exact duplicate of 'add_insight' at henchman/agents/working_memory.py:149  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

5. **henchman/agents/working_memory.py:133** — 🟠 HIGH — Duplicate Code  
   Function 'add_recent_file' is an exact duplicate of 'add_problem' at henchman/agents/working_memory.py:153  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

6. **henchman/agents/working_memory.py:137** — 🟠 HIGH — Duplicate Code  
   Function 'add_decision' is an exact duplicate of 'add_completed_step' at henchman/agents/working_memory.py:141  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

7. **henchman/agents/working_memory.py:137** — 🟠 HIGH — Duplicate Code  
   Function 'add_decision' is an exact duplicate of 'add_next_action' at henchman/agents/working_memory.py:145  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

8. **henchman/agents/working_memory.py:137** — 🟠 HIGH — Duplicate Code  
   Function 'add_decision' is an exact duplicate of 'add_insight' at henchman/agents/working_memory.py:149  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

9. **henchman/agents/working_memory.py:137** — 🟠 HIGH — Duplicate Code  
   Function 'add_decision' is an exact duplicate of 'add_problem' at henchman/agents/working_memory.py:153  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

10. **henchman/agents/working_memory.py:141** — 🟠 HIGH — Duplicate Code  
   Function 'add_completed_step' is an exact duplicate of 'add_next_action' at henchman/agents/working_memory.py:145  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

11. **henchman/agents/working_memory.py:141** — 🟠 HIGH — Duplicate Code  
   Function 'add_completed_step' is an exact duplicate of 'add_insight' at henchman/agents/working_memory.py:149  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

12. **henchman/agents/working_memory.py:141** — 🟠 HIGH — Duplicate Code  
   Function 'add_completed_step' is an exact duplicate of 'add_problem' at henchman/agents/working_memory.py:153  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

13. **henchman/agents/working_memory.py:145** — 🟠 HIGH — Duplicate Code  
   Function 'add_next_action' is an exact duplicate of 'add_insight' at henchman/agents/working_memory.py:149  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

14. **henchman/agents/working_memory.py:145** — 🟠 HIGH — Duplicate Code  
   Function 'add_next_action' is an exact duplicate of 'add_problem' at henchman/agents/working_memory.py:153  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

15. **henchman/agents/working_memory.py:149** — 🟠 HIGH — Duplicate Code  
   Function 'add_insight' is an exact duplicate of 'add_problem' at henchman/agents/working_memory.py:153  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._


## 📊 Files Ranked by Quality

| Rank | File | Grade | Score | Smells | LOC | MI | Avg CC |
|-----:|:-----|:------|------:|-------:|----:|---:|-------:|
| 1 | henchman/agents/working_memory.py | ❌ F | 30.0 | 27 | 219 | 100 | 0.0 |
| 2 | henchman/utils/intelligent_context.py | ❌ F | 30.0 | 137 | 2274 | 100 | 0.0 |
| 3 | henchman/tools/builtins/symbol_trace.py | 🔶 D | 63.6 | 23 | 381 | 100 | 0.0 |
| 4 | henchman/utils/message_compactor.py | 🔶 D | 66.4 | 24 | 235 | 100 | 0.0 |
| 5 | henchman/core/agent.py | 🔶 D | 67.8 | 23 | 426 | 100 | 0.0 |
| 6 | henchman/cli/textual_screens.py | 🔶 D | 69.2 | 22 | 398 | 100 | 0.0 |
| 7 | henchman/agents/ledger.py | ⚠️ C | 70.6 | 15 | 411 | 100 | 0.0 |
| 8 | henchman/extensions/plugin_database.py | ⚠️ C | 72.0 | 17 | 161 | 100 | 0.0 |
| 9 | henchman/mcp/manager.py | ⚠️ C | 74.1 | 14 | 173 | 100 | 0.0 |
| 10 | henchman/utils/compression_strategy.py | ⚠️ C | 74.8 | 15 | 245 | 100 | 0.0 |

## 📁 Per-File Details

_Showing 20 worst files. 187 additional files omitted._

### henchman/agents/working_memory.py — ❌ F (30.0/100)

LOC: 219 | Classes: 7 | Functions: 0 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 133 | 🟠 HIGH | Duplicate Code | Function 'add_recent_file' is an exact duplicate of 'add_decision' at henchman/agents/working_memory.py:137 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 133 | 🟠 HIGH | Duplicate Code | Function 'add_recent_file' is an exact duplicate of 'add_completed_step' at henchman/agents/working_memory.py:141 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 133 | 🟠 HIGH | Duplicate Code | Function 'add_recent_file' is an exact duplicate of 'add_next_action' at henchman/agents/working_memory.py:145 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 133 | 🟠 HIGH | Duplicate Code | Function 'add_recent_file' is an exact duplicate of 'add_insight' at henchman/agents/working_memory.py:149 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 133 | 🟠 HIGH | Duplicate Code | Function 'add_recent_file' is an exact duplicate of 'add_problem' at henchman/agents/working_memory.py:153 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 137 | 🟠 HIGH | Duplicate Code | Function 'add_decision' is an exact duplicate of 'add_completed_step' at henchman/agents/working_memory.py:141 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 137 | 🟠 HIGH | Duplicate Code | Function 'add_decision' is an exact duplicate of 'add_next_action' at henchman/agents/working_memory.py:145 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 137 | 🟠 HIGH | Duplicate Code | Function 'add_decision' is an exact duplicate of 'add_insight' at henchman/agents/working_memory.py:149 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 137 | 🟠 HIGH | Duplicate Code | Function 'add_decision' is an exact duplicate of 'add_problem' at henchman/agents/working_memory.py:153 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 141 | 🟠 HIGH | Duplicate Code | Function 'add_completed_step' is an exact duplicate of 'add_next_action' at henchman/agents/working_memory.py:145 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 141 | 🟠 HIGH | Duplicate Code | Function 'add_completed_step' is an exact duplicate of 'add_insight' at henchman/agents/working_memory.py:149 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 141 | 🟠 HIGH | Duplicate Code | Function 'add_completed_step' is an exact duplicate of 'add_problem' at henchman/agents/working_memory.py:153 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 145 | 🟠 HIGH | Duplicate Code | Function 'add_next_action' is an exact duplicate of 'add_insight' at henchman/agents/working_memory.py:149 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 145 | 🟠 HIGH | Duplicate Code | Function 'add_next_action' is an exact duplicate of 'add_problem' at henchman/agents/working_memory.py:153 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 149 | 🟠 HIGH | Duplicate Code | Function 'add_insight' is an exact duplicate of 'add_problem' at henchman/agents/working_memory.py:153 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |

_... and 12 more smells._

### henchman/utils/intelligent_context.py — ❌ F (30.0/100)

LOC: 2274 | Classes: 20 | Functions: 0 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 1417 | 🟡 MEDIUM | Feature Envy | Method 'IntelligentTruncator._truncate_with_marker' accesses 'params' 6 times but 'self' only 3 times | Move Method — consider moving '_truncate_with_marker' to the class that owns 'params'. |
| 1665 | 🟡 MEDIUM | Feature Envy | Method 'SequenceValidator.validate_compacted_sequence' accesses 'cls' 5 times but 'self' only 0 times | Move Method — consider moving 'validate_compacted_sequence' to the class that owns 'cls'. |
| 2700 | 🟡 MEDIUM | Feature Envy | Method 'IntelligentContextManager._apply_intelligent_truncation_with_semantic_preservation' accesses 'message' 5 times but 'self' only 2 times | Move Method — consider moving '_apply_intelligent_truncation_with_semantic_preservation' to the class that owns 'message'. |
| 2734 | 🟡 MEDIUM | Duplicate Code | Function '_count_tokens' is 100% similar to 'validate_compacted_sequence' at henchman/utils/intelligent_context.py:2936 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 45 | 🟢 LOW | Lint Violation | [PYI019] Use `Self` instead of custom TypeVar `T` | Fix ruff violation PYI019. |
| 211 | 🟢 LOW | Missing Type Hint | Function 'not_found' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 224 | 🟢 LOW | Large Class | Class '_ParserState' spans 330 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
| 256 | 🟢 LOW | Lint Violation | [W293] Blank line contains whitespace | Fix ruff violation W293. |
| 261 | 🟢 LOW | Lint Violation | [W293] Blank line contains whitespace | Fix ruff violation W293. |
| 283 | 🟢 LOW | Lint Violation | [W293] Blank line contains whitespace | Fix ruff violation W293. |
| 306 | 🟢 LOW | Magic Number | Magic number 3 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 315 | 🟢 LOW | Lint Violation | [ARG002] Unused method argument: `content` | Fix ruff violation ARG002. |
| 315 | 🟢 LOW | Lint Violation | [ARG002] Unused method argument: `i` | Fix ruff violation ARG002. |
| 397 | 🟢 LOW | Lint Violation | [FBT001] Boolean-typed positional argument in function definition | Fix ruff violation FBT001. |
| 434 | 🟢 LOW | Lint Violation | [W293] Blank line contains whitespace | Fix ruff violation W293. |

_... and 122 more smells._

### henchman/tools/builtins/symbol_trace.py — 🔶 D (63.6/100)

LOC: 381 | Classes: 5 | Functions: 11 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 153 | 🟡 MEDIUM | Deep Nesting | Nesting depth 5 in '_find_definitions_in_file' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 195 | 🟡 MEDIUM | Deep Nesting | Nesting depth 5 in '_find_imports_in_file' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 77 | 🟢 LOW | Lint Violation | [FBT001] Boolean-typed positional argument in function definition | Fix ruff violation FBT001. |
| 100 | 🟢 LOW | Magic Number | Magic number 120 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 106 | 🟢 LOW | Long Method | Function '_find_definitions_in_file' has 45 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 146 | 🟢 LOW | Lint Violation | [COM812] Trailing comma missing | Fix ruff violation COM812. |
| 152 | 🟢 LOW | Deep Nesting | Nesting depth 4 in '_find_definitions_in_file' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 154 | 🟢 LOW | Lint Violation | [PERF401] Use `list.extend` to create a transformed list | Fix ruff violation PERF401. |
| 160 | 🟢 LOW | Lint Violation | [COM812] Trailing comma missing | Fix ruff violation COM812. |
| 188 | 🟢 LOW | Deep Nesting | Nesting depth 4 in '_find_imports_in_file' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 193 | 🟢 LOW | Deep Nesting | Nesting depth 4 in '_find_imports_in_file' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 230 | 🟢 LOW | Lint Violation | [COM812] Trailing comma missing | Fix ruff violation COM812. |
| 242 | 🟢 LOW | Lint Violation | [COM812] Trailing comma missing | Fix ruff violation COM812. |
| 251 | 🟢 LOW | Deep Nesting | Nesting depth 4 in '_collect_annotations_from_node' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 277 | 🟢 LOW | Magic Number | Magic number 20 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |

_... and 8 more smells._

### henchman/utils/message_compactor.py — 🔶 D (66.4/100)

LOC: 235 | Classes: 1 | Functions: 0 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 10 | 🟢 LOW | Lint Violation | [TC001] Move application import `henchman.providers.base.Message` into a type-checking block | Fix ruff violation TC001. |
| 19 | 🟢 LOW | Large Class | Class 'MessageCompactor' spans 300 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
| 26 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 34 | 🟢 LOW | Long Method | Function 'apply_intelligent_truncation' has 44 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 34 | 🟢 LOW | Missing Type Hint | Function 'apply_intelligent_truncation' has incomplete type hints: 1/5 params untyped | Add Type Annotations for all parameters and return type. |
| 77 | 🟢 LOW | Lint Violation | [COM812] Trailing comma missing | Fix ruff violation COM812. |
| 92 | 🟢 LOW | Lint Violation | [COM812] Trailing comma missing | Fix ruff violation COM812. |
| 97 | 🟢 LOW | Lint Violation | [COM812] Trailing comma missing | Fix ruff violation COM812. |
| 103 | 🟢 LOW | Missing Type Hint | Function '_count_tokens' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 113 | 🟢 LOW | Lint Violation | [PLC0415] `import` should be at the top-level of a file | Fix ruff violation PLC0415. |
| 117 | 🟢 LOW | Missing Type Hint | Function '_sort_by_importance' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 118 | 🟢 LOW | Lint Violation | [COM812] Trailing comma missing | Fix ruff violation COM812. |
| 131 | 🟢 LOW | Missing Type Hint | Function '_add_protected_messages' has incomplete type hints: 1/6 params untyped | Add Type Annotations for all parameters and return type. |
| 169 | 🟢 LOW | Missing Type Hint | Function '_calculate_cluster_importance' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 170 | 🟢 LOW | Lint Violation | [COM812] Trailing comma missing | Fix ruff violation COM812. |

_... and 9 more smells._

### henchman/core/agent.py — 🔶 D (67.8/100)

LOC: 426 | Classes: 1 | Functions: 3 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 54 | 🟢 LOW | Lint Violation | [COM812] Trailing comma missing | Fix ruff violation COM812. |
| 144 | 🟢 LOW | Large Class | Class 'Agent' spans 398 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
| 144 | 🟢 LOW | Large Class | Class 'Agent' has 21 methods (threshold: 20) | Split Class — group related methods into smaller collaborating classes. |
| 168 | 🟢 LOW | Lint Violation | [PLC0415] `import` should be at the top-level of a file | Fix ruff violation PLC0415. |
| 198 | 🟢 LOW | Long Method | Function '__getattr__' has 42 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 219 | 🟢 LOW | Lint Violation | [RET505] Unnecessary `elif` after `return` statement | Fix ruff violation RET505. |
| 223 | 🟢 LOW | Lint Violation | [TRY003] Avoid specifying long messages outside the exception class | Fix ruff violation TRY003. |
| 224 | 🟢 LOW | Lint Violation | [EM102] Exception must not use an f-string literal, assign to variable first | Fix ruff violation EM102. |
| 225 | 🟢 LOW | Lint Violation | [COM812] Trailing comma missing | Fix ruff violation COM812. |
| 232 | 🟢 LOW | Lint Violation | [RET505] Unnecessary `else` after `return` statement | Fix ruff violation RET505. |
| 234 | 🟢 LOW | Lint Violation | [TRY003] Avoid specifying long messages outside the exception class | Fix ruff violation TRY003. |
| 235 | 🟢 LOW | Lint Violation | [EM102] Exception must not use an f-string literal, assign to variable first | Fix ruff violation EM102. |
| 236 | 🟢 LOW | Lint Violation | [COM812] Trailing comma missing | Fix ruff violation COM812. |
| 244 | 🟢 LOW | Lint Violation | [TRY003] Avoid specifying long messages outside the exception class | Fix ruff violation TRY003. |
| 245 | 🟢 LOW | Lint Violation | [EM102] Exception must not use an f-string literal, assign to variable first | Fix ruff violation EM102. |

_... and 8 more smells._

### henchman/cli/textual_screens.py — 🔶 D (69.2/100)

LOC: 398 | Classes: 4 | Functions: 0 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 14 | 🟢 LOW | Lint Violation | [TC002] Move third-party import `textual.binding.Binding` into a type-checking block | Fix ruff violation TC002. |
| 20 | 🟢 LOW | Lint Violation | [TC001] Move application import `henchman.core.session.SessionMetadata` into a type-checking block | Fix ruff violation TC001. |
| 89 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 98 | 🟢 LOW | Missing Type Hint | Function 'compose' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 106 | 🟢 LOW | Long Method | Function '_build_confirmation_dialog' has 35 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 106 | 🟢 LOW | Missing Type Hint | Function '_build_confirmation_dialog' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 148 | 🟢 LOW | Missing Type Hint | Function '_build_params_label' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 165 | 🟢 LOW | Missing Type Hint | Function 'on_button_pressed' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 176 | 🟢 LOW | Missing Type Hint | Function 'action_approve' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 184 | 🟢 LOW | Missing Type Hint | Function 'action_deny' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 214 | 🟢 LOW | Lint Violation | [E501] Line too long (120 > 100) | Fix ruff violation E501. |
| 216 | 🟢 LOW | Missing Type Hint | Function 'compose' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 250 | 🟢 LOW | Missing Type Hint | Function 'on_button_pressed' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 286 | 🟢 LOW | Lint Violation | [E501] Line too long (120 > 100) | Fix ruff violation E501. |
| 288 | 🟢 LOW | Missing Type Hint | Function 'compose' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |

_... and 7 more smells._

### henchman/agents/ledger.py — ⚠️ C (70.6/100)

LOC: 411 | Classes: 6 | Functions: 2 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 390 | 🟡 MEDIUM | Duplicate Code | Function 'add_checklist_item' is 95% similar to 'add_delegation' at henchman/agents/ledger.py:425 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 458 | 🟡 MEDIUM | Duplicate Code | Function 'complete_delegation' is 100% similar to 'track_file_access' at henchman/agents/metrics.py:118 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 458 | 🟡 MEDIUM | Duplicate Code | Function 'complete_delegation' is 94% similar to '_render_diff' at henchman/cli/console.py:666 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 458 | 🟡 MEDIUM | Duplicate Code | Function 'complete_delegation' is 100% similar to '_update_installation_cache' at henchman/extensions/plugin_manager.py:333 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 12 | 🟢 LOW | Lint Violation | [TC003] Move standard library import `collections.abc.Callable` into a type-checking block | Fix ruff violation TC003. |
| 12 | 🟢 LOW | Lint Violation | [TC003] Move standard library import `collections.abc.Iterable` into a type-checking block | Fix ruff violation TC003. |
| 34 | 🟢 LOW | Lint Violation | [COM812] Trailing comma missing | Fix ruff violation COM812. |
| 87 | 🟢 LOW | Lint Violation | [COM812] Trailing comma missing | Fix ruff violation COM812. |
| 94 | 🟢 LOW | Lint Violation | [COM812] Trailing comma missing | Fix ruff violation COM812. |
| 107 | 🟢 LOW | Lint Violation | [COM812] Trailing comma missing | Fix ruff violation COM812. |
| 181 | 🟢 LOW | Lint Violation | [E501] Line too long (102 > 100) | Fix ruff violation E501. |
| 225 | 🟢 LOW | Lint Violation | [COM812] Trailing comma missing | Fix ruff violation COM812. |
| 280 | 🟢 LOW | Lint Violation | [PERF401] Use `list.extend` to create a transformed list | Fix ruff violation PERF401. |
| 418 | 🟢 LOW | Lint Violation | [TRY003] Avoid specifying long messages outside the exception class | Fix ruff violation TRY003. |
| 418 | 🟢 LOW | Lint Violation | [EM102] Exception must not use an f-string literal, assign to variable first | Fix ruff violation EM102. |

### henchman/extensions/plugin_database.py — ⚠️ C (72.0/100)

LOC: 161 | Classes: 1 | Functions: 0 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 100 | 🟡 MEDIUM | Feature Envy | Method 'PluginDatabase._row_to_installation' accesses 'PC' 6 times but 'self' only 0 times | Move Method — consider moving '_row_to_installation' to the class that owns 'PC'. |
| 160 | 🟡 MEDIUM | Feature Envy | Method 'PluginDatabase._build_installation_params' accesses 'installation' 6 times but 'self' only 0 times | Move Method — consider moving '_build_installation_params' to the class that owns 'installation'. |
| 3 | 🟢 LOW | Lint Violation | [RUF100] Unused `noqa` directive (unused: `E501`) | Fix ruff violation RUF100. |
| 28 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 36 | 🟢 LOW | Missing Type Hint | Function 'initialize' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 36 | 🟢 LOW | Feature Envy | Method 'PluginDatabase.initialize' accesses 'conn' 3 times but 'self' only 1 times | Move Method — consider moving 'initialize' to the class that owns 'conn'. |
| 36 | 🟢 LOW | Feature Envy | Method 'PluginDatabase.initialize' accesses 'cursor' 3 times but 'self' only 1 times | Move Method — consider moving 'initialize' to the class that owns 'cursor'. |
| 63 | 🟢 LOW | Lint Violation | [COM812] Trailing comma missing | Fix ruff violation COM812. |
| 66 | 🟢 LOW | Lint Violation | [COM812] Trailing comma missing | Fix ruff violation COM812. |
| 73 | 🟢 LOW | Missing Type Hint | Function 'load_installations' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 89 | 🟢 LOW | Deep Nesting | Nesting depth 4 in 'load_installations' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 100 | 🟢 LOW | Missing Type Hint | Function '_row_to_installation' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 134 | 🟢 LOW | Missing Type Hint | Function 'save_installation' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 134 | 🟢 LOW | Feature Envy | Method 'PluginDatabase.save_installation' accesses 'conn' 3 times but 'self' only 2 times | Move Method — consider moving 'save_installation' to the class that owns 'conn'. |
| 160 | 🟢 LOW | Missing Type Hint | Function '_build_installation_params' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |

_... and 2 more smells._

### henchman/mcp/manager.py — ⚠️ C (74.1/100)

LOC: 173 | Classes: 1 | Functions: 0 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 38 | 🟡 MEDIUM | Duplicate Code | Function 'get_server_names' is 100% similar to 'list_providers' at henchman/providers/registry.py:50 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 38 | 🟡 MEDIUM | Duplicate Code | Function 'get_server_names' is 100% similar to 'list_tools' at henchman/tools/registry.py:142 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 132 | 🟡 MEDIUM | Feature Envy | Method 'McpManager._build_logging_env' accesses 'command' 5 times but 'self' only 0 times | Move Method — consider moving '_build_logging_env' to the class that owns 'command'. |
| 26 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 38 | 🟢 LOW | Missing Type Hint | Function 'get_server_names' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 46 | 🟢 LOW | Missing Type Hint | Function 'is_trusted' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 59 | 🟢 LOW | Missing Type Hint | Function 'connect_all' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 87 | 🟢 LOW | Missing Type Hint | Function 'disconnect_all' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 98 | 🟢 LOW | Missing Type Hint | Function 'get_all_tools' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 106 | 🟢 LOW | Missing Type Hint | Function 'call_tool' has incomplete type hints: 1/4 params untyped | Add Type Annotations for all parameters and return type. |
| 132 | 🟢 LOW | Long Method | Function '_build_logging_env' has 35 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 166 | 🟢 LOW | Lint Violation | [COM812] Trailing comma missing | Fix ruff violation COM812. |
| 174 | 🟢 LOW | Lint Violation | [COM812] Trailing comma missing | Fix ruff violation COM812. |
| 184 | 🟢 LOW | Feature Envy | Method 'McpManager.create_from_settings' accesses 'server_config' 4 times but 'self' only 0 times | Move Method — consider moving 'create_from_settings' to the class that owns 'server_config'. |

### henchman/utils/compression_strategy.py — ⚠️ C (74.8/100)

LOC: 245 | Classes: 4 | Functions: 0 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 65 | 🟡 MEDIUM | Long Method | Function 'compress' has 56 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 274 | 🟡 MEDIUM | Feature Envy | Method 'CompressionStrategyFactory.create_for_conversation_type' accesses 'CSC' 6 times but 'self' only 0 times | Move Method — consider moving 'create_for_conversation_type' to the class that owns 'CSC'. |
| 103 | 🟢 LOW | Deep Nesting | Nesting depth 4 in 'compress' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 117 | 🟢 LOW | Deep Nesting | Nesting depth 4 in 'compress' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 127 | 🟢 LOW | Deep Nesting | Nesting depth 4 in 'compress' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 134 | 🟢 LOW | Deep Nesting | Nesting depth 4 in 'compress' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 178 | 🟢 LOW | Lint Violation | [N806] Variable `MIN_TOKEN_REDUCTION_RATIO` in function should be lowercase | Fix ruff violation N806. |
| 185 | 🟢 LOW | Lint Violation | [E501] Line too long (101 > 100) | Fix ruff violation E501. |
| 199 | 🟢 LOW | Feature Envy | Method 'CompressionStrategy._generate_cluster_summary' accesses 'msg' 4 times but 'self' only 0 times | Move Method — consider moving '_generate_cluster_summary' to the class that owns 'msg'. |
| 200 | 🟢 LOW | Lint Violation | [COM812] Trailing comma missing | Fix ruff violation COM812. |
| 201 | 🟢 LOW | Lint Violation | [RUF100] Unused `noqa` directive (unused: `E501`) | Fix ruff violation RUF100. |
| 245 | 🟢 LOW | Deep Nesting | Nesting depth 4 in '_preserve_tool_sequences_in_cluster' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 248 | 🟢 LOW | Feature Envy | Method 'CompressionStrategy._preserve_code_blocks_in_cluster' accesses 'msg' 4 times but 'self' only 0 times | Move Method — consider moving '_preserve_code_blocks_in_cluster' to the class that owns 'msg'. |
| 266 | 🟢 LOW | Lint Violation | [RUF100] Unused `noqa` directive (unused: `E501`) | Fix ruff violation RUF100. |
| 274 | 🟢 LOW | Long Method | Function 'create_for_conversation_type' has 42 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |

### henchman/mcp/tool.py — ⚠️ C (76.2/100)

LOC: 82 | Classes: 1 | Functions: 0 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 23 | 🟡 MEDIUM | Duplicate Code | Function '__init__' is 100% similar to '__init__' at henchman/tools/builtins/rag_search.py:28 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 23 | 🟡 MEDIUM | Duplicate Code | Function '__init__' is 100% similar to '__init__' at henchman/utils/message_clusterer.py:24 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 45 | 🟡 MEDIUM | Duplicate Code | Function 'name' is 100% similar to 'description' at henchman/mcp/tool.py:54 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 63 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 94% similar to 'parameters' at henchman/tools/builtins/grep.py:584 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 23 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/5 params untyped | Add Type Annotations for all parameters and return type. |
| 45 | 🟢 LOW | Missing Type Hint | Function 'name' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 54 | 🟢 LOW | Missing Type Hint | Function 'description' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 63 | 🟢 LOW | Missing Type Hint | Function 'parameters' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 72 | 🟢 LOW | Missing Type Hint | Function 'kind' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 85 | 🟢 LOW | Missing Type Hint | Function 'execute' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 85 | 🟢 LOW | Feature Envy | Method 'McpTool.execute' accesses 'result' 4 times but 'self' only 2 times | Move Method — consider moving 'execute' to the class that owns 'result'. |

### henchman/knowledge/store.py — ⚠️ C (76.9/100)

LOC: 462 | Classes: 2 | Functions: 9 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 107 | 🟡 MEDIUM | Duplicate Code | Function '_relation_to_edge_attrs' is 100% similar to '_format_tool_for_anthropic' at henchman/providers/anthropic.py:130 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 107 | 🟡 MEDIUM | Duplicate Code | Function '_relation_to_edge_attrs' is 100% similar to 'to_metadata' at henchman/rag/chunker.py:42 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 407 | 🟡 MEDIUM | Duplicate Code | Function 'add_entity' is 100% similar to 'add_relation' at henchman/knowledge/store.py:499 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 518 | 🟡 MEDIUM | Duplicate Code | Function 'get_relations' is 94% similar to 'extract_imports' at henchman/tools/builtins/import_graph.py:267 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 518 | 🟡 MEDIUM | Duplicate Code | Function 'get_relations' is 94% similar to 'extract_critical_sections' at henchman/utils/message_analyzer.py:108 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 103 | 🟢 LOW | Lint Violation | [COM812] Trailing comma missing | Fix ruff violation COM812. |
| 107 | 🟢 LOW | Lint Violation | [RUF102] Invalid rule code in `# noqa`: PLR0801 | Fix ruff violation RUF102. |
| 107 | 🟢 LOW | Lint Violation | [RUF100] Unused `noqa` directive (unknown: `PLR0801`) | Fix ruff violation RUF100. |
| 257 | 🟢 LOW | Deep Nesting | Nesting depth 4 in 'get_neighbors' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |

### henchman/tools/builtins/file_overview.py — ⚠️ C (76.9/100)

LOC: 295 | Classes: 1 | Functions: 10 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 349 | 🟡 MEDIUM | Duplicate Code | Function 'execute' is 96% similar to 'execute' at henchman/tools/builtins/pattern_search.py:363 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 35 | 🟢 LOW | Long Method | Function '_format_function_sig' has 33 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 37 | 🟢 LOW | Lint Violation | [FBT001] Boolean-typed positional argument in function definition | Fix ruff violation FBT001. |
| 85 | 🟢 LOW | Lint Violation | [FBT001] Boolean-typed positional argument in function definition | Fix ruff violation FBT001. |
| 110 | 🟢 LOW | Lint Violation | [PERF401] Use `list.extend` to create a transformed list | Fix ruff violation PERF401. |
| 128 | 🟢 LOW | Lint Violation | [PERF401] Use `list.extend` to create a transformed list | Fix ruff violation PERF401. |
| 136 | 🟢 LOW | Primitive Obsession | Function '_summarize_python' has 3 primitive-typed parameters: source: Name(id='str', ctx=Load()), depth: Name(id='int', ctx=Load()), include_docs: Name(id='bool', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 136 | 🟢 LOW | Lint Violation | [FBT001] Boolean-typed positional argument in function definition | Fix ruff violation FBT001. |
| 165 | 🟢 LOW | Magic Number | Magic number 200 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 205 | 🟢 LOW | Magic Number | Magic number 20 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 228 | 🟢 LOW | Magic Number | Magic number 20 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 253 | 🟢 LOW | Magic Number | Magic number 15 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 255 | 🟢 LOW | Magic Number | Magic number 15 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 259 | 🟢 LOW | Long Method | Function '_execute_file_overview' has 35 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 342 | 🟢 LOW | Lint Violation | [E501] Line too long (103 > 100) | Fix ruff violation E501. |

### henchman/agents/presets.py — ⚠️ C (77.6/100)

LOC: 194 | Classes: 1 | Functions: 7 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 123 | 🟡 MEDIUM | Duplicate Code | Function '_create_planner_config' is 100% similar to '_create_explorer_config' at henchman/agents/presets.py:145 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 123 | 🟡 MEDIUM | Duplicate Code | Function '_create_planner_config' is 100% similar to '_create_engineer_config' at henchman/agents/presets.py:167 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 123 | 🟡 MEDIUM | Duplicate Code | Function '_create_planner_config' is 100% similar to '_create_data_engineer_config' at henchman/agents/presets.py:188 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 145 | 🟡 MEDIUM | Duplicate Code | Function '_create_explorer_config' is 100% similar to '_create_engineer_config' at henchman/agents/presets.py:167 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 145 | 🟡 MEDIUM | Duplicate Code | Function '_create_explorer_config' is 100% similar to '_create_data_engineer_config' at henchman/agents/presets.py:188 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 167 | 🟡 MEDIUM | Duplicate Code | Function '_create_engineer_config' is 100% similar to '_create_data_engineer_config' at henchman/agents/presets.py:188 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 49 | 🟢 LOW | Primitive Obsession | Function '_create_agent_config' has 3 primitive-typed parameters: name: Name(id='str', ctx=Load()), role: Name(id='str', ctx=Load()), description: Name(id='str', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |

### henchman/utils/tokens.py — ⚠️ C (79.7/100)

LOC: 125 | Classes: 1 | Functions: 1 | MI: 100 | Avg CC: 0.0

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

### henchman/agents/pool.py — 👍 B (80.4/100)

LOC: 197 | Classes: 1 | Functions: 1 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 65 | 🟡 MEDIUM | Primitive Obsession | Function '__init__' has 5 primitive-typed parameters: environment_context: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), intelligent_context: Name(id='bool', ctx=Load()), importance_threshold: Name(id='float', ctx=Load()), cluster_similarity_threshold: Name(id='float', ctx=Load()), adaptive_compression: Name(id='bool', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 105 | 🟡 MEDIUM | Long Method | Function 'get_agent' has 62 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 65 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/11 params untyped | Add Type Annotations for all parameters and return type. |
| 105 | 🟢 LOW | Missing Type Hint | Function 'get_agent' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 180 | 🟢 LOW | Missing Type Hint | Function 'get_identity' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 201 | 🟢 LOW | Missing Type Hint | Function 'list_agents' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 201 | 🟢 LOW | Feature Envy | Method 'AgentPool.list_agents' accesses 'config' 3 times but 'self' only 1 times | Move Method — consider moving 'list_agents' to the class that owns 'config'. |
| 218 | 🟢 LOW | Missing Type Hint | Function 'list_active_agents' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 226 | 🟢 LOW | Missing Type Hint | Function 'reset_agent' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 238 | 🟢 LOW | Missing Type Hint | Function 'reset_all' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 247 | 🟢 LOW | Missing Type Hint | Function 'shutdown' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |

### henchman/mcp/client.py — 👍 B (80.4/100)

LOC: 199 | Classes: 4 | Functions: 0 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 33 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 42 | 🟢 LOW | Long Method | Function 'write' has 46 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 42 | 🟢 LOW | Missing Type Hint | Function 'write' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 42 | 🟢 LOW | Feature Envy | Method 'FilteredStream.write' accesses 're' 3 times but 'self' only 1 times | Move Method — consider moving 'write' to the class that owns 're'. |
| 42 | 🟢 LOW | Feature Envy | Method 'FilteredStream.write' accesses 'line' 3 times but 'self' only 1 times | Move Method — consider moving 'write' to the class that owns 'line'. |
| 83 | 🟢 LOW | Lint Violation | [RUF100] Unused `noqa` directive (unused: `E501`) | Fix ruff violation RUF100. |
| 133 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/4 params untyped | Add Type Annotations for all parameters and return type. |
| 149 | 🟢 LOW | Missing Type Hint | Function 'is_connected' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 153 | 🟢 LOW | Long Method | Function 'connect' has 34 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 153 | 🟢 LOW | Missing Type Hint | Function 'connect' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 198 | 🟢 LOW | Missing Type Hint | Function 'disconnect' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 211 | 🟢 LOW | Missing Type Hint | Function 'discover_tools' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 231 | 🟢 LOW | Missing Type Hint | Function 'get_tools' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 239 | 🟢 LOW | Missing Type Hint | Function 'call_tool' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |

### henchman/tools/builtins/pattern_search.py — 👍 B (80.4/100)

LOC: 312 | Classes: 3 | Functions: 7 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 234 | 🟡 MEDIUM | Long Method | Function '_execute_pattern_search' has 52 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 363 | 🟡 MEDIUM | Primitive Obsession | Function 'execute' has 4 primitive-typed parameters: description: Name(id='str', ctx=Load()), path: Name(id='str', ctx=Load()), top_k: Name(id='int', ctx=Load()), strategy: Name(id='str', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 70 | 🟢 LOW | Magic Number | Magic number 3 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 73 | 🟢 LOW | Long Method | Function '_extract_structural_patterns' has 35 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 96 | 🟢 LOW | Magic Number | Magic number 3 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 168 | 🟢 LOW | Deep Nesting | Nesting depth 4 in '_search_file_structural' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 226 | 🟢 LOW | Magic Number | Magic number 5 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 253 | 🟢 LOW | Lint Violation | [E501] Line too long (103 > 100) | Fix ruff violation E501. |
| 328 | 🟢 LOW | Magic Number | Magic number 10 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 394 | 🟢 LOW | Lint Violation | [COM812] Trailing comma missing | Fix ruff violation COM812. |
| 395 | 🟢 LOW | Lint Violation | [COM812] Trailing comma missing | Fix ruff violation COM812. |

### henchman/metrics/exporter.py — 👍 B (81.1/100)

LOC: 262 | Classes: 3 | Functions: 0 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 224 | 🟡 MEDIUM | Feature Envy | Method 'MetricsExporter._get_filtered_metrics' accesses 'filters' 6 times but 'self' only 1 times | Move Method — consider moving '_get_filtered_metrics' to the class that owns 'filters'. |
| 49 | 🟢 LOW | Feature Envy | Method 'PrometheusFormatter.format' accesses 'cls' 3 times but 'self' only 0 times | Move Method — consider moving 'format' to the class that owns 'cls'. |
| 74 | 🟢 LOW | Lint Violation | [COM812] Trailing comma missing | Fix ruff violation COM812. |
| 85 | 🟢 LOW | Lint Violation | [COM812] Trailing comma missing | Fix ruff violation COM812. |
| 137 | 🟢 LOW | Lint Violation | [COM812] Trailing comma missing | Fix ruff violation COM812. |
| 163 | 🟢 LOW | Lint Violation | [COM812] Trailing comma missing | Fix ruff violation COM812. |
| 180 | 🟢 LOW | Lint Violation | [COM812] Trailing comma missing | Fix ruff violation COM812. |
| 216 | 🟢 LOW | Lint Violation | [UP037] Remove quotes from type annotation | Fix ruff violation UP037. |
| 254 | 🟢 LOW | Feature Envy | Method 'MetricsExporter.export_to_csv' accesses 'path' 3 times but 'self' only 1 times | Move Method — consider moving 'export_to_csv' to the class that owns 'path'. |
| 256 | 🟢 LOW | Lint Violation | [PLC0415] `import` should be at the top-level of a file | Fix ruff violation PLC0415. |
| 281 | 🟢 LOW | Lint Violation | [COM812] Trailing comma missing | Fix ruff violation COM812. |
| 286 | 🟢 LOW | Lint Violation | [PLC0415] `import` should be at the top-level of a file | Fix ruff violation PLC0415. |

### henchman/agents/orchestrator_execution.py — 👍 B (81.8/100)

LOC: 150 | Classes: 1 | Functions: 2 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 177 | 🟡 MEDIUM | Duplicate Code | Function 'assess_completion' is 100% similar to 'save' at henchman/core/session_manager_base.py:102 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 177 | 🟡 MEDIUM | Duplicate Code | Function 'assess_completion' is 100% similar to '_import_from_node_contains_module' at henchman/tools/builtins/import_graph.py:611 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 60 | 🟢 LOW | Long Method | Function 'run_agent_loop' has 37 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 60 | 🟢 LOW | Feature Envy | Method 'ExecutionController.run_agent_loop' accesses 'params' 3 times but 'self' only 2 times | Move Method — consider moving 'run_agent_loop' to the class that owns 'params'. |
| 93 | 🟢 LOW | Lint Violation | [COM812] Trailing comma missing | Fix ruff violation COM812. |
| 118 | 🟢 LOW | Lint Violation | [FBT001] Boolean-typed positional argument in function definition | Fix ruff violation FBT001. |
| 118 | 🟢 LOW | Lint Violation | [ARG002] Unused method argument: `generator_exhausted` | Fix ruff violation ARG002. |
| 154 | 🟢 LOW | Lint Violation | [TRY003] Avoid specifying long messages outside the exception class | Fix ruff violation TRY003. |
| 155 | 🟢 LOW | Lint Violation | [EM101] Exception must not use a string literal, assign to variable first | Fix ruff violation EM101. |
| 157 | 🟢 LOW | Lint Violation | [COM812] Trailing comma missing | Fix ruff violation COM812. |

## ✨ Clean Files (60 files with no smells)

<details><summary>Click to expand</summary>

- henchman/__init__.py — ✅ A
- henchman/__main__.py — ✅ A
- henchman/agents/__init__.py — ✅ A
- henchman/agents/config.py — ✅ A
- henchman/agents/orchestrator_components.py — ✅ A
- henchman/agents/orchestrator_events.py — ✅ A
- henchman/agents/orchestrator_init.py — ✅ A
- henchman/agents/orchestrator_prompts.py — ✅ A
- henchman/agents/orchestrator_tech_lead.py — ✅ A
- henchman/agents/orchestrator_timeout.py — ✅ A
- henchman/agents/orchestrator_tools.py — ✅ A
- henchman/agents/orchestrator_turns.py — ✅ A
- henchman/agents/orchestrator_types.py — ✅ A
- henchman/agents/orchestrator_validation.py — ✅ A
- henchman/api/__init__.py — ✅ A
- henchman/api/auth.py — ✅ A
- henchman/api/endpoints/__init__.py — ✅ A
- henchman/cli/__init__.py — ✅ A
- henchman/cli/app.py — ✅ A
- henchman/cli/commands/model.py — ✅ A
- henchman/cli/commands/team.py — ✅ A
- henchman/cli/input.py — ✅ A
- henchman/cli/prompts.py — ✅ A
- henchman/config/__init__.py — ✅ A
- henchman/config/settings.py — ✅ A
- henchman/core/__init__.py — ✅ A
- henchman/core/agent_stall.py — ✅ A
- henchman/core/events.py — ✅ A
- henchman/core/session.py — ✅ A
- henchman/core/session_branch.py — ✅ A
- henchman/core/session_helpers.py — ✅ A
- henchman/core/session_manager.py — ✅ A
- henchman/core/session_merge.py — ✅ A
- henchman/core/session_templates.py — ✅ A
- henchman/extensions/__init__.py — ✅ A
- henchman/extensions/constants.py — ✅ A
- henchman/extensions/models.py — ✅ A
- henchman/extensions/plugin_registry_client.py — ✅ A
- henchman/knowledge/__init__.py — ✅ A
- henchman/knowledge/models.py — ✅ A
- henchman/mcp/__init__.py — ✅ A
- henchman/metrics/__init__.py — ✅ A
- henchman/metrics/models.py — ✅ A
- henchman/providers/__init__.py — ✅ A
- henchman/providers/utils.py — ✅ A
- henchman/rag/__init__.py — ✅ A
- henchman/tools/__init__.py — ✅ A
- henchman/tools/builtins/__init__.py — ✅ A
- henchman/tools/builtins/dead_code.py — ✅ A
- henchman/tools/builtins/delegate.py — ✅ A
- henchman/tools/builtins/kg_common.py — ✅ A
- henchman/tools/builtins/pytest_run.py — ✅ A
- henchman/tools/builtins/python_ast.py — ✅ A
- henchman/tools/builtins/test_gen.py — ✅ A
- henchman/tools/utils.py — ✅ A
- henchman/utils/__init__.py — ✅ A
- henchman/utils/cluster_utils.py — ✅ A
- henchman/utils/lazy_import.py — ✅ A
- henchman/utils/sorting_utils.py — ✅ A
- henchman/version.py — ✅ A

</details>

---

_Report generated by XP Code Smell Detector. Smells are static heuristics — use judgement when prioritising fixes._

