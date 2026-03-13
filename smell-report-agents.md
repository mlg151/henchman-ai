# Code Smell Report — 👍 B (Score: 87.9/100)

_Scanned: /home/matthew/mlg-cli/src/henchman/agents_  

_Generated: 2026-03-12T19:27:27.386419+00:00_

## Executive Summary

| Metric | Value |
|:-------|------:|
| **Overall Grade** | 👍 B |
| **Overall Score** | 87.9/100 |
| **Files Scanned** | 28 |
| **Total Lines (non-blank)** | 4,724 |
| **Total Smells** | 108 |
| **Avg Maintainability Index** | 100.0 |
| **Avg Cyclomatic Complexity** | 0.0 |

### Smells by Severity

| Severity | Count |
|:---------|------:|
| low | 80 |
| high | 15 |
| medium | 13 |

### Smells by Category

| Category | Count |
|:---------|------:|
| Lint Violation | 49 |
| Duplicate Code | 24 |
| Missing Type Hint | 9 |
| Feature Envy | 9 |
| Long Method | 7 |
| Primitive Obsession | 4 |
| Magic Number | 3 |
| Deep Nesting | 2 |
| Large Class | 1 |

## 🎯 Prioritised Refactoring Queue

These are the highest-impact smells to address first:

1. **working_memory.py:133** — 🟠 HIGH — Duplicate Code  
   Function 'add_recent_file' is an exact duplicate of 'add_decision' at working_memory.py:137  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

2. **working_memory.py:133** — 🟠 HIGH — Duplicate Code  
   Function 'add_recent_file' is an exact duplicate of 'add_completed_step' at working_memory.py:141  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

3. **working_memory.py:133** — 🟠 HIGH — Duplicate Code  
   Function 'add_recent_file' is an exact duplicate of 'add_next_action' at working_memory.py:145  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

4. **working_memory.py:133** — 🟠 HIGH — Duplicate Code  
   Function 'add_recent_file' is an exact duplicate of 'add_insight' at working_memory.py:149  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

5. **working_memory.py:133** — 🟠 HIGH — Duplicate Code  
   Function 'add_recent_file' is an exact duplicate of 'add_problem' at working_memory.py:153  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

6. **working_memory.py:137** — 🟠 HIGH — Duplicate Code  
   Function 'add_decision' is an exact duplicate of 'add_completed_step' at working_memory.py:141  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

7. **working_memory.py:137** — 🟠 HIGH — Duplicate Code  
   Function 'add_decision' is an exact duplicate of 'add_next_action' at working_memory.py:145  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

8. **working_memory.py:137** — 🟠 HIGH — Duplicate Code  
   Function 'add_decision' is an exact duplicate of 'add_insight' at working_memory.py:149  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

9. **working_memory.py:137** — 🟠 HIGH — Duplicate Code  
   Function 'add_decision' is an exact duplicate of 'add_problem' at working_memory.py:153  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

10. **working_memory.py:141** — 🟠 HIGH — Duplicate Code  
   Function 'add_completed_step' is an exact duplicate of 'add_next_action' at working_memory.py:145  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

11. **working_memory.py:141** — 🟠 HIGH — Duplicate Code  
   Function 'add_completed_step' is an exact duplicate of 'add_insight' at working_memory.py:149  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

12. **working_memory.py:141** — 🟠 HIGH — Duplicate Code  
   Function 'add_completed_step' is an exact duplicate of 'add_problem' at working_memory.py:153  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

13. **working_memory.py:145** — 🟠 HIGH — Duplicate Code  
   Function 'add_next_action' is an exact duplicate of 'add_insight' at working_memory.py:149  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

14. **working_memory.py:145** — 🟠 HIGH — Duplicate Code  
   Function 'add_next_action' is an exact duplicate of 'add_problem' at working_memory.py:153  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

15. **working_memory.py:149** — 🟠 HIGH — Duplicate Code  
   Function 'add_insight' is an exact duplicate of 'add_problem' at working_memory.py:153  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._


## 📊 Files Ranked by Quality

| Rank | File | Grade | Score | Smells | LOC | MI | Avg CC |
|-----:|:-----|:------|------:|-------:|----:|---:|-------:|
| 1 | working_memory.py | ❌ F | 30.0 | 27 | 219 | 100 | 0.0 |
| 2 | ledger.py | ⚠️ C | 77.6 | 13 | 411 | 100 | 0.0 |
| 3 | presets.py | ⚠️ C | 77.6 | 7 | 194 | 100 | 0.0 |
| 4 | pool.py | 👍 B | 80.4 | 11 | 197 | 100 | 0.0 |
| 5 | delegation.py | 👍 B | 83.2 | 12 | 856 | 100 | 0.0 |
| 6 | orchestrator_delegation_ctrl.py | 👍 B | 87.4 | 6 | 160 | 100 | 0.0 |
| 7 | orchestrator_execution.py | 👍 B | 88.8 | 8 | 150 | 100 | 0.0 |
| 8 | orchestrator_loop.py | 👍 B | 88.8 | 8 | 189 | 100 | 0.0 |
| 9 | orchestrator_anchoring.py | ✅ A | 90.2 | 7 | 122 | 100 | 0.0 |
| 10 | prompts.py | ✅ A | 95.8 | 3 | 476 | 100 | 0.0 |

## 📁 Per-File Details

_Showing 20 worst files. 8 additional files omitted._

### working_memory.py — ❌ F (30.0/100)

LOC: 219 | Classes: 7 | Functions: 0 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 133 | 🟠 HIGH | Duplicate Code | Function 'add_recent_file' is an exact duplicate of 'add_decision' at working_memory.py:137 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 133 | 🟠 HIGH | Duplicate Code | Function 'add_recent_file' is an exact duplicate of 'add_completed_step' at working_memory.py:141 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 133 | 🟠 HIGH | Duplicate Code | Function 'add_recent_file' is an exact duplicate of 'add_next_action' at working_memory.py:145 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 133 | 🟠 HIGH | Duplicate Code | Function 'add_recent_file' is an exact duplicate of 'add_insight' at working_memory.py:149 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 133 | 🟠 HIGH | Duplicate Code | Function 'add_recent_file' is an exact duplicate of 'add_problem' at working_memory.py:153 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 137 | 🟠 HIGH | Duplicate Code | Function 'add_decision' is an exact duplicate of 'add_completed_step' at working_memory.py:141 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 137 | 🟠 HIGH | Duplicate Code | Function 'add_decision' is an exact duplicate of 'add_next_action' at working_memory.py:145 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 137 | 🟠 HIGH | Duplicate Code | Function 'add_decision' is an exact duplicate of 'add_insight' at working_memory.py:149 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 137 | 🟠 HIGH | Duplicate Code | Function 'add_decision' is an exact duplicate of 'add_problem' at working_memory.py:153 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 141 | 🟠 HIGH | Duplicate Code | Function 'add_completed_step' is an exact duplicate of 'add_next_action' at working_memory.py:145 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 141 | 🟠 HIGH | Duplicate Code | Function 'add_completed_step' is an exact duplicate of 'add_insight' at working_memory.py:149 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 141 | 🟠 HIGH | Duplicate Code | Function 'add_completed_step' is an exact duplicate of 'add_problem' at working_memory.py:153 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 145 | 🟠 HIGH | Duplicate Code | Function 'add_next_action' is an exact duplicate of 'add_insight' at working_memory.py:149 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 145 | 🟠 HIGH | Duplicate Code | Function 'add_next_action' is an exact duplicate of 'add_problem' at working_memory.py:153 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 149 | 🟠 HIGH | Duplicate Code | Function 'add_insight' is an exact duplicate of 'add_problem' at working_memory.py:153 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |

_... and 12 more smells._

### ledger.py — ⚠️ C (77.6/100)

LOC: 411 | Classes: 6 | Functions: 2 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 390 | 🟡 MEDIUM | Duplicate Code | Function 'add_checklist_item' is 95% similar to 'add_delegation' at ledger.py:425 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 458 | 🟡 MEDIUM | Duplicate Code | Function 'complete_delegation' is 100% similar to 'track_file_access' at metrics.py:118 | Extract Shared Function — identify the common logic and parameterise the differences. |
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

### presets.py — ⚠️ C (77.6/100)

LOC: 194 | Classes: 1 | Functions: 7 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 123 | 🟡 MEDIUM | Duplicate Code | Function '_create_planner_config' is 100% similar to '_create_explorer_config' at presets.py:145 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 123 | 🟡 MEDIUM | Duplicate Code | Function '_create_planner_config' is 100% similar to '_create_engineer_config' at presets.py:167 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 123 | 🟡 MEDIUM | Duplicate Code | Function '_create_planner_config' is 100% similar to '_create_data_engineer_config' at presets.py:188 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 145 | 🟡 MEDIUM | Duplicate Code | Function '_create_explorer_config' is 100% similar to '_create_engineer_config' at presets.py:167 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 145 | 🟡 MEDIUM | Duplicate Code | Function '_create_explorer_config' is 100% similar to '_create_data_engineer_config' at presets.py:188 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 167 | 🟡 MEDIUM | Duplicate Code | Function '_create_engineer_config' is 100% similar to '_create_data_engineer_config' at presets.py:188 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 49 | 🟢 LOW | Primitive Obsession | Function '_create_agent_config' has 3 primitive-typed parameters: name: Name(id='str', ctx=Load()), role: Name(id='str', ctx=Load()), description: Name(id='str', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |

### pool.py — 👍 B (80.4/100)

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

### delegation.py — 👍 B (83.2/100)

LOC: 856 | Classes: 3 | Functions: 18 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 86 | 🟢 LOW | Lint Violation | [COM812] Trailing comma missing | Fix ruff violation COM812. |
| 120 | 🟢 LOW | Lint Violation | [RUF002] Docstring contains ambiguous `×` (MULTIPLICATION SIGN). Did you mean `x` (LATIN SMALL LETTER X)? | Fix ruff violation RUF002. |
| 136 | 🟢 LOW | Magic Number | Magic number 0.3 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 150 | 🟢 LOW | Magic Number | Magic number 0.7 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 284 | 🟢 LOW | Long Method | Function '_validate_messages_access' has 31 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 419 | 🟢 LOW | Primitive Obsession | Function '_append_list_section' has 3 primitive-typed parameters: header: Name(id='str', ctx=Load()), item_format: Name(id='str', ctx=Load()), footer: Name(id='str', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 515 | 🟢 LOW | Lint Violation | [TRY003] Avoid specifying long messages outside the exception class | Fix ruff violation TRY003. |
| 516 | 🟢 LOW | Lint Violation | [EM102] Exception must not use an f-string literal, assign to variable first | Fix ruff violation EM102. |
| 516 | 🟢 LOW | Lint Violation | [COM812] Trailing comma missing | Fix ruff violation COM812. |
| 555 | 🟢 LOW | Long Method | Function '_prepare_execution' has 32 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 688 | 🟢 LOW | Large Class | Class 'DelegationRunner' spans 372 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
| 719 | 🟢 LOW | Long Method | Function 'run_delegation' has 30 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |

### orchestrator_delegation_ctrl.py — 👍 B (87.4/100)

LOC: 160 | Classes: 2 | Functions: 0 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 120 | 🟡 MEDIUM | Long Method | Function '_run_delegation' has 53 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 120 | 🟡 MEDIUM | Feature Envy | Method 'DelegationController._run_delegation' accesses 'params' 6 times but 'self' only 5 times | Move Method — consider moving '_run_delegation' to the class that owns 'params'. |
| 169 | 🟢 LOW | Lint Violation | [COM812] Trailing comma missing | Fix ruff violation COM812. |
| 187 | 🟢 LOW | Feature Envy | Method 'DelegationController._stream_delegation' accesses 'params' 4 times but 'self' only 1 times | Move Method — consider moving '_stream_delegation' to the class that owns 'params'. |
| 187 | 🟢 LOW | Feature Envy | Method 'DelegationController._stream_delegation' accesses 'sub_event' 3 times but 'self' only 1 times | Move Method — consider moving '_stream_delegation' to the class that owns 'sub_event'. |
| 187 | 🟢 LOW | Feature Envy | Method 'DelegationController._stream_delegation' accesses 'state' 3 times but 'self' only 1 times | Move Method — consider moving '_stream_delegation' to the class that owns 'state'. |

### orchestrator_execution.py — 👍 B (88.8/100)

LOC: 150 | Classes: 1 | Functions: 2 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 60 | 🟢 LOW | Long Method | Function 'run_agent_loop' has 37 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 60 | 🟢 LOW | Feature Envy | Method 'ExecutionController.run_agent_loop' accesses 'params' 3 times but 'self' only 2 times | Move Method — consider moving 'run_agent_loop' to the class that owns 'params'. |
| 93 | 🟢 LOW | Lint Violation | [COM812] Trailing comma missing | Fix ruff violation COM812. |
| 118 | 🟢 LOW | Lint Violation | [FBT001] Boolean-typed positional argument in function definition | Fix ruff violation FBT001. |
| 118 | 🟢 LOW | Lint Violation | [ARG002] Unused method argument: `generator_exhausted` | Fix ruff violation ARG002. |
| 154 | 🟢 LOW | Lint Violation | [TRY003] Avoid specifying long messages outside the exception class | Fix ruff violation TRY003. |
| 155 | 🟢 LOW | Lint Violation | [EM101] Exception must not use a string literal, assign to variable first | Fix ruff violation EM101. |
| 157 | 🟢 LOW | Lint Violation | [COM812] Trailing comma missing | Fix ruff violation COM812. |

### orchestrator_loop.py — 👍 B (88.8/100)

LOC: 189 | Classes: 0 | Functions: 6 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 109 | 🟢 LOW | Lint Violation | [TRY203] Remove exception handler; error is immediately re-raised | Fix ruff violation TRY203. |
| 167 | 🟢 LOW | Lint Violation | [PLC0415] `import` should be at the top-level of a file | Fix ruff violation PLC0415. |
| 170 | 🟢 LOW | Lint Violation | [E501] Line too long (107 > 100) | Fix ruff violation E501. |
| 211 | 🟢 LOW | Lint Violation | [G004] Logging statement uses f-string | Fix ruff violation G004. |
| 240 | 🟢 LOW | Lint Violation | [TRY003] Avoid specifying long messages outside the exception class | Fix ruff violation TRY003. |
| 240 | 🟢 LOW | Lint Violation | [EM101] Exception must not use a string literal, assign to variable first | Fix ruff violation EM101. |
| 242 | 🟢 LOW | Lint Violation | [TRY003] Avoid specifying long messages outside the exception class | Fix ruff violation TRY003. |
| 242 | 🟢 LOW | Lint Violation | [EM102] Exception must not use an f-string literal, assign to variable first | Fix ruff violation EM102. |

### orchestrator_anchoring.py — ✅ A (90.2/100)

LOC: 122 | Classes: 0 | Functions: 5 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 68 | 🟢 LOW | Lint Violation | [TRY003] Avoid specifying long messages outside the exception class | Fix ruff violation TRY003. |
| 69 | 🟢 LOW | Lint Violation | [EM102] Exception must not use an f-string literal, assign to variable first | Fix ruff violation EM102. |
| 69 | 🟢 LOW | Lint Violation | [COM812] Trailing comma missing | Fix ruff violation COM812. |
| 71 | 🟢 LOW | Lint Violation | [TRY003] Avoid specifying long messages outside the exception class | Fix ruff violation TRY003. |
| 72 | 🟢 LOW | Lint Violation | [EM102] Exception must not use an f-string literal, assign to variable first | Fix ruff violation EM102. |
| 72 | 🟢 LOW | Lint Violation | [COM812] Trailing comma missing | Fix ruff violation COM812. |
| 125 | 🟢 LOW | Lint Violation | [COM812] Trailing comma missing | Fix ruff violation COM812. |

### prompts.py — ✅ A (95.8/100)

LOC: 476 | Classes: 0 | Functions: 1 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 557 | 🟢 LOW | Long Method | Function 'get_agent_prompt' has 45 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 586 | 🟢 LOW | Deep Nesting | Nesting depth 4 in 'get_agent_prompt' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 589 | 🟢 LOW | Deep Nesting | Nesting depth 4 in 'get_agent_prompt' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |

### orchestrator_metrics_ctrl.py — ✅ A (96.5/100)

LOC: 56 | Classes: 1 | Functions: 0 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 17 | 🟡 MEDIUM | Duplicate Code | Function 'update_tool_metrics' is 96% similar to 'update_tool_metrics' at orchestrator_tools.py:38 | Extract Shared Function — identify the common logic and parameterise the differences. |

### metrics_reporter.py — ✅ A (97.2/100)

LOC: 251 | Classes: 2 | Functions: 4 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 191 | 🟢 LOW | Feature Envy | Method 'MetricsReporter._format_task_completion_time' accesses 'time' 4 times but 'self' only 2 times | Move Method — consider moving '_format_task_completion_time' to the class that owns 'time'. |
| 202 | 🟢 LOW | Magic Number | Magic number 60 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |

### orchestrator_run.py — ✅ A (97.2/100)

LOC: 61 | Classes: 0 | Functions: 2 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 66 | 🟢 LOW | Lint Violation | [COM812] Trailing comma missing | Fix ruff violation COM812. |
| 73 | 🟢 LOW | Lint Violation | [COM812] Trailing comma missing | Fix ruff violation COM812. |

### identity.py — ✅ A (98.6/100)

LOC: 14 | Classes: 1 | Functions: 0 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 19 | 🟢 LOW | Missing Type Hint | Function '__str__' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |

## ✨ Clean Files (14 files with no smells)

<details><summary>Click to expand</summary>

- __init__.py — ✅ A
- config.py — ✅ A
- metrics.py — ✅ A
- orchestrator.py — ✅ A
- orchestrator_components.py — ✅ A
- orchestrator_events.py — ✅ A
- orchestrator_init.py — ✅ A
- orchestrator_prompts.py — ✅ A
- orchestrator_tech_lead.py — ✅ A
- orchestrator_timeout.py — ✅ A
- orchestrator_tools.py — ✅ A
- orchestrator_turns.py — ✅ A
- orchestrator_types.py — ✅ A
- orchestrator_validation.py — ✅ A

</details>

---

_Report generated by XP Code Smell Detector. Smells are static heuristics — use judgement when prioritising fixes._

