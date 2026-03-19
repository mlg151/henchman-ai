# Documentation Smell Report — ✅ A (Score: 99.9/100)

_Project: /home/matthew/mlg-cli_  
_Generated: 2026-03-19T00:00:03.226588+00:00_

## Executive Summary

| Metric | Value |
|:-------|------:|
| **Overall Grade** | ✅ A |
| **Overall Score** | 99.9/100 |
| **Doc Files Scanned** | 22 |
| **Source Files Checked** | 196 |
| **Total Smells** | 7 |
| **Docstring Coverage** | 100.0% |

### Smells by Severity

| Severity | Count |
|:---------|------:|
| low | 4 |
| medium | 3 |

### Smells by Category

| Category | Count |
|:---------|------:|
| Incomplete Docstring | 7 |

## 🎯 Prioritised Fix Queue

These are the highest-impact documentation smells to address first:

1. **src/henchman/cli/textual_widgets.py:1026** — 🟡 MEDIUM — Incomplete Docstring  
   'ChatPane.add_user_message' has 1 parameter(s) but no Args: section in docstring  
   → _Add an Args: section documenting: text_

2. **src/henchman/cli/textual_widgets.py:1030** — 🟡 MEDIUM — Incomplete Docstring  
   'ChatPane.add_system_message' has 1 parameter(s) but no Args: section in docstring  
   → _Add an Args: section documenting: text_

3. **src/henchman/cli/textual_widgets.py:1034** — 🟡 MEDIUM — Incomplete Docstring  
   'ChatPane.add_error_message' has 1 parameter(s) but no Args: section in docstring  
   → _Add an Args: section documenting: text_

4. **src/henchman/cli/app.py:671** — 🟢 LOW — Incomplete Docstring  
   'xyztest_command' returns a value but has no Returns: or Yields: section  
   → _Add a Returns: section describing the return value of 'xyztest_command'._

5. **src/henchman/cli/textual_widgets.py:1026** — 🟢 LOW — Incomplete Docstring  
   'ChatPane.add_user_message' returns a value but has no Returns: or Yields: section  
   → _Add a Returns: section describing the return value of 'ChatPane.add_user_message'._

6. **src/henchman/cli/textual_widgets.py:1030** — 🟢 LOW — Incomplete Docstring  
   'ChatPane.add_system_message' returns a value but has no Returns: or Yields: section  
   → _Add a Returns: section describing the return value of 'ChatPane.add_system_message'._

7. **src/henchman/cli/textual_widgets.py:1034** — 🟢 LOW — Incomplete Docstring  
   'ChatPane.add_error_message' returns a value but has no Returns: or Yields: section  
   → _Add a Returns: section describing the return value of 'ChatPane.add_error_message'._


## 📊 Files Ranked by Quality

| Rank | File | Grade | Score | Smells | Last Modified |
|-----:|:-----|:------|------:|-------:|:-------------|
| 1 | src/henchman/cli/textual_widgets.py | ⚠️ C | 79.0 | 6 | 2026-03-18 |
| 2 | src/henchman/cli/app.py | ✅ A | 98.0 | 1 | 2026-03-18 |
| 3 | CHANGELOG.md | ✅ A | 100.0 | 0 | 2026-03-18 |
| 4 | CONTRIBUTING.md | ✅ A | 100.0 | 0 | 2026-03-13 |
| 5 | README.md | ✅ A | 100.0 | 0 | 2026-03-16 |
| 6 | RELEASE_CHECKLIST.md | ✅ A | 100.0 | 0 | 2026-03-03 |
| 7 | docs/CHANGELOG.md | ✅ A | 100.0 | 0 | 2026-03-13 |
| 8 | docs/CONTRIBUTING.md | ✅ A | 100.0 | 0 | 2026-03-13 |
| 9 | docs/RELEASE_CHECKLIST.md | ✅ A | 100.0 | 0 | 2026-03-13 |
| 10 | docs/agents.md | ✅ A | 100.0 | 0 | 2026-03-16 |
| 11 | docs/api.md | ✅ A | 100.0 | 0 | 2026-03-18 |
| 12 | docs/architecture.md | ✅ A | 100.0 | 0 | 2026-03-18 |
| 13 | docs/configuration.md | ✅ A | 100.0 | 0 | 2026-03-15 |
| 14 | docs/evals/README.md | ✅ A | 100.0 | 0 | 2026-03-13 |
| 15 | docs/extensions.md | ✅ A | 100.0 | 0 | 2026-03-17 |

## 📁 Per-File Details

_Showing 25 worst files. 193 additional files omitted._

### src/henchman/cli/textual_widgets.py — ⚠️ C (79.0/100) (last modified 2026-03-18)

Public APIs: 44 | Documented: 44 | Coverage: 100.0%

| Line | Severity | Type | Message | Suggested Fix |
|-----:|:---------|:-----|:--------|:--------------|
| 1026 | 🟡 MEDIUM | Incomplete Docstring | 'ChatPane.add_user_message' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: text |
| 1030 | 🟡 MEDIUM | Incomplete Docstring | 'ChatPane.add_system_message' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: text |
| 1034 | 🟡 MEDIUM | Incomplete Docstring | 'ChatPane.add_error_message' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: text |
| 1026 | 🟢 LOW | Incomplete Docstring | 'ChatPane.add_user_message' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ChatPane.add_user_message'. |
| 1030 | 🟢 LOW | Incomplete Docstring | 'ChatPane.add_system_message' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ChatPane.add_system_message'. |
| 1034 | 🟢 LOW | Incomplete Docstring | 'ChatPane.add_error_message' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ChatPane.add_error_message'. |

### src/henchman/cli/app.py — ✅ A (98.0/100) (last modified 2026-03-18)

Public APIs: 6 | Documented: 6 | Coverage: 100.0%

| Line | Severity | Type | Message | Suggested Fix |
|-----:|:---------|:-----|:--------|:--------------|
| 671 | 🟢 LOW | Incomplete Docstring | 'xyztest_command' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'xyztest_command'. |

## ✨ Clean Files (216 files with no smells)

<details><summary>Click to expand</summary>

- CHANGELOG.md — ✅ A
- CONTRIBUTING.md — ✅ A
- README.md — ✅ A
- RELEASE_CHECKLIST.md — ✅ A
- docs/CHANGELOG.md — ✅ A
- docs/CONTRIBUTING.md — ✅ A
- docs/RELEASE_CHECKLIST.md — ✅ A
- docs/agents.md — ✅ A
- docs/api.md — ✅ A
- docs/architecture.md — ✅ A
- docs/configuration.md — ✅ A
- docs/evals/README.md — ✅ A
- docs/extensions.md — ✅ A
- docs/getting-started.md — ✅ A
- docs/index.md — ✅ A
- docs/intelligent-context-management.md — ✅ A
- docs/mcp.md — ✅ A
- docs/providers.md — ✅ A
- docs/tools.md — ✅ A
- evals/README.md — ✅ A
- tests/README.md — ✅ A
- tests/ui_integration/INTERACTIVE_SESSION_TESTS.md — ✅ A
- src/henchman/agents/delegation.py — ✅ A
- src/henchman/agents/file_read_decision_maker.py — ✅ A
- src/henchman/agents/identity.py — ✅ A
- src/henchman/agents/ledger.py — ✅ A
- src/henchman/agents/line_range_utils.py — ✅ A
- src/henchman/agents/metrics.py — ✅ A
- src/henchman/agents/metrics_reporter.py — ✅ A
- src/henchman/agents/orchestrator.py — ✅ A
- src/henchman/agents/orchestrator_anchoring.py — ✅ A
- src/henchman/agents/orchestrator_components.py — ✅ A
- src/henchman/agents/orchestrator_delegation_ctrl.py — ✅ A
- src/henchman/agents/orchestrator_events.py — ✅ A
- src/henchman/agents/orchestrator_execution.py — ✅ A
- src/henchman/agents/orchestrator_init.py — ✅ A
- src/henchman/agents/orchestrator_loop.py — ✅ A
- src/henchman/agents/orchestrator_metrics_ctrl.py — ✅ A
- src/henchman/agents/orchestrator_prompts.py — ✅ A
- src/henchman/agents/orchestrator_run.py — ✅ A
- src/henchman/agents/orchestrator_tech_lead.py — ✅ A
- src/henchman/agents/orchestrator_timeout.py — ✅ A
- src/henchman/agents/orchestrator_tools.py — ✅ A
- src/henchman/agents/orchestrator_turns.py — ✅ A
- src/henchman/agents/orchestrator_types.py — ✅ A
- src/henchman/agents/orchestrator_validation.py — ✅ A
- src/henchman/agents/pool.py — ✅ A
- src/henchman/agents/presets.py — ✅ A
- src/henchman/agents/prompts.py — ✅ A
- src/henchman/agents/working_memory.py — ✅ A
- src/henchman/api/auth.py — ✅ A
- src/henchman/api/endpoints/chat.py — ✅ A
- src/henchman/api/endpoints/health.py — ✅ A
- src/henchman/api/server.py — ✅ A
- src/henchman/api/state.py — ✅ A
- src/henchman/chat/base.py — ✅ A
- src/henchman/chat/discord_bot.py — ✅ A
- src/henchman/chat/manager.py — ✅ A
- src/henchman/cli/chat_serve.py — ✅ A
- src/henchman/cli/command_processor.py — ✅ A
- src/henchman/cli/commands/__init__.py — ✅ A
- src/henchman/cli/commands/agent.py — ✅ A
- src/henchman/cli/commands/builtins.py — ✅ A
- src/henchman/cli/commands/chat.py — ✅ A
- src/henchman/cli/commands/context.py — ✅ A
- src/henchman/cli/commands/extensions.py — ✅ A
- src/henchman/cli/commands/mcp.py — ✅ A
- src/henchman/cli/commands/model.py — ✅ A
- src/henchman/cli/commands/plan.py — ✅ A
- src/henchman/cli/commands/rag.py — ✅ A
- src/henchman/cli/commands/session.py — ✅ A
- src/henchman/cli/commands/team.py — ✅ A
- src/henchman/cli/commands/theme.py — ✅ A
- src/henchman/cli/commands/unlimited.py — ✅ A
- src/henchman/cli/console.py — ✅ A
- src/henchman/cli/console_helpers.py — ✅ A
- src/henchman/cli/core_init.py — ✅ A
- src/henchman/cli/input.py — ✅ A
- src/henchman/cli/input_handler.py — ✅ A
- src/henchman/cli/json_output.py — ✅ A
- src/henchman/cli/output_handler.py — ✅ A
- src/henchman/cli/plugins.py — ✅ A
- src/henchman/cli/repl.py — ✅ A
- src/henchman/cli/serve.py — ✅ A
- src/henchman/cli/session_manager.py — ✅ A
- src/henchman/cli/stream_event_handlers.py — ✅ A
- src/henchman/cli/textual_app.py — ✅ A
- src/henchman/cli/textual_bridge.py — ✅ A
- src/henchman/cli/textual_config.py — ✅ A
- src/henchman/cli/textual_messages.py — ✅ A
- src/henchman/cli/textual_screens.py — ✅ A
- src/henchman/cli/tool_executor.py — ✅ A
- src/henchman/cli/tool_manager.py — ✅ A
- src/henchman/cli/ui_renderer.py — ✅ A
- src/henchman/config/context.py — ✅ A
- src/henchman/config/environment.py — ✅ A
- src/henchman/config/schema.py — ✅ A
- src/henchman/config/settings.py — ✅ A
- src/henchman/core/agent.py — ✅ A
- src/henchman/core/agent_config.py — ✅ A
- src/henchman/core/agent_stall.py — ✅ A
- src/henchman/core/agent_streaming.py — ✅ A
- src/henchman/core/eventbus.py — ✅ A
- src/henchman/core/events.py — ✅ A
- src/henchman/core/session_branch.py — ✅ A
- src/henchman/core/session_data.py — ✅ A
- src/henchman/core/session_export.py — ✅ A
- src/henchman/core/session_helpers.py — ✅ A
- src/henchman/core/session_manager.py — ✅ A
- src/henchman/core/session_merge.py — ✅ A
- src/henchman/core/session_models.py — ✅ A
- src/henchman/core/session_templates.py — ✅ A
- src/henchman/core/turn.py — ✅ A
- src/henchman/extensions/base.py — ✅ A
- src/henchman/extensions/constants.py — ✅ A
- src/henchman/extensions/manager.py — ✅ A
- src/henchman/extensions/models.py — ✅ A
- src/henchman/extensions/plugin_compatibility.py — ✅ A
- src/henchman/extensions/plugin_database.py — ✅ A
- src/henchman/extensions/plugin_installer.py — ✅ A
- src/henchman/extensions/plugin_manager.py — ✅ A
- src/henchman/extensions/plugin_registry_client.py — ✅ A
- src/henchman/extensions/plugin_security_scanner.py — ✅ A
- src/henchman/knowledge/models.py — ✅ A
- src/henchman/knowledge/scanner.py — ✅ A
- src/henchman/knowledge/store.py — ✅ A
- src/henchman/mcp/client.py — ✅ A
- src/henchman/mcp/config.py — ✅ A
- src/henchman/mcp/manager.py — ✅ A
- src/henchman/mcp/tool.py — ✅ A
- src/henchman/metrics/collector.py — ✅ A
- src/henchman/metrics/dashboard.py — ✅ A
- src/henchman/metrics/exporter.py — ✅ A
- src/henchman/metrics/models.py — ✅ A
- src/henchman/metrics/storage.py — ✅ A
- src/henchman/providers/anthropic.py — ✅ A
- src/henchman/providers/base.py — ✅ A
- src/henchman/providers/deepseek.py — ✅ A
- src/henchman/providers/ollama.py — ✅ A
- src/henchman/providers/openai_compat.py — ✅ A
- src/henchman/providers/openrouter.py — ✅ A
- src/henchman/providers/registry.py — ✅ A
- src/henchman/providers/utils.py — ✅ A
- src/henchman/rag/chunker.py — ✅ A
- src/henchman/rag/concurrency.py — ✅ A
- src/henchman/rag/embedder.py — ✅ A
- src/henchman/rag/indexer.py — ✅ A
- src/henchman/rag/repo_id.py — ✅ A
- src/henchman/rag/store.py — ✅ A
- src/henchman/rag/system.py — ✅ A
- src/henchman/tools/base.py — ✅ A
- src/henchman/tools/builtins/ask_user.py — ✅ A
- src/henchman/tools/builtins/code_format.py — ✅ A
- src/henchman/tools/builtins/coverage_map.py — ✅ A
- src/henchman/tools/builtins/dead_code.py — ✅ A
- src/henchman/tools/builtins/deep_research.py — ✅ A
- src/henchman/tools/builtins/delegate.py — ✅ A
- src/henchman/tools/builtins/diff_view.py — ✅ A
- src/henchman/tools/builtins/env_inspect.py — ✅ A
- src/henchman/tools/builtins/file_edit.py — ✅ A
- src/henchman/tools/builtins/file_overview.py — ✅ A
- src/henchman/tools/builtins/file_read.py — ✅ A
- src/henchman/tools/builtins/file_write.py — ✅ A
- src/henchman/tools/builtins/git_ops.py — ✅ A
- src/henchman/tools/builtins/glob_tool.py — ✅ A
- src/henchman/tools/builtins/grep.py — ✅ A
- src/henchman/tools/builtins/import_graph.py — ✅ A
- src/henchman/tools/builtins/kg_common.py — ✅ A
- src/henchman/tools/builtins/kg_query.py — ✅ A
- src/henchman/tools/builtins/kg_update.py — ✅ A
- src/henchman/tools/builtins/lint_check.py — ✅ A
- src/henchman/tools/builtins/ls.py — ✅ A
- src/henchman/tools/builtins/patch_apply.py — ✅ A
- src/henchman/tools/builtins/pattern_search.py — ✅ A
- src/henchman/tools/builtins/pip_inspect.py — ✅ A
- src/henchman/tools/builtins/pytest_run.py — ✅ A
- src/henchman/tools/builtins/python_ast.py — ✅ A
- src/henchman/tools/builtins/python_ast_helpers.py — ✅ A
- src/henchman/tools/builtins/python_exec.py — ✅ A
- src/henchman/tools/builtins/rag_search.py — ✅ A
- src/henchman/tools/builtins/research_notes.py — ✅ A
- src/henchman/tools/builtins/shell.py — ✅ A
- src/henchman/tools/builtins/symbol_trace.py — ✅ A
- src/henchman/tools/builtins/test_gen.py — ✅ A
- src/henchman/tools/builtins/traceback_parse.py — ✅ A
- src/henchman/tools/builtins/web_fetch.py — ✅ A
- src/henchman/tools/builtins/web_search.py — ✅ A
- src/henchman/tools/registry.py — ✅ A
- src/henchman/tools/security/shell_secure.py — ✅ A
- src/henchman/tools/security.py — ✅ A
- src/henchman/tools/utils.py — ✅ A
- src/henchman/utils/cluster_utils.py — ✅ A
- src/henchman/utils/compaction.py — ✅ A
- src/henchman/utils/compression_strategy.py — ✅ A
- src/henchman/utils/importance_scorer.py — ✅ A
- src/henchman/utils/intelligent_context.py — ✅ A
- src/henchman/utils/intelligent_context_aggregator.py — ✅ A
- src/henchman/utils/intelligent_context_config.py — ✅ A
- src/henchman/utils/intelligent_context_detector.py — ✅ A
- src/henchman/utils/intelligent_context_extractor.py — ✅ A
- src/henchman/utils/intelligent_context_formatter.py — ✅ A
- src/henchman/utils/intelligent_context_parser.py — ✅ A
- src/henchman/utils/intelligent_context_summarizer.py — ✅ A
- src/henchman/utils/intelligent_context_topic_extractor.py — ✅ A
- src/henchman/utils/intelligent_context_types.py — ✅ A
- src/henchman/utils/lazy_import.py — ✅ A
- src/henchman/utils/message_analyzer.py — ✅ A
- src/henchman/utils/message_clusterer.py — ✅ A
- src/henchman/utils/message_compactor.py — ✅ A
- src/henchman/utils/ratelimit.py — ✅ A
- src/henchman/utils/registry.py — ✅ A
- src/henchman/utils/retry.py — ✅ A
- src/henchman/utils/serialization.py — ✅ A
- src/henchman/utils/sorting_utils.py — ✅ A
- src/henchman/utils/tokens.py — ✅ A
- src/henchman/utils/validation.py — ✅ A

</details>

---

_Report generated by XP Documentation Smell Detector. Smells are static heuristics — use judgement when prioritising fixes._
