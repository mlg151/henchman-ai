# Code Smell Report — 👍 B (Score: 80.3/100)

_Scanned: /home/matthew/mlg-cli/src/henchman_  

_Generated: 2026-03-17T14:00:40.643023+00:00_

## Executive Summary

| Metric | Value |
|:-------|------:|
| **Overall Grade** | 👍 B |
| **Overall Score** | 80.3/100 |
| **Files Scanned** | 217 |
| **Total Lines (non-blank)** | 46,853 |
| **Total Smells** | 372 |
| **Avg Maintainability Index** | 69.5 |
| **Avg Cyclomatic Complexity** | 13.3 |

### Smells by Severity

| Severity | Count |
|:---------|------:|
| low | 201 |
| medium | 164 |
| high | 7 |

### Smells by Category

| Category | Count |
|:---------|------:|
| Duplicate Code | 124 |
| Missing Type Hint | 56 |
| Long Method | 45 |
| Primitive Obsession | 40 |
| Feature Envy | 38 |
| Magic Number | 25 |
| Complex Function | 16 |
| Deep Nesting | 16 |
| Large Class | 12 |

## 🎯 Prioritised Refactoring Queue

These are the highest-impact smells to address first:

1. **agents/orchestrator_events.py:30** — 🟠 HIGH — Duplicate Code  
   Function 'extract_brief_fields' is an exact duplicate of '_build_storage_kwargs' at metrics/exporter.py:55  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

2. **cli/app.py:42** — 🟠 HIGH — Duplicate Code  
   Function '_import_attrs' is an exact duplicate of '_import_attrs' at core/agent.py:98  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

3. **extensions/plugin_compatibility.py:91** — 🟠 HIGH — Duplicate Code  
   Function '_check_os_compatibility' is an exact duplicate of '_compress_ranges' at tools/builtins/coverage_map.py:206  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

4. **metrics/dashboard.py:218** — 🟠 HIGH — Duplicate Code  
   Function '_write_token_csv_rows' is an exact duplicate of '_write_cost_csv_rows' at metrics/dashboard.py:224  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

5. **metrics/dashboard.py:218** — 🟠 HIGH — Duplicate Code  
   Function '_write_token_csv_rows' is an exact duplicate of '_write_tool_csv_rows' at metrics/dashboard.py:230  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

6. **metrics/dashboard.py:224** — 🟠 HIGH — Duplicate Code  
   Function '_write_cost_csv_rows' is an exact duplicate of '_write_tool_csv_rows' at metrics/dashboard.py:230  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

7. **utils/compaction.py:882** — 🟠 HIGH — Duplicate Code  
   Function '_format_messages_for_summary' is an exact duplicate of '_generate_cluster_summary' at utils/compression_strategy.py:278  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

8. **/home/matthew/mlg-cli/src/henchman/agents/orchestrator_delegation_ctrl.py:122** — 🟡 MEDIUM — Complex Function  
   Function '_run_delegation' has cyclomatic complexity 18 (rank C)  
   → _Extract Method / Replace Conditional with Polymorphism to reduce branching._

9. **/home/matthew/mlg-cli/src/henchman/config/environment.py:133** — 🟡 MEDIUM — Complex Function  
   Function '_detect_git_status' has cyclomatic complexity 17 (rank C)  
   → _Extract Method / Replace Conditional with Polymorphism to reduce branching._

10. **/home/matthew/mlg-cli/src/henchman/mcp/manager.py:36** — 🟡 MEDIUM — Complex Function  
   Function '_detect_server_type' has cyclomatic complexity 11 (rank C)  
   → _Extract Method / Replace Conditional with Polymorphism to reduce branching._

11. **/home/matthew/mlg-cli/src/henchman/rag/system.py:250** — 🟡 MEDIUM — Complex Function  
   Function 'initialize_rag' has cyclomatic complexity 19 (rank C)  
   → _Extract Method / Replace Conditional with Polymorphism to reduce branching._

12. **/home/matthew/mlg-cli/src/henchman/tools/builtins/env_inspect.py:82** — 🟡 MEDIUM — Complex Function  
   Function 'execute' has cyclomatic complexity 14 (rank C)  
   → _Extract Method / Replace Conditional with Polymorphism to reduce branching._

13. **/home/matthew/mlg-cli/src/henchman/tools/builtins/file_overview.py:37** — 🟡 MEDIUM — Complex Function  
   Function '_format_function_sig' has cyclomatic complexity 11 (rank C)  
   → _Extract Method / Replace Conditional with Polymorphism to reduce branching._

14. **/home/matthew/mlg-cli/src/henchman/tools/builtins/file_overview.py:138** — 🟡 MEDIUM — Complex Function  
   Function '_summarize_python' has cyclomatic complexity 11 (rank C)  
   → _Extract Method / Replace Conditional with Polymorphism to reduce branching._

15. **/home/matthew/mlg-cli/src/henchman/tools/builtins/ls.py:54** — 🟡 MEDIUM — Complex Function  
   Function 'execute' has cyclomatic complexity 14 (rank C)  
   → _Extract Method / Replace Conditional with Polymorphism to reduce branching._


## 📊 Files Ranked by Quality

| Rank | File | Grade | Score | Smells | LOC | MI | Avg CC |
|-----:|:-----|:------|------:|-------:|----:|---:|-------:|
| 1 | cli/textual_mixins.py | ❌ F | 45.8 | 10 | 1476 | 1 | 0.0 |
| 2 | utils/compaction.py | ❌ F | 57.2 | 7 | 857 | 30 | 11.0 |
| 3 | knowledge/store.py | 🔶 D | 63.6 | 7 | 482 | 46 | 0.0 |
| 4 | agents/orchestrator_delegation_ctrl.py | 🔶 D | 65.1 | 8 | 179 | 63 | 18.0 |
| 5 | agents/working_memory.py | 🔶 D | 65.4 | 5 | 535 | 43 | 0.0 |
| 6 | metrics/dashboard.py | 🔶 D | 67.2 | 3 | 340 | 61 | 0.0 |
| 7 | cli/commands/builtins.py | 🔶 D | 69.0 | 6 | 276 | 67 | 0.0 |
| 8 | extensions/plugin_manager.py | 🔶 D | 69.4 | 4 | 344 | 38 | 0.0 |
| 9 | utils/validation.py | 🔶 D | 69.6 | 7 | 192 | 59 | 11.5 |
| 10 | agents/metrics_reporter.py | 🔶 D | 69.9 | 6 | 251 | 56 | 0.0 |

## 📁 Per-File Details

_Showing 20 worst files. 197 additional files omitted._

### cli/textual_mixins.py — ❌ F (45.8/100)

LOC: 1476 | Classes: 13 | Functions: 6 | MI: 1 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 113 | 🟡 MEDIUM | Duplicate Code | Function '__init__' is 100% similar to '_reset_string_state' at utils/intelligent_context_parser.py:221 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 489 | 🟡 MEDIUM | Long Method | Function '_textual_confirm' has 52 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 1304 | 🟡 MEDIUM | Duplicate Code | Function '_format_tool_args' is 93% similar to '_format_full_tool_args' at cli/textual_mixins.py:1323 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 1437 | 🟡 MEDIUM | Duplicate Code | Function 'on_switch_provider_message' is 94% similar to 'discover_directory' at extensions/manager.py:235 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 1437 | 🟡 MEDIUM | Duplicate Code | Function 'on_switch_provider_message' is 94% similar to '__exit__' at rag/concurrency.py:127 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 533 | 🟢 LOW | Deep Nesting | Nesting depth 4 in '_textual_confirm' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 543 | 🟢 LOW | Deep Nesting | Nesting depth 4 in '_textual_confirm' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 562 | 🟢 LOW | Deep Nesting | Nesting depth 4 in '_cleanup_confirm_futures' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 1207 | 🟢 LOW | Feature Envy | Method '_CommandPaletteMixin._fill_input_with_text' accesses 'widget' 3 times but 'self' only 1 times | Move Method — consider moving '_fill_input_with_text' to the class that owns 'widget'. |
| 1753 | 🟢 LOW | Primitive Obsession | Function 'update_status' has 3 primitive-typed parameters: message: Name(id='str', ctx=Load()), tokens: BinOp(left=Name(id='int', ctx=Load()), op=BitOr(), right=Constant(value=None)), cost: BinOp(left=Name(id='float', ctx=Load()), op=BitOr(), right=Constant(value=None)) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |

### utils/compaction.py — ❌ F (57.2/100)

LOC: 857 | Classes: 11 | Functions: 11 | MI: 30 | Avg CC: 11.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 882 | 🟠 HIGH | Duplicate Code | Function '_format_messages_for_summary' is an exact duplicate of '_generate_cluster_summary' at utils/compression_strategy.py:278 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 56 | 🟡 MEDIUM | Duplicate Code | Function 'token_count' is 94% similar to '_truncate_with_marker' at utils/intelligent_context_formatter.py:379 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 751 | 🟡 MEDIUM | Duplicate Code | Function 'validate_compacted_sequence' is 100% similar to '_detect_conversation_type' at utils/message_analyzer.py:95 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 1053 | 🟡 MEDIUM | Complex Function | Function '_attempt_summarization' has cyclomatic complexity 11 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 559 | 🟢 LOW | Feature Envy | Method '_ContextCompactorHelpersMixin._select_sequences_to_keep' accesses 'last_sequence' 3 times but 'self' only 1 times | Move Method — consider moving '_select_sequences_to_keep' to the class that owns 'last_sequence'. |
| 602 | 🟢 LOW | Feature Envy | Method '_ContextCompactorHelpersMixin._reconstruct_result' accesses 'result' 4 times but 'self' only 0 times | Move Method — consider moving '_reconstruct_result' to the class that owns 'result'. |
| 703 | 🟢 LOW | Long Method | Function '_perform_compaction' has 33 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |

### knowledge/store.py — 🔶 D (63.6/100)

LOC: 482 | Classes: 2 | Functions: 10 | MI: 46 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 107 | 🟡 MEDIUM | Duplicate Code | Function '_relation_to_edge_attrs' is 100% similar to '_format_tool_for_anthropic' at providers/anthropic.py:130 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 107 | 🟡 MEDIUM | Duplicate Code | Function '_relation_to_edge_attrs' is 100% similar to 'to_metadata' at rag/chunker.py:42 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 434 | 🟡 MEDIUM | Duplicate Code | Function 'add_entity' is 100% similar to 'add_relation' at knowledge/store.py:526 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 545 | 🟡 MEDIUM | Duplicate Code | Function 'get_relations' is 94% similar to 'extract_imports' at tools/builtins/import_graph.py:267 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 545 | 🟡 MEDIUM | Duplicate Code | Function 'get_relations' is 94% similar to 'extract_critical_sections' at utils/message_analyzer.py:106 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 333 | 🟢 LOW | Large Class | Class 'KnowledgeStore' spans 303 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
| 333 | 🟢 LOW | Large Class | Class 'KnowledgeStore' has 20 methods (threshold: 20) | Split Class — group related methods into smaller collaborating classes. |

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

### agents/working_memory.py — 🔶 D (65.4/100)

LOC: 535 | Classes: 8 | Functions: 11 | MI: 43 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 392 | 🟡 MEDIUM | Duplicate Code | Function 'add_recent_file' is 95% similar to '_list_agents' at cli/commands/agent.py:221 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 407 | 🟡 MEDIUM | Duplicate Code | Function 'add_decision' is 100% similar to 'set_session' at cli/repl.py:291 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 407 | 🟡 MEDIUM | Duplicate Code | Function 'add_decision' is 100% similar to 'post' at cli/textual_bridge.py:181 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 407 | 🟡 MEDIUM | Duplicate Code | Function 'add_decision' is 100% similar to 'add_auto_approve_policy' at tools/registry.py:170 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 407 | 🟡 MEDIUM | Duplicate Code | Function 'add_decision' is 100% similar to 'remove_auto_approve_policy' at tools/registry.py:184 | Extract Shared Function — identify the common logic and parameterise the differences. |

### metrics/dashboard.py — 🔶 D (67.2/100)

LOC: 340 | Classes: 2 | Functions: 17 | MI: 61 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 218 | 🟠 HIGH | Duplicate Code | Function '_write_token_csv_rows' is an exact duplicate of '_write_cost_csv_rows' at metrics/dashboard.py:224 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 218 | 🟠 HIGH | Duplicate Code | Function '_write_token_csv_rows' is an exact duplicate of '_write_tool_csv_rows' at metrics/dashboard.py:230 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 224 | 🟠 HIGH | Duplicate Code | Function '_write_cost_csv_rows' is an exact duplicate of '_write_tool_csv_rows' at metrics/dashboard.py:230 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |

### cli/commands/builtins.py — 🔶 D (69.0/100)

LOC: 276 | Classes: 4 | Functions: 7 | MI: 67 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 197 | 🟡 MEDIUM | Duplicate Code | Function '_show_specific_command_help' is 100% similar to '_should_index' at rag/indexer.py:226 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 197 | 🟡 MEDIUM | Duplicate Code | Function '_show_specific_command_help' is 100% similar to 'classify_import' at tools/builtins/import_graph.py:278 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 197 | 🟡 MEDIUM | Duplicate Code | Function '_show_specific_command_help' is 94% similar to '_truncate_with_marker' at utils/intelligent_context_formatter.py:379 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 208 | 🟡 MEDIUM | Duplicate Code | Function '_list_all_commands' is 94% similar to 'on_switch_provider_message' at cli/textual_mixins.py:1437 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 208 | 🟡 MEDIUM | Duplicate Code | Function '_list_all_commands' is 100% similar to 'discover_directory' at extensions/manager.py:235 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 208 | 🟡 MEDIUM | Duplicate Code | Function '_list_all_commands' is 100% similar to '__exit__' at rag/concurrency.py:127 | Extract Shared Function — identify the common logic and parameterise the differences. |

### extensions/plugin_manager.py — 🔶 D (69.4/100)

LOC: 344 | Classes: 2 | Functions: 8 | MI: 38 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 57 | 🟡 MEDIUM | Duplicate Code | Function 'to_search_params' is 100% similar to 'to_declaration' at tools/base.py:137 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 57 | 🟡 MEDIUM | Duplicate Code | Function 'to_search_params' is 100% similar to 'to_config' at tools/builtins/coverage_map.py:44 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 202 | 🟡 MEDIUM | Primitive Obsession | Function 'search_plugins' has 4 primitive-typed parameters: query: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), page: Name(id='int', ctx=Load()), page_size: Name(id='int', ctx=Load()), category: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 256 | 🟢 LOW | Primitive Obsession | Function 'install_plugin' has 3 primitive-typed parameters: plugin_name: Name(id='str', ctx=Load()), version: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), confirm_permissions: Name(id='bool', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |

### utils/validation.py — 🔶 D (69.6/100)

LOC: 192 | Classes: 0 | Functions: 5 | MI: 59 | Avg CC: 11.5

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 12 | 🟡 MEDIUM | Long Method | Function 'validate_message_sequence' has 62 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 12 | 🟡 MEDIUM | Complex Function | Function 'validate_message_sequence' has cyclomatic complexity 11 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 122 | 🟡 MEDIUM | Long Method | Function 'repair_message_sequence' has 71 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 122 | 🟡 MEDIUM | Complex Function | Function 'repair_message_sequence' has cyclomatic complexity 12 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 43 | 🟢 LOW | Deep Nesting | Nesting depth 4 in 'validate_message_sequence' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 53 | 🟢 LOW | Deep Nesting | Nesting depth 4 in 'validate_message_sequence' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 242 | 🟢 LOW | Magic Number | Magic number 50 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |

### agents/metrics_reporter.py — 🔶 D (69.9/100)

LOC: 251 | Classes: 2 | Functions: 4 | MI: 56 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 32 | 🟡 MEDIUM | Duplicate Code | Function '_build_metrics_section' is 100% similar to '_format_findings' at tools/builtins/dead_code.py:594 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 257 | 🟡 MEDIUM | Duplicate Code | Function '_format_documentation_coverage' is 94% similar to '_str_payload' at cli/textual_messages.py:38 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 264 | 🟡 MEDIUM | Duplicate Code | Function '_format_tool_call_statistics' is 93% similar to 'list_themes' at cli/console.py:367 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 264 | 🟡 MEDIUM | Duplicate Code | Function '_format_tool_call_statistics' is 93% similar to 'list_auto_approve_policies' at tools/registry.py:195 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 191 | 🟢 LOW | Feature Envy | Method 'MetricsReporter._format_task_completion_time' accesses 'time' 4 times but 'self' only 2 times | Move Method — consider moving '_format_task_completion_time' to the class that owns 'time'. |
| 202 | 🟢 LOW | Magic Number | Magic number 60 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |

### cli/commands/context.py — ⚠️ C (70.0/100)

LOC: 549 | Classes: 7 | Functions: 11 | MI: 47 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 130 | 🟡 MEDIUM | Duplicate Code | Function '__init__' is 100% similar to '__init__' at cli/json_output.py:69 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 130 | 🟡 MEDIUM | Duplicate Code | Function '__init__' is 100% similar to '__init__' at tools/builtins/coverage_map.py:394 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 130 | 🟡 MEDIUM | Duplicate Code | Function '__init__' is 100% similar to '__init__' at tools/security/shell_secure.py:442 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 536 | 🟡 MEDIUM | Duplicate Code | Function '_show_help_message' is 94% similar to '_list_themes' at cli/commands/theme.py:206 | Extract Shared Function — identify the common logic and parameterise the differences. |

### cli/repl.py — ⚠️ C (70.8/100)

LOC: 442 | Classes: 2 | Functions: 3 | MI: 47 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 291 | 🟡 MEDIUM | Duplicate Code | Function 'set_session' is 100% similar to 'post' at cli/textual_bridge.py:181 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 291 | 🟡 MEDIUM | Duplicate Code | Function 'set_session' is 100% similar to 'add_auto_approve_policy' at tools/registry.py:170 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 291 | 🟡 MEDIUM | Duplicate Code | Function 'set_session' is 100% similar to 'remove_auto_approve_policy' at tools/registry.py:184 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 144 | 🟢 LOW | Large Class | Class 'Repl' spans 389 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
| 144 | 🟢 LOW | Large Class | Class 'Repl' has 22 methods (threshold: 20) | Split Class — group related methods into smaller collaborating classes. |

### tools/builtins/research_notes.py — ⚠️ C (71.0/100)

LOC: 293 | Classes: 2 | Functions: 10 | MI: 57 | Avg CC: 13.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 204 | 🟡 MEDIUM | Deep Nesting | Nesting depth 5 in '_action_search' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 220 | 🟡 MEDIUM | Complex Function | Function '_execute_research_notes' has cyclomatic complexity 13 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 339 | 🟡 MEDIUM | Primitive Obsession | Function 'execute' has 4 primitive-typed parameters: action: Name(id='str', ctx=Load()), tag: Name(id='str', ctx=Load()), content: Name(id='str', ctx=Load()), query: Name(id='str', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 173 | 🟢 LOW | Magic Number | Magic number 19 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 203 | 🟢 LOW | Deep Nesting | Nesting depth 4 in '_action_search' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 205 | 🟢 LOW | Magic Number | Magic number 100 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 220 | 🟢 LOW | Long Method | Function '_execute_research_notes' has 33 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |

### tools/builtins/file_overview.py — ⚠️ C (71.2/100)

LOC: 297 | Classes: 1 | Functions: 10 | MI: 51 | Avg CC: 11.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 37 | 🟡 MEDIUM | Complex Function | Function '_format_function_sig' has cyclomatic complexity 11 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 138 | 🟡 MEDIUM | Complex Function | Function '_summarize_python' has cyclomatic complexity 11 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 37 | 🟢 LOW | Long Method | Function '_format_function_sig' has 33 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 138 | 🟢 LOW | Primitive Obsession | Function '_summarize_python' has 3 primitive-typed parameters: source: Name(id='str', ctx=Load()), depth: Name(id='int', ctx=Load()), include_docs: Name(id='bool', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 207 | 🟢 LOW | Magic Number | Magic number 20 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 230 | 🟢 LOW | Magic Number | Magic number 20 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 261 | 🟢 LOW | Long Method | Function '_execute_file_overview' has 35 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |

### agents/presets.py — ⚠️ C (72.1/100)

LOC: 194 | Classes: 1 | Functions: 7 | MI: 82 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 123 | 🟡 MEDIUM | Duplicate Code | Function '_create_planner_config' is 100% similar to '_create_explorer_config' at agents/presets.py:145 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 123 | 🟡 MEDIUM | Duplicate Code | Function '_create_planner_config' is 100% similar to '_create_engineer_config' at agents/presets.py:167 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 123 | 🟡 MEDIUM | Duplicate Code | Function '_create_planner_config' is 100% similar to '_create_data_engineer_config' at agents/presets.py:188 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 145 | 🟡 MEDIUM | Duplicate Code | Function '_create_explorer_config' is 100% similar to '_create_engineer_config' at agents/presets.py:167 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 145 | 🟡 MEDIUM | Duplicate Code | Function '_create_explorer_config' is 100% similar to '_create_data_engineer_config' at agents/presets.py:188 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 167 | 🟡 MEDIUM | Duplicate Code | Function '_create_engineer_config' is 100% similar to '_create_data_engineer_config' at agents/presets.py:188 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 49 | 🟢 LOW | Primitive Obsession | Function '_create_agent_config' has 3 primitive-typed parameters: name: Name(id='str', ctx=Load()), role: Name(id='str', ctx=Load()), description: Name(id='str', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |

### agents/metrics.py — ⚠️ C (72.2/100)

LOC: 344 | Classes: 5 | Functions: 2 | MI: 54 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 118 | 🟡 MEDIUM | Duplicate Code | Function 'track_file_access' is 94% similar to '_render_diff' at cli/console.py:666 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 118 | 🟡 MEDIUM | Duplicate Code | Function 'track_file_access' is 100% similar to 'register' at extensions/manager.py:154 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 193 | 🟡 MEDIUM | Duplicate Code | Function 'reset' is 100% similar to '__init__' at cli/textual_mixins.py:113 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 193 | 🟡 MEDIUM | Duplicate Code | Function 'reset' is 100% similar to '_reset_string_state' at utils/intelligent_context_parser.py:221 | Extract Shared Function — identify the common logic and parameterise the differences. |

### api/endpoints/chat.py — ⚠️ C (73.4/100)

LOC: 397 | Classes: 4 | Functions: 12 | MI: 49 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 298 | 🟡 MEDIUM | Long Method | Function 'chat_completion' has 65 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 381 | 🟡 MEDIUM | Long Method | Function 'chat_completion_stream' has 70 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 191 | 🟢 LOW | Long Method | Function '_process_stream_event' has 31 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 223 | 🟢 LOW | Deep Nesting | Nesting depth 4 in '_process_stream_event' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 424 | 🟢 LOW | Long Method | Function 'event_generator' has 31 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |

### utils/message_clusterer.py — ⚠️ C (73.4/100)

LOC: 328 | Classes: 1 | Functions: 0 | MI: 49 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 15 | 🟢 LOW | Large Class | Class 'MessageClusterer' spans 443 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
| 24 | 🟢 LOW | Primitive Obsession | Function '__init__' has 3 primitive-typed parameters: cluster_similarity_threshold: Name(id='float', ctx=Load()), minimum_word_length: Name(id='int', ctx=Load()), minimum_shared_words: Name(id='int', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 69 | 🟢 LOW | Feature Envy | Method 'MessageClusterer._cluster_tool_call_sequences' accesses 'curr_msg' 3 times but 'self' only 2 times | Move Method — consider moving '_cluster_tool_call_sequences' to the class that owns 'curr_msg'. |
| 69 | 🟢 LOW | Feature Envy | Method 'MessageClusterer._cluster_tool_call_sequences' accesses 'next_msg' 3 times but 'self' only 2 times | Move Method — consider moving '_cluster_tool_call_sequences' to the class that owns 'next_msg'. |
| 148 | 🟢 LOW | Feature Envy | Method 'MessageClusterer._should_merge_adjacent_clusters' accesses 'last_msg' 4 times but 'self' only 0 times | Move Method — consider moving '_should_merge_adjacent_clusters' to the class that owns 'last_msg'. |
| 148 | 🟢 LOW | Feature Envy | Method 'MessageClusterer._should_merge_adjacent_clusters' accesses 'first_msg' 3 times but 'self' only 0 times | Move Method — consider moving '_should_merge_adjacent_clusters' to the class that owns 'first_msg'. |
| 185 | 🟢 LOW | Long Method | Function '_cluster_topic_similarity' has 38 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 265 | 🟢 LOW | Deep Nesting | Nesting depth 4 in '_extract_cluster_keywords' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |

### tools/security/shell_secure.py — ⚠️ C (73.5/100)

LOC: 487 | Classes: 3 | Functions: 14 | MI: 51 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 37 | 🟡 MEDIUM | Long Method | Function '_default_allowed_commands' has 55 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 96 | 🟡 MEDIUM | Duplicate Code | Function '_default_denied_patterns' is 100% similar to '_get_default_keywords' at utils/intelligent_context_extractor.py:278 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 332 | 🟡 MEDIUM | Duplicate Code | Function '_apply_moderate_security' is 100% similar to '_apply_permissive_security' at tools/security/shell_secure.py:344 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 576 | 🟢 LOW | Primitive Obsession | Function 'execute' has 3 primitive-typed parameters: command: Name(id='str', ctx=Load()), timeout: BinOp(left=Name(id='int', ctx=Load()), op=BitOr(), right=Constant(value=None)), cwd: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |

### tools/builtins/import_graph.py — ⚠️ C (73.7/100)

LOC: 504 | Classes: 5 | Functions: 21 | MI: 36 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 267 | 🟡 MEDIUM | Duplicate Code | Function 'extract_imports' is 100% similar to 'extract_critical_sections' at utils/message_analyzer.py:106 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 278 | 🟡 MEDIUM | Duplicate Code | Function 'classify_import' is 94% similar to '_truncate_with_marker' at utils/intelligent_context_formatter.py:379 | Extract Shared Function — identify the common logic and parameterise the differences. |

## ✨ Clean Files (87 files with no smells)

<details><summary>Click to expand</summary>

- __init__.py — ✅ A
- __main__.py — ✅ A
- agents/__init__.py — ✅ A
- agents/config.py — ✅ A
- agents/file_read_decision_maker.py — 👍 B
- agents/line_range_utils.py — 👍 B
- agents/orchestrator_components.py — ✅ A
- agents/orchestrator_init.py — 👍 B
- agents/orchestrator_prompts.py — ✅ A
- agents/orchestrator_run.py — ✅ A
- agents/orchestrator_tech_lead.py — ✅ A
- agents/orchestrator_timeout.py — ✅ A
- agents/orchestrator_tools.py — ✅ A
- agents/orchestrator_turns.py — ✅ A
- agents/orchestrator_types.py — 👍 B
- agents/orchestrator_validation.py — ✅ A
- agents/prompts.py — 👍 B
- api/__init__.py — ✅ A
- api/auth.py — ✅ A
- api/endpoints/__init__.py — ✅ A
- cli/__init__.py — ✅ A
- cli/commands/__init__.py — 👍 B
- cli/commands/extensions.py — ✅ A
- cli/commands/model.py — 👍 B
- cli/commands/plan.py — ✅ A
- cli/commands/rag.py — 👍 B
- cli/commands/team.py — ✅ A
- cli/input.py — 👍 B
- cli/prompts.py — ✅ A
- cli/stream_event_handlers.py — 👍 B
- cli/textual_screens.py — 👍 B
- cli/textual_widgets.py — ⚠️ C
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
- extensions/base.py — ✅ A
- extensions/constants.py — ✅ A
- extensions/models.py — 👍 B
- extensions/plugin_registry_client.py — ✅ A
- knowledge/__init__.py — ✅ A
- knowledge/models.py — ✅ A
- mcp/__init__.py — ✅ A
- mcp/client.py — 👍 B
- metrics/__init__.py — ✅ A
- metrics/models.py — 👍 B
- providers/__init__.py — ✅ A
- providers/utils.py — ✅ A
- rag/__init__.py — ✅ A
- tools/__init__.py — ✅ A
- tools/builtins/__init__.py — ✅ A
- tools/builtins/dead_code.py — 👍 B
- tools/builtins/delegate.py — ✅ A
- tools/builtins/grep.py — 👍 B
- tools/builtins/kg_common.py — ✅ A
- tools/builtins/kg_update.py — 👍 B
- tools/builtins/pytest_run.py — 👍 B
- tools/builtins/python_ast.py — ✅ A
- tools/builtins/test_gen.py — 👍 B
- tools/builtins/web_search.py — ✅ A
- tools/security/__init__.py — ✅ A
- tools/utils.py — ✅ A
- utils/__init__.py — ✅ A
- utils/cluster_utils.py — ✅ A
- utils/compression_strategy.py — 👍 B
- utils/intelligent_context_aggregator.py — 👍 B
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
