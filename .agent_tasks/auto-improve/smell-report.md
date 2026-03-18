# Code Smell Report — ⚠️ C (Score: 78.8/100)

_Scanned: /home/matthew/mlg-cli/src/henchman_  

_Generated: 2026-03-18T22:00:39.488112+00:00_

## Executive Summary

| Metric | Value |
|:-------|------:|
| **Overall Grade** | ⚠️ C |
| **Overall Score** | 78.8/100 |
| **Files Scanned** | 222 |
| **Total Lines (non-blank)** | 47,810 |
| **Total Smells** | 462 |
| **Avg Maintainability Index** | 69.7 |
| **Avg Cyclomatic Complexity** | 13.2 |

### Smells by Severity

| Severity | Count |
|:---------|------:|
| low | 252 |
| medium | 194 |
| high | 15 |
| critical | 1 |

### Smells by Category

| Category | Count |
|:---------|------:|
| Duplicate Code | 137 |
| Missing Type Hint | 85 |
| Long Method | 54 |
| Feature Envy | 48 |
| Primitive Obsession | 46 |
| Magic Number | 30 |
| Deep Nesting | 28 |
| Complex Function | 20 |
| Large Class | 14 |

## 🎯 Prioritised Refactoring Queue

These are the highest-impact smells to address first:

1. **chat/manager.py:178** — 🔴 CRITICAL — Deep Nesting  
   Nesting depth 8 in '_get_provider_settings' (threshold: 4)  
   → _Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return._

2. **agents/orchestrator_events.py:30** — 🟠 HIGH — Duplicate Code  
   Function 'extract_brief_fields' is an exact duplicate of '_build_storage_kwargs' at metrics/exporter.py:55  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

3. **chat/discord_bot.py:78** — 🟠 HIGH — Feature Envy  
   Method 'DiscordBot._setup_events' accesses 'message' 12 times but 'self' only 7 times  
   → _Move Method — consider moving '_setup_events' to the class that owns 'message'._

4. **chat/manager.py:174** — 🟠 HIGH — Deep Nesting  
   Nesting depth 6 in '_get_provider_settings' (threshold: 4)  
   → _Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return._

5. **chat/manager.py:176** — 🟠 HIGH — Deep Nesting  
   Nesting depth 7 in '_get_provider_settings' (threshold: 4)  
   → _Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return._

6. **chat/manager.py:190** — 🟠 HIGH — Feature Envy  
   Method 'ChatManager._handle_message' accesses 'message' 17 times but 'self' only 4 times  
   → _Move Method — consider moving '_handle_message' to the class that owns 'message'._

7. **chat/manager.py:274** — 🟠 HIGH — Feature Envy  
   Method 'ChatManager._handle_command' accesses 'message' 15 times but 'self' only 8 times  
   → _Move Method — consider moving '_handle_command' to the class that owns 'message'._

8. **cli/app.py:43** — 🟠 HIGH — Duplicate Code  
   Function '_import_attrs' is an exact duplicate of '_import_attrs' at core/agent.py:98  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

9. **cli/textual_mixins.py:493** — 🟠 HIGH — Long Method  
   Function '_textual_confirm' has 90 lines (threshold: 30)  
   → _Extract Method — break this function into smaller, intention-revealing helper functions._

10. **cli/textual_widgets.py:498** — 🟠 HIGH — Primitive Obsession  
   Repeated primitive parameter group appears in: '__init__' (line 498), '_add_message_with_prefix' (line 1004)  
   → _Replace Data Value with Object — create a shared data structure for this recurring parameter group._

11. **cli/textual_widgets.py:1026** — 🟠 HIGH — Duplicate Code  
   Function 'add_user_message' is an exact duplicate of 'add_error_message' at cli/textual_widgets.py:1034  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

12. **extensions/plugin_compatibility.py:91** — 🟠 HIGH — Duplicate Code  
   Function '_check_os_compatibility' is an exact duplicate of '_compress_ranges' at tools/builtins/coverage_map.py:206  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

13. **metrics/dashboard.py:218** — 🟠 HIGH — Duplicate Code  
   Function '_write_token_csv_rows' is an exact duplicate of '_write_cost_csv_rows' at metrics/dashboard.py:224  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

14. **metrics/dashboard.py:218** — 🟠 HIGH — Duplicate Code  
   Function '_write_token_csv_rows' is an exact duplicate of '_write_tool_csv_rows' at metrics/dashboard.py:230  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

15. **metrics/dashboard.py:224** — 🟠 HIGH — Duplicate Code  
   Function '_write_cost_csv_rows' is an exact duplicate of '_write_tool_csv_rows' at metrics/dashboard.py:230  
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._


## 📊 Files Ranked by Quality

| Rank | File | Grade | Score | Smells | LOC | MI | Avg CC |
|-----:|:-----|:------|------:|-------:|----:|---:|-------:|
| 1 | chat/manager.py | ❌ F | 15.6 | 45 | 302 | 52 | 12.3 |
| 2 | cli/textual_mixins.py | ❌ F | 36.0 | 13 | 1488 | 1 | 0.0 |
| 3 | cli/textual_widgets.py | ❌ F | 47.1 | 8 | 1037 | 26 | 0.0 |
| 4 | chat/discord_bot.py | ❌ F | 51.3 | 18 | 232 | 61 | 0.0 |
| 5 | utils/compaction.py | ❌ F | 57.2 | 7 | 856 | 30 | 11.0 |
| 6 | knowledge/store.py | 🔶 D | 63.6 | 7 | 482 | 46 | 0.0 |
| 7 | agents/orchestrator_delegation_ctrl.py | 🔶 D | 65.1 | 8 | 179 | 63 | 18.0 |
| 8 | agents/working_memory.py | 🔶 D | 65.4 | 5 | 535 | 43 | 0.0 |
| 9 | metrics/dashboard.py | 🔶 D | 67.2 | 3 | 340 | 61 | 0.0 |
| 10 | cli/commands/builtins.py | 🔶 D | 69.0 | 6 | 276 | 67 | 0.0 |

## 📁 Per-File Details

_Showing 20 worst files. 202 additional files omitted._

### chat/manager.py — ❌ F (15.6/100)

LOC: 302 | Classes: 1 | Functions: 0 | MI: 52 | Avg CC: 12.3

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 178 | 🔴 CRITICAL | Deep Nesting | Nesting depth 8 in '_get_provider_settings' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 174 | 🟠 HIGH | Deep Nesting | Nesting depth 6 in '_get_provider_settings' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 176 | 🟠 HIGH | Deep Nesting | Nesting depth 7 in '_get_provider_settings' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 190 | 🟠 HIGH | Feature Envy | Method 'ChatManager._handle_message' accesses 'message' 17 times but 'self' only 4 times | Move Method — consider moving '_handle_message' to the class that owns 'message'. |
| 274 | 🟠 HIGH | Feature Envy | Method 'ChatManager._handle_command' accesses 'message' 15 times but 'self' only 8 times | Move Method — consider moving '_handle_command' to the class that owns 'message'. |
| 35 | 🟡 MEDIUM | Duplicate Code | Function '__init__' is 93% similar to '__init__' at cli/ui_renderer.py:80 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 123 | 🟡 MEDIUM | Long Method | Function '_get_provider_settings' has 57 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 123 | 🟡 MEDIUM | Feature Envy | Method 'ChatManager._get_provider_settings' accesses 'defaults' 9 times but 'self' only 1 times | Move Method — consider moving '_get_provider_settings' to the class that owns 'defaults'. |
| 123 | 🟡 MEDIUM | Complex Function | Function '_get_provider_settings' has cyclomatic complexity 14 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 172 | 🟡 MEDIUM | Deep Nesting | Nesting depth 5 in '_get_provider_settings' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 190 | 🟡 MEDIUM | Long Method | Function '_handle_message' has 74 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 190 | 🟡 MEDIUM | Feature Envy | Method 'ChatManager._handle_message' accesses 'bot' 6 times but 'self' only 4 times | Move Method — consider moving '_handle_message' to the class that owns 'bot'. |
| 190 | 🟡 MEDIUM | Feature Envy | Method 'ChatManager._handle_message' accesses 'event' 5 times but 'self' only 4 times | Move Method — consider moving '_handle_message' to the class that owns 'event'. |
| 190 | 🟡 MEDIUM | Complex Function | Function '_handle_message' has cyclomatic complexity 11 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 245 | 🟡 MEDIUM | Deep Nesting | Nesting depth 5 in '_handle_message' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |

_... and 30 more smells._

### cli/textual_mixins.py — ❌ F (36.0/100)

LOC: 1488 | Classes: 13 | Functions: 6 | MI: 1 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 493 | 🟠 HIGH | Long Method | Function '_textual_confirm' has 90 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 111 | 🟡 MEDIUM | Duplicate Code | Function '__init__' is 100% similar to '_reset_string_state' at utils/intelligent_context_parser.py:221 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 493 | 🟡 MEDIUM | Feature Envy | Method '_InitMixin._textual_confirm' accesses 'future' 6 times but 'self' only 4 times | Move Method — consider moving '_textual_confirm' to the class that owns 'future'. |
| 1362 | 🟡 MEDIUM | Duplicate Code | Function '_format_tool_args' is 93% similar to '_format_full_tool_args' at cli/textual_mixins.py:1381 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 1495 | 🟡 MEDIUM | Duplicate Code | Function 'on_switch_provider_message' is 94% similar to 'discover_directory' at extensions/manager.py:235 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 1495 | 🟡 MEDIUM | Duplicate Code | Function 'on_switch_provider_message' is 94% similar to '__exit__' at rag/concurrency.py:127 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 141 | 🟢 LOW | Missing Type Hint | Function '__aiter__' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 143 | 🟢 LOW | Missing Type Hint | Function '__anext__' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 525 | 🟢 LOW | Long Method | Function '_callback' has 38 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 550 | 🟢 LOW | Deep Nesting | Nesting depth 4 in '_callback' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 621 | 🟢 LOW | Deep Nesting | Nesting depth 4 in '_cleanup_confirm_futures' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 1265 | 🟢 LOW | Feature Envy | Method '_CommandPaletteMixin._fill_input_with_text' accesses 'widget' 3 times but 'self' only 1 times | Move Method — consider moving '_fill_input_with_text' to the class that owns 'widget'. |
| 1811 | 🟢 LOW | Primitive Obsession | Function 'update_status' has 3 primitive-typed parameters: message: Name(id='str', ctx=Load()), tokens: BinOp(left=Name(id='int', ctx=Load()), op=BitOr(), right=Constant(value=None)), cost: BinOp(left=Name(id='float', ctx=Load()), op=BitOr(), right=Constant(value=None)) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |

### cli/textual_widgets.py — ❌ F (47.1/100)

LOC: 1037 | Classes: 17 | Functions: 6 | MI: 26 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 498 | 🟠 HIGH | Primitive Obsession | Repeated primitive parameter group appears in: '__init__' (line 498), '_add_message_with_prefix' (line 1004) | Replace Data Value with Object — create a shared data structure for this recurring parameter group. |
| 1026 | 🟠 HIGH | Duplicate Code | Function 'add_user_message' is an exact duplicate of 'add_error_message' at cli/textual_widgets.py:1034 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 1026 | 🟡 MEDIUM | Duplicate Code | Function 'add_user_message' is 100% similar to 'save' at core/session_manager_base.py:102 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 1026 | 🟡 MEDIUM | Duplicate Code | Function 'add_user_message' is 100% similar to '_import_from_node_contains_module' at tools/builtins/import_graph.py:611 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 1034 | 🟡 MEDIUM | Duplicate Code | Function 'add_error_message' is 100% similar to 'save' at core/session_manager_base.py:102 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 1034 | 🟡 MEDIUM | Duplicate Code | Function 'add_error_message' is 100% similar to '_import_from_node_contains_module' at tools/builtins/import_graph.py:611 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 498 | 🟢 LOW | Primitive Obsession | Function '__init__' has 3 primitive-typed parameters: prefix: Name(id='str', ctx=Load()), content: Name(id='str', ctx=Load()), trusted: Name(id='bool', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 1004 | 🟢 LOW | Primitive Obsession | Function '_add_message_with_prefix' has 3 primitive-typed parameters: prefix: Name(id='str', ctx=Load()), text: Name(id='str', ctx=Load()), trusted: Name(id='bool', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |

### chat/discord_bot.py — ❌ F (51.3/100)

LOC: 232 | Classes: 1 | Functions: 1 | MI: 61 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 78 | 🟠 HIGH | Feature Envy | Method 'DiscordBot._setup_events' accesses 'message' 12 times but 'self' only 7 times | Move Method — consider moving '_setup_events' to the class that owns 'message'. |
| 78 | 🟡 MEDIUM | Long Method | Function '_setup_events' has 69 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 78 | 🟡 MEDIUM | Feature Envy | Method 'DiscordBot._setup_events' accesses 'client' 9 times but 'self' only 7 times | Move Method — consider moving '_setup_events' to the class that owns 'client'. |
| 139 | 🟡 MEDIUM | Duplicate Code | Function 'on_disconnect' is 100% similar to 'on_resumed' at chat/discord_bot.py:145 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 49 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 78 | 🟢 LOW | Missing Type Hint | Function '_setup_events' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 94 | 🟢 LOW | Long Method | Function 'on_message' has 37 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 151 | 🟢 LOW | Missing Type Hint | Function 'platform' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 160 | 🟢 LOW | Missing Type Hint | Function 'is_connected' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 168 | 🟢 LOW | Missing Type Hint | Function 'start' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 177 | 🟢 LOW | Missing Type Hint | Function 'stop' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 187 | 🟢 LOW | Missing Type Hint | Function 'send_message' has incomplete type hints: 1/4 params untyped | Add Type Annotations for all parameters and return type. |
| 187 | 🟢 LOW | Primitive Obsession | Function 'send_message' has 3 primitive-typed parameters: user_id: Name(id='str', ctx=Load()), content: Name(id='str', ctx=Load()), split_long: Name(id='bool', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 223 | 🟢 LOW | Missing Type Hint | Function 'send_typing' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 240 | 🟢 LOW | Missing Type Hint | Function 'set_message_handler' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |

_... and 3 more smells._

### utils/compaction.py — ❌ F (57.2/100)

LOC: 856 | Classes: 11 | Functions: 11 | MI: 30 | Avg CC: 11.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 881 | 🟠 HIGH | Duplicate Code | Function '_format_messages_for_summary' is an exact duplicate of '_generate_cluster_summary' at utils/compression_strategy.py:278 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 55 | 🟡 MEDIUM | Duplicate Code | Function 'token_count' is 94% similar to '_truncate_with_marker' at utils/intelligent_context_formatter.py:379 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 750 | 🟡 MEDIUM | Duplicate Code | Function 'validate_compacted_sequence' is 100% similar to '_detect_conversation_type' at utils/message_analyzer.py:95 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 1052 | 🟡 MEDIUM | Complex Function | Function '_attempt_summarization' has cyclomatic complexity 11 (rank C) | Extract Method / Replace Conditional with Polymorphism to reduce branching. |
| 558 | 🟢 LOW | Feature Envy | Method '_ContextCompactorHelpersMixin._select_sequences_to_keep' accesses 'last_sequence' 3 times but 'self' only 1 times | Move Method — consider moving '_select_sequences_to_keep' to the class that owns 'last_sequence'. |
| 601 | 🟢 LOW | Feature Envy | Method '_ContextCompactorHelpersMixin._reconstruct_result' accesses 'result' 4 times but 'self' only 0 times | Move Method — consider moving '_reconstruct_result' to the class that owns 'result'. |
| 702 | 🟢 LOW | Long Method | Function '_perform_compaction' has 33 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |

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
| 208 | 🟡 MEDIUM | Duplicate Code | Function '_list_all_commands' is 94% similar to 'on_switch_provider_message' at cli/textual_mixins.py:1495 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 208 | 🟡 MEDIUM | Duplicate Code | Function '_list_all_commands' is 100% similar to 'discover_directory' at extensions/manager.py:235 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 208 | 🟡 MEDIUM | Duplicate Code | Function '_list_all_commands' is 100% similar to '__exit__' at rag/concurrency.py:127 | Extract Shared Function — identify the common logic and parameterise the differences. |

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

### extensions/plugin_manager.py — ⚠️ C (70.8/100)

LOC: 395 | Classes: 2 | Functions: 8 | MI: 47 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 57 | 🟡 MEDIUM | Duplicate Code | Function 'to_search_params' is 100% similar to 'to_declaration' at tools/base.py:137 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 57 | 🟡 MEDIUM | Duplicate Code | Function 'to_search_params' is 100% similar to 'to_config' at tools/builtins/coverage_map.py:44 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 210 | 🟡 MEDIUM | Primitive Obsession | Function 'search_plugins' has 4 primitive-typed parameters: query: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), page: Name(id='int', ctx=Load()), page_size: Name(id='int', ctx=Load()), category: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 158 | 🟢 LOW | Large Class | Class 'PluginManager' spans 307 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
| 264 | 🟢 LOW | Primitive Obsession | Function 'install_plugin' has 3 primitive-typed parameters: plugin_name: Name(id='str', ctx=Load()), version: BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)), confirm_permissions: Name(id='bool', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |

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
| 193 | 🟡 MEDIUM | Duplicate Code | Function 'reset' is 100% similar to '__init__' at cli/textual_mixins.py:111 | Extract Shared Function — identify the common logic and parameterise the differences. |
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

## ✨ Clean Files (85 files with no smells)

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
- cli/textual_screens.py — 👍 B
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
