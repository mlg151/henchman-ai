# Code Smell Report — 👍 B (Score: 86.6/100)

_Scanned: /home/matthew/mlg-cli/src_  

_Generated: 2026-03-11T19:36:29.725570+00:00_

## Executive Summary

| Metric | Value |
|:-------|------:|
| **Overall Grade** | 👍 B |
| **Overall Score** | 86.6/100 |
| **Files Scanned** | 210 |
| **Total Lines (non-blank)** | 44,614 |
| **Total Smells** | 1067 |
| **Avg Maintainability Index** | 100.0 |
| **Avg Cyclomatic Complexity** | 0.0 |

### Smells by Severity

| Severity | Count |
|:---------|------:|
| low | 869 |
| medium | 174 |
| high | 24 |

### Smells by Category

| Category | Count |
|:---------|------:|
| Lint Violation | 332 |
| Missing Type Hint | 253 |
| Duplicate Code | 130 |
| Feature Envy | 94 |
| Long Method | 86 |
| Magic Number | 62 |
| Deep Nesting | 47 |
| Primitive Obsession | 46 |
| Large Class | 17 |

## 🎯 Prioritised Refactoring Queue

These are the highest-impact smells to address first:

1. **henchman/utils/content_extractor.py:77** — 🟠 HIGH — Duplicate Code  
   Function 'from_sections' is an exact duplicate of 'from_sections' at henchman/utils/intelligent_context.py:45  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

2. **henchman/utils/content_extractor.py:106** — 🟠 HIGH — Duplicate Code  
   Function 'not_found' is an exact duplicate of 'not_found' at henchman/utils/intelligent_context.py:121  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

3. **henchman/utils/content_extractor.py:129** — 🟠 HIGH — Duplicate Code  
   Function 'handle_backslash' is an exact duplicate of 'handle_backslash' at henchman/utils/intelligent_context.py:144  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

4. **henchman/utils/content_extractor.py:152** — 🟠 HIGH — Duplicate Code  
   Function 'handle_string_start' is an exact duplicate of 'handle_string_start' at henchman/utils/intelligent_context.py:167  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

5. **henchman/utils/content_extractor.py:179** — 🟠 HIGH — Duplicate Code  
   Function 'handle_string_end' is an exact duplicate of 'handle_string_end' at henchman/utils/intelligent_context.py:194  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

6. **henchman/utils/content_extractor.py:205** — 🟠 HIGH — Duplicate Code  
   Function 'handle_backticks' is an exact duplicate of 'handle_backticks' at henchman/utils/intelligent_context.py:220  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

7. **henchman/utils/content_extractor.py:249** — 🟠 HIGH — Duplicate Code  
   Function 'find_closing_fence' is an exact duplicate of 'find_closing_fence' at henchman/utils/intelligent_context.py:269  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

8. **henchman/utils/content_extractor.py:319** — 🟠 HIGH — Duplicate Code  
   Function '_count_backticks' is an exact duplicate of '_count_backticks' at henchman/utils/intelligent_context.py:345  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

9. **henchman/utils/content_extractor.py:330** — 🟠 HIGH — Duplicate Code  
   Function '_parse_language' is an exact duplicate of '_parse_language' at henchman/utils/intelligent_context.py:360  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

10. **henchman/utils/content_extractor.py:354** — 🟠 HIGH — Duplicate Code  
   Function '_extract_single_block' is an exact duplicate of '_extract_single_block' at henchman/utils/intelligent_context.py:390  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

11. **henchman/utils/content_extractor.py:385** — 🟠 HIGH — Duplicate Code  
   Function 'extract_code_blocks' is an exact duplicate of 'extract_code_blocks' at henchman/utils/intelligent_context.py:428  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

12. **henchman/utils/content_extractor.py:407** — 🟠 HIGH — Duplicate Code  
   Function '_extract_by_patterns' is an exact duplicate of '_extract_by_patterns' at henchman/utils/intelligent_context.py:458  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

13. **henchman/utils/content_extractor.py:423** — 🟠 HIGH — Duplicate Code  
   Function '_add_unique_match' is an exact duplicate of '_add_unique_match' at henchman/utils/intelligent_context.py:486  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

14. **henchman/utils/content_extractor.py:442** — 🟠 HIGH — Duplicate Code  
   Function 'extract_error_sections' is an exact duplicate of 'extract_tool_sections' at henchman/utils/content_extractor.py:447  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

15. **henchman/utils/content_extractor.py:442** — 🟠 HIGH — Duplicate Code  
   Function 'extract_error_sections' is an exact duplicate of 'extract_tool_sections' at henchman/utils/intelligent_context.py:544  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._


## 📊 Files Ranked by Quality

| Rank | File | Grade | Score | Smells | LOC | MI | Avg CC |
|-----:|:-----|:------|------:|-------:|----:|---:|-------:|
| 1 | henchman/utils/content_extractor.py | ❌ F | 30.0 | 56 | 403 | 100 | 0.0 |
| 2 | henchman/utils/intelligent_context.py | ❌ F | 30.0 | 173 | 2344 | 100 | 0.0 |
| 3 | henchman/metrics/exporter.py | ❌ F | 45.4 | 39 | 324 | 100 | 0.0 |
| 4 | henchman/agents/working_memory.py | ❌ F | 48.2 | 34 | 365 | 100 | 0.0 |
| 5 | henchman/tools/builtins/symbol_trace.py | 🔶 D | 60.1 | 24 | 381 | 100 | 0.0 |
| 6 | henchman/core/agent.py | 🔶 D | 64.3 | 24 | 420 | 100 | 0.0 |
| 7 | henchman/knowledge/scanner.py | 🔶 D | 66.4 | 15 | 349 | 100 | 0.0 |
| 8 | henchman/utils/message_compactor.py | 🔶 D | 66.4 | 24 | 235 | 100 | 0.0 |
| 9 | henchman/tools/builtins/file_overview.py | 🔶 D | 67.1 | 19 | 293 | 100 | 0.0 |
| 10 | henchman/cli/textual_screens.py | 🔶 D | 69.2 | 22 | 398 | 100 | 0.0 |

## 📁 Per-File Details

_Showing 20 worst files. 190 additional files omitted._

### henchman/utils/content_extractor.py — ❌ F (30.0/100)

LOC: 403 | Classes: 5 | Functions: 0 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 77 | 🟠 HIGH | Duplicate Code | Function 'from_sections' is an exact duplicate of 'from_sections' at henchman/utils/intelligent_context.py:45 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 106 | 🟠 HIGH | Duplicate Code | Function 'not_found' is an exact duplicate of 'not_found' at henchman/utils/intelligent_context.py:121 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 129 | 🟠 HIGH | Duplicate Code | Function 'handle_backslash' is an exact duplicate of 'handle_backslash' at henchman/utils/intelligent_context.py:144 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 152 | 🟠 HIGH | Duplicate Code | Function 'handle_string_start' is an exact duplicate of 'handle_string_start' at henchman/utils/intelligent_context.py:167 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 179 | 🟠 HIGH | Duplicate Code | Function 'handle_string_end' is an exact duplicate of 'handle_string_end' at henchman/utils/intelligent_context.py:194 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 205 | 🟠 HIGH | Duplicate Code | Function 'handle_backticks' is an exact duplicate of 'handle_backticks' at henchman/utils/intelligent_context.py:220 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 249 | 🟠 HIGH | Duplicate Code | Function 'find_closing_fence' is an exact duplicate of 'find_closing_fence' at henchman/utils/intelligent_context.py:269 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 319 | 🟠 HIGH | Duplicate Code | Function '_count_backticks' is an exact duplicate of '_count_backticks' at henchman/utils/intelligent_context.py:345 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 330 | 🟠 HIGH | Duplicate Code | Function '_parse_language' is an exact duplicate of '_parse_language' at henchman/utils/intelligent_context.py:360 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 354 | 🟠 HIGH | Duplicate Code | Function '_extract_single_block' is an exact duplicate of '_extract_single_block' at henchman/utils/intelligent_context.py:390 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 385 | 🟠 HIGH | Duplicate Code | Function 'extract_code_blocks' is an exact duplicate of 'extract_code_blocks' at henchman/utils/intelligent_context.py:428 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 407 | 🟠 HIGH | Duplicate Code | Function '_extract_by_patterns' is an exact duplicate of '_extract_by_patterns' at henchman/utils/intelligent_context.py:458 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 423 | 🟠 HIGH | Duplicate Code | Function '_add_unique_match' is an exact duplicate of '_add_unique_match' at henchman/utils/intelligent_context.py:486 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 442 | 🟠 HIGH | Duplicate Code | Function 'extract_error_sections' is an exact duplicate of 'extract_tool_sections' at henchman/utils/content_extractor.py:447 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 442 | 🟠 HIGH | Duplicate Code | Function 'extract_error_sections' is an exact duplicate of 'extract_tool_sections' at henchman/utils/intelligent_context.py:544 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |

_... and 41 more smells._

### henchman/utils/intelligent_context.py — ❌ F (30.0/100)

LOC: 2344 | Classes: 18 | Functions: 0 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 882 | 🟠 HIGH | Duplicate Code | Function '__init__' is an exact duplicate of '__init__' at henchman/utils/message_safety_enforcer.py:12 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 893 | 🟠 HIGH | Duplicate Code | Function 'enforce_safety_limits' is an exact duplicate of 'enforce_safety_limits' at henchman/utils/message_safety_enforcer.py:23 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 940 | 🟠 HIGH | Duplicate Code | Function '_create_truncated_message' is an exact duplicate of '_create_truncated_message' at henchman/utils/message_safety_enforcer.py:46 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 971 | 🟠 HIGH | Duplicate Code | Function 'count_messages_tokens' is an exact duplicate of 'count_messages_tokens' at henchman/utils/message_safety_enforcer.py:69 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 400 | 🟡 MEDIUM | Lint Violation | [PLR2004] Magic value used in comparison, consider replacing `6` with a constant variable | Fix ruff violation PLR2004. |
| 403 | 🟡 MEDIUM | Lint Violation | [PLR2004] Magic value used in comparison, consider replacing `3` with a constant variable | Fix ruff violation PLR2004. |
| 1173 | 🟡 MEDIUM | Lint Violation | [PLR2004] Magic value used in comparison, consider replacing `2` with a constant variable | Fix ruff violation PLR2004. |
| 1415 | 🟡 MEDIUM | Feature Envy | Method 'SequenceValidator.validate_compacted_sequence' accesses 'cls' 5 times but 'self' only 0 times | Move Method — consider moving 'validate_compacted_sequence' to the class that owns 'cls'. |
| 2333 | 🟡 MEDIUM | Large Class | Class 'IntelligentContextManager' spans 733 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
| 2348 | 🟡 MEDIUM | Primitive Obsession | Function '__init__' has 5 primitive-typed parameters: max_tokens: BinOp(left=Name(id='int', ctx=Load()), op=BitOr(), right=Constant(value=None)), max_protected_ratio: BinOp(left=Name(id='float', ctx=Load()), op=BitOr(), right=Constant(value=None)), importance_threshold: BinOp(left=Name(id='float', ctx=Load()), op=BitOr(), right=Constant(value=None)), cluster_similarity_threshold: BinOp(left=Name(id='float', ctx=Load()), op=BitOr(), right=Constant(value=None)), adaptive_compression: BinOp(left=Name(id='bool', ctx=Load()), op=BitOr(), right=Constant(value=None)) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 2348 | 🟡 MEDIUM | Lint Violation | [PLR0913] Too many arguments in function definition (6 > 5) | Fix ruff violation PLR0913. |
| 2474 | 🟡 MEDIUM | Feature Envy | Method 'IntelligentContextManager._apply_intelligent_truncation_with_semantic_preservation' accesses 'message' 5 times but 'self' only 2 times | Move Method — consider moving '_apply_intelligent_truncation_with_semantic_preservation' to the class that owns 'message'. |
| 2508 | 🟡 MEDIUM | Duplicate Code | Function '_count_tokens' is 100% similar to 'validate_compacted_sequence' at henchman/utils/intelligent_context.py:2899 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 2989 | 🟡 MEDIUM | Duplicate Code | Function '_calculate_cluster_importance' is 95% similar to '_preserve_critical_context' at henchman/utils/intelligent_context.py:3043 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 3043 | 🟡 MEDIUM | Duplicate Code | Function '_preserve_critical_context' is 95% similar to '_calculate_importance_scores' at henchman/utils/message_analyzer.py:71 | Extract Shared Function — identify the common logic and parameterise the differences. |

_... and 158 more smells._

### henchman/metrics/exporter.py — ❌ F (45.4/100)

LOC: 324 | Classes: 1 | Functions: 0 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 18 | 🟢 LOW | Large Class | Class 'MetricsExporter' spans 460 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
| 28 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 36 | 🟢 LOW | Missing Type Hint | Function '_get_filtered_metrics' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 55 | 🟢 LOW | Missing Type Hint | Function 'export_to_json' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 91 | 🟢 LOW | Missing Type Hint | Function '_get_current_timestamp' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 101 | 🟢 LOW | Missing Type Hint | Function '_write_empty_csv' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 114 | 🟢 LOW | Long Method | Function '_convert_to_prometheus_format' has 34 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 114 | 🟢 LOW | Missing Type Hint | Function '_convert_to_prometheus_format' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 159 | 🟢 LOW | Missing Type Hint | Function '_extract_metric_value' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 175 | 🟢 LOW | Missing Type Hint | Function '_sanitize_prometheus_name' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 184 | 🟢 LOW | Lint Violation | [PLC0415] `import` should be at the top-level of a file | Fix ruff violation PLC0415. |
| 187 | 🟢 LOW | Lint Violation | [Q000] Single quotes found but double quotes preferred | Fix ruff violation Q000. |
| 187 | 🟢 LOW | Lint Violation | [Q000] Single quotes found but double quotes preferred | Fix ruff violation Q000. |
| 195 | 🟢 LOW | Missing Type Hint | Function '_build_prometheus_labels' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 223 | 🟢 LOW | Lint Violation | [Q000] Single quotes found but double quotes preferred | Fix ruff violation Q000. |

_... and 24 more smells._

### henchman/agents/working_memory.py — ❌ F (48.2/100)

LOC: 365 | Classes: 8 | Functions: 0 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 35 | 🟡 MEDIUM | Duplicate Code | Function 'to_dict' is 100% similar to 'to_dict' at henchman/core/session_models.py:20 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 35 | 🟡 MEDIUM | Duplicate Code | Function 'to_dict' is 93% similar to '_format_tool' at henchman/providers/openai_compat.py:186 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 35 | 🟢 LOW | Missing Type Hint | Function 'to_dict' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 44 | 🟢 LOW | Lint Violation | [PYI019] Use `Self` instead of custom TypeVar `T` | Fix ruff violation PYI019. |
| 72 | 🟢 LOW | Missing Type Hint | Function '_deserialize_field' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 185 | 🟢 LOW | Missing Type Hint | Function 'overlaps' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 197 | 🟢 LOW | Missing Type Hint | Function 'from_str' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 242 | 🟢 LOW | Missing Type Hint | Function 'add_recent_file' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 250 | 🟢 LOW | Missing Type Hint | Function 'add_decision' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 258 | 🟢 LOW | Missing Type Hint | Function 'add_completed_step' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 266 | 🟢 LOW | Missing Type Hint | Function 'add_next_action' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 274 | 🟢 LOW | Missing Type Hint | Function 'add_insight' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 282 | 🟢 LOW | Missing Type Hint | Function 'add_problem' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 290 | 🟢 LOW | Missing Type Hint | Function 'update_problem' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 290 | 🟢 LOW | Feature Envy | Method 'WorkingMemory.update_problem' accesses 'entry' 3 times but 'self' only 1 times | Move Method — consider moving 'update_problem' to the class that owns 'entry'. |

_... and 19 more smells._

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

### henchman/core/agent.py — 🔶 D (64.3/100)

LOC: 420 | Classes: 1 | Functions: 3 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 248 | 🟡 MEDIUM | Lint Violation | [PLR0912] Too many branches (13 > 12) | Fix ruff violation PLR0912. |
| 54 | 🟢 LOW | Lint Violation | [COM812] Trailing comma missing | Fix ruff violation COM812. |
| 140 | 🟢 LOW | Large Class | Class 'Agent' spans 411 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
| 164 | 🟢 LOW | Lint Violation | [PLC0415] `import` should be at the top-level of a file | Fix ruff violation PLC0415. |
| 194 | 🟢 LOW | Long Method | Function '__getattr__' has 42 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 215 | 🟢 LOW | Lint Violation | [RET505] Unnecessary `elif` after `return` statement | Fix ruff violation RET505. |
| 219 | 🟢 LOW | Lint Violation | [TRY003] Avoid specifying long messages outside the exception class | Fix ruff violation TRY003. |
| 220 | 🟢 LOW | Lint Violation | [EM102] Exception must not use an f-string literal, assign to variable first | Fix ruff violation EM102. |
| 221 | 🟢 LOW | Lint Violation | [COM812] Trailing comma missing | Fix ruff violation COM812. |
| 228 | 🟢 LOW | Lint Violation | [RET505] Unnecessary `else` after `return` statement | Fix ruff violation RET505. |
| 230 | 🟢 LOW | Lint Violation | [TRY003] Avoid specifying long messages outside the exception class | Fix ruff violation TRY003. |
| 231 | 🟢 LOW | Lint Violation | [EM102] Exception must not use an f-string literal, assign to variable first | Fix ruff violation EM102. |
| 232 | 🟢 LOW | Lint Violation | [COM812] Trailing comma missing | Fix ruff violation COM812. |
| 240 | 🟢 LOW | Lint Violation | [TRY003] Avoid specifying long messages outside the exception class | Fix ruff violation TRY003. |
| 241 | 🟢 LOW | Lint Violation | [EM102] Exception must not use an f-string literal, assign to variable first | Fix ruff violation EM102. |

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
| 321 | 🟢 LOW | Lint Violation | [RET505] Unnecessary `elif` after `return` statement | Fix ruff violation RET505. |
| 358 | 🟢 LOW | Lint Violation | [FBT001] Boolean-typed positional argument in function definition | Fix ruff violation FBT001. |
| 360 | 🟢 LOW | Lint Violation | [RUF100] Unused `noqa` directive (unused: `ARG001`) | Fix ruff violation RUF100. |
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

### henchman/utils/intelligent_truncator.py — ⚠️ C (73.4/100)

LOC: 96 | Classes: 1 | Functions: 0 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 16 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 24 | 🟢 LOW | Missing Type Hint | Function 'truncate_with_semantic_preservation' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 43 | 🟢 LOW | Missing Type Hint | Function '_truncate_with_preserved_sections' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 53 | 🟢 LOW | Missing Type Hint | Function '_truncate_with_available_capacity' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 61 | 🟢 LOW | Missing Type Hint | Function '_add_context_with_truncation' has incomplete type hints: 1/4 params untyped | Add Type Annotations for all parameters and return type. |
| 61 | 🟢 LOW | Feature Envy | Method 'IntelligentTruncator._add_context_with_truncation' accesses 'TokenCounter' 3 times but 'self' only 1 times | Move Method — consider moving '_add_context_with_truncation' to the class that owns 'TokenCounter'. |
| 62 | 🟢 LOW | Lint Violation | [COM812] Trailing comma missing | Fix ruff violation COM812. |
| 66 | 🟢 LOW | Lint Violation | [COM812] Trailing comma missing | Fix ruff violation COM812. |
| 72 | 🟢 LOW | Lint Violation | [E501] Line too long (117 > 100) | Fix ruff violation E501. |
| 75 | 🟢 LOW | Lint Violation | [E501] Line too long (110 > 100) | Fix ruff violation E501. |
| 77 | 🟢 LOW | Lint Violation | [E501] Line too long (115 > 100) | Fix ruff violation E501. |
| 82 | 🟢 LOW | Missing Type Hint | Function '_add_minimal_truncation_marker' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 96 | 🟢 LOW | Missing Type Hint | Function '_truncate_with_marker' has incomplete type hints: 1/4 params untyped | Add Type Annotations for all parameters and return type. |
| 96 | 🟢 LOW | Primitive Obsession | Function '_truncate_with_marker' has 3 primitive-typed parameters: content: Name(id='str', ctx=Load()), marker: Name(id='str', ctx=Load()), min_content_tokens: Name(id='int', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 102 | 🟢 LOW | Lint Violation | [E501] Line too long (121 > 100) | Fix ruff violation E501. |

_... and 4 more smells._

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

### henchman/utils/conversation_type_detector.py — ⚠️ C (77.6/100)

LOC: 69 | Classes: 1 | Functions: 0 | MI: 100 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 45 | 🟡 MEDIUM | Duplicate Code | Function 'detect' is 93% similar to 'detect' at henchman/utils/intelligent_context.py:779 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 66 | 🟡 MEDIUM | Duplicate Code | Function '_count_keywords_by_type' is 100% similar to '_count_keywords_by_type' at henchman/utils/intelligent_context.py:807 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 73 | 🟡 MEDIUM | Duplicate Code | Function '_count_keywords' is 100% similar to '_count_keywords' at henchman/utils/intelligent_context.py:821 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 77 | 🟡 MEDIUM | Duplicate Code | Function '_determine_conversation_type' is 97% similar to '_determine_conversation_type' at henchman/utils/intelligent_context.py:833 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 7 | 🟢 LOW | Lint Violation | [TC001] Move application import `henchman.providers.base.Message` into a type-checking block | Fix ruff violation TC001. |
| 45 | 🟢 LOW | Missing Type Hint | Function 'detect' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 62 | 🟢 LOW | Missing Type Hint | Function '_extract_all_content' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 66 | 🟢 LOW | Missing Type Hint | Function '_count_keywords_by_type' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 73 | 🟢 LOW | Missing Type Hint | Function '_count_keywords' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 77 | 🟢 LOW | Missing Type Hint | Function '_determine_conversation_type' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |

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
