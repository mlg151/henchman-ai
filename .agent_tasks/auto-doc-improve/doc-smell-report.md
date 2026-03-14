# Documentation Smell Report — ✅ A (Score: 99.9/100)

_Project: /home/matthew/mlg-cli_  
_Generated: 2026-03-14T02:00:03.636603+00:00_

## Executive Summary

| Metric | Value |
|:-------|------:|
| **Overall Grade** | ✅ A |
| **Overall Score** | 99.9/100 |
| **Doc Files Scanned** | 55 |
| **Source Files Checked** | 190 |
| **Total Smells** | 8 |
| **Docstring Coverage** | 100.0% |

### Smells by Severity

| Severity | Count |
|:---------|------:|
| low | 5 |
| medium | 3 |

### Smells by Category

| Category | Count |
|:---------|------:|
| Incomplete Docstring | 8 |

## 🎯 Prioritised Fix Queue

These are the highest-impact documentation smells to address first:

1. **src/henchman/utils/intelligent_context_extractor.py:166** — 🟡 MEDIUM — Incomplete Docstring  
   'extract_tool_sections' has 1 parameter(s) but no Args: section in docstring  
   → _Add an Args: section documenting: content_

2. **src/henchman/utils/intelligent_context_extractor.py:217** — 🟡 MEDIUM — Incomplete Docstring  
   'extract_keyword_sections' has 2 parameter(s) but no Args: section in docstring  
   → _Add an Args: section documenting: content, keywords_

3. **src/henchman/utils/intelligent_context_extractor.py:267** — 🟡 MEDIUM — Incomplete Docstring  
   'extract_critical_sections' has 1 parameter(s) but no Args: section in docstring  
   → _Add an Args: section documenting: content_

4. **src/henchman/agents/working_memory.py:384** — 🟢 LOW — Incomplete Docstring  
   'WorkingMemorySystem.switch_memory' returns a value but has no Returns: or Yields: section  
   → _Add a Returns: section describing the return value of 'WorkingMemorySystem.switch_memory'._

5. **src/henchman/utils/intelligent_context_extractor.py:166** — 🟢 LOW — Incomplete Docstring  
   'extract_tool_sections' returns a value but has no Returns: or Yields: section  
   → _Add a Returns: section describing the return value of 'extract_tool_sections'._

6. **src/henchman/utils/intelligent_context_extractor.py:217** — 🟢 LOW — Incomplete Docstring  
   'extract_keyword_sections' returns a value but has no Returns: or Yields: section  
   → _Add a Returns: section describing the return value of 'extract_keyword_sections'._

7. **src/henchman/utils/intelligent_context_extractor.py:267** — 🟢 LOW — Incomplete Docstring  
   'extract_critical_sections' returns a value but has no Returns: or Yields: section  
   → _Add a Returns: section describing the return value of 'extract_critical_sections'._

8. **src/henchman/utils/intelligent_context_types.py:279** — 🟢 LOW — Incomplete Docstring  
   'ContentAnalysis.update_from_content' returns a value but has no Returns: or Yields: section  
   → _Add a Returns: section describing the return value of 'ContentAnalysis.update_from_content'._


## 📊 Files Ranked by Quality

| Rank | File | Grade | Score | Smells | Last Modified |
|-----:|:-----|:------|------:|-------:|:-------------|
| 1 | src/henchman/utils/intelligent_context_extractor.py | ⚠️ C | 79.0 | 6 | 2026-03-14 |
| 2 | src/henchman/agents/working_memory.py | ✅ A | 98.0 | 1 | 2026-03-14 |
| 3 | src/henchman/utils/intelligent_context_types.py | ✅ A | 98.0 | 1 | 2026-03-13 |
| 4 | CHANGELOG.md | ✅ A | 100.0 | 0 | 2026-03-13 |
| 5 | CONTRIBUTING.md | ✅ A | 100.0 | 0 | 2026-03-13 |
| 6 | README.md | ✅ A | 100.0 | 0 | 2026-03-13 |
| 7 | RELEASE_CHECKLIST.md | ✅ A | 100.0 | 0 | 2026-03-03 |
| 8 | docs/CHANGELOG.md | ✅ A | 100.0 | 0 | 2026-03-13 |
| 9 | docs/CONTRIBUTING.md | ✅ A | 100.0 | 0 | 2026-03-13 |
| 10 | docs/RELEASE_CHECKLIST.md | ✅ A | 100.0 | 0 | 2026-03-13 |
| 11 | docs/agents.md | ✅ A | 100.0 | 0 | 2026-03-13 |
| 12 | docs/api.md | ✅ A | 100.0 | 0 | 2026-03-13 |
| 13 | docs/architecture.md | ✅ A | 100.0 | 0 | 2026-03-13 |
| 14 | docs/configuration.md | ✅ A | 100.0 | 0 | 2026-03-13 |
| 15 | docs/evals/README.md | ✅ A | 100.0 | 0 | 2026-03-13 |

## 📁 Per-File Details

_Showing 25 worst files. 220 additional files omitted._

### src/henchman/utils/intelligent_context_extractor.py — ⚠️ C (79.0/100) (last modified 2026-03-14)

Public APIs: 6 | Documented: 6 | Coverage: 100.0%

| Line | Severity | Type | Message | Suggested Fix |
|-----:|:---------|:-----|:--------|:--------------|
| 166 | 🟡 MEDIUM | Incomplete Docstring | 'extract_tool_sections' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: content |
| 217 | 🟡 MEDIUM | Incomplete Docstring | 'extract_keyword_sections' has 2 parameter(s) but no Args: section in docstring | Add an Args: section documenting: content, keywords |
| 267 | 🟡 MEDIUM | Incomplete Docstring | 'extract_critical_sections' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: content |
| 166 | 🟢 LOW | Incomplete Docstring | 'extract_tool_sections' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'extract_tool_sections'. |
| 217 | 🟢 LOW | Incomplete Docstring | 'extract_keyword_sections' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'extract_keyword_sections'. |
| 267 | 🟢 LOW | Incomplete Docstring | 'extract_critical_sections' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'extract_critical_sections'. |

### src/henchman/agents/working_memory.py — ✅ A (98.0/100) (last modified 2026-03-14)

Public APIs: 26 | Documented: 26 | Coverage: 100.0%

| Line | Severity | Type | Message | Suggested Fix |
|-----:|:---------|:-----|:--------|:--------------|
| 384 | 🟢 LOW | Incomplete Docstring | 'WorkingMemorySystem.switch_memory' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'WorkingMemorySystem.switch_memory'. |

### src/henchman/utils/intelligent_context_types.py — ✅ A (98.0/100) (last modified 2026-03-13)

Public APIs: 20 | Documented: 20 | Coverage: 100.0%

| Line | Severity | Type | Message | Suggested Fix |
|-----:|:---------|:-----|:--------|:--------------|
| 279 | 🟢 LOW | Incomplete Docstring | 'ContentAnalysis.update_from_content' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ContentAnalysis.update_from_content'. |

## ✨ Clean Files (242 files with no smells)

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
- smell-report-after-1.md — ✅ A
- smell-report-after-2.md — ✅ A
- smell-report-after-3.md — ✅ A
- smell-report-after-4.md — ✅ A
- smell-report-after-5.md — ✅ A
- smell-report-after-6.md — ✅ A
- smell-report-after-ruff.md — ✅ A
- smell-report-agents.md — ✅ A
- smell-report-final-A-2.md — ✅ A
- smell-report-final-A-3.md — ✅ A
- smell-report-final-A-4.md — ✅ A
- smell-report-final-A-5.md — ✅ A
- smell-report-final-A.md — ✅ A
- smell-report-final.md — ✅ A
- smell-report-final2.md — ✅ A
- smell-report-final3.md — ✅ A
- smell-report-final4.md — ✅ A
- smell-report-final5.md — ✅ A
- smell-report-final6.md — ✅ A
- smell-report-final7.md — ✅ A
- smell-report-final8.md — ✅ A
- smell-report-final9.md — ✅ A
- smell-report-new.md — ✅ A
- smell-report.md — ✅ A
- smell-report10.md — ✅ A
- smell-report2.md — ✅ A
- smell-report3.md — ✅ A
- smell-report4.md — ✅ A
- smell-report5.md — ✅ A
- smell-report6.md — ✅ A
- smell-report7.md — ✅ A
- smell-report8.md — ✅ A
- smell-report9.md — ✅ A
- tests/README.md — ✅ A
- tests/ui_integration/INTERACTIVE_SESSION_TESTS.md — ✅ A
- src/henchman/agents/delegation.py — ✅ A
- src/henchman/agents/identity.py — ✅ A
- src/henchman/agents/ledger.py — ✅ A
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
- src/henchman/api/auth.py — ✅ A
- src/henchman/api/endpoints/chat.py — ✅ A
- src/henchman/api/endpoints/health.py — ✅ A
- src/henchman/api/server.py — ✅ A
- src/henchman/api/state.py — ✅ A
- src/henchman/cli/app.py — ✅ A
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
- src/henchman/cli/textual_widgets.py — ✅ A
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
- src/henchman/utils/intelligent_context_formatter.py — ✅ A
- src/henchman/utils/intelligent_context_parser.py — ✅ A
- src/henchman/utils/intelligent_context_summarizer.py — ✅ A
- src/henchman/utils/intelligent_context_topic_extractor.py — ✅ A
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
