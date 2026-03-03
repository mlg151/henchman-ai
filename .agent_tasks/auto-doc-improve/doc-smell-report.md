# Documentation Smell Report — ✅ A (Score: 95.7/100)

_Project: /home/matthew/mlg-cli_  
_Generated: 2026-03-03T06:15:02.381479+00:00_

## Executive Summary

| Metric | Value |
|:-------|------:|
| **Overall Grade** | ✅ A |
| **Overall Score** | 95.7/100 |
| **Doc Files Scanned** | 18 |
| **Source Files Checked** | 166 |
| **Total Smells** | 421 |
| **Docstring Coverage** | 100.0% |

### Smells by Severity

| Severity | Count |
|:---------|------:|
| low | 335 |
| medium | 86 |

### Smells by Category

| Category | Count |
|:---------|------:|
| Incomplete Docstring | 413 |
| Missing Docstring | 4 |
| Stale Content | 2 |
| Config Issue | 1 |
| Consistency Error | 1 |

## 🎯 Prioritised Fix Queue

These are the highest-impact documentation smells to address first:

1. **pyproject.toml:65** — 🟡 MEDIUM — Consistency Error  
   States coverage threshold of 4% but other files require 100%. Found thresholds: 100%, 4%  
   → _Align all coverage requirements to 100% (the strictest value)._

2. **src/henchman/agents/identity.py:1** — 🟡 MEDIUM — Missing Docstring  
   Module is missing a docstring  
   → _Add a module-level docstring describing the module's purpose._

3. **src/henchman/agents/metrics.py:91** — 🟡 MEDIUM — Incomplete Docstring  
   'PerformanceMetrics.track_file_access' has 1 parameter(s) but no Args: section in docstring  
   → _Add an Args: section documenting: file_path_

4. **src/henchman/agents/metrics.py:95** — 🟡 MEDIUM — Incomplete Docstring  
   'PerformanceMetrics.track_tool_usage' has 1 parameter(s) but no Args: section in docstring  
   → _Add an Args: section documenting: tool_name_

5. **src/henchman/agents/metrics.py:152** — 🟡 MEDIUM — Incomplete Docstring  
   'ToolMetrics.track_tool_call' has 2 parameter(s) but no Args: section in docstring  
   → _Add an Args: section documenting: tool_name, success_

6. **src/henchman/agents/orchestrator.py:76** — 🟡 MEDIUM — Incomplete Docstring  
   'Orchestrator.run' has 1 parameter(s) but no Args: section in docstring  
   → _Add an Args: section documenting: user_input_

7. **src/henchman/agents/orchestrator.py:94** — 🟡 MEDIUM — Incomplete Docstring  
   'Orchestrator.run_direct' has 2 parameter(s) but no Args: section in docstring  
   → _Add an Args: section documenting: role, user_input_

8. **src/henchman/agents/orchestrator_anchoring.py:19** — 🟡 MEDIUM — Incomplete Docstring  
   'inject_role_anchor' has 3 parameter(s) but no Args: section in docstring  
   → _Add an Args: section documenting: orchestrator, agent, tool_call_count_

9. **src/henchman/agents/orchestrator_anchoring.py:42** — 🟡 MEDIUM — Incomplete Docstring  
   'assess_agent_completion' has 2 parameter(s) but no Args: section in docstring  
   → _Add an Args: section documenting: orchestrator, agent_

10. **src/henchman/agents/orchestrator_components.py:39** — 🟡 MEDIUM — Incomplete Docstring  
   'AgentValidator.check_thinking_pattern' has 1 parameter(s) but no Args: section in docstring  
   → _Add an Args: section documenting: agent_

11. **src/henchman/agents/orchestrator_components.py:57** — 🟡 MEDIUM — Incomplete Docstring  
   'AgentValidator.check_stall_failure' has 1 parameter(s) but no Args: section in docstring  
   → _Add an Args: section documenting: agent_

12. **src/henchman/agents/orchestrator_delegation_ctrl.py:55** — 🟡 MEDIUM — Incomplete Docstring  
   'DelegationController.execute_delegation_tool' has 3 parameter(s) but no Args: section in docstring  
   → _Add an Args: section documenting: agent, tool_call, depth_

13. **src/henchman/agents/orchestrator_events.py:26** — 🟡 MEDIUM — Incomplete Docstring  
   'extract_brief_fields' has 1 parameter(s) but no Args: section in docstring  
   → _Add an Args: section documenting: arguments_

14. **src/henchman/agents/orchestrator_events.py:31** — 🟡 MEDIUM — Incomplete Docstring  
   'create_delegation_event' has 3 parameter(s) but no Args: section in docstring  
   → _Add an Args: section documenting: agent, target, task_

15. **src/henchman/agents/orchestrator_events.py:48** — 🟡 MEDIUM — Incomplete Docstring  
   'create_tool_result_event' has 3 parameter(s) but no Args: section in docstring  
   → _Add an Args: section documenting: agent, tool_call, result_content_

16. **src/henchman/agents/orchestrator_events.py:66** — 🟡 MEDIUM — Incomplete Docstring  
   'update_ledger' has 4 parameter(s) but no Args: section in docstring  
   → _Add an Args: section documenting: ledger, record, result, had_error_

17. **src/henchman/agents/orchestrator_execution.py:60** — 🟡 MEDIUM — Incomplete Docstring  
   'ExecutionController.run_agent_loop' has 1 parameter(s) but no Args: section in docstring  
   → _Add an Args: section documenting: params_

18. **src/henchman/agents/orchestrator_execution.py:117** — 🟡 MEDIUM — Incomplete Docstring  
   'ExecutionController.assess_completion' has 1 parameter(s) but no Args: section in docstring  
   → _Add an Args: section documenting: agent_

19. **src/henchman/agents/orchestrator_loop.py:51** — 🟡 MEDIUM — Incomplete Docstring  
   'run_tools_and_collect' has 5 parameter(s) but no Args: section in docstring  
   → _Add an Args: section documenting: orchestrator, agent, pending, params, state_

20. **src/henchman/agents/orchestrator_loop.py:71** — 🟡 MEDIUM — Incomplete Docstring  
   'collect_events' has 2 parameter(s) but no Args: section in docstring  
   → _Add an Args: section documenting: generator, pending_


## 📊 Files Ranked by Quality

| Rank | File | Grade | Score | Smells | Last Modified |
|-----:|:-----|:------|------:|-------:|:-------------|
| 1 | src/henchman/cli/commands/session.py | ❌ F | 0.0 | 31 | 2026-03-02 |
| 2 | src/henchman/cli/ui_renderer.py | ❌ F | 0.0 | 38 | 2026-03-02 |
| 3 | src/henchman/cli/textual_widgets.py | ❌ F | 49.0 | 24 | 2026-03-01 |
| 4 | src/henchman/core/session_manager.py | ❌ F | 49.0 | 15 | 2026-02-28 |
| 5 | src/henchman/cli/console.py | ❌ F | 56.0 | 22 | 2026-03-03 |
| 6 | src/henchman/agents/orchestrator_loop.py | ❌ F | 58.0 | 12 | 2026-02-28 |
| 7 | src/henchman/agents/metrics.py | 🔶 D | 61.0 | 15 | 2026-02-27 |
| 8 | src/henchman/cli/stream_event_handlers.py | 🔶 D | 65.0 | 10 | 2026-03-01 |
| 9 | src/henchman/agents/orchestrator_events.py | ⚠️ C | 72.0 | 8 | 2026-02-28 |
| 10 | src/henchman/agents/orchestrator_validation.py | ⚠️ C | 72.0 | 8 | 2026-02-28 |
| 11 | src/henchman/cli/commands/context.py | ⚠️ C | 72.0 | 14 | 2026-03-03 |
| 12 | src/henchman/cli/output_handler.py | ⚠️ C | 74.0 | 13 | 2026-02-27 |
| 13 | src/henchman/api/server.py | ⚠️ C | 75.0 | 8 | 2026-02-26 |
| 14 | src/henchman/agents/orchestrator_metrics_ctrl.py | ⚠️ C | 79.0 | 6 | 2026-02-28 |
| 15 | src/henchman/agents/orchestrator.py | 👍 B | 80.0 | 7 | 2026-02-28 |

## 📁 Per-File Details

_Showing 25 worst files. 160 additional files omitted._

### src/henchman/cli/commands/session.py — ❌ F (0.0/100) (last modified 2026-03-02)

Public APIs: 45 | Documented: 45 | Coverage: 100.0%

| Line | Severity | Type | Message | Suggested Fix |
|-----:|:---------|:-----|:--------|:--------------|
| 126 | 🟡 MEDIUM | Incomplete Docstring | 'CommandOperationContext.print_success' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: message |
| 130 | 🟡 MEDIUM | Incomplete Docstring | 'CommandOperationContext.print_error' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: message |
| 134 | 🟡 MEDIUM | Incomplete Docstring | 'CommandOperationContext.print_info' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: message |
| 138 | 🟡 MEDIUM | Incomplete Docstring | 'CommandOperationContext.print_usage' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: usage |
| 237 | 🟡 MEDIUM | Incomplete Docstring | 'SessionCommandExecutor.execute' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: manager |
| 257 | 🟡 MEDIUM | Incomplete Docstring | 'BranchExecutor.execute' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: manager |
| 338 | 🟡 MEDIUM | Incomplete Docstring | 'MergeExecutor.execute' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: manager |
| 363 | 🟡 MEDIUM | Incomplete Docstring | 'TemplateSaveExecutor.execute' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: manager |
| 392 | 🟡 MEDIUM | Incomplete Docstring | 'TemplateCreateExecutor.execute' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: manager |
| 421 | 🟡 MEDIUM | Incomplete Docstring | 'TemplateListExecutor.execute' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: manager |
| 445 | 🟡 MEDIUM | Incomplete Docstring | 'TemplateDeleteExecutor.execute' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: manager |
| 469 | 🟡 MEDIUM | Incomplete Docstring | 'ExportExecutor.execute' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: manager |
| 498 | 🟡 MEDIUM | Incomplete Docstring | 'ImportExecutor.execute' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: manager |
| 126 | 🟢 LOW | Incomplete Docstring | 'CommandOperationContext.print_success' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'CommandOperationContext.print_success'. |
| 130 | 🟢 LOW | Incomplete Docstring | 'CommandOperationContext.print_error' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'CommandOperationContext.print_error'. |

_... and 16 more smells._

### src/henchman/cli/ui_renderer.py — ❌ F (0.0/100) (last modified 2026-03-02)

Public APIs: 35 | Documented: 35 | Coverage: 100.0%

| Line | Severity | Type | Message | Suggested Fix |
|-----:|:---------|:-----|:--------|:--------------|
| 274 | 🟡 MEDIUM | Incomplete Docstring | 'UIRenderer.success' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: message |
| 278 | 🟡 MEDIUM | Incomplete Docstring | 'UIRenderer.info' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: message |
| 282 | 🟡 MEDIUM | Incomplete Docstring | 'UIRenderer.warning' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: message |
| 286 | 🟡 MEDIUM | Incomplete Docstring | 'UIRenderer.error' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: message |
| 290 | 🟡 MEDIUM | Incomplete Docstring | 'UIRenderer.muted' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: text |
| 294 | 🟡 MEDIUM | Incomplete Docstring | 'UIRenderer.heading' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: text |
| 298 | 🟡 MEDIUM | Incomplete Docstring | 'UIRenderer.markdown' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: content |
| 302 | 🟡 MEDIUM | Incomplete Docstring | 'UIRenderer.code' has 2 parameter(s) but no Args: section in docstring | Add an Args: section documenting: code, language |
| 306 | 🟡 MEDIUM | Incomplete Docstring | 'UIRenderer.rule' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: title |
| 314 | 🟡 MEDIUM | Incomplete Docstring | 'UIRenderer.tool_call' has 2 parameter(s) but no Args: section in docstring | Add an Args: section documenting: name, arguments |
| 318 | 🟡 MEDIUM | Incomplete Docstring | 'UIRenderer.tool_result' has 3 parameter(s) but no Args: section in docstring | Add an Args: section documenting: content, success, error |
| 322 | 🟡 MEDIUM | Incomplete Docstring | 'UIRenderer.tool_summary' has 2 parameter(s) but no Args: section in docstring | Add an Args: section documenting: name, duration |
| 69 | 🟢 LOW | Incomplete Docstring | 'ProgressManager.update_task' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ProgressManager.update_task'. |
| 84 | 🟢 LOW | Incomplete Docstring | 'ProgressManager.complete_task' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ProgressManager.complete_task'. |
| 136 | 🟢 LOW | Incomplete Docstring | 'UIRenderer.print_welcome' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'UIRenderer.print_welcome'. |

_... and 23 more smells._

### src/henchman/cli/textual_widgets.py — ❌ F (49.0/100) (last modified 2026-03-01)

Public APIs: 46 | Documented: 46 | Coverage: 100.0%

| Line | Severity | Type | Message | Suggested Fix |
|-----:|:---------|:-----|:--------|:--------------|
| 243 | 🟡 MEDIUM | Incomplete Docstring | 'CollapsibleMessage.content' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: value |
| 243 | 🟢 LOW | Incomplete Docstring | 'CollapsibleMessage.content' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'CollapsibleMessage.content'. |
| 262 | 🟢 LOW | Incomplete Docstring | 'CollapsibleMessage.toggle_expansion' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'CollapsibleMessage.toggle_expansion'. |
| 270 | 🟢 LOW | Incomplete Docstring | 'CollapsibleMessage.on_click' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'CollapsibleMessage.on_click'. |
| 278 | 🟢 LOW | Incomplete Docstring | 'CollapsibleMessage.set_highlight' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'CollapsibleMessage.set_highlight'. |
| 344 | 🟢 LOW | Incomplete Docstring | 'HenchmanTextArea.on_key' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'HenchmanTextArea.on_key'. |
| 379 | 🟢 LOW | Incomplete Docstring | 'HenchmanTextArea.action_newline' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'HenchmanTextArea.action_newline'. |
| 383 | 🟢 LOW | Incomplete Docstring | 'HenchmanTextArea.action_history_up' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'HenchmanTextArea.action_history_up'. |
| 394 | 🟢 LOW | Incomplete Docstring | 'HenchmanTextArea.action_history_down' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'HenchmanTextArea.action_history_down'. |
| 477 | 🟢 LOW | Incomplete Docstring | 'ChatMessage.set_highlight' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ChatMessage.set_highlight'. |
| 490 | 🟢 LOW | Incomplete Docstring | 'ChatMessage.finalize_as_markdown' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ChatMessage.finalize_as_markdown'. |
| 589 | 🟢 LOW | Incomplete Docstring | 'ThinkingMessage.append' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ThinkingMessage.append'. |
| 601 | 🟢 LOW | Incomplete Docstring | 'ThinkingMessage.set_content' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ThinkingMessage.set_content'. |
| 885 | 🟢 LOW | Incomplete Docstring | 'ChatPane.on_mount' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ChatPane.on_mount'. |
| 924 | 🟢 LOW | Incomplete Docstring | 'ChatPane.add_user_message' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ChatPane.add_user_message'. |

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

### src/henchman/agents/orchestrator_loop.py — ❌ F (58.0/100) (last modified 2026-02-28)

Public APIs: 6 | Documented: 6 | Coverage: 100.0%

| Line | Severity | Type | Message | Suggested Fix |
|-----:|:---------|:-----|:--------|:--------------|
| 51 | 🟡 MEDIUM | Incomplete Docstring | 'run_tools_and_collect' has 5 parameter(s) but no Args: section in docstring | Add an Args: section documenting: orchestrator, agent, pending, params, state |
| 71 | 🟡 MEDIUM | Incomplete Docstring | 'collect_events' has 2 parameter(s) but no Args: section in docstring | Add an Args: section documenting: generator, pending |
| 90 | 🟡 MEDIUM | Incomplete Docstring | 'check_turn_limits' has 3 parameter(s) but no Args: section in docstring | Add an Args: section documenting: agent, params, state |
| 107 | 🟡 MEDIUM | Incomplete Docstring | 'finalize_loop' has 3 parameter(s) but no Args: section in docstring | Add an Args: section documenting: orchestrator, agent, state |
| 122 | 🟡 MEDIUM | Incomplete Docstring | 'check_colon_stall' has 2 parameter(s) but no Args: section in docstring | Add an Args: section documenting: agent, retries |
| 137 | 🟡 MEDIUM | Incomplete Docstring | 'last_assistant_content' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: agent |
| 51 | 🟢 LOW | Incomplete Docstring | 'run_tools_and_collect' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'run_tools_and_collect'. |
| 71 | 🟢 LOW | Incomplete Docstring | 'collect_events' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'collect_events'. |
| 90 | 🟢 LOW | Incomplete Docstring | 'check_turn_limits' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'check_turn_limits'. |
| 107 | 🟢 LOW | Incomplete Docstring | 'finalize_loop' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'finalize_loop'. |
| 122 | 🟢 LOW | Incomplete Docstring | 'check_colon_stall' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'check_colon_stall'. |
| 137 | 🟢 LOW | Incomplete Docstring | 'last_assistant_content' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'last_assistant_content'. |

### src/henchman/agents/metrics.py — 🔶 D (61.0/100) (last modified 2026-02-27)

Public APIs: 19 | Documented: 19 | Coverage: 100.0%

| Line | Severity | Type | Message | Suggested Fix |
|-----:|:---------|:-----|:--------|:--------------|
| 91 | 🟡 MEDIUM | Incomplete Docstring | 'PerformanceMetrics.track_file_access' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: file_path |
| 95 | 🟡 MEDIUM | Incomplete Docstring | 'PerformanceMetrics.track_tool_usage' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: tool_name |
| 152 | 🟡 MEDIUM | Incomplete Docstring | 'ToolMetrics.track_tool_call' has 2 parameter(s) but no Args: section in docstring | Add an Args: section documenting: tool_name, success |
| 71 | 🟢 LOW | Incomplete Docstring | 'PerformanceMetrics.reset' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'PerformanceMetrics.reset'. |
| 83 | 🟢 LOW | Incomplete Docstring | 'PerformanceMetrics.calculate_file_re_reads' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'PerformanceMetrics.calculate_file_re_reads'. |
| 91 | 🟢 LOW | Incomplete Docstring | 'PerformanceMetrics.track_file_access' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'PerformanceMetrics.track_file_access'. |
| 95 | 🟢 LOW | Incomplete Docstring | 'PerformanceMetrics.track_tool_usage' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'PerformanceMetrics.track_tool_usage'. |
| 110 | 🟢 LOW | Incomplete Docstring | 'QualityMetrics.reset' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'QualityMetrics.reset'. |
| 117 | 🟢 LOW | Incomplete Docstring | 'QualityMetrics.calculate_test_percentage' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'QualityMetrics.calculate_test_percentage'. |
| 140 | 🟢 LOW | Incomplete Docstring | 'ToolMetrics.reset' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ToolMetrics.reset'. |
| 152 | 🟢 LOW | Incomplete Docstring | 'ToolMetrics.track_tool_call' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ToolMetrics.track_tool_call'. |
| 176 | 🟢 LOW | Incomplete Docstring | 'ToolMetrics.calculate_error_rate' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ToolMetrics.calculate_error_rate'. |
| 219 | 🟢 LOW | Incomplete Docstring | 'OrchestratorMetrics.reset_for_run' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'OrchestratorMetrics.reset_for_run'. |
| 230 | 🟢 LOW | Incomplete Docstring | 'OrchestratorMetrics.calculate_final_metrics' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'OrchestratorMetrics.calculate_final_metrics'. |
| 252 | 🟢 LOW | Incomplete Docstring | 'OrchestratorMetrics.update_tool_metrics' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'OrchestratorMetrics.update_tool_metrics'. |

### src/henchman/cli/stream_event_handlers.py — 🔶 D (65.0/100) (last modified 2026-03-01)

Public APIs: 6 | Documented: 6 | Coverage: 100.0%

| Line | Severity | Type | Message | Suggested Fix |
|-----:|:---------|:-----|:--------|:--------------|
| 52 | 🟡 MEDIUM | Incomplete Docstring | 'determine_event_ownership' has 2 parameter(s) but no Args: section in docstring | Add an Args: section documenting: event, agent |
| 63 | 🟡 MEDIUM | Incomplete Docstring | 'update_processing_state' has 4 parameter(s) but no Args: section in docstring | Add an Args: section documenting: output_handler, state, event, agent |
| 241 | 🟡 MEDIUM | Incomplete Docstring | 'dispatch_event' has 5 parameter(s) but no Args: section in docstring | Add an Args: section documenting: output_handler, event, state, agent, content_collector |
| 276 | 🟡 MEDIUM | Incomplete Docstring | 'handle_post_stream_processing' has 5 parameter(s) but no Args: section in docstring | Add an Args: section documenting: output_handler, state, agent, content_collector, execute_tool_calls_fn |
| 319 | 🟡 MEDIUM | Incomplete Docstring | 'build_confirmation_message' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: request |
| 52 | 🟢 LOW | Incomplete Docstring | 'determine_event_ownership' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'determine_event_ownership'. |
| 63 | 🟢 LOW | Incomplete Docstring | 'update_processing_state' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'update_processing_state'. |
| 241 | 🟢 LOW | Incomplete Docstring | 'dispatch_event' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'dispatch_event'. |
| 276 | 🟢 LOW | Incomplete Docstring | 'handle_post_stream_processing' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'handle_post_stream_processing'. |
| 319 | 🟢 LOW | Incomplete Docstring | 'build_confirmation_message' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'build_confirmation_message'. |

### src/henchman/agents/orchestrator_events.py — ⚠️ C (72.0/100) (last modified 2026-02-28)

Public APIs: 4 | Documented: 4 | Coverage: 100.0%

| Line | Severity | Type | Message | Suggested Fix |
|-----:|:---------|:-----|:--------|:--------------|
| 26 | 🟡 MEDIUM | Incomplete Docstring | 'extract_brief_fields' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: arguments |
| 31 | 🟡 MEDIUM | Incomplete Docstring | 'create_delegation_event' has 3 parameter(s) but no Args: section in docstring | Add an Args: section documenting: agent, target, task |
| 48 | 🟡 MEDIUM | Incomplete Docstring | 'create_tool_result_event' has 3 parameter(s) but no Args: section in docstring | Add an Args: section documenting: agent, tool_call, result_content |
| 66 | 🟡 MEDIUM | Incomplete Docstring | 'update_ledger' has 4 parameter(s) but no Args: section in docstring | Add an Args: section documenting: ledger, record, result, had_error |
| 26 | 🟢 LOW | Incomplete Docstring | 'extract_brief_fields' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'extract_brief_fields'. |
| 31 | 🟢 LOW | Incomplete Docstring | 'create_delegation_event' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'create_delegation_event'. |
| 48 | 🟢 LOW | Incomplete Docstring | 'create_tool_result_event' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'create_tool_result_event'. |
| 66 | 🟢 LOW | Incomplete Docstring | 'update_ledger' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'update_ledger'. |

### src/henchman/agents/orchestrator_validation.py — ⚠️ C (72.0/100) (last modified 2026-02-28)

Public APIs: 4 | Documented: 4 | Coverage: 100.0%

| Line | Severity | Type | Message | Suggested Fix |
|-----:|:---------|:-----|:--------|:--------------|
| 23 | 🟡 MEDIUM | Incomplete Docstring | 'should_check_thinking' has 2 parameter(s) but no Args: section in docstring | Add an Args: section documenting: orchestrator, agent |
| 32 | 🟡 MEDIUM | Incomplete Docstring | 'handle_valid_thinking' has 2 parameter(s) but no Args: section in docstring | Add an Args: section documenting: metrics, content |
| 45 | 🟡 MEDIUM | Incomplete Docstring | 'handle_missing_thinking' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: agent |
| 64 | 🟡 MEDIUM | Incomplete Docstring | 'check_stall_failure' has 2 parameter(s) but no Args: section in docstring | Add an Args: section documenting: orchestrator, agent |
| 23 | 🟢 LOW | Incomplete Docstring | 'should_check_thinking' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'should_check_thinking'. |
| 32 | 🟢 LOW | Incomplete Docstring | 'handle_valid_thinking' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'handle_valid_thinking'. |
| 45 | 🟢 LOW | Incomplete Docstring | 'handle_missing_thinking' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'handle_missing_thinking'. |
| 64 | 🟢 LOW | Incomplete Docstring | 'check_stall_failure' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'check_stall_failure'. |

### src/henchman/cli/commands/context.py — ⚠️ C (72.0/100) (last modified 2026-03-03)

Public APIs: 25 | Documented: 25 | Coverage: 100.0%

| Line | Severity | Type | Message | Suggested Fix |
|-----:|:---------|:-----|:--------|:--------------|
| 50 | 🟢 LOW | Incomplete Docstring | 'RangeParameterConfig.validate_value' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'RangeParameterConfig.validate_value'. |
| 91 | 🟢 LOW | Incomplete Docstring | 'ConsoleOutputHelper.print_status_header' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ConsoleOutputHelper.print_status_header'. |
| 99 | 🟢 LOW | Incomplete Docstring | 'ConsoleOutputHelper.print_enabled_status' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ConsoleOutputHelper.print_enabled_status'. |
| 108 | 🟢 LOW | Incomplete Docstring | 'ConsoleOutputHelper.print_status_value' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ConsoleOutputHelper.print_status_value'. |
| 117 | 🟢 LOW | Incomplete Docstring | 'ConsoleOutputHelper.print_command_help' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ConsoleOutputHelper.print_command_help'. |
| 126 | 🟢 LOW | Incomplete Docstring | 'ConsoleOutputHelper.print_error_message' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ConsoleOutputHelper.print_error_message'. |
| 135 | 🟢 LOW | Incomplete Docstring | 'ConsoleOutputHelper.print_usage_help' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ConsoleOutputHelper.print_usage_help'. |
| 147 | 🟢 LOW | Incomplete Docstring | 'ConsoleOutputHelper.print_line' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ConsoleOutputHelper.print_line'. |
| 163 | 🟢 LOW | Incomplete Docstring | 'ContextConsoleHelper.print_status_info' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ContextConsoleHelper.print_status_info'. |
| 227 | 🟢 LOW | Incomplete Docstring | 'ContextConsoleHelper.print_strategy_usage' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ContextConsoleHelper.print_strategy_usage'. |
| 249 | 🟢 LOW | Incomplete Docstring | 'ContextConsoleHelper.print_strategy_status' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ContextConsoleHelper.print_strategy_status'. |
| 316 | 🟢 LOW | Incomplete Docstring | 'StrategyManager.manage_strategy' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'StrategyManager.manage_strategy'. |
| 452 | 🟢 LOW | Incomplete Docstring | 'ContextCommand.execute' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ContextCommand.execute'. |
| 540 | 🟢 LOW | Incomplete Docstring | 'StatisticsManager.show_stats' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'StatisticsManager.show_stats'. |

### src/henchman/cli/output_handler.py — ⚠️ C (74.0/100) (last modified 2026-02-27)

Public APIs: 18 | Documented: 18 | Coverage: 100.0%

| Line | Severity | Type | Message | Suggested Fix |
|-----:|:---------|:-----|:--------|:--------------|
| 238 | 🟢 LOW | Incomplete Docstring | 'OutputHandler.print_welcome' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'OutputHandler.print_welcome'. |
| 242 | 🟢 LOW | Incomplete Docstring | 'OutputHandler.print_goodbye' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'OutputHandler.print_goodbye'. |
| 246 | 🟢 LOW | Incomplete Docstring | 'OutputHandler.print_newline' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'OutputHandler.print_newline'. |
| 250 | 🟢 LOW | Incomplete Docstring | 'OutputHandler.success' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'OutputHandler.success'. |
| 258 | 🟢 LOW | Incomplete Docstring | 'OutputHandler.error' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'OutputHandler.error'. |
| 266 | 🟢 LOW | Incomplete Docstring | 'OutputHandler.warning' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'OutputHandler.warning'. |
| 274 | 🟢 LOW | Incomplete Docstring | 'OutputHandler.muted' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'OutputHandler.muted'. |
| 282 | 🟢 LOW | Incomplete Docstring | 'OutputHandler.thinking' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'OutputHandler.thinking'. |
| 290 | 🟢 LOW | Incomplete Docstring | 'OutputHandler.print_agent_content' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'OutputHandler.print_agent_content'. |
| 310 | 🟢 LOW | Incomplete Docstring | 'OutputHandler.show_turn_status' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'OutputHandler.show_turn_status'. |
| 345 | 🟢 LOW | Incomplete Docstring | 'OutputHandler.update_task' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'OutputHandler.update_task'. |
| 355 | 🟢 LOW | Incomplete Docstring | 'OutputHandler.complete_task' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'OutputHandler.complete_task'. |
| 363 | 🟢 LOW | Incomplete Docstring | 'OutputHandler.start_background_indexing' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'OutputHandler.start_background_indexing'. |

### src/henchman/api/server.py — ⚠️ C (75.0/100) (last modified 2026-02-26)

Public APIs: 7 | Documented: 7 | Coverage: 100.0%

| Line | Severity | Type | Message | Suggested Fix |
|-----:|:---------|:-----|:--------|:--------------|
| 75 | 🟡 MEDIUM | Incomplete Docstring | 'lifespan' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: _app |
| 148 | 🟡 MEDIUM | Incomplete Docstring | 'http_exception_handler' has 2 parameter(s) but no Args: section in docstring | Add an Args: section documenting: request, exc |
| 161 | 🟡 MEDIUM | Incomplete Docstring | 'generic_exception_handler' has 2 parameter(s) but no Args: section in docstring | Add an Args: section documenting: request, _exc |
| 75 | 🟢 LOW | Incomplete Docstring | 'lifespan' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'lifespan'. |
| 138 | 🟢 LOW | Incomplete Docstring | 'root' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'root'. |
| 148 | 🟢 LOW | Incomplete Docstring | 'http_exception_handler' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'http_exception_handler'. |
| 161 | 🟢 LOW | Incomplete Docstring | 'generic_exception_handler' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'generic_exception_handler'. |
| 173 | 🟢 LOW | Incomplete Docstring | 'run_server' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'run_server'. |

### src/henchman/agents/orchestrator_metrics_ctrl.py — ⚠️ C (79.0/100) (last modified 2026-02-28)

Public APIs: 4 | Documented: 4 | Coverage: 100.0%

| Line | Severity | Type | Message | Suggested Fix |
|-----:|:---------|:-----|:--------|:--------------|
| 17 | 🟡 MEDIUM | Incomplete Docstring | 'ToolMetricsController.update_tool_metrics' has 3 parameter(s) but no Args: section in docstring | Add an Args: section documenting: tool_name, arguments, success |
| 27 | 🟡 MEDIUM | Incomplete Docstring | 'ToolMetricsController.track_tool_error' has 3 parameter(s) but no Args: section in docstring | Add an Args: section documenting: tool_errors, tool_name, result_content |
| 39 | 🟡 MEDIUM | Incomplete Docstring | 'ToolMetricsController.update_delegation_metrics' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: target |
| 17 | 🟢 LOW | Incomplete Docstring | 'ToolMetricsController.update_tool_metrics' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ToolMetricsController.update_tool_metrics'. |
| 27 | 🟢 LOW | Incomplete Docstring | 'ToolMetricsController.track_tool_error' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ToolMetricsController.track_tool_error'. |
| 39 | 🟢 LOW | Incomplete Docstring | 'ToolMetricsController.update_delegation_metrics' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ToolMetricsController.update_delegation_metrics'. |

### src/henchman/agents/orchestrator.py — 👍 B (80.0/100) (last modified 2026-02-28)

Public APIs: 6 | Documented: 6 | Coverage: 100.0%

| Line | Severity | Type | Message | Suggested Fix |
|-----:|:---------|:-----|:--------|:--------------|
| 76 | 🟡 MEDIUM | Incomplete Docstring | 'Orchestrator.run' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: user_input |
| 94 | 🟡 MEDIUM | Incomplete Docstring | 'Orchestrator.run_direct' has 2 parameter(s) but no Args: section in docstring | Add an Args: section documenting: role, user_input |
| 76 | 🟢 LOW | Incomplete Docstring | 'Orchestrator.run' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'Orchestrator.run'. |
| 94 | 🟢 LOW | Incomplete Docstring | 'Orchestrator.run_direct' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'Orchestrator.run_direct'. |
| 117 | 🟢 LOW | Incomplete Docstring | 'Orchestrator.get_metrics_report' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'Orchestrator.get_metrics_report'. |
| 121 | 🟢 LOW | Incomplete Docstring | 'Orchestrator.get_pool' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'Orchestrator.get_pool'. |
| 125 | 🟢 LOW | Incomplete Docstring | 'Orchestrator.get_event_bus' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'Orchestrator.get_event_bus'. |

### src/henchman/metrics/storage.py — 👍 B (82.0/100) (last modified 2026-03-03)

Public APIs: 16 | Documented: 16 | Coverage: 100.0%

| Line | Severity | Type | Message | Suggested Fix |
|-----:|:---------|:-----|:--------|:--------------|
| 223 | 🟡 MEDIUM | Incomplete Docstring | 'DatabaseSchemaManager.create_metrics_table' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: cursor |
| 232 | 🟡 MEDIUM | Incomplete Docstring | 'DatabaseSchemaManager.create_indexes' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: cursor |
| 223 | 🟢 LOW | Incomplete Docstring | 'DatabaseSchemaManager.create_metrics_table' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'DatabaseSchemaManager.create_metrics_table'. |
| 232 | 🟢 LOW | Incomplete Docstring | 'DatabaseSchemaManager.create_indexes' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'DatabaseSchemaManager.create_indexes'. |
| 469 | 🟢 LOW | Incomplete Docstring | 'MetricsStorage.store_metric' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'MetricsStorage.store_metric'. |
| 772 | 🟢 LOW | Incomplete Docstring | 'MetricsStorage.clear_metrics' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'MetricsStorage.clear_metrics'. |

### src/henchman/utils/validation.py — 👍 B (83.0/100) (last modified 2026-02-20)

Public APIs: 4 | Documented: 4 | Coverage: 100.0%

| Line | Severity | Type | Message | Suggested Fix |
|-----:|:---------|:-----|:--------|:--------------|
| 12 | 🟡 MEDIUM | Incomplete Docstring | 'validate_message_sequence' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: messages |
| 179 | 🟡 MEDIUM | Incomplete Docstring | 'is_valid_message_sequence' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: messages |
| 192 | 🟡 MEDIUM | Incomplete Docstring | 'format_message_sequence_for_debug' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: messages |
| 12 | 🟢 LOW | Incomplete Docstring | 'validate_message_sequence' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'validate_message_sequence'. |

### src/henchman/cli/app.py — 👍 B (84.0/100) (last modified 2026-02-27)

Public APIs: 5 | Documented: 5 | Coverage: 100.0%

| Line | Severity | Type | Message | Suggested Fix |
|-----:|:---------|:-----|:--------|:--------------|
| 600 | 🟡 MEDIUM | Incomplete Docstring | 'cli' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: ctx |
| 645 | 🟡 MEDIUM | Incomplete Docstring | 'chat_command' has 8 parameter(s) but no Args: section in docstring | Add an Args: section documenting: prompt, agent, team, output_format, plan, yes, tui, debug |
| 600 | 🟢 LOW | Incomplete Docstring | 'cli' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'cli'. |
| 645 | 🟢 LOW | Incomplete Docstring | 'chat_command' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'chat_command'. |
| 703 | 🟢 LOW | Incomplete Docstring | 'main' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'main'. |

### src/henchman/agents/orchestrator_anchoring.py — 👍 B (86.0/100) (last modified 2026-02-28)

Public APIs: 2 | Documented: 2 | Coverage: 100.0%

| Line | Severity | Type | Message | Suggested Fix |
|-----:|:---------|:-----|:--------|:--------------|
| 19 | 🟡 MEDIUM | Incomplete Docstring | 'inject_role_anchor' has 3 parameter(s) but no Args: section in docstring | Add an Args: section documenting: orchestrator, agent, tool_call_count |
| 42 | 🟡 MEDIUM | Incomplete Docstring | 'assess_agent_completion' has 2 parameter(s) but no Args: section in docstring | Add an Args: section documenting: orchestrator, agent |
| 19 | 🟢 LOW | Incomplete Docstring | 'inject_role_anchor' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'inject_role_anchor'. |
| 42 | 🟢 LOW | Incomplete Docstring | 'assess_agent_completion' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'assess_agent_completion'. |

### src/henchman/agents/orchestrator_components.py — 👍 B (86.0/100) (last modified 2026-02-28)

Public APIs: 4 | Documented: 4 | Coverage: 100.0%

| Line | Severity | Type | Message | Suggested Fix |
|-----:|:---------|:-----|:--------|:--------------|
| 39 | 🟡 MEDIUM | Incomplete Docstring | 'AgentValidator.check_thinking_pattern' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: agent |
| 57 | 🟡 MEDIUM | Incomplete Docstring | 'AgentValidator.check_stall_failure' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: agent |
| 39 | 🟢 LOW | Incomplete Docstring | 'AgentValidator.check_thinking_pattern' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'AgentValidator.check_thinking_pattern'. |
| 57 | 🟢 LOW | Incomplete Docstring | 'AgentValidator.check_stall_failure' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'AgentValidator.check_stall_failure'. |

### src/henchman/agents/orchestrator_execution.py — 👍 B (86.0/100) (last modified 2026-02-28)

Public APIs: 3 | Documented: 3 | Coverage: 100.0%

| Line | Severity | Type | Message | Suggested Fix |
|-----:|:---------|:-----|:--------|:--------------|
| 60 | 🟡 MEDIUM | Incomplete Docstring | 'ExecutionController.run_agent_loop' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: params |
| 117 | 🟡 MEDIUM | Incomplete Docstring | 'ExecutionController.assess_completion' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: agent |
| 60 | 🟢 LOW | Incomplete Docstring | 'ExecutionController.run_agent_loop' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ExecutionController.run_agent_loop'. |
| 117 | 🟢 LOW | Incomplete Docstring | 'ExecutionController.assess_completion' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ExecutionController.assess_completion'. |

### src/henchman/agents/orchestrator_tools.py — 👍 B (86.0/100) (last modified 2026-02-28)

Public APIs: 3 | Documented: 3 | Coverage: 100.0%

| Line | Severity | Type | Message | Suggested Fix |
|-----:|:---------|:-----|:--------|:--------------|
| 38 | 🟡 MEDIUM | Incomplete Docstring | 'ToolController.update_tool_metrics' has 3 parameter(s) but no Args: section in docstring | Add an Args: section documenting: tool_name, args, success |
| 50 | 🟡 MEDIUM | Incomplete Docstring | 'ToolController.process_pending_tool_calls' has 4 parameter(s) but no Args: section in docstring | Add an Args: section documenting: agent, pending_tool_calls, depth, tool_errors |
| 38 | 🟢 LOW | Incomplete Docstring | 'ToolController.update_tool_metrics' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ToolController.update_tool_metrics'. |
| 50 | 🟢 LOW | Incomplete Docstring | 'ToolController.process_pending_tool_calls' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ToolController.process_pending_tool_calls'. |

### src/henchman/cli/textual_screens.py — 👍 B (86.0/100) (last modified 2026-02-24)

Public APIs: 15 | Documented: 15 | Coverage: 100.0%

| Line | Severity | Type | Message | Suggested Fix |
|-----:|:---------|:-----|:--------|:--------------|
| 154 | 🟢 LOW | Incomplete Docstring | 'ConfirmToolScreen.on_button_pressed' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ConfirmToolScreen.on_button_pressed'. |
| 162 | 🟢 LOW | Incomplete Docstring | 'ConfirmToolScreen.action_approve' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ConfirmToolScreen.action_approve'. |
| 166 | 🟢 LOW | Incomplete Docstring | 'ConfirmToolScreen.action_deny' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ConfirmToolScreen.action_deny'. |
| 228 | 🟢 LOW | Incomplete Docstring | 'HelpScreen.on_button_pressed' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'HelpScreen.on_button_pressed'. |
| 343 | 🟢 LOW | Incomplete Docstring | 'ProviderScreen.on_button_pressed' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ProviderScreen.on_button_pressed'. |
| 450 | 🟢 LOW | Incomplete Docstring | 'SessionScreen.on_button_pressed' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'SessionScreen.on_button_pressed'. |
| 468 | 🟢 LOW | Incomplete Docstring | 'SessionScreen.action_cancel' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'SessionScreen.action_cancel'. |

### src/henchman/knowledge/store.py — 👍 B (86.0/100) (last modified 2026-02-17)

Public APIs: 23 | Documented: 23 | Coverage: 100.0%

| Line | Severity | Type | Message | Suggested Fix |
|-----:|:---------|:-----|:--------|:--------------|
| 144 | 🟢 LOW | Incomplete Docstring | 'KnowledgeStore.load' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'KnowledgeStore.load'. |
| 164 | 🟢 LOW | Incomplete Docstring | 'KnowledgeStore.save' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'KnowledgeStore.save'. |
| 179 | 🟢 LOW | Incomplete Docstring | 'KnowledgeStore.add_entity' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'KnowledgeStore.add_entity'. |
| 294 | 🟢 LOW | Incomplete Docstring | 'KnowledgeStore.add_relation' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'KnowledgeStore.add_relation'. |
| 442 | 🟢 LOW | Incomplete Docstring | 'KnowledgeStore.entity_count' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'KnowledgeStore.entity_count'. |
| 446 | 🟢 LOW | Incomplete Docstring | 'KnowledgeStore.relation_count' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'KnowledgeStore.relation_count'. |
| 450 | 🟢 LOW | Incomplete Docstring | 'KnowledgeStore.clear' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'KnowledgeStore.clear'. |

### src/henchman/tools/registry.py — 👍 B (86.0/100) (last modified 2026-02-13)

Public APIs: 15 | Documented: 15 | Coverage: 100.0%

| Line | Severity | Type | Message | Suggested Fix |
|-----:|:---------|:-----|:--------|:--------------|
| 63 | 🟢 LOW | Incomplete Docstring | 'ToolRegistry.set_retry_config' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ToolRegistry.set_retry_config'. |
| 71 | 🟢 LOW | Incomplete Docstring | 'ToolRegistry.set_plan_mode' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ToolRegistry.set_plan_mode'. |
| 79 | 🟢 LOW | Incomplete Docstring | 'ToolRegistry.register' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ToolRegistry.register'. |
| 93 | 🟢 LOW | Incomplete Docstring | 'ToolRegistry.unregister' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ToolRegistry.unregister'. |
| 137 | 🟢 LOW | Incomplete Docstring | 'ToolRegistry.set_confirmation_handler' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ToolRegistry.set_confirmation_handler'. |
| 146 | 🟢 LOW | Incomplete Docstring | 'ToolRegistry.add_auto_approve_policy' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ToolRegistry.add_auto_approve_policy'. |
| 157 | 🟢 LOW | Incomplete Docstring | 'ToolRegistry.remove_auto_approve_policy' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ToolRegistry.remove_auto_approve_policy'. |

## ✨ Clean Files (96 files with no smells)

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
- src/henchman/agents/metrics_reporter.py — ✅ A
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
- src/henchman/cli/textual_messages.py — ✅ A
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
