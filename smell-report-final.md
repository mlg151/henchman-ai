# Code Smell Report — 👍 B (Score: 86.9/100)

_Scanned: /home/matthew/mlg-cli/src_  

_Generated: 2026-03-11T19:18:28.086375+00:00_

## Executive Summary

| Metric | Value |
|:-------|------:|
| **Overall Grade** | 👍 B |
| **Overall Score** | 86.9/100 |
| **Files Scanned** | 206 |
| **Total Lines (non-blank)** | 43,983 |
| **Total Smells** | 997 |
| **Avg Maintainability Index** | 100.0 |
| **Avg Cyclomatic Complexity** | 0.0 |

### Smells by Severity

| Severity | Count |
|:---------|------:|
| low | 819 |
| medium | 174 |
| high | 4 |

### Smells by Category

| Category | Count |
|:---------|------:|
| Lint Violation | 328 |
| Missing Type Hint | 228 |
| Duplicate Code | 105 |
| Feature Envy | 88 |
| Long Method | 84 |
| Magic Number | 56 |
| Primitive Obsession | 46 |
| Deep Nesting | 45 |
| Large Class | 17 |

## 🎯 Prioritised Refactoring Queue

These are the highest-impact smells to address first:

1. **henchman/cli/json_output.py:113** — 🟠 HIGH — Duplicate Code  
   Function '_event_to_dict' is an exact duplicate of '_format_tool' at henchman/providers/openai_compat.py:186  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

2. **henchman/utils/intelligent_context.py:346** — 🟠 HIGH — Primitive Obsession  
   Repeated primitive parameter group appears in: '_find_closing_fence' (line 346), '_truncate_with_marker' (line 1167)  
   → _Replace Data Value with Object — create a shared data structure for this recurring parameter group._

3. **henchman/utils/intelligent_context.py:346** — 🟠 HIGH — Feature Envy  
   Method 'ContentExtractor._find_closing_fence' accesses 'state' 12 times but 'self' only 0 times  
   → _Move Method — consider moving '_find_closing_fence' to the class that owns 'state'._

4. **henchman/utils/intelligent_context.py:534** — 🟠 HIGH — Duplicate Code  
   Function 'extract_error_sections' is an exact duplicate of 'extract_tool_sections' at henchman/utils/intelligent_context.py:546  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

5. **/home/matthew/mlg-cli/src/henchman/agents/orchestrator_execution.py:60** — 🟡 MEDIUM — Lint Violation  
   [C901] `run_agent_loop` is too complex (12 > 10)  
   → _Fix ruff violation C901._

6. **/home/matthew/mlg-cli/src/henchman/core/agent.py:248** — 🟡 MEDIUM — Lint Violation  
   [PLR0912] Too many branches (13 > 12)  
   → _Fix ruff violation PLR0912._

7. **/home/matthew/mlg-cli/src/henchman/knowledge/scanner.py:253** — 🟡 MEDIUM — Lint Violation  
   [C901] `_find_import_target_optimized` is too complex (14 > 10)  
   → _Fix ruff violation C901._

8. **/home/matthew/mlg-cli/src/henchman/knowledge/scanner.py:253** — 🟡 MEDIUM — Lint Violation  
   [PLR0911] Too many return statements (7 > 6)  
   → _Fix ruff violation PLR0911._

9. **/home/matthew/mlg-cli/src/henchman/knowledge/scanner.py:354** — 🟡 MEDIUM — Lint Violation  
   [PLR0913] Too many arguments in function definition (6 > 5)  
   → _Fix ruff violation PLR0913._

10. **/home/matthew/mlg-cli/src/henchman/metrics/exporter.py:273** — 🟡 MEDIUM — Lint Violation  
   [SIM118] Use `key in dict` instead of `key in dict.keys()`  
   → _Fix ruff violation SIM118._

11. **/home/matthew/mlg-cli/src/henchman/tools/base.py:105** — 🟡 MEDIUM — Lint Violation  
   [B009] Do not call `getattr` with a constant attribute value. It is not any safer than normal property access.  
   → _Fix ruff violation B009._

12. **/home/matthew/mlg-cli/src/henchman/tools/builtins/deep_research.py:87** — 🟡 MEDIUM — Lint Violation  
   [PLR2004] Magic value used in comparison, consider replacing `10` with a constant variable  
   → _Fix ruff violation PLR2004._

13. **/home/matthew/mlg-cli/src/henchman/tools/builtins/deep_research.py:217** — 🟡 MEDIUM — Lint Violation  
   [PLR2004] Magic value used in comparison, consider replacing `800` with a constant variable  
   → _Fix ruff violation PLR2004._

14. **/home/matthew/mlg-cli/src/henchman/tools/builtins/file_overview.py:105** — 🟡 MEDIUM — Lint Violation  
   [PLR2004] Magic value used in comparison, consider replacing `2` with a constant variable  
   → _Fix ruff violation PLR2004._

15. **/home/matthew/mlg-cli/src/henchman/tools/builtins/file_overview.py:249** — 🟡 MEDIUM — Lint Violation  
   [PLR2004] Magic value used in comparison, consider replacing `30` with a constant variable  
   → _Fix ruff violation PLR2004._


## 📊 Files Ranked by Quality

| Rank | File | Grade | Score | Smells | LOC | MI | Avg CC |
|-----:|:-----|:------|------:|-------:|----:|---:|-------:|
| 1 | henchman/utils/intelligent_context.py | ❌ F | 30.0 | 174 | 2343 | 100 | 0.0 |
| 2 | henchman/agents/working_memory.py | ❌ F | 36.3 | 41 | 365 | 100 | 0.0 |
| 3 | henchman/metrics/exporter.py | ❌ F | 40.5 | 41 | 324 | 100 | 0.0 |
| 4 | henchman/core/agent.py | ❌ F | 58.7 | 28 | 420 | 100 | 0.0 |
| 5 | henchman/tools/builtins/symbol_trace.py | 🔶 D | 60.1 | 24 | 381 | 100 | 0.0 |
| 6 | henchman/knowledge/scanner.py | 🔶 D | 66.4 | 15 | 349 | 100 | 0.0 |
| 7 | henchman/utils/message_compactor.py | 🔶 D | 66.4 | 24 | 235 | 100 | 0.0 |
| 8 | henchman/tools/builtins/file_overview.py | 🔶 D | 67.1 | 19 | 293 | 100 | 0.0 |
| 9 | henchman/cli/textual_screens.py | 🔶 D | 69.2 | 22 | 398 | 100 | 0.0 |
| 10 | henchman/agents/ledger.py | ⚠️ C | 70.6 | 15 | 411 | 100 | 0.0 |

## 📁 Per-File Details

_Showing 20 worst files. 186 additional files omitted._

### henchman/utils/intelligent_context.py — ❌ F (30.0/100)

LOC: 2343 | Classes: 18 | Functions: 0 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 346 | 🟠 HIGH | Primitive Obsession | Repeated primitive parameter group appears in: '_find_closing_fence' (line 346), '_truncate_with_marker' (line 1167) | Replace Data Value with Object — create a shared data structure for this recurring parameter group. |
| 346 | 🟠 HIGH | Feature Envy | Method 'ContentExtractor._find_closing_fence' accesses 'state' 12 times but 'self' only 0 times | Move Method — consider moving '_find_closing_fence' to the class that owns 'state'. |
| 534 | 🟠 HIGH | Duplicate Code | Function 'extract_error_sections' is an exact duplicate of 'extract_tool_sections' at henchman/utils/intelligent_context.py:546 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 261 | 🟡 MEDIUM | Lint Violation | [SIM103] Return the negated condition directly | Fix ruff violation SIM103. |
| 346 | 🟡 MEDIUM | Lint Violation | [C901] `_find_closing_fence` is too complex (11 > 10) | Fix ruff violation C901. |
| 362 | 🟡 MEDIUM | Lint Violation | [SIM102] Use a single `if` statement instead of nested `if` statements | Fix ruff violation SIM102. |
| 401 | 🟡 MEDIUM | Lint Violation | [PLR2004] Magic value used in comparison, consider replacing `6` with a constant variable | Fix ruff violation PLR2004. |
| 404 | 🟡 MEDIUM | Lint Violation | [PLR2004] Magic value used in comparison, consider replacing `3` with a constant variable | Fix ruff violation PLR2004. |
| 423 | 🟡 MEDIUM | Lint Violation | [SIM108] Use ternary operator `block = f"```{language}\n{code_content}\n```" if language else f"```\n{code_content}\n```"` instead of `if`-`else`-block | Fix ruff violation SIM108. |
| 1413 | 🟡 MEDIUM | Feature Envy | Method 'SequenceValidator.validate_compacted_sequence' accesses 'cls' 5 times but 'self' only 0 times | Move Method — consider moving 'validate_compacted_sequence' to the class that owns 'cls'. |
| 2331 | 🟡 MEDIUM | Large Class | Class 'IntelligentContextManager' spans 733 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
| 2346 | 🟡 MEDIUM | Primitive Obsession | Function '__init__' has 5 primitive-typed parameters: max_tokens: BinOp(left=Name(id='int', ctx=Load()), op=BitOr(), right=Constant(value=None)), max_protected_ratio: BinOp(left=Name(id='float', ctx=Load()), op=BitOr(), right=Constant(value=None)), importance_threshold: BinOp(left=Name(id='float', ctx=Load()), op=BitOr(), right=Constant(value=None)), cluster_similarity_threshold: BinOp(left=Name(id='float', ctx=Load()), op=BitOr(), right=Constant(value=None)), adaptive_compression: BinOp(left=Name(id='bool', ctx=Load()), op=BitOr(), right=Constant(value=None)) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 2346 | 🟡 MEDIUM | Lint Violation | [PLR0913] Too many arguments in function definition (6 > 5) | Fix ruff violation PLR0913. |
| 2472 | 🟡 MEDIUM | Feature Envy | Method 'IntelligentContextManager._apply_intelligent_truncation_with_semantic_preservation' accesses 'message' 5 times but 'self' only 2 times | Move Method — consider moving '_apply_intelligent_truncation_with_semantic_preservation' to the class that owns 'message'. |
| 2506 | 🟡 MEDIUM | Duplicate Code | Function '_count_tokens' is 100% similar to 'validate_compacted_sequence' at henchman/utils/intelligent_context.py:2897 | Extract Shared Function — identify the common logic and parameterise the differences. |

_... and 159 more smells._

### henchman/agents/working_memory.py — ❌ F (36.3/100)

LOC: 365 | Classes: 8 | Functions: 0 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 35 | 🟡 MEDIUM | Duplicate Code | Function 'to_dict' is 93% similar to '_event_to_dict' at henchman/cli/json_output.py:113 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 35 | 🟡 MEDIUM | Duplicate Code | Function 'to_dict' is 100% similar to 'to_dict' at henchman/core/session_models.py:20 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 35 | 🟡 MEDIUM | Duplicate Code | Function 'to_dict' is 93% similar to '_format_tool' at henchman/providers/openai_compat.py:186 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 9 | 🟢 LOW | Lint Violation | [I001] Import block is un-sorted or un-formatted | Fix ruff violation I001. |
| 35 | 🟢 LOW | Missing Type Hint | Function 'to_dict' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 44 | 🟢 LOW | Lint Violation | [PYI019] Use `Self` instead of custom TypeVar `T` | Fix ruff violation PYI019. |
| 55 | 🟢 LOW | Lint Violation | [W293] Blank line contains whitespace | Fix ruff violation W293. |
| 60 | 🟢 LOW | Lint Violation | [W293] Blank line contains whitespace | Fix ruff violation W293. |
| 63 | 🟢 LOW | Lint Violation | [W293] Blank line contains whitespace | Fix ruff violation W293. |
| 68 | 🟢 LOW | Lint Violation | [W293] Blank line contains whitespace | Fix ruff violation W293. |
| 72 | 🟢 LOW | Missing Type Hint | Function '_deserialize_field' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 185 | 🟢 LOW | Missing Type Hint | Function 'overlaps' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 197 | 🟢 LOW | Missing Type Hint | Function 'from_str' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 242 | 🟢 LOW | Missing Type Hint | Function 'add_recent_file' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 250 | 🟢 LOW | Missing Type Hint | Function 'add_decision' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |

_... and 26 more smells._

### henchman/metrics/exporter.py — ❌ F (40.5/100)

LOC: 324 | Classes: 1 | Functions: 0 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 273 | 🟡 MEDIUM | Lint Violation | [SIM118] Use `key in dict` instead of `key in dict.keys()` | Fix ruff violation SIM118. |
| 6 | 🟢 LOW | Lint Violation | [I001] Import block is un-sorted or un-formatted | Fix ruff violation I001. |
| 19 | 🟢 LOW | Large Class | Class 'MetricsExporter' spans 460 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
| 29 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 37 | 🟢 LOW | Missing Type Hint | Function '_get_filtered_metrics' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 56 | 🟢 LOW | Missing Type Hint | Function 'export_to_json' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 92 | 🟢 LOW | Missing Type Hint | Function '_get_current_timestamp' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 102 | 🟢 LOW | Missing Type Hint | Function '_write_empty_csv' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 115 | 🟢 LOW | Long Method | Function '_convert_to_prometheus_format' has 34 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 115 | 🟢 LOW | Missing Type Hint | Function '_convert_to_prometheus_format' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 160 | 🟢 LOW | Missing Type Hint | Function '_extract_metric_value' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 176 | 🟢 LOW | Missing Type Hint | Function '_sanitize_prometheus_name' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 185 | 🟢 LOW | Lint Violation | [PLC0415] `import` should be at the top-level of a file | Fix ruff violation PLC0415. |
| 188 | 🟢 LOW | Lint Violation | [Q000] Single quotes found but double quotes preferred | Fix ruff violation Q000. |
| 188 | 🟢 LOW | Lint Violation | [Q000] Single quotes found but double quotes preferred | Fix ruff violation Q000. |

_... and 26 more smells._

### henchman/core/agent.py — ❌ F (58.7/100)

LOC: 420 | Classes: 1 | Functions: 3 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 248 | 🟡 MEDIUM | Lint Violation | [PLR0912] Too many branches (13 > 12) | Fix ruff violation PLR0912. |
| 54 | 🟢 LOW | Lint Violation | [COM812] Trailing comma missing | Fix ruff violation COM812. |
| 140 | 🟢 LOW | Large Class | Class 'Agent' spans 411 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
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
| 240 | 🟢 LOW | Lint Violation | [TRY003] Avoid specifying long messages outside the exception class | Fix ruff violation TRY003. |

_... and 13 more smells._

### henchman/tools/builtins/symbol_trace.py — 🔶 D (60.1/100)

LOC: 381 | Classes: 5 | Functions: 11 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 153 | 🟡 MEDIUM | Deep Nesting | Nesting depth 5 in '_find_definitions_in_file' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 195 | 🟡 MEDIUM | Deep Nesting | Nesting depth 5 in '_find_imports_in_file' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 195 | 🟡 MEDIUM | Lint Violation | [PLR1714] Consider merging multiple comparisons: `symbol in (name, alias.name)`. Use a `set` if the elements are hashable. | Fix ruff violation PLR1714. |
| 77 | 🟢 LOW | Lint Violation | [FBT001] Boolean-typed positional argument in function definition | Fix ruff violation FBT001. |
| 100 | 🟢 LOW | Magic Number | Magic number 120 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 106 | 🟢 LOW | Long Method | Function '_find_definitions_in_file' has 45 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 146 | 🟢 LOW | Lint Violation | [COM812] Trailing comma missing | Fix ruff violation COM812. |
| 152 | 🟢 LOW | Deep Nesting | Nesting depth 4 in '_find_definitions_in_file' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 154 | 🟢 LOW | Lint Violation | [PERF401] Use `list.extend` to create a transformed list | Fix ruff violation PERF401. |
| 160 | 🟢 LOW | Lint Violation | [COM812] Trailing comma missing | Fix ruff violation COM812. |
| 188 | 🟢 LOW | Deep Nesting | Nesting depth 4 in '_find_imports_in_file' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 193 | 🟢 LOW | Deep Nesting | Nesting depth 4 in '_find_imports_in_file' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 229 | 🟢 LOW | Lint Violation | [COM812] Trailing comma missing | Fix ruff violation COM812. |
| 241 | 🟢 LOW | Lint Violation | [COM812] Trailing comma missing | Fix ruff violation COM812. |
| 250 | 🟢 LOW | Deep Nesting | Nesting depth 4 in '_collect_annotations_from_node' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |

_... and 9 more smells._

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

### henchman/tools/builtins/file_overview.py — 🔶 D (67.1/100)

LOC: 293 | Classes: 1 | Functions: 10 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 105 | 🟡 MEDIUM | Lint Violation | [PLR2004] Magic value used in comparison, consider replacing `2` with a constant variable | Fix ruff violation PLR2004. |
| 249 | 🟡 MEDIUM | Lint Violation | [PLR2004] Magic value used in comparison, consider replacing `30` with a constant variable | Fix ruff violation PLR2004. |
| 347 | 🟡 MEDIUM | Duplicate Code | Function 'execute' is 96% similar to 'execute' at henchman/tools/builtins/pattern_search.py:363 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 33 | 🟢 LOW | Long Method | Function '_format_function_sig' has 33 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 35 | 🟢 LOW | Lint Violation | [FBT001] Boolean-typed positional argument in function definition | Fix ruff violation FBT001. |
| 83 | 🟢 LOW | Lint Violation | [FBT001] Boolean-typed positional argument in function definition | Fix ruff violation FBT001. |
| 108 | 🟢 LOW | Lint Violation | [PERF401] Use `list.extend` to create a transformed list | Fix ruff violation PERF401. |
| 126 | 🟢 LOW | Lint Violation | [PERF401] Use `list.extend` to create a transformed list | Fix ruff violation PERF401. |
| 134 | 🟢 LOW | Primitive Obsession | Function '_summarize_python' has 3 primitive-typed parameters: source: Name(id='str', ctx=Load()), depth: Name(id='int', ctx=Load()), include_docs: Name(id='bool', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 134 | 🟢 LOW | Lint Violation | [FBT001] Boolean-typed positional argument in function definition | Fix ruff violation FBT001. |
| 163 | 🟢 LOW | Magic Number | Magic number 200 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 203 | 🟢 LOW | Magic Number | Magic number 20 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 226 | 🟢 LOW | Magic Number | Magic number 20 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 249 | 🟢 LOW | Magic Number | Magic number 30 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 251 | 🟢 LOW | Magic Number | Magic number 15 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |

_... and 4 more smells._

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

### henchman/tools/builtins/deep_research.py — ⚠️ C (77.6/100)

LOC: 281 | Classes: 4 | Functions: 6 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 87 | 🟡 MEDIUM | Lint Violation | [PLR2004] Magic value used in comparison, consider replacing `10` with a constant variable | Fix ruff violation PLR2004. |
| 217 | 🟡 MEDIUM | Lint Violation | [PLR2004] Magic value used in comparison, consider replacing `800` with a constant variable | Fix ruff violation PLR2004. |
| 53 | 🟢 LOW | Lint Violation | [W293] Blank line contains whitespace | Fix ruff violation W293. |
| 86 | 🟢 LOW | Lint Violation | [PLW2901] `for` loop variable `sentence` overwritten by assignment target | Fix ruff violation PLW2901. |
| 87 | 🟢 LOW | Magic Number | Magic number 10 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 91 | 🟢 LOW | Magic Number | Magic number 60 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 137 | 🟢 LOW | Magic Number | Magic number 3 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 139 | 🟢 LOW | Deep Nesting | Nesting depth 4 in '_search_duckduckgo' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 216 | 🟢 LOW | Magic Number | Magic number 800 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 217 | 🟢 LOW | Magic Number | Magic number 800 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 225 | 🟢 LOW | Lint Violation | [PERF401] Use `list.extend` to create a transformed list | Fix ruff violation PERF401. |
| 256 | 🟢 LOW | Deep Nesting | Nesting depth 4 in '_execute_deep_research' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 323 | 🟢 LOW | Primitive Obsession | Function 'execute' has 3 primitive-typed parameters: question: Name(id='str', ctx=Load()), max_sources: Name(id='int', ctx=Load()), focus: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |

### henchman/tools/builtins/research_notes.py — ⚠️ C (78.3/100)

LOC: 303 | Classes: 2 | Functions: 10 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 204 | 🟡 MEDIUM | Deep Nesting | Nesting depth 5 in '_action_search' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 220 | 🟡 MEDIUM | Lint Violation | [PLR0911] Too many return statements (9 > 6) | Fix ruff violation PLR0911. |
| 349 | 🟡 MEDIUM | Primitive Obsession | Function 'execute' has 4 primitive-typed parameters: action: Name(id='str', ctx=Load()), tag: Name(id='str', ctx=Load()), content: Name(id='str', ctx=Load()), query: Name(id='str', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 72 | 🟢 LOW | Lint Violation | [TRY300] Consider moving this statement to an `else` block | Fix ruff violation TRY300. |
| 173 | 🟢 LOW | Magic Number | Magic number 19 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 176 | 🟢 LOW | Lint Violation | [PERF203] `try`-`except` within a loop incurs performance overhead | Fix ruff violation PERF203. |
| 203 | 🟢 LOW | Deep Nesting | Nesting depth 4 in '_action_search' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 205 | 🟢 LOW | Magic Number | Magic number 100 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 220 | 🟢 LOW | Long Method | Function '_execute_research_notes' has 43 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 375 | 🟢 LOW | Lint Violation | [COM812] Trailing comma missing | Fix ruff violation COM812. |
| 376 | 🟢 LOW | Lint Violation | [COM812] Trailing comma missing | Fix ruff violation COM812. |

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
