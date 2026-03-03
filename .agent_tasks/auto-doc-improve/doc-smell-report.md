# Documentation Smell Report — ✅ A (Score: 97.1/100)

_Project: /home/matthew/mlg-cli_  
_Generated: 2026-03-03T17:30:02.868608+00:00_

## Executive Summary

| Metric | Value |
|:-------|------:|
| **Overall Grade** | ✅ A |
| **Overall Score** | 97.1/100 |
| **Doc Files Scanned** | 18 |
| **Source Files Checked** | 167 |
| **Total Smells** | 302 |
| **Docstring Coverage** | 99.3% |

### Smells by Severity

| Severity | Count |
|:---------|------:|
| low | 274 |
| medium | 28 |

### Smells by Category

| Category | Count |
|:---------|------:|
| Incomplete Docstring | 288 |
| Missing Docstring | 10 |
| Stale Content | 2 |
| Config Issue | 1 |
| Consistency Error | 1 |

## 🎯 Prioritised Fix Queue

These are the highest-impact documentation smells to address first:

1. **pyproject.toml:65** — 🟡 MEDIUM — Consistency Error  
   States coverage threshold of 4% but other files require 100%. Found thresholds: 100%, 4%  
   → _Align all coverage requirements to 100% (the strictest value)._

2. **src/henchman/cli/stream_event_handlers.py:256** — 🟡 MEDIUM — Incomplete Docstring  
   'dispatch_event' has 5 parameter(s) but no Args: section in docstring  
   → _Add an Args: section documenting: output_handler, event, state, agent, content_collector_

3. **src/henchman/cli/stream_event_handlers.py:291** — 🟡 MEDIUM — Incomplete Docstring  
   'handle_post_stream_processing' has 5 parameter(s) but no Args: section in docstring  
   → _Add an Args: section documenting: output_handler, state, agent, content_collector, execute_tool_calls_fn_

4. **src/henchman/cli/stream_event_handlers.py:334** — 🟡 MEDIUM — Incomplete Docstring  
   'build_confirmation_message' has 1 parameter(s) but no Args: section in docstring  
   → _Add an Args: section documenting: request_

5. **src/henchman/cli/textual_driver.py:1** — 🟡 MEDIUM — Missing Docstring  
   Module is missing a docstring  
   → _Add a module-level docstring describing the module's purpose._

6. **src/henchman/cli/textual_messages.py:47** — 🟡 MEDIUM — Missing Docstring  
   Public function 'AgentContentMessage.content' is missing a docstring  
   → _Add a Google-style docstring to 'AgentContentMessage.content'._

7. **src/henchman/cli/textual_messages.py:55** — 🟡 MEDIUM — Missing Docstring  
   Public function 'AgentThoughtMessage.thought' is missing a docstring  
   → _Add a Google-style docstring to 'AgentThoughtMessage.thought'._

8. **src/henchman/cli/textual_messages.py:63** — 🟡 MEDIUM — Missing Docstring  
   Public function 'ToolCallRequestMessage.tool_call' is missing a docstring  
   → _Add a Google-style docstring to 'ToolCallRequestMessage.tool_call'._

9. **src/henchman/cli/textual_messages.py:71** — 🟡 MEDIUM — Missing Docstring  
   Public function 'ToolCallResultMessage.result' is missing a docstring  
   → _Add a Google-style docstring to 'ToolCallResultMessage.result'._

10. **src/henchman/cli/textual_messages.py:79** — 🟡 MEDIUM — Missing Docstring  
   Public function 'ToolConfirmationMessage.request' is missing a docstring  
   → _Add a Google-style docstring to 'ToolConfirmationMessage.request'._

11. **src/henchman/cli/textual_messages.py:87** — 🟡 MEDIUM — Missing Docstring  
   Public function 'AgentStatusMessage.status' is missing a docstring  
   → _Add a Google-style docstring to 'AgentStatusMessage.status'._

12. **src/henchman/cli/textual_messages.py:128** — 🟡 MEDIUM — Missing Docstring  
   Public function 'CommandOutputMessage.text' is missing a docstring  
   → _Add a Google-style docstring to 'CommandOutputMessage.text'._

13. **src/henchman/cli/textual_messages.py:147** — 🟡 MEDIUM — Missing Docstring  
   Public function 'SwitchProviderMessage.provider_name' is missing a docstring  
   → _Add a Google-style docstring to 'SwitchProviderMessage.provider_name'._

14. **src/henchman/cli/textual_widgets.py:246** — 🟡 MEDIUM — Incomplete Docstring  
   'CollapsibleMessage.content' has 1 parameter(s) but no Args: section in docstring  
   → _Add an Args: section documenting: value_

15. **src/henchman/core/agent.py:253** — 🟡 MEDIUM — Incomplete Docstring  
   'Agent.submit_tool_result' has 2 parameter(s) but no Args: section in docstring  
   → _Add an Args: section documenting: tool_call_id, result_

16. **src/henchman/core/eventbus.py:1** — 🟡 MEDIUM — Missing Docstring  
   Module is missing a docstring  
   → _Add a module-level docstring describing the module's purpose._

17. **src/henchman/core/session_manager.py:51** — 🟡 MEDIUM — Incomplete Docstring  
   'SessionManager.branch_session' has 3 parameter(s) but no Args: section in docstring  
   → _Add an Args: section documenting: session_id, branch_point, tag_

18. **src/henchman/core/session_manager.py:67** — 🟡 MEDIUM — Incomplete Docstring  
   'SessionManager.merge_sessions' has 3 parameter(s) but no Args: section in docstring  
   → _Add an Args: section documenting: session_ids, strategy, tag_

19. **src/henchman/core/session_manager.py:92** — 🟡 MEDIUM — Incomplete Docstring  
   'SessionManager.export_session' has 3 parameter(s) but no Args: section in docstring  
   → _Add an Args: section documenting: session_id, format, include_metadata_

20. **src/henchman/core/session_manager.py:113** — 🟡 MEDIUM — Incomplete Docstring  
   'SessionManager.import_session' has 3 parameter(s) but no Args: section in docstring  
   → _Add an Args: section documenting: data, format, tag_


## 📊 Files Ranked by Quality

| Rank | File | Grade | Score | Smells | Last Modified |
|-----:|:-----|:------|------:|-------:|:-------------|
| 1 | src/henchman/cli/textual_widgets.py | ❌ F | 49.0 | 24 | 2026-03-03 |
| 2 | src/henchman/core/session_manager.py | ❌ F | 49.0 | 15 | 2026-02-28 |
| 3 | src/henchman/cli/console.py | ❌ F | 56.0 | 22 | 2026-03-03 |
| 4 | src/henchman/cli/textual_messages.py | 🔶 D | 60.0 | 8 | 2026-03-03 |
| 5 | src/henchman/cli/commands/session.py | 🔶 D | 66.0 | 17 | 2026-03-03 |
| 6 | src/henchman/agents/metrics.py | ⚠️ C | 76.0 | 12 | 2026-03-03 |
| 7 | src/henchman/cli/stream_event_handlers.py | ⚠️ C | 77.0 | 7 | 2026-03-03 |
| 8 | src/henchman/metrics/storage.py | 👍 B | 82.0 | 6 | 2026-03-03 |
| 9 | src/henchman/utils/validation.py | 👍 B | 83.0 | 4 | 2026-03-03 |
| 10 | src/henchman/cli/ui_renderer.py | 👍 B | 84.0 | 8 | 2026-03-03 |
| 11 | src/henchman/cli/commands/context.py | 👍 B | 86.0 | 7 | 2026-03-03 |
| 12 | src/henchman/cli/console_helpers.py | 👍 B | 86.0 | 7 | 2026-03-03 |
| 13 | src/henchman/cli/textual_screens.py | 👍 B | 86.0 | 7 | 2026-03-03 |
| 14 | src/henchman/knowledge/store.py | 👍 B | 86.0 | 7 | 2026-03-03 |
| 15 | src/henchman/tools/registry.py | 👍 B | 86.0 | 7 | 2026-03-03 |

## 📁 Per-File Details

_Showing 25 worst files. 161 additional files omitted._

### src/henchman/cli/textual_widgets.py — ❌ F (49.0/100) (last modified 2026-03-03)

Public APIs: 46 | Documented: 46 | Coverage: 100.0%

| Line | Severity | Type | Message | Suggested Fix |
|-----:|:---------|:-----|:--------|:--------------|
| 246 | 🟡 MEDIUM | Incomplete Docstring | 'CollapsibleMessage.content' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: value |
| 246 | 🟢 LOW | Incomplete Docstring | 'CollapsibleMessage.content' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'CollapsibleMessage.content'. |
| 265 | 🟢 LOW | Incomplete Docstring | 'CollapsibleMessage.toggle_expansion' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'CollapsibleMessage.toggle_expansion'. |
| 273 | 🟢 LOW | Incomplete Docstring | 'CollapsibleMessage.on_click' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'CollapsibleMessage.on_click'. |
| 281 | 🟢 LOW | Incomplete Docstring | 'CollapsibleMessage.set_highlight' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'CollapsibleMessage.set_highlight'. |
| 347 | 🟢 LOW | Incomplete Docstring | 'HenchmanTextArea.on_key' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'HenchmanTextArea.on_key'. |
| 381 | 🟢 LOW | Incomplete Docstring | 'HenchmanTextArea.action_newline' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'HenchmanTextArea.action_newline'. |
| 385 | 🟢 LOW | Incomplete Docstring | 'HenchmanTextArea.action_history_up' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'HenchmanTextArea.action_history_up'. |
| 395 | 🟢 LOW | Incomplete Docstring | 'HenchmanTextArea.action_history_down' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'HenchmanTextArea.action_history_down'. |
| 477 | 🟢 LOW | Incomplete Docstring | 'ChatMessage.set_highlight' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ChatMessage.set_highlight'. |
| 490 | 🟢 LOW | Incomplete Docstring | 'ChatMessage.finalize_as_markdown' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ChatMessage.finalize_as_markdown'. |
| 589 | 🟢 LOW | Incomplete Docstring | 'ThinkingMessage.append' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ThinkingMessage.append'. |
| 601 | 🟢 LOW | Incomplete Docstring | 'ThinkingMessage.set_content' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ThinkingMessage.set_content'. |
| 884 | 🟢 LOW | Incomplete Docstring | 'ChatPane.on_mount' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ChatPane.on_mount'. |
| 923 | 🟢 LOW | Incomplete Docstring | 'ChatPane.add_user_message' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ChatPane.add_user_message'. |

_... and 9 more smells._

### src/henchman/core/session_manager.py — ❌ F (49.0/100) (last modified 2026-02-28)

Public APIs: 9 | Documented: 9 | Coverage: 100.0%

| Line | Severity | Type | Message | Suggested Fix |
|-----:|:---------|:-----|:--------|:--------------|
| 51 | 🟡 MEDIUM | Incomplete Docstring | 'SessionManager.branch_session' has 3 parameter(s) but no Args: section in docstring | Add an Args: section documenting: session_id, branch_point, tag |
| 67 | 🟡 MEDIUM | Incomplete Docstring | 'SessionManager.merge_sessions' has 3 parameter(s) but no Args: section in docstring | Add an Args: section documenting: session_ids, strategy, tag |
| 92 | 🟡 MEDIUM | Incomplete Docstring | 'SessionManager.export_session' has 3 parameter(s) but no Args: section in docstring | Add an Args: section documenting: session_id, format, include_metadata |
| 113 | 🟡 MEDIUM | Incomplete Docstring | 'SessionManager.import_session' has 3 parameter(s) but no Args: section in docstring | Add an Args: section documenting: data, format, tag |
| 133 | 🟡 MEDIUM | Incomplete Docstring | 'SessionManager.save_template' has 4 parameter(s) but no Args: section in docstring | Add an Args: section documenting: session_id, name, description, parameters |
| 153 | 🟡 MEDIUM | Incomplete Docstring | 'SessionManager.create_from_template' has 3 parameter(s) but no Args: section in docstring | Add an Args: section documenting: template_id, parameters, tag |
| 175 | 🟡 MEDIUM | Incomplete Docstring | 'SessionManager.delete_template' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: template_id |
| 51 | 🟢 LOW | Incomplete Docstring | 'SessionManager.branch_session' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'SessionManager.branch_session'. |
| 67 | 🟢 LOW | Incomplete Docstring | 'SessionManager.merge_sessions' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'SessionManager.merge_sessions'. |
| 92 | 🟢 LOW | Incomplete Docstring | 'SessionManager.export_session' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'SessionManager.export_session'. |
| 113 | 🟢 LOW | Incomplete Docstring | 'SessionManager.import_session' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'SessionManager.import_session'. |
| 133 | 🟢 LOW | Incomplete Docstring | 'SessionManager.save_template' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'SessionManager.save_template'. |
| 153 | 🟢 LOW | Incomplete Docstring | 'SessionManager.create_from_template' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'SessionManager.create_from_template'. |
| 168 | 🟢 LOW | Incomplete Docstring | 'SessionManager.list_templates' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'SessionManager.list_templates'. |
| 175 | 🟢 LOW | Incomplete Docstring | 'SessionManager.delete_template' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'SessionManager.delete_template'. |

### src/henchman/cli/console.py — ❌ F (56.0/100) (last modified 2026-03-03)

Public APIs: 43 | Documented: 43 | Coverage: 100.0%

| Line | Severity | Type | Message | Suggested Fix |
|-----:|:---------|:-----|:--------|:--------------|
| 340 | 🟢 LOW | Incomplete Docstring | 'ThemeManager.set_theme' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ThemeManager.set_theme'. |
| 356 | 🟢 LOW | Incomplete Docstring | 'ThemeManager.register_theme' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ThemeManager.register_theme'. |
| 424 | 🟢 LOW | Incomplete Docstring | 'OutputRenderer.print' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'OutputRenderer.print'. |
| 433 | 🟢 LOW | Incomplete Docstring | 'OutputRenderer.success' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'OutputRenderer.success'. |
| 443 | 🟢 LOW | Incomplete Docstring | 'OutputRenderer.info' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'OutputRenderer.info'. |
| 453 | 🟢 LOW | Incomplete Docstring | 'OutputRenderer.warning' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'OutputRenderer.warning'. |
| 463 | 🟢 LOW | Incomplete Docstring | 'OutputRenderer.error' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'OutputRenderer.error'. |
| 485 | 🟢 LOW | Incomplete Docstring | 'OutputRenderer.muted' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'OutputRenderer.muted'. |
| 493 | 🟢 LOW | Incomplete Docstring | 'OutputRenderer.heading' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'OutputRenderer.heading'. |
| 501 | 🟢 LOW | Incomplete Docstring | 'OutputRenderer.markdown' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'OutputRenderer.markdown'. |
| 518 | 🟢 LOW | Incomplete Docstring | 'OutputRenderer.code' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'OutputRenderer.code'. |
| 530 | 🟢 LOW | Incomplete Docstring | 'OutputRenderer.rule' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'OutputRenderer.rule'. |
| 541 | 🟢 LOW | Incomplete Docstring | 'OutputRenderer.clear' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'OutputRenderer.clear'. |
| 545 | 🟢 LOW | Incomplete Docstring | 'OutputRenderer.tool_call' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'OutputRenderer.tool_call'. |
| 558 | 🟢 LOW | Incomplete Docstring | 'OutputRenderer.tool_result' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'OutputRenderer.tool_result'. |

_... and 7 more smells._

### src/henchman/cli/textual_messages.py — 🔶 D (60.0/100) (last modified 2026-03-03)

Public APIs: 17 | Documented: 9 | Coverage: 53.0%

| Line | Severity | Type | Message | Suggested Fix |
|-----:|:---------|:-----|:--------|:--------------|
| 47 | 🟡 MEDIUM | Missing Docstring | Public function 'AgentContentMessage.content' is missing a docstring | Add a Google-style docstring to 'AgentContentMessage.content'. |
| 55 | 🟡 MEDIUM | Missing Docstring | Public function 'AgentThoughtMessage.thought' is missing a docstring | Add a Google-style docstring to 'AgentThoughtMessage.thought'. |
| 63 | 🟡 MEDIUM | Missing Docstring | Public function 'ToolCallRequestMessage.tool_call' is missing a docstring | Add a Google-style docstring to 'ToolCallRequestMessage.tool_call'. |
| 71 | 🟡 MEDIUM | Missing Docstring | Public function 'ToolCallResultMessage.result' is missing a docstring | Add a Google-style docstring to 'ToolCallResultMessage.result'. |
| 79 | 🟡 MEDIUM | Missing Docstring | Public function 'ToolConfirmationMessage.request' is missing a docstring | Add a Google-style docstring to 'ToolConfirmationMessage.request'. |
| 87 | 🟡 MEDIUM | Missing Docstring | Public function 'AgentStatusMessage.status' is missing a docstring | Add a Google-style docstring to 'AgentStatusMessage.status'. |
| 128 | 🟡 MEDIUM | Missing Docstring | Public function 'CommandOutputMessage.text' is missing a docstring | Add a Google-style docstring to 'CommandOutputMessage.text'. |
| 147 | 🟡 MEDIUM | Missing Docstring | Public function 'SwitchProviderMessage.provider_name' is missing a docstring | Add a Google-style docstring to 'SwitchProviderMessage.provider_name'. |

### src/henchman/cli/commands/session.py — 🔶 D (66.0/100) (last modified 2026-03-03)

Public APIs: 45 | Documented: 45 | Coverage: 100.0%

| Line | Severity | Type | Message | Suggested Fix |
|-----:|:---------|:-----|:--------|:--------------|
| 126 | 🟢 LOW | Incomplete Docstring | 'CommandOperationContext.print_success' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'CommandOperationContext.print_success'. |
| 134 | 🟢 LOW | Incomplete Docstring | 'CommandOperationContext.print_error' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'CommandOperationContext.print_error'. |
| 142 | 🟢 LOW | Incomplete Docstring | 'CommandOperationContext.print_info' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'CommandOperationContext.print_info'. |
| 150 | 🟢 LOW | Incomplete Docstring | 'CommandOperationContext.print_usage' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'CommandOperationContext.print_usage'. |
| 253 | 🟢 LOW | Incomplete Docstring | 'SessionCommandExecutor.execute' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'SessionCommandExecutor.execute'. |
| 277 | 🟢 LOW | Incomplete Docstring | 'BranchExecutor.execute' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'BranchExecutor.execute'. |
| 362 | 🟢 LOW | Incomplete Docstring | 'MergeExecutor.execute' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'MergeExecutor.execute'. |
| 427 | 🟢 LOW | Incomplete Docstring | 'TemplateCreateExecutor.execute' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'TemplateCreateExecutor.execute'. |
| 460 | 🟢 LOW | Incomplete Docstring | 'TemplateListExecutor.execute' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'TemplateListExecutor.execute'. |
| 488 | 🟢 LOW | Incomplete Docstring | 'TemplateDeleteExecutor.execute' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'TemplateDeleteExecutor.execute'. |
| 516 | 🟢 LOW | Incomplete Docstring | 'ExportExecutor.execute' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ExportExecutor.execute'. |
| 549 | 🟢 LOW | Incomplete Docstring | 'ImportExecutor.execute' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ImportExecutor.execute'. |
| 765 | 🟢 LOW | Incomplete Docstring | 'display_sessions_list' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'display_sessions_list'. |
| 786 | 🟢 LOW | Incomplete Docstring | 'display_session_entry' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'display_session_entry'. |
| 807 | 🟢 LOW | Incomplete Docstring | 'display_enhanced_session_info' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'display_enhanced_session_info'. |

_... and 2 more smells._

### src/henchman/agents/metrics.py — ⚠️ C (76.0/100) (last modified 2026-03-03)

Public APIs: 19 | Documented: 19 | Coverage: 100.0%

| Line | Severity | Type | Message | Suggested Fix |
|-----:|:---------|:-----|:--------|:--------------|
| 90 | 🟢 LOW | Incomplete Docstring | 'PerformanceMetrics.reset' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'PerformanceMetrics.reset'. |
| 102 | 🟢 LOW | Incomplete Docstring | 'PerformanceMetrics.calculate_file_re_reads' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'PerformanceMetrics.calculate_file_re_reads'. |
| 110 | 🟢 LOW | Incomplete Docstring | 'PerformanceMetrics.track_file_access' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'PerformanceMetrics.track_file_access'. |
| 118 | 🟢 LOW | Incomplete Docstring | 'PerformanceMetrics.track_tool_usage' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'PerformanceMetrics.track_tool_usage'. |
| 141 | 🟢 LOW | Incomplete Docstring | 'QualityMetrics.reset' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'QualityMetrics.reset'. |
| 148 | 🟢 LOW | Incomplete Docstring | 'QualityMetrics.calculate_test_percentage' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'QualityMetrics.calculate_test_percentage'. |
| 173 | 🟢 LOW | Incomplete Docstring | 'ToolMetrics.reset' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ToolMetrics.reset'. |
| 185 | 🟢 LOW | Incomplete Docstring | 'ToolMetrics.track_tool_call' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ToolMetrics.track_tool_call'. |
| 205 | 🟢 LOW | Incomplete Docstring | 'ToolMetrics.calculate_error_rate' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ToolMetrics.calculate_error_rate'. |
| 285 | 🟢 LOW | Incomplete Docstring | 'OrchestratorMetrics.reset_for_run' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'OrchestratorMetrics.reset_for_run'. |
| 296 | 🟢 LOW | Incomplete Docstring | 'OrchestratorMetrics.calculate_final_metrics' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'OrchestratorMetrics.calculate_final_metrics'. |
| 312 | 🟢 LOW | Incomplete Docstring | 'OrchestratorMetrics.update_tool_metrics' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'OrchestratorMetrics.update_tool_metrics'. |

### src/henchman/cli/stream_event_handlers.py — ⚠️ C (77.0/100) (last modified 2026-03-03)

Public APIs: 6 | Documented: 6 | Coverage: 100.0%

| Line | Severity | Type | Message | Suggested Fix |
|-----:|:---------|:-----|:--------|:--------------|
| 256 | 🟡 MEDIUM | Incomplete Docstring | 'dispatch_event' has 5 parameter(s) but no Args: section in docstring | Add an Args: section documenting: output_handler, event, state, agent, content_collector |
| 291 | 🟡 MEDIUM | Incomplete Docstring | 'handle_post_stream_processing' has 5 parameter(s) but no Args: section in docstring | Add an Args: section documenting: output_handler, state, agent, content_collector, execute_tool_calls_fn |
| 334 | 🟡 MEDIUM | Incomplete Docstring | 'build_confirmation_message' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: request |
| 71 | 🟢 LOW | Incomplete Docstring | 'update_processing_state' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'update_processing_state'. |
| 256 | 🟢 LOW | Incomplete Docstring | 'dispatch_event' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'dispatch_event'. |
| 291 | 🟢 LOW | Incomplete Docstring | 'handle_post_stream_processing' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'handle_post_stream_processing'. |
| 334 | 🟢 LOW | Incomplete Docstring | 'build_confirmation_message' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'build_confirmation_message'. |

### src/henchman/metrics/storage.py — 👍 B (82.0/100) (last modified 2026-03-03)

Public APIs: 17 | Documented: 17 | Coverage: 100.0%

| Line | Severity | Type | Message | Suggested Fix |
|-----:|:---------|:-----|:--------|:--------------|
| 309 | 🟡 MEDIUM | Incomplete Docstring | 'DatabaseSchemaManager.create_metrics_table' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: cursor |
| 321 | 🟡 MEDIUM | Incomplete Docstring | 'DatabaseSchemaManager.create_indexes' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: cursor |
| 309 | 🟢 LOW | Incomplete Docstring | 'DatabaseSchemaManager.create_metrics_table' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'DatabaseSchemaManager.create_metrics_table'. |
| 321 | 🟢 LOW | Incomplete Docstring | 'DatabaseSchemaManager.create_indexes' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'DatabaseSchemaManager.create_indexes'. |
| 571 | 🟢 LOW | Incomplete Docstring | 'MetricsStorage.store_metric' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'MetricsStorage.store_metric'. |
| 834 | 🟢 LOW | Incomplete Docstring | 'MetricsStorage.clear_metrics' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'MetricsStorage.clear_metrics'. |

### src/henchman/utils/validation.py — 👍 B (83.0/100) (last modified 2026-03-03)

Public APIs: 4 | Documented: 4 | Coverage: 100.0%

| Line | Severity | Type | Message | Suggested Fix |
|-----:|:---------|:-----|:--------|:--------------|
| 12 | 🟡 MEDIUM | Incomplete Docstring | 'validate_message_sequence' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: messages |
| 191 | 🟡 MEDIUM | Incomplete Docstring | 'is_valid_message_sequence' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: messages |
| 205 | 🟡 MEDIUM | Incomplete Docstring | 'format_message_sequence_for_debug' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: messages |
| 12 | 🟢 LOW | Incomplete Docstring | 'validate_message_sequence' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'validate_message_sequence'. |

### src/henchman/cli/ui_renderer.py — 👍 B (84.0/100) (last modified 2026-03-03)

Public APIs: 15 | Documented: 15 | Coverage: 100.0%

| Line | Severity | Type | Message | Suggested Fix |
|-----:|:---------|:-----|:--------|:--------------|
| 114 | 🟢 LOW | Incomplete Docstring | 'ProgressManager.update_task' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ProgressManager.update_task'. |
| 134 | 🟢 LOW | Incomplete Docstring | 'ProgressManager.complete_task' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ProgressManager.complete_task'. |
| 217 | 🟢 LOW | Incomplete Docstring | 'UIRenderer.print_welcome' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'UIRenderer.print_welcome'. |
| 223 | 🟢 LOW | Incomplete Docstring | 'UIRenderer.print_goodbye' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'UIRenderer.print_goodbye'. |
| 257 | 🟢 LOW | Incomplete Docstring | 'UIRenderer.start_thinking' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'UIRenderer.start_thinking'. |
| 281 | 🟢 LOW | Incomplete Docstring | 'UIRenderer.stop_thinking' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'UIRenderer.stop_thinking'. |
| 320 | 🟢 LOW | Incomplete Docstring | 'UIRenderer.print_newline' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'UIRenderer.print_newline'. |
| 324 | 🟢 LOW | Incomplete Docstring | 'UIRenderer.show_thinking' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'UIRenderer.show_thinking'. |

### src/henchman/cli/commands/context.py — 👍 B (86.0/100) (last modified 2026-03-03)

Public APIs: 18 | Documented: 18 | Coverage: 100.0%

| Line | Severity | Type | Message | Suggested Fix |
|-----:|:---------|:-----|:--------|:--------------|
| 74 | 🟢 LOW | Incomplete Docstring | 'RangeParameterConfig.validate_value' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'RangeParameterConfig.validate_value'. |
| 124 | 🟢 LOW | Incomplete Docstring | 'ContextConsoleHelper.print_status_info' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ContextConsoleHelper.print_status_info'. |
| 143 | 🟢 LOW | Incomplete Docstring | 'ContextConsoleHelper.print_strategy_usage' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ContextConsoleHelper.print_strategy_usage'. |
| 156 | 🟢 LOW | Incomplete Docstring | 'ContextConsoleHelper.print_strategy_status' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ContextConsoleHelper.print_strategy_status'. |
| 296 | 🟢 LOW | Incomplete Docstring | 'StrategyManager.manage_strategy' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'StrategyManager.manage_strategy'. |
| 460 | 🟢 LOW | Incomplete Docstring | 'ContextCommand.execute' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ContextCommand.execute'. |
| 570 | 🟢 LOW | Incomplete Docstring | 'StatisticsManager.show_stats' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'StatisticsManager.show_stats'. |

### src/henchman/cli/console_helpers.py — 👍 B (86.0/100) (last modified 2026-03-03)

Public APIs: 8 | Documented: 8 | Coverage: 100.0%

| Line | Severity | Type | Message | Suggested Fix |
|-----:|:---------|:-----|:--------|:--------------|
| 10 | 🟢 LOW | Incomplete Docstring | 'ConsoleHelper.print_status_header' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ConsoleHelper.print_status_header'. |
| 20 | 🟢 LOW | Incomplete Docstring | 'ConsoleHelper.print_status_value' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ConsoleHelper.print_status_value'. |
| 32 | 🟢 LOW | Incomplete Docstring | 'ConsoleHelper.print_enabled_status' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ConsoleHelper.print_enabled_status'. |
| 45 | 🟢 LOW | Incomplete Docstring | 'ConsoleHelper.print_command_help' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ConsoleHelper.print_command_help'. |
| 56 | 🟢 LOW | Incomplete Docstring | 'ConsoleHelper.print_error_message' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ConsoleHelper.print_error_message'. |
| 69 | 🟢 LOW | Incomplete Docstring | 'ConsoleHelper.print_usage_help' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ConsoleHelper.print_usage_help'. |
| 86 | 🟢 LOW | Incomplete Docstring | 'ConsoleHelper.print_parameter_list' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ConsoleHelper.print_parameter_list'. |

### src/henchman/cli/textual_screens.py — 👍 B (86.0/100) (last modified 2026-03-03)

Public APIs: 15 | Documented: 15 | Coverage: 100.0%

| Line | Severity | Type | Message | Suggested Fix |
|-----:|:---------|:-----|:--------|:--------------|
| 155 | 🟢 LOW | Incomplete Docstring | 'ConfirmToolScreen.on_button_pressed' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ConfirmToolScreen.on_button_pressed'. |
| 163 | 🟢 LOW | Incomplete Docstring | 'ConfirmToolScreen.action_approve' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ConfirmToolScreen.action_approve'. |
| 167 | 🟢 LOW | Incomplete Docstring | 'ConfirmToolScreen.action_deny' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ConfirmToolScreen.action_deny'. |
| 229 | 🟢 LOW | Incomplete Docstring | 'HelpScreen.on_button_pressed' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'HelpScreen.on_button_pressed'. |
| 344 | 🟢 LOW | Incomplete Docstring | 'ProviderScreen.on_button_pressed' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ProviderScreen.on_button_pressed'. |
| 451 | 🟢 LOW | Incomplete Docstring | 'SessionScreen.on_button_pressed' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'SessionScreen.on_button_pressed'. |
| 469 | 🟢 LOW | Incomplete Docstring | 'SessionScreen.action_cancel' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'SessionScreen.action_cancel'. |

### src/henchman/knowledge/store.py — 👍 B (86.0/100) (last modified 2026-03-03)

Public APIs: 23 | Documented: 23 | Coverage: 100.0%

| Line | Severity | Type | Message | Suggested Fix |
|-----:|:---------|:-----|:--------|:--------------|
| 235 | 🟢 LOW | Incomplete Docstring | 'KnowledgeStore.load' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'KnowledgeStore.load'. |
| 255 | 🟢 LOW | Incomplete Docstring | 'KnowledgeStore.save' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'KnowledgeStore.save'. |
| 270 | 🟢 LOW | Incomplete Docstring | 'KnowledgeStore.add_entity' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'KnowledgeStore.add_entity'. |
| 385 | 🟢 LOW | Incomplete Docstring | 'KnowledgeStore.add_relation' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'KnowledgeStore.add_relation'. |
| 533 | 🟢 LOW | Incomplete Docstring | 'KnowledgeStore.entity_count' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'KnowledgeStore.entity_count'. |
| 537 | 🟢 LOW | Incomplete Docstring | 'KnowledgeStore.relation_count' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'KnowledgeStore.relation_count'. |
| 541 | 🟢 LOW | Incomplete Docstring | 'KnowledgeStore.clear' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'KnowledgeStore.clear'. |

### src/henchman/tools/registry.py — 👍 B (86.0/100) (last modified 2026-03-03)

Public APIs: 15 | Documented: 15 | Coverage: 100.0%

| Line | Severity | Type | Message | Suggested Fix |
|-----:|:---------|:-----|:--------|:--------------|
| 68 | 🟢 LOW | Incomplete Docstring | 'ToolRegistry.set_retry_config' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ToolRegistry.set_retry_config'. |
| 76 | 🟢 LOW | Incomplete Docstring | 'ToolRegistry.set_plan_mode' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ToolRegistry.set_plan_mode'. |
| 84 | 🟢 LOW | Incomplete Docstring | 'ToolRegistry.register' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ToolRegistry.register'. |
| 98 | 🟢 LOW | Incomplete Docstring | 'ToolRegistry.unregister' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ToolRegistry.unregister'. |
| 142 | 🟢 LOW | Incomplete Docstring | 'ToolRegistry.set_confirmation_handler' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ToolRegistry.set_confirmation_handler'. |
| 151 | 🟢 LOW | Incomplete Docstring | 'ToolRegistry.add_auto_approve_policy' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ToolRegistry.add_auto_approve_policy'. |
| 162 | 🟢 LOW | Incomplete Docstring | 'ToolRegistry.remove_auto_approve_policy' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ToolRegistry.remove_auto_approve_policy'. |

### src/henchman/cli/session_manager.py — 👍 B (88.0/100) (last modified 2026-03-03)

Public APIs: 14 | Documented: 14 | Coverage: 100.0%

| Line | Severity | Type | Message | Suggested Fix |
|-----:|:---------|:-----|:--------|:--------------|
| 61 | 🟢 LOW | Incomplete Docstring | 'ReplSessionManager.set_session' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ReplSessionManager.set_session'. |
| 106 | 🟢 LOW | Incomplete Docstring | 'ReplSessionManager.auto_save_session' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ReplSessionManager.auto_save_session'. |
| 196 | 🟢 LOW | Incomplete Docstring | 'ReplSessionManager.delete' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ReplSessionManager.delete'. |
| 218 | 🟢 LOW | Incomplete Docstring | 'ReplSessionManager.record_user_message' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ReplSessionManager.record_user_message'. |
| 227 | 🟢 LOW | Incomplete Docstring | 'ReplSessionManager.record_agent_message' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ReplSessionManager.record_agent_message'. |
| 250 | 🟢 LOW | Incomplete Docstring | 'ReplSessionManager.record_tool_result' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ReplSessionManager.record_tool_result'. |

### src/henchman/cli/textual_bridge.py — 👍 B (88.0/100) (last modified 2026-03-03)

Public APIs: 10 | Documented: 10 | Coverage: 100.0%

| Line | Severity | Type | Message | Suggested Fix |
|-----:|:---------|:-----|:--------|:--------------|
| 84 | 🟢 LOW | Incomplete Docstring | 'TuiConsoleAdapter.flush_to_chat' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'TuiConsoleAdapter.flush_to_chat'. |
| 92 | 🟢 LOW | Incomplete Docstring | 'TuiConsoleAdapter.print' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'TuiConsoleAdapter.print'. |
| 174 | 🟢 LOW | Incomplete Docstring | 'MessagePoster.post' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'MessagePoster.post'. |
| 182 | 🟢 LOW | Incomplete Docstring | 'MessagePoster.post_message' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'MessagePoster.post_message'. |
| 201 | 🟢 LOW | Incomplete Docstring | 'MessagePoster.post_status_message' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'MessagePoster.post_status_message'. |
| 240 | 🟢 LOW | Incomplete Docstring | 'EventBridge.forward_events' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'EventBridge.forward_events'. |

### src/henchman/core/agent.py — 👍 B (89.0/100) (last modified 2026-03-03)

Public APIs: 6 | Documented: 6 | Coverage: 100.0%

| Line | Severity | Type | Message | Suggested Fix |
|-----:|:---------|:-----|:--------|:--------------|
| 253 | 🟡 MEDIUM | Incomplete Docstring | 'Agent.submit_tool_result' has 2 parameter(s) but no Args: section in docstring | Add an Args: section documenting: tool_call_id, result |
| 237 | 🟢 LOW | Incomplete Docstring | 'Agent.clear_history' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'Agent.clear_history'. |
| 253 | 🟢 LOW | Incomplete Docstring | 'Agent.submit_tool_result' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'Agent.submit_tool_result'. |
| 277 | 🟢 LOW | Incomplete Docstring | 'Agent.continue_with_tool_results' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'Agent.continue_with_tool_results'. |

### src/henchman/core/eventbus.py — 👍 B (89.0/100) (last modified 2026-03-03)

Public APIs: 7 | Documented: 7 | Coverage: 100.0%

| Line | Severity | Type | Message | Suggested Fix |
|-----:|:---------|:-----|:--------|:--------------|
| 1 | 🟡 MEDIUM | Missing Docstring | Module is missing a docstring | Add a module-level docstring describing the module's purpose. |
| 53 | 🟢 LOW | Incomplete Docstring | 'EventBus.unsubscribe' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'EventBus.unsubscribe'. |
| 62 | 🟢 LOW | Incomplete Docstring | 'EventBus.publish' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'EventBus.publish'. |
| 117 | 🟢 LOW | Incomplete Docstring | 'EventBus.clear_history' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'EventBus.clear_history'. |

### src/henchman/metrics/collector.py — ✅ A (90.0/100) (last modified 2026-03-03)

Public APIs: 14 | Documented: 14 | Coverage: 100.0%

| Line | Severity | Type | Message | Suggested Fix |
|-----:|:---------|:-----|:--------|:--------------|
| 230 | 🟢 LOW | Incomplete Docstring | 'MetricsCollector.should_sample' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'MetricsCollector.should_sample'. |
| 240 | 🟢 LOW | Incomplete Docstring | 'MetricsCollector.start_command' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'MetricsCollector.start_command'. |
| 397 | 🟢 LOW | Incomplete Docstring | 'MetricsCollector.record_agent_switch' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'MetricsCollector.record_agent_switch'. |
| 401 | 🟢 LOW | Incomplete Docstring | 'MetricsCollector.record_context_compaction' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'MetricsCollector.record_context_compaction'. |
| 490 | 🟢 LOW | Incomplete Docstring | 'MetricsCollector.process_agent_event' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'MetricsCollector.process_agent_event'. |

### src/henchman/agents/ledger.py — ✅ A (92.0/100) (last modified 2026-03-03)

Public APIs: 12 | Documented: 12 | Coverage: 100.0%

| Line | Severity | Type | Message | Suggested Fix |
|-----:|:---------|:-----|:--------|:--------------|
| 92 | 🟢 LOW | Incomplete Docstring | 'TaskLedger.check_item' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'TaskLedger.check_item'. |
| 121 | 🟢 LOW | Incomplete Docstring | 'TaskLedger.complete_delegation' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'TaskLedger.complete_delegation'. |
| 131 | 🟢 LOW | Incomplete Docstring | 'TaskLedger.fail_delegation' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'TaskLedger.fail_delegation'. |
| 141 | 🟢 LOW | Incomplete Docstring | 'TaskLedger.mark_verified' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'TaskLedger.mark_verified'. |

### src/henchman/cli/commands/__init__.py — ✅ A (92.0/100) (last modified 2026-03-03)

Public APIs: 15 | Documented: 15 | Coverage: 100.0%

| Line | Severity | Type | Message | Suggested Fix |
|-----:|:---------|:-----|:--------|:--------------|
| 102 | 🟢 LOW | Incomplete Docstring | 'Command.execute' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'Command.execute'. |
| 142 | 🟢 LOW | Incomplete Docstring | 'CommandRegistry.register' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'CommandRegistry.register'. |
| 177 | 🟢 LOW | Incomplete Docstring | 'CommandRegistry.execute' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'CommandRegistry.execute'. |
| 194 | 🟢 LOW | Incomplete Docstring | 'show_command_help' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'show_command_help'. |

### src/henchman/cli/commands/builtins.py — ✅ A (92.0/100) (last modified 2026-03-03)

Public APIs: 21 | Documented: 21 | Coverage: 100.0%

| Line | Severity | Type | Message | Suggested Fix |
|-----:|:---------|:-----|:--------|:--------------|
| 52 | 🟢 LOW | Incomplete Docstring | 'HelpCommand.execute' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'HelpCommand.execute'. |
| 146 | 🟢 LOW | Incomplete Docstring | 'QuitCommand.execute' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'QuitCommand.execute'. |
| 189 | 🟢 LOW | Incomplete Docstring | 'ClearCommand.execute' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ClearCommand.execute'. |
| 234 | 🟢 LOW | Incomplete Docstring | 'ToolsCommand.execute' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ToolsCommand.execute'. |

### src/henchman/cli/plugins.py — ✅ A (92.0/100) (last modified 2026-03-03)

Public APIs: 8 | Documented: 8 | Coverage: 100.0%

| Line | Severity | Type | Message | Suggested Fix |
|-----:|:---------|:-----|:--------|:--------------|
| 42 | 🟢 LOW | Incomplete Docstring | 'UIPlugin.register' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'UIPlugin.register'. |
| 49 | 🟢 LOW | Incomplete Docstring | 'UIPlugin.render' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'UIPlugin.render'. |
| 69 | 🟢 LOW | Incomplete Docstring | 'PluginManager.load_plugins_from_directory' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'PluginManager.load_plugins_from_directory'. |
| 134 | 🟢 LOW | Incomplete Docstring | 'PluginManager.register_plugin' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'PluginManager.register_plugin'. |

### src/henchman/cli/tool_manager.py — ✅ A (92.0/100) (last modified 2026-03-03)

Public APIs: 6 | Documented: 6 | Coverage: 100.0%

| Line | Severity | Type | Message | Suggested Fix |
|-----:|:---------|:-----|:--------|:--------------|
| 36 | 🟢 LOW | Incomplete Docstring | 'ToolManager.register_builtin_tools' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ToolManager.register_builtin_tools'. |
| 125 | 🟢 LOW | Incomplete Docstring | 'ToolManager.set_confirmation_handler' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ToolManager.set_confirmation_handler'. |
| 137 | 🟢 LOW | Incomplete Docstring | 'ToolManager.set_auto_approve' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ToolManager.set_auto_approve'. |
| 145 | 🟢 LOW | Incomplete Docstring | 'ToolManager.set_plan_mode' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ToolManager.set_plan_mode'. |

## ✨ Clean Files (102 files with no smells)

<details><summary>Click to expand</summary>

- CHANGELOG.md — ✅ A
- RELEASE_CHECKLIST.md — ✅ A
- docs/agents.md — ✅ A
- docs/api.md — ✅ A
- docs/architecture.md — ✅ A
- docs/configuration.md — ✅ A
- docs/extensions.md — ✅ A
- docs/getting-started.md — ✅ A
- docs/index.md — ✅ A
- docs/intelligent-context-management.md — ✅ A
- docs/mcp.md — ✅ A
- docs/providers.md — ✅ A
- docs/tools.md — ✅ A
- evals/README.md — ✅ A
- tests/ui_integration/INTERACTIVE_SESSION_TESTS.md — ✅ A
- src/henchman/agents/delegation.py — ✅ A
- src/henchman/agents/identity.py — ✅ A
- src/henchman/agents/metrics_reporter.py — ✅ A
- src/henchman/agents/orchestrator_anchoring.py — ✅ A
- src/henchman/agents/orchestrator_components.py — ✅ A
- src/henchman/agents/orchestrator_delegation_ctrl.py — ✅ A
- src/henchman/agents/orchestrator_execution.py — ✅ A
- src/henchman/agents/orchestrator_loop.py — ✅ A
- src/henchman/agents/orchestrator_prompts.py — ✅ A
- src/henchman/agents/orchestrator_timeout.py — ✅ A
- src/henchman/agents/orchestrator_turns.py — ✅ A
- src/henchman/agents/orchestrator_types.py — ✅ A
- src/henchman/agents/presets.py — ✅ A
- src/henchman/agents/prompts.py — ✅ A
- src/henchman/api/auth.py — ✅ A
- src/henchman/api/endpoints/chat.py — ✅ A
- src/henchman/api/endpoints/health.py — ✅ A
- src/henchman/api/state.py — ✅ A
- src/henchman/cli/command_processor.py — ✅ A
- src/henchman/config/context.py — ✅ A
- src/henchman/config/environment.py — ✅ A
- src/henchman/config/schema.py — ✅ A
- src/henchman/core/agent_config.py — ✅ A
- src/henchman/core/agent_stall.py — ✅ A
- src/henchman/core/agent_streaming.py — ✅ A
- src/henchman/core/events.py — ✅ A
- src/henchman/core/session_branch.py — ✅ A
- src/henchman/core/session_data.py — ✅ A
- src/henchman/core/session_helpers.py — ✅ A
- src/henchman/core/session_models.py — ✅ A
- src/henchman/extensions/base.py — ✅ A
- src/henchman/extensions/constants.py — ✅ A
- src/henchman/extensions/models.py — ✅ A
- src/henchman/extensions/plugin_compatibility.py — ✅ A
- src/henchman/knowledge/models.py — ✅ A
- src/henchman/knowledge/scanner.py — ✅ A
- src/henchman/mcp/config.py — ✅ A
- src/henchman/mcp/tool.py — ✅ A
- src/henchman/metrics/models.py — ✅ A
- src/henchman/providers/anthropic.py — ✅ A
- src/henchman/providers/base.py — ✅ A
- src/henchman/providers/deepseek.py — ✅ A
- src/henchman/providers/ollama.py — ✅ A
- src/henchman/providers/openai_compat.py — ✅ A
- src/henchman/providers/openrouter.py — ✅ A
- src/henchman/rag/chunker.py — ✅ A
- src/henchman/rag/embedder.py — ✅ A
- src/henchman/rag/repo_id.py — ✅ A
- src/henchman/tools/base.py — ✅ A
- src/henchman/tools/builtins/ask_user.py — ✅ A
- src/henchman/tools/builtins/code_format.py — ✅ A
- src/henchman/tools/builtins/dead_code.py — ✅ A
- src/henchman/tools/builtins/delegate.py — ✅ A
- src/henchman/tools/builtins/diff_view.py — ✅ A
- src/henchman/tools/builtins/env_inspect.py — ✅ A
- src/henchman/tools/builtins/file_edit.py — ✅ A
- src/henchman/tools/builtins/file_read.py — ✅ A
- src/henchman/tools/builtins/file_write.py — ✅ A
- src/henchman/tools/builtins/git_ops.py — ✅ A
- src/henchman/tools/builtins/glob_tool.py — ✅ A
- src/henchman/tools/builtins/grep.py — ✅ A
- src/henchman/tools/builtins/import_graph.py — ✅ A
- src/henchman/tools/builtins/kg_query.py — ✅ A
- src/henchman/tools/builtins/kg_update.py — ✅ A
- src/henchman/tools/builtins/lint_check.py — ✅ A
- src/henchman/tools/builtins/ls.py — ✅ A
- src/henchman/tools/builtins/patch_apply.py — ✅ A
- src/henchman/tools/builtins/pip_inspect.py — ✅ A
- src/henchman/tools/builtins/pytest_run.py — ✅ A
- src/henchman/tools/builtins/python_ast.py — ✅ A
- src/henchman/tools/builtins/python_exec.py — ✅ A
- src/henchman/tools/builtins/rag_search.py — ✅ A
- src/henchman/tools/builtins/shell.py — ✅ A
- src/henchman/tools/builtins/test_gen.py — ✅ A
- src/henchman/tools/builtins/traceback_parse.py — ✅ A
- src/henchman/tools/builtins/web_fetch.py — ✅ A
- src/henchman/tools/builtins/web_search.py — ✅ A
- src/henchman/tools/security/shell_secure.py — ✅ A
- src/henchman/tools/utils.py — ✅ A
- src/henchman/utils/compaction.py — ✅ A
- src/henchman/utils/compression_strategy.py — ✅ A
- src/henchman/utils/importance_scorer.py — ✅ A
- src/henchman/utils/intelligent_context.py — ✅ A
- src/henchman/utils/lazy_import.py — ✅ A
- src/henchman/utils/message_clusterer.py — ✅ A
- src/henchman/utils/retry.py — ✅ A
- src/henchman/utils/tokens.py — ✅ A

</details>

---

_Report generated by XP Documentation Smell Detector. Smells are static heuristics — use judgement when prioritising fixes._
