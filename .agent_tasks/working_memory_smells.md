# Code Smell Report — 👍 B (Score: 87.4/100)

_Scanned: /home/matthew/mlg-cli/src/henchman/agents_  

_Generated: 2026-03-11T18:38:31.881858+00:00_

## Executive Summary

| Metric | Value |
|:-------|------:|
| **Overall Grade** | 👍 B |
| **Overall Score** | 87.4/100 |
| **Files Scanned** | 28 |
| **Total Lines (non-blank)** | 4,886 |
| **Total Smells** | 113 |
| **Avg Maintainability Index** | 100.0 |
| **Avg Cyclomatic Complexity** | 0.0 |

### Smells by Severity

| Severity | Count |
|:---------|------:|
| low | 99 |
| medium | 13 |
| high | 1 |

### Smells by Category

| Category | Count |
|:---------|------:|
| Lint Violation | 48 |
| Missing Type Hint | 28 |
| Feature Envy | 11 |
| Duplicate Code | 9 |
| Long Method | 7 |
| Primitive Obsession | 4 |
| Magic Number | 3 |
| Deep Nesting | 2 |
| Large Class | 1 |

## 🎯 Prioritised Refactoring Queue

These are the highest-impact smells to address first:

1. **orchestrator_delegation_ctrl.py:120** — 🟠 HIGH — Feature Envy  
   Method 'DelegationController._run_delegation' accesses 'params' 10 times but 'self' only 5 times  
   → _Move Method — consider moving '_run_delegation' to the class that owns 'params'._

2. **/home/matthew/mlg-cli/src/henchman/agents/orchestrator_execution.py:60** — 🟡 MEDIUM — Lint Violation  
   [C901] `run_agent_loop` is too complex (12 > 10)  
   → _Fix ruff violation C901._

3. **ledger.py:390** — 🟡 MEDIUM — Duplicate Code  
   Function 'add_checklist_item' is 95% similar to 'add_delegation' at ledger.py:425  
   → _Extract Shared Function — identify the common logic and parameterise the differences._

4. **ledger.py:458** — 🟡 MEDIUM — Duplicate Code  
   Function 'complete_delegation' is 100% similar to 'track_file_access' at metrics.py:118  
   → _Extract Shared Function — identify the common logic and parameterise the differences._

5. **orchestrator_metrics_ctrl.py:17** — 🟡 MEDIUM — Duplicate Code  
   Function 'update_tool_metrics' is 96% similar to 'update_tool_metrics' at orchestrator_tools.py:38  
   → _Extract Shared Function — identify the common logic and parameterise the differences._

6. **pool.py:65** — 🟡 MEDIUM — Primitive Obsession  
   Function '__init__' has 5 primitive-typed parameters: environment_context: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), intelligent_context: Name(id='bool', ctx=Load()), importance_threshold: Name(id='float', ctx=Load()), cluster_similarity_threshold: Name(id='float', ctx=Load()), adaptive_compression: Name(id='bool', ctx=Load())  
   → _Introduce Parameter Object — group related primitives into a dataclass or NamedTuple._

7. **pool.py:105** — 🟡 MEDIUM — Long Method  
   Function 'get_agent' has 62 lines (threshold: 30)  
   → _Extract Method — break this function into smaller, intention-revealing helper functions._

8. **presets.py:123** — 🟡 MEDIUM — Duplicate Code  
   Function '_create_planner_config' is 100% similar to '_create_explorer_config' at presets.py:145  
   → _Extract Shared Function — identify the common logic and parameterise the differences._

9. **presets.py:123** — 🟡 MEDIUM — Duplicate Code  
   Function '_create_planner_config' is 100% similar to '_create_engineer_config' at presets.py:167  
   → _Extract Shared Function — identify the common logic and parameterise the differences._

10. **presets.py:123** — 🟡 MEDIUM — Duplicate Code  
   Function '_create_planner_config' is 100% similar to '_create_data_engineer_config' at presets.py:188  
   → _Extract Shared Function — identify the common logic and parameterise the differences._

11. **presets.py:145** — 🟡 MEDIUM — Duplicate Code  
   Function '_create_explorer_config' is 100% similar to '_create_engineer_config' at presets.py:167  
   → _Extract Shared Function — identify the common logic and parameterise the differences._

12. **presets.py:145** — 🟡 MEDIUM — Duplicate Code  
   Function '_create_explorer_config' is 100% similar to '_create_data_engineer_config' at presets.py:188  
   → _Extract Shared Function — identify the common logic and parameterise the differences._

13. **presets.py:167** — 🟡 MEDIUM — Duplicate Code  
   Function '_create_engineer_config' is 100% similar to '_create_data_engineer_config' at presets.py:188  
   → _Extract Shared Function — identify the common logic and parameterise the differences._

14. **working_memory.py:381** — 🟡 MEDIUM — Feature Envy  
   Method 'WorkingMemory.from_dict' accesses 'data' 9 times but 'self' only 0 times  
   → _Move Method — consider moving 'from_dict' to the class that owns 'data'._

15. **/home/matthew/mlg-cli/src/henchman/agents/delegation.py:86** — 🟢 LOW — Lint Violation  
   [COM812] Trailing comma missing  
   → _Fix ruff violation COM812._


## 📊 Files Ranked by Quality

| Rank | File | Grade | Score | Smells | LOC | MI | Avg CC |
|-----:|:-----|:------|------:|-------:|----:|---:|-------:|
| 1 | working_memory.py | ❌ F | 50.3 | 34 | 396 | 100 | 0.0 |
| 2 | ledger.py | ⚠️ C | 77.6 | 13 | 411 | 100 | 0.0 |
| 3 | presets.py | ⚠️ C | 77.6 | 7 | 194 | 100 | 0.0 |
| 4 | pool.py | 👍 B | 80.4 | 11 | 197 | 100 | 0.0 |
| 5 | delegation.py | 👍 B | 83.2 | 12 | 856 | 100 | 0.0 |
| 6 | orchestrator_delegation_ctrl.py | 👍 B | 84.6 | 7 | 156 | 100 | 0.0 |
| 7 | orchestrator_loop.py | 👍 B | 88.8 | 8 | 189 | 100 | 0.0 |
| 8 | orchestrator_anchoring.py | ✅ A | 90.2 | 7 | 122 | 100 | 0.0 |
| 9 | orchestrator_execution.py | ✅ A | 90.9 | 5 | 139 | 100 | 0.0 |
| 10 | prompts.py | ✅ A | 95.8 | 3 | 476 | 100 | 0.0 |

## 📁 Per-File Details

_Showing 20 worst files. 8 additional files omitted._

### working_memory.py — ❌ F (50.3/100)

LOC: 396 | Classes: 8 | Functions: 1 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 381 | 🟡 MEDIUM | Feature Envy | Method 'WorkingMemory.from_dict' accesses 'data' 9 times but 'self' only 0 times | Move Method — consider moving 'from_dict' to the class that owns 'data'. |
| 35 | 🟢 LOW | Missing Type Hint | Function 'to_dict' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 44 | 🟢 LOW | Lint Violation | [PYI019] Use `Self` instead of custom TypeVar `T` | Fix ruff violation PYI019. |
| 80 | 🟢 LOW | Feature Envy | Method 'WorkingMemoryEntry.from_dict' accesses 'data' 3 times but 'self' only 0 times | Move Method — consider moving 'from_dict' to the class that owns 'data'. |
| 156 | 🟢 LOW | Missing Type Hint | Function 'overlaps' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 213 | 🟢 LOW | Missing Type Hint | Function 'add_recent_file' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 221 | 🟢 LOW | Missing Type Hint | Function 'add_decision' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 229 | 🟢 LOW | Missing Type Hint | Function 'add_completed_step' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 237 | 🟢 LOW | Missing Type Hint | Function 'add_next_action' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 245 | 🟢 LOW | Missing Type Hint | Function 'add_insight' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 253 | 🟢 LOW | Missing Type Hint | Function 'add_problem' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 261 | 🟢 LOW | Missing Type Hint | Function 'update_problem' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 261 | 🟢 LOW | Feature Envy | Method 'WorkingMemory.update_problem' accesses 'entry' 3 times but 'self' only 1 times | Move Method — consider moving 'update_problem' to the class that owns 'entry'. |
| 261 | 🟢 LOW | Feature Envy | Method 'WorkingMemory.update_problem' accesses 'updated_entry' 3 times but 'self' only 1 times | Move Method — consider moving 'update_problem' to the class that owns 'updated_entry'. |
| 277 | 🟢 LOW | Missing Type Hint | Function 'should_read_file' has incomplete type hints: 1/4 params untyped | Add Type Annotations for all parameters and return type. |

_... and 19 more smells._

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

### orchestrator_delegation_ctrl.py — 👍 B (84.6/100)

LOC: 156 | Classes: 2 | Functions: 0 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 120 | 🟠 HIGH | Feature Envy | Method 'DelegationController._run_delegation' accesses 'params' 10 times but 'self' only 5 times | Move Method — consider moving '_run_delegation' to the class that owns 'params'. |
| 9 | 🟢 LOW | Lint Violation | [F401] `typing.Any` imported but unused | Fix ruff violation F401. |
| 120 | 🟢 LOW | Long Method | Function '_run_delegation' has 48 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 164 | 🟢 LOW | Lint Violation | [COM812] Trailing comma missing | Fix ruff violation COM812. |
| 182 | 🟢 LOW | Feature Envy | Method 'DelegationController._stream_delegation' accesses 'params' 4 times but 'self' only 1 times | Move Method — consider moving '_stream_delegation' to the class that owns 'params'. |
| 182 | 🟢 LOW | Feature Envy | Method 'DelegationController._stream_delegation' accesses 'sub_event' 3 times but 'self' only 1 times | Move Method — consider moving '_stream_delegation' to the class that owns 'sub_event'. |
| 182 | 🟢 LOW | Feature Envy | Method 'DelegationController._stream_delegation' accesses 'state' 3 times but 'self' only 1 times | Move Method — consider moving '_stream_delegation' to the class that owns 'state'. |

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

### orchestrator_execution.py — ✅ A (90.9/100)

LOC: 139 | Classes: 1 | Functions: 2 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 60 | 🟡 MEDIUM | Lint Violation | [C901] `run_agent_loop` is too complex (12 > 10) | Fix ruff violation C901. |
| 60 | 🟢 LOW | Long Method | Function 'run_agent_loop' has 43 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 129 | 🟢 LOW | Lint Violation | [TRY003] Avoid specifying long messages outside the exception class | Fix ruff violation TRY003. |
| 130 | 🟢 LOW | Lint Violation | [EM101] Exception must not use a string literal, assign to variable first | Fix ruff violation EM101. |
| 132 | 🟢 LOW | Lint Violation | [COM812] Trailing comma missing | Fix ruff violation COM812. |

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

