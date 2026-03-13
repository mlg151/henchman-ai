# Code Smell Report — 👍 B (Score: 85.5/100)

_Scanned: /home/matthew/mlg-cli/src_  

_Generated: 2026-03-11T18:11:47.389026+00:00_

## Executive Summary

| Metric | Value |
|:-------|------:|
| **Overall Grade** | 👍 B |
| **Overall Score** | 85.5/100 |
| **Files Scanned** | 206 |
| **Total Lines (non-blank)** | 43,994 |
| **Total Smells** | 1156 |
| **Avg Maintainability Index** | 100.0 |
| **Avg Cyclomatic Complexity** | 0.0 |

### Smells by Severity

| Severity | Count |
|:---------|------:|
| low | 881 |
| medium | 231 |
| high | 41 |
| critical | 3 |

### Smells by Category

| Category | Count |
|:---------|------:|
| Lint Violation | 385 |
| Missing Type Hint | 223 |
| Duplicate Code | 147 |
| Deep Nesting | 93 |
| Feature Envy | 88 |
| Long Method | 87 |
| Primitive Obsession | 58 |
| Magic Number | 57 |
| Large Class | 18 |

## 🎯 Prioritised Refactoring Queue

These are the highest-impact smells to address first:

1. **henchman/tools/builtins/symbol_trace.py:242** — 🔴 CRITICAL — Deep Nesting  
   Nesting depth 8 in '_collect_annotations' (threshold: 4)  
   → _Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return._

2. **henchman/tools/builtins/symbol_trace.py:244** — 🔴 CRITICAL — Deep Nesting  
   Nesting depth 8 in '_collect_annotations' (threshold: 4)  
   → _Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return._

3. **henchman/utils/intelligent_context.py:138** — 🔴 CRITICAL — Long Method  
   Function 'extract_code_blocks' has 299 lines (threshold: 30)  
   → _Extract Method — break this function into smaller, intention-revealing helper functions._

4. **henchman/__init__.py:12** — 🟠 HIGH — Duplicate Code  
   Function '__getattr__' is an exact duplicate of '__getattr__' at henchman/utils/lazy_import.py:23  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

5. **henchman/agents/orchestrator_anchoring.py:77** — 🟠 HIGH — Deep Nesting  
   Nesting depth 6 in 'assess_agent_completion' (threshold: 4)  
   → _Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return._

6. **henchman/agents/orchestrator_anchoring.py:79** — 🟠 HIGH — Deep Nesting  
   Nesting depth 7 in 'assess_agent_completion' (threshold: 4)  
   → _Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return._

7. **henchman/agents/orchestrator_delegation_ctrl.py:64** — 🟠 HIGH — Duplicate Code  
   Function '__init__' is an exact duplicate of '__init__' at henchman/cli/textual_messages.py:143  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

8. **henchman/agents/orchestrator_delegation_ctrl.py:128** — 🟠 HIGH — Feature Envy  
   Method 'DelegationController._run_delegation' accesses 'params' 10 times but 'self' only 5 times  
   → _Move Method — consider moving '_run_delegation' to the class that owns 'params'._

9. **henchman/agents/working_memory.py:255** — 🟠 HIGH — Primitive Obsession  
   Repeated primitive parameter group appears in: 'add_recent_file' (line 255), 'add_decision' (line 282), 'add_next_action' (line 308), 'add_problem' (line 336), 'update_problem' (line 351)  
   → _Replace Data Value with Object — create a shared data structure for this recurring parameter group._

10. **henchman/cli/json_output.py:88** — 🟠 HIGH — Duplicate Code  
   Function '_event_to_dict' is an exact duplicate of '_format_tool' at henchman/providers/openai_compat.py:186  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

11. **henchman/metrics/exporter.py:341** — 🟠 HIGH — Long Method  
   Function 'export_summary' has 84 lines (threshold: 30)  
   → _Extract Method — break this function into smaller, intention-revealing helper functions._

12. **henchman/tools/builtins/deep_research.py:320** — 🟠 HIGH — Duplicate Code  
   Function 'parameters' is an exact duplicate of 'parameters' at henchman/tools/builtins/file_overview.py:344  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

13. **henchman/tools/builtins/deep_research.py:320** — 🟠 HIGH — Duplicate Code  
   Function 'parameters' is an exact duplicate of 'parameters' at henchman/tools/builtins/pattern_search.py:364  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

14. **henchman/tools/builtins/deep_research.py:320** — 🟠 HIGH — Duplicate Code  
   Function 'parameters' is an exact duplicate of 'parameters' at henchman/tools/builtins/research_notes.py:328  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

15. **henchman/tools/builtins/deep_research.py:320** — 🟠 HIGH — Duplicate Code  
   Function 'parameters' is an exact duplicate of 'parameters' at henchman/tools/builtins/symbol_trace.py:403  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._


## 📊 Files Ranked by Quality

| Rank | File | Grade | Score | Smells | LOC | MI | Avg CC |
|-----:|:-----|:------|------:|-------:|----:|---:|-------:|
| 1 | henchman/agents/working_memory.py | ❌ F | 30.0 | 71 | 487 | 100 | 0.0 |
| 2 | henchman/metrics/exporter.py | ❌ F | 30.0 | 87 | 307 | 100 | 0.0 |
| 3 | henchman/tools/builtins/symbol_trace.py | ❌ F | 30.0 | 44 | 352 | 100 | 0.0 |
| 4 | henchman/utils/intelligent_context.py | ❌ F | 30.0 | 194 | 2265 | 100 | 0.0 |
| 5 | henchman/tools/builtins/file_overview.py | ❌ F | 32.1 | 26 | 297 | 100 | 0.0 |
| 6 | henchman/tools/builtins/deep_research.py | ❌ F | 37.7 | 21 | 285 | 100 | 0.0 |
| 7 | henchman/tools/builtins/pattern_search.py | ❌ F | 49.6 | 15 | 314 | 100 | 0.0 |
| 8 | henchman/core/agent.py | ❌ F | 55.2 | 29 | 420 | 100 | 0.0 |
| 9 | henchman/agents/orchestrator_anchoring.py | ❌ F | 55.9 | 16 | 123 | 100 | 0.0 |
| 10 | henchman/tools/builtins/research_notes.py | 🔶 D | 60.1 | 13 | 300 | 100 | 0.0 |

## 📁 Per-File Details

_Showing 20 worst files. 186 additional files omitted._

### henchman/agents/working_memory.py — ❌ F (30.0/100)

LOC: 487 | Classes: 6 | Functions: 2 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 255 | 🟠 HIGH | Primitive Obsession | Repeated primitive parameter group appears in: 'add_recent_file' (line 255), 'add_decision' (line 282), 'add_next_action' (line 308), 'add_problem' (line 336), 'update_problem' (line 351) | Replace Data Value with Object — create a shared data structure for this recurring parameter group. |
| 41 | 🟡 MEDIUM | Duplicate Code | Function 'to_dict' is 100% similar to 'to_dict' at henchman/agents/working_memory.py:88 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 41 | 🟡 MEDIUM | Duplicate Code | Function 'to_dict' is 100% similar to 'to_dict' at henchman/agents/working_memory.py:127 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 41 | 🟡 MEDIUM | Duplicate Code | Function 'to_dict' is 100% similar to 'to_dict' at henchman/agents/working_memory.py:170 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 41 | 🟡 MEDIUM | Duplicate Code | Function 'to_dict' is 100% similar to 'to_dict' at henchman/mcp/config.py:28 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 88 | 🟡 MEDIUM | Duplicate Code | Function 'to_dict' is 100% similar to 'to_dict' at henchman/agents/working_memory.py:127 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 88 | 🟡 MEDIUM | Duplicate Code | Function 'to_dict' is 100% similar to 'to_dict' at henchman/agents/working_memory.py:170 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 88 | 🟡 MEDIUM | Duplicate Code | Function 'to_dict' is 100% similar to 'to_dict' at henchman/mcp/config.py:28 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 127 | 🟡 MEDIUM | Duplicate Code | Function 'to_dict' is 100% similar to 'to_dict' at henchman/agents/working_memory.py:170 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 127 | 🟡 MEDIUM | Duplicate Code | Function 'to_dict' is 100% similar to 'to_dict' at henchman/mcp/config.py:28 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 140 | 🟡 MEDIUM | Duplicate Code | Function 'from_dict' is 100% similar to 'from_dict' at henchman/agents/working_memory.py:179 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 140 | 🟡 MEDIUM | Duplicate Code | Function 'from_dict' is 93% similar to 'message_from_dict' at henchman/core/session_models.py:74 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 170 | 🟡 MEDIUM | Duplicate Code | Function 'to_dict' is 100% similar to 'to_dict' at henchman/mcp/config.py:28 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 179 | 🟡 MEDIUM | Duplicate Code | Function 'from_dict' is 93% similar to 'message_from_dict' at henchman/core/session_models.py:74 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 205 | 🟡 MEDIUM | Lint Violation | [PLR2004] Magic value used in comparison, consider replacing `2` with a constant variable | Fix ruff violation PLR2004. |

_... and 56 more smells._

### henchman/metrics/exporter.py — ❌ F (30.0/100)

LOC: 307 | Classes: 1 | Functions: 0 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 341 | 🟠 HIGH | Long Method | Function 'export_summary' has 84 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 204 | 🟡 MEDIUM | Lint Violation | [PLR2004] Magic value used in comparison, consider replacing `32` with a constant variable | Fix ruff violation PLR2004. |
| 222 | 🟡 MEDIUM | Long Method | Function 'export_to_csv' has 50 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 279 | 🟡 MEDIUM | Deep Nesting | Nesting depth 5 in 'export_to_csv' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 341 | 🟡 MEDIUM | Lint Violation | [C901] `export_summary` is too complex (13 > 10) | Fix ruff violation C901. |
| 7 | 🟢 LOW | Lint Violation | [F401] `math` imported but unused | Fix ruff violation F401. |
| 12 | 🟢 LOW | Large Class | Class 'MetricsExporter' spans 431 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
| 22 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 30 | 🟢 LOW | Missing Type Hint | Function 'export_to_json' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 74 | 🟢 LOW | Missing Type Hint | Function '_get_current_timestamp' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 84 | 🟢 LOW | Missing Type Hint | Function '_write_empty_csv' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 92 | 🟢 LOW | Lint Violation | [W293] Blank line contains whitespace | Fix ruff violation W293. |
| 97 | 🟢 LOW | Long Method | Function '_convert_to_prometheus_format' has 47 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 97 | 🟢 LOW | Missing Type Hint | Function '_convert_to_prometheus_format' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 97 | 🟢 LOW | Feature Envy | Method 'MetricsExporter._convert_to_prometheus_format' accesses 'lines' 3 times but 'self' only 2 times | Move Method — consider moving '_convert_to_prometheus_format' to the class that owns 'lines'. |

_... and 72 more smells._

### henchman/tools/builtins/symbol_trace.py — ❌ F (30.0/100)

LOC: 352 | Classes: 4 | Functions: 7 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 242 | 🔴 CRITICAL | Deep Nesting | Nesting depth 8 in '_collect_annotations' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 244 | 🔴 CRITICAL | Deep Nesting | Nesting depth 8 in '_collect_annotations' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 137 | 🟠 HIGH | Deep Nesting | Nesting depth 6 in '_find_definitions_in_file' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 239 | 🟠 HIGH | Deep Nesting | Nesting depth 6 in '_collect_annotations' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 240 | 🟠 HIGH | Deep Nesting | Nesting depth 7 in '_collect_annotations' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 308 | 🟠 HIGH | Primitive Obsession | Repeated primitive parameter group appears in: '_execute_symbol_trace' (line 308), 'execute' (line 412) | Replace Data Value with Object — create a shared data structure for this recurring parameter group. |
| 136 | 🟡 MEDIUM | Deep Nesting | Nesting depth 5 in '_find_definitions_in_file' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 179 | 🟡 MEDIUM | Deep Nesting | Nesting depth 5 in '_find_imports_in_file' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 179 | 🟡 MEDIUM | Lint Violation | [PLR1714] Consider merging multiple comparisons: `symbol in (name, alias.name)`. Use a `set` if the elements are hashable. | Fix ruff violation PLR1714. |
| 212 | 🟡 MEDIUM | Lint Violation | [C901] `_collect_annotations` is too complex (14 > 10) | Fix ruff violation C901. |
| 212 | 🟡 MEDIUM | Lint Violation | [PLR0912] Too many branches (13 > 12) | Fix ruff violation PLR0912. |
| 236 | 🟡 MEDIUM | Deep Nesting | Nesting depth 5 in '_collect_annotations' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 238 | 🟡 MEDIUM | Deep Nesting | Nesting depth 5 in '_collect_annotations' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 250 | 🟡 MEDIUM | Deep Nesting | Nesting depth 5 in '_collect_annotations' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 252 | 🟡 MEDIUM | Deep Nesting | Nesting depth 5 in '_collect_annotations' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |

_... and 29 more smells._

### henchman/utils/intelligent_context.py — ❌ F (30.0/100)

LOC: 2265 | Classes: 16 | Functions: 0 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 138 | 🔴 CRITICAL | Long Method | Function 'extract_code_blocks' has 299 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 245 | 🟠 HIGH | Deep Nesting | Nesting depth 6 in 'extract_code_blocks' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 250 | 🟠 HIGH | Deep Nesting | Nesting depth 7 in 'extract_code_blocks' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 255 | 🟠 HIGH | Deep Nesting | Nesting depth 7 in 'extract_code_blocks' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 291 | 🟠 HIGH | Deep Nesting | Nesting depth 6 in 'extract_code_blocks' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 301 | 🟠 HIGH | Deep Nesting | Nesting depth 6 in 'extract_code_blocks' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 305 | 🟠 HIGH | Deep Nesting | Nesting depth 7 in 'extract_code_blocks' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 314 | 🟠 HIGH | Deep Nesting | Nesting depth 7 in 'extract_code_blocks' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 340 | 🟠 HIGH | Deep Nesting | Nesting depth 6 in 'extract_code_blocks' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 342 | 🟠 HIGH | Deep Nesting | Nesting depth 7 in 'extract_code_blocks' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 377 | 🟠 HIGH | Deep Nesting | Nesting depth 6 in 'extract_code_blocks' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 385 | 🟠 HIGH | Deep Nesting | Nesting depth 7 in 'extract_code_blocks' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 393 | 🟠 HIGH | Deep Nesting | Nesting depth 6 in 'extract_code_blocks' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 398 | 🟠 HIGH | Deep Nesting | Nesting depth 7 in 'extract_code_blocks' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 418 | 🟠 HIGH | Deep Nesting | Nesting depth 6 in 'extract_code_blocks' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |

_... and 179 more smells._

### henchman/tools/builtins/file_overview.py — ❌ F (32.1/100)

LOC: 297 | Classes: 1 | Functions: 10 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 344 | 🟠 HIGH | Duplicate Code | Function 'parameters' is an exact duplicate of 'parameters' at henchman/tools/builtins/pattern_search.py:364 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 344 | 🟠 HIGH | Duplicate Code | Function 'parameters' is an exact duplicate of 'parameters' at henchman/tools/builtins/research_notes.py:328 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 344 | 🟠 HIGH | Duplicate Code | Function 'parameters' is an exact duplicate of 'parameters' at henchman/tools/builtins/symbol_trace.py:403 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 105 | 🟡 MEDIUM | Lint Violation | [PLR2004] Magic value used in comparison, consider replacing `2` with a constant variable | Fix ruff violation PLR2004. |
| 249 | 🟡 MEDIUM | Lint Violation | [PLR2004] Magic value used in comparison, consider replacing `30` with a constant variable | Fix ruff violation PLR2004. |
| 344 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at henchman/tools/builtins/git_ops.py:290 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 344 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at henchman/tools/builtins/glob_tool.py:89 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 344 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at henchman/tools/builtins/web_fetch.py:130 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 353 | 🟡 MEDIUM | Duplicate Code | Function 'execute' is 100% similar to 'execute' at henchman/tools/builtins/pattern_search.py:373 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 353 | 🟡 MEDIUM | Duplicate Code | Function 'execute' is 100% similar to 'execute' at henchman/tools/builtins/symbol_trace.py:412 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 33 | 🟢 LOW | Long Method | Function '_format_function_sig' has 33 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 35 | 🟢 LOW | Lint Violation | [FBT001] Boolean-typed positional argument in function definition | Fix ruff violation FBT001. |
| 83 | 🟢 LOW | Lint Violation | [FBT001] Boolean-typed positional argument in function definition | Fix ruff violation FBT001. |
| 108 | 🟢 LOW | Lint Violation | [PERF401] Use `list.extend` to create a transformed list | Fix ruff violation PERF401. |
| 126 | 🟢 LOW | Lint Violation | [PERF401] Use `list.extend` to create a transformed list | Fix ruff violation PERF401. |

_... and 11 more smells._

### henchman/tools/builtins/deep_research.py — ❌ F (37.7/100)

LOC: 285 | Classes: 4 | Functions: 6 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 320 | 🟠 HIGH | Duplicate Code | Function 'parameters' is an exact duplicate of 'parameters' at henchman/tools/builtins/file_overview.py:344 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 320 | 🟠 HIGH | Duplicate Code | Function 'parameters' is an exact duplicate of 'parameters' at henchman/tools/builtins/pattern_search.py:364 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 320 | 🟠 HIGH | Duplicate Code | Function 'parameters' is an exact duplicate of 'parameters' at henchman/tools/builtins/research_notes.py:328 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 320 | 🟠 HIGH | Duplicate Code | Function 'parameters' is an exact duplicate of 'parameters' at henchman/tools/builtins/symbol_trace.py:403 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 87 | 🟡 MEDIUM | Lint Violation | [PLR2004] Magic value used in comparison, consider replacing `10` with a constant variable | Fix ruff violation PLR2004. |
| 217 | 🟡 MEDIUM | Lint Violation | [PLR2004] Magic value used in comparison, consider replacing `800` with a constant variable | Fix ruff violation PLR2004. |
| 320 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at henchman/tools/builtins/git_ops.py:290 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 320 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at henchman/tools/builtins/glob_tool.py:89 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 320 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at henchman/tools/builtins/web_fetch.py:130 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 53 | 🟢 LOW | Lint Violation | [W293] Blank line contains whitespace | Fix ruff violation W293. |
| 59 | 🟢 LOW | Lint Violation | [W293] Blank line contains whitespace | Fix ruff violation W293. |
| 86 | 🟢 LOW | Lint Violation | [PLW2901] `for` loop variable `sentence` overwritten by assignment target | Fix ruff violation PLW2901. |
| 87 | 🟢 LOW | Magic Number | Magic number 10 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 91 | 🟢 LOW | Magic Number | Magic number 60 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 137 | 🟢 LOW | Magic Number | Magic number 3 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |

_... and 6 more smells._

### henchman/tools/builtins/pattern_search.py — ❌ F (49.6/100)

LOC: 314 | Classes: 2 | Functions: 7 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 225 | 🟠 HIGH | Primitive Obsession | Repeated primitive parameter group appears in: '_execute_pattern_search' (line 225), 'execute' (line 373) | Replace Data Value with Object — create a shared data structure for this recurring parameter group. |
| 364 | 🟠 HIGH | Duplicate Code | Function 'parameters' is an exact duplicate of 'parameters' at henchman/tools/builtins/research_notes.py:328 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 364 | 🟠 HIGH | Duplicate Code | Function 'parameters' is an exact duplicate of 'parameters' at henchman/tools/builtins/symbol_trace.py:403 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 225 | 🟡 MEDIUM | Long Method | Function '_execute_pattern_search' has 58 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 225 | 🟡 MEDIUM | Primitive Obsession | Function '_execute_pattern_search' has 4 primitive-typed parameters: description: Name(id='str', ctx=Load()), path: Name(id='str', ctx=Load()), top_k: Name(id='int', ctx=Load()), strategy: Name(id='str', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 225 | 🟡 MEDIUM | Lint Violation | [C901] `_execute_pattern_search` is too complex (12 > 10) | Fix ruff violation C901. |
| 364 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at henchman/tools/builtins/web_fetch.py:130 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 373 | 🟡 MEDIUM | Primitive Obsession | Function 'execute' has 4 primitive-typed parameters: description: Name(id='str', ctx=Load()), path: Name(id='str', ctx=Load()), top_k: Name(id='int', ctx=Load()), strategy: Name(id='str', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 373 | 🟡 MEDIUM | Duplicate Code | Function 'execute' is 100% similar to 'execute' at henchman/tools/builtins/symbol_trace.py:412 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 61 | 🟢 LOW | Magic Number | Magic number 3 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 64 | 🟢 LOW | Long Method | Function '_extract_structural_patterns' has 35 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 87 | 🟢 LOW | Magic Number | Magic number 3 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 159 | 🟢 LOW | Deep Nesting | Nesting depth 4 in '_search_file_structural' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 217 | 🟢 LOW | Magic Number | Magic number 5 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 333 | 🟢 LOW | Magic Number | Magic number 10 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |

### henchman/core/agent.py — ❌ F (55.2/100)

LOC: 420 | Classes: 1 | Functions: 3 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 248 | 🟡 MEDIUM | Lint Violation | [PLR0912] Too many branches (13 > 12) | Fix ruff violation PLR0912. |
| 306 | 🟡 MEDIUM | Lint Violation | [SIM102] Use a single `if` statement instead of nested `if` statements | Fix ruff violation SIM102. |
| 54 | 🟢 LOW | Lint Violation | [COM812] Trailing comma missing | Fix ruff violation COM812. |
| 140 | 🟢 LOW | Large Class | Class 'Agent' spans 412 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
| 164 | 🟢 LOW | Lint Violation | [PLC0415] `import` should be at the top-level of a file | Fix ruff violation PLC0415. |
| 194 | 🟢 LOW | Long Method | Function '__getattr__' has 42 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 200 | 🟢 LOW | Lint Violation | [W293] Blank line contains whitespace | Fix ruff violation W293. |
| 215 | 🟢 LOW | Lint Violation | [RET505] Unnecessary `elif` after `return` statement | Fix ruff violation RET505. |
| 219 | 🟢 LOW | Lint Violation | [TRY003] Avoid specifying long messages outside the exception class | Fix ruff violation TRY003. |
| 220 | 🟢 LOW | Lint Violation | [EM102] Exception must not use an f-string literal, assign to variable first | Fix ruff violation EM102. |
| 221 | 🟢 LOW | Lint Violation | [COM812] Trailing comma missing | Fix ruff violation COM812. |
| 228 | 🟢 LOW | Lint Violation | [RET505] Unnecessary `else` after `return` statement | Fix ruff violation RET505. |
| 230 | 🟢 LOW | Lint Violation | [TRY003] Avoid specifying long messages outside the exception class | Fix ruff violation TRY003. |
| 231 | 🟢 LOW | Lint Violation | [EM102] Exception must not use an f-string literal, assign to variable first | Fix ruff violation EM102. |
| 232 | 🟢 LOW | Lint Violation | [COM812] Trailing comma missing | Fix ruff violation COM812. |

_... and 14 more smells._

### henchman/agents/orchestrator_anchoring.py — ❌ F (55.9/100)

LOC: 123 | Classes: 0 | Functions: 4 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 77 | 🟠 HIGH | Deep Nesting | Nesting depth 6 in 'assess_agent_completion' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 79 | 🟠 HIGH | Deep Nesting | Nesting depth 7 in 'assess_agent_completion' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 53 | 🟡 MEDIUM | Lint Violation | [C901] `assess_agent_completion` is too complex (12 > 10) | Fix ruff violation C901. |
| 53 | 🟡 MEDIUM | Lint Violation | [PLR0912] Too many branches (13 > 12) | Fix ruff violation PLR0912. |
| 74 | 🟡 MEDIUM | Deep Nesting | Nesting depth 5 in 'assess_agent_completion' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 88 | 🟡 MEDIUM | Lint Violation | [PLR1730] Replace `if` statement with `tool_calls = max(tool_calls, 0)` | Fix ruff violation PLR1730. |
| 107 | 🟡 MEDIUM | Duplicate Code | Function '_is_truthy_failure' is 95% similar to '_file_imports_module' at henchman/tools/builtins/import_graph.py:597 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 53 | 🟢 LOW | Long Method | Function 'assess_agent_completion' has 41 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 72 | 🟢 LOW | Deep Nesting | Nesting depth 4 in 'assess_agent_completion' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 80 | 🟢 LOW | Lint Violation | [TRY003] Avoid specifying long messages outside the exception class | Fix ruff violation TRY003. |
| 81 | 🟢 LOW | Lint Violation | [EM102] Exception must not use an f-string literal, assign to variable first | Fix ruff violation EM102. |
| 81 | 🟢 LOW | Lint Violation | [COM812] Trailing comma missing | Fix ruff violation COM812. |
| 84 | 🟢 LOW | Lint Violation | [TRY003] Avoid specifying long messages outside the exception class | Fix ruff violation TRY003. |
| 85 | 🟢 LOW | Lint Violation | [EM102] Exception must not use an f-string literal, assign to variable first | Fix ruff violation EM102. |
| 85 | 🟢 LOW | Lint Violation | [COM812] Trailing comma missing | Fix ruff violation COM812. |

_... and 1 more smells._

### henchman/tools/builtins/research_notes.py — 🔶 D (60.1/100)

LOC: 300 | Classes: 1 | Functions: 10 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 209 | 🟠 HIGH | Primitive Obsession | Repeated primitive parameter group appears in: '_execute_research_notes' (line 209), 'execute' (line 353) | Replace Data Value with Object — create a shared data structure for this recurring parameter group. |
| 328 | 🟠 HIGH | Duplicate Code | Function 'parameters' is an exact duplicate of 'parameters' at henchman/tools/builtins/symbol_trace.py:403 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 193 | 🟡 MEDIUM | Deep Nesting | Nesting depth 5 in '_action_search' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 209 | 🟡 MEDIUM | Primitive Obsession | Function '_execute_research_notes' has 4 primitive-typed parameters: action: Name(id='str', ctx=Load()), tag: Name(id='str', ctx=Load()), content: Name(id='str', ctx=Load()), query: Name(id='str', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 209 | 🟡 MEDIUM | Lint Violation | [PLR0911] Too many return statements (9 > 6) | Fix ruff violation PLR0911. |
| 328 | 🟡 MEDIUM | Duplicate Code | Function 'parameters' is 100% similar to 'parameters' at henchman/tools/builtins/web_fetch.py:130 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 353 | 🟡 MEDIUM | Primitive Obsession | Function 'execute' has 4 primitive-typed parameters: action: Name(id='str', ctx=Load()), tag: Name(id='str', ctx=Load()), content: Name(id='str', ctx=Load()), query: Name(id='str', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 61 | 🟢 LOW | Lint Violation | [TRY300] Consider moving this statement to an `else` block | Fix ruff violation TRY300. |
| 162 | 🟢 LOW | Magic Number | Magic number 19 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 165 | 🟢 LOW | Lint Violation | [PERF203] `try`-`except` within a loop incurs performance overhead | Fix ruff violation PERF203. |
| 192 | 🟢 LOW | Deep Nesting | Nesting depth 4 in '_action_search' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 194 | 🟢 LOW | Magic Number | Magic number 100 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 209 | 🟢 LOW | Long Method | Function '_execute_research_notes' has 43 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |

### henchman/knowledge/scanner.py — 🔶 D (66.4/100)

LOC: 349 | Classes: 0 | Functions: 13 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 40 | 🟡 MEDIUM | Duplicate Code | Function '_path_to_entity_id' is 100% similar to '_slugify' at henchman/knowledge/store.py:70 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 253 | 🟡 MEDIUM | Long Method | Function '_find_import_target_optimized' has 55 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 253 | 🟡 MEDIUM | Lint Violation | [C901] `_find_import_target_optimized` is too complex (14 > 10) | Fix ruff violation C901. |
| 253 | 🟡 MEDIUM | Lint Violation | [PLR0911] Too many return statements (7 > 6) | Fix ruff violation PLR0911. |
| 354 | 🟡 MEDIUM | Long Method | Function '_scan_file' has 65 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 354 | 🟡 MEDIUM | Lint Violation | [PLR0913] Too many arguments in function definition (6 > 5) | Fix ruff violation PLR0913. |
| 173 | 🟢 LOW | Long Method | Function '_build_module_lookup' has 44 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 200 | 🟢 LOW | Lint Violation | [PIE810] Call `endswith` once with a `tuple` | Fix ruff violation PIE810. |
| 212 | 🟢 LOW | Lint Violation | [PIE810] Call `endswith` once with a `tuple` | Fix ruff violation PIE810. |
| 253 | 🟢 LOW | Primitive Obsession | Function '_find_import_target_optimized' has 3 primitive-typed parameters: mod: Name(id='str', ctx=Load()), file_eid: Name(id='str', ctx=Load()), file_module: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 258 | 🟢 LOW | Lint Violation | [ARG001] Unused function argument: `eid_to_module` | Fix ruff violation ARG001. |
| 321 | 🟢 LOW | Lint Violation | [RET505] Unnecessary `elif` after `return` statement | Fix ruff violation RET505. |
| 358 | 🟢 LOW | Lint Violation | [FBT001] Boolean-typed positional argument in function definition | Fix ruff violation FBT001. |
| 421 | 🟢 LOW | Lint Violation | [COM812] Trailing comma missing | Fix ruff violation COM812. |
| 434 | 🟢 LOW | Lint Violation | [RUF100] Unused `noqa` directive (unused: `C901`, `PLR0912`) | Fix ruff violation RUF100. |

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

### henchman/utils/compression_strategy.py — ⚠️ C (72.0/100)

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
| 187 | 🟢 LOW | Lint Violation | [W293] Blank line contains whitespace | Fix ruff violation W293. |
| 190 | 🟢 LOW | Lint Violation | [W293] Blank line contains whitespace | Fix ruff violation W293. |
| 199 | 🟢 LOW | Feature Envy | Method 'CompressionStrategy._generate_cluster_summary' accesses 'msg' 4 times but 'self' only 0 times | Move Method — consider moving '_generate_cluster_summary' to the class that owns 'msg'. |
| 200 | 🟢 LOW | Lint Violation | [COM812] Trailing comma missing | Fix ruff violation COM812. |
| 201 | 🟢 LOW | Lint Violation | [RUF100] Unused `noqa` directive (unused: `E501`) | Fix ruff violation RUF100. |
| 245 | 🟢 LOW | Deep Nesting | Nesting depth 4 in '_preserve_tool_sequences_in_cluster' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 248 | 🟢 LOW | Feature Envy | Method 'CompressionStrategy._preserve_code_blocks_in_cluster' accesses 'msg' 4 times but 'self' only 0 times | Move Method — consider moving '_preserve_code_blocks_in_cluster' to the class that owns 'msg'. |

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

## ✨ Clean Files (57 files with no smells)

<details><summary>Click to expand</summary>

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
- henchman/version.py — ✅ A

</details>

---

_Report generated by XP Code Smell Detector. Smells are static heuristics — use judgement when prioritising fixes._
