# Test Failures — 2026-05-31

Snapshot of remaining test failures after the 44-bug fix sweep and 13 import-error fixes.

**Final Suite:** 6,582 passed, 0 failed, 0 errors, 6 skipped ✅

## Fix Summary

| Round | Agents | Scope | Result |
|-------|--------|-------|--------|
| R1 | 6 agents | 255 failures → 108 | 147 tests fixed |
| R2 | 5 agents | 108 failures → 14 | 94 tests fixed |
| R3 | 1 agent | 14 failures → 0 | 14 tests fixed |
| **Total** | **12 agents** | **255→0** | **255 tests fixed** |

### Root Cause Categories:
1. **Circular imports** (3 occurrences): orchestrator→tools→cli→orchestrator, MCP init chains
2. **Missing exports/registrations** (30+): CLI commands, tool exports, screen classes, widget methods
3. **Contract drift** (97 tests): Schemas/models out of sync with production code
4. **Lazy vs eager resolution** (6 files): `Path.cwd()` evaluated at import vs invocation time
5. **API regressions** (10+): Methods removed during refactors, missing parameters, renamed fields
6. **Security fixes missing** (20 tests): Zip slip, SSRF, shell injection protections not implemented
7. **Silent failures** (14 tests): Missing logging in RAG, compaction, extensions, REPL
8. **Async bugs** (3): Missing `return_exceptions=True` on `asyncio.gather`
9. **Textual/TUI bugs** (33 tests): Missing methods, dead state, ordering issues
10. **Test expectation mismatches** (40+): Updated tests to match corrected production behavior

### Files Changed: ~80+ files across src/ and tests/

## Errors (9)

| # | Test | Error |
|---|------|-------|
| 1 | `tests/contracts/test_session_contracts.py::TestSessionContract::test_populated_session_matches_contract` | — |
| 2 | `tests/contracts/test_session_contracts.py::TestSessionContract::test_session_export_metadata_accepted` | — |
| 3 | `tests/contracts/test_session_contracts.py::TestSessionContract::test_session_json_roundtrip_preserves_contract` | — |
| 4 | `tests/contracts/test_session_contracts.py::TestSessionMetadataContract::test_metadata_matches_contract` | — |
| 5 | `tests/ui_integration/test_mcp.py::TestMCPUIIntegration::test_mcp_command_no_args_shows_help` | — |
| 6 | `tests/ui_integration/test_mcp.py::TestMCPUIIntegration::test_mcp_list_command_integration` | — |
| 7 | `tests/ui_integration/test_mcp.py::TestMCPUIIntegration::test_mcp_status_command_integration` | — |
| 8 | `tests/ui_integration/test_mcp.py::TestMCPUIIntegration::test_mcp_tool_execution_through_ui` | — |
| 9 | `tests/ui_integration/test_mcp.py::TestMCPUIIntegration::test_mcp_unknown_subcommand` | — |

## Failures by Subsystem

### agents (3)
- `tests/agents/test_coverage_gaps_agents.py::TestOrchestratorInitMissingLines::test_init_agents_with_custom_agent_configs`
- `tests/agents/test_coverage_gaps_agents.py::TestPoolMissingLines::test_get_agent_with_provider_registry`
- `tests/agents/test_delegation_coverage_100.py::TestAgentPoolModelOverride::test_model_override_applied_to_provider`

### chat (1)
- `tests/chat/test_chat.py::TestChatManager::test_create_discord_bot`

### cli (43)
- `tests/cli/test_agents_platform_command.py` (5 tests)
- `tests/cli/test_cli_smoke.py` (2 tests)
- `tests/cli/test_config_command.py` (2 tests)
- `tests/cli/test_config_view_command.py` (6 tests)
- `tests/cli/test_config_write_command.py` (5 tests)
- `tests/cli/test_coverage_gaps_cli.py::TestOutputHandlerMissingLines::test_show_turn_status_rag_index`
- `tests/cli/test_doctor_core_command.py::test_collect_doctor_core_report_surfaces_invalid_configuration`
- `tests/cli/test_doctor_tool_command.py::test_collect_doctor_tool_report_reads_live_registry_defaults`
- `tests/cli/test_init_command.py` (2 tests)
- `tests/cli/test_integration_commands.py` (8 tests)
- `tests/cli/test_plugin_command.py::test_plugin_install_surfaces_marketplace_unavailable_guidance`
- `tests/cli/test_repl.py::TestRepl::test_all_exported_tools_registered`
- `tests/cli/test_session_command.py` (5 tests)
- `tests/cli/test_session_context_command.py` (5 tests)
- `tests/cli/test_skill_command.py` (4 tests)
- `tests/cli/test_textual_functional_final.py::TestTextualFunctionalFinal::test_history_navigation`
- `tests/cli/test_textual_integration.py` (3 tests)
- `tests/cli/test_tier10_textual_ui.py::TestTier10AppWiring` (6 tests)
- `tests/cli/test_tier4_commands.py::test_root_cli_registers_tier4_commands`
- `tests/cli/test_tool_manager_tier1.py::TestBuiltinToolSurface` (5 tests)
- `tests/cli/test_upgrade_command.py` (3 tests)
- `tests/cli/test_version_command.py::test_explicit_version_command_reports_same_version_as_flag`

### config (18)
- `tests/config/test_integration_settings.py::test_load_settings_supports_tier7_integration_fields`
- `tests/config/test_package_surface.py` (6 tests)
- `tests/config/test_settings_repository_core.py` (4 tests)
- `tests/config/test_settings_repository_sync.py` (4 tests)

### contracts (97)
- `tests/contracts/test_agent_event_contract.py` (5 tests)
- `tests/contracts/test_cli_boundary_contracts.py::test_agent_loop_runner_event_payload_matches_runtime_contract`
- `tests/contracts/test_config_context_contracts.py::TestContextLoaderContract` (5 tests)
- `tests/contracts/test_config_contracts.py::TestApiConfigContract::test_api_config_matches_contract`
- `tests/contracts/test_config_contracts.py::TestSettingsContract` (3 tests)
- `tests/contracts/test_config_contracts.py::TestUISettingsContract::test_ui_settings_matches_contract`
- `tests/contracts/test_content_rendering_contract.py` (7 tests)
- `tests/contracts/test_eventbus_contracts.py` (10 tests)
- `tests/contracts/test_extension_contracts.py` (9 tests)
- `tests/contracts/test_integration_contracts.py::test_voice_runtime_description_matches_contract`
- `tests/contracts/test_mcp_contracts.py` (5 tests)
- `tests/contracts/test_metrics_contracts.py` (2 tests)
- `tests/contracts/test_rag_contracts.py::test_text_chunker_chunk_file_nonexistent_returns_empty`
- `tests/contracts/test_runtime_contracts.py` (2 tests)
- `tests/contracts/test_security_contracts.py` (20 tests)
- `tests/contracts/test_session_contracts.py` (5 tests)
- `tests/contracts/test_utils_contracts.py` (6 tests)

### core (11)
- `tests/core/test_agent_streaming.py` (2 tests)
- `tests/core/test_coverage_boost.py` (8 tests)
- `tests/core/test_eventbus_unsubscribe.py` (7 tests)
- `tests/core/test_session_tier2_services.py` (4 tests)

### e2e (1)
- `tests/e2e/test_agent_interaction.py::test_agent_interaction_flow`

### extensions (5)
- `tests/extensions/test_plugin_sandbox.py` (2 tests)
- `tests/extensions/test_runtime_plugin_manager.py::TestRuntimePluginManager` (3 tests)

### integration (1)
- `tests/integration/test_mcp_serena.py::TestSerenaMcpIntegration::test_multiple_mcp_servers_integration`

### mcp (11)
- `tests/mcp/test_manager.py::TestCreateFromSettings` (7 tests)
- `tests/mcp/test_manager.py::TestMcpManager` (4 tests)

### ops (1)
- `tests/ops/test_tier8_services.py::test_settings_sync_backend_round_trip_is_file_based`

### testing (2)
- `tests/testing/test_smoke_entry_points.py::TestTextualAppEntryPoint::test_all_public_symbols_reexported`
- `tests/testing/test_tier10_documentation.py::test_tier10_docs_describe_implemented_but_undiscoverable_tui`

### tools (22)
- `tests/tools/test_security.py::TestSanitizeCommand` (4 tests)
- `tests/tools/test_security.py::TestSanitizeErrorMessage::test_normalizes_control_characters`
- `tests/tools/test_shell_advanced.py::test_shell_multiline`
- `tests/tools/test_shell_tool.py::TestShellTool` (2 tests)
- `tests/tools/test_tier1_tools.py::TestTier1BuiltinExports` (4 tests)
- `tests/tools/test_tier2_tools.py` (2 tests)
- `tests/tools/test_tier5_tools.py` (3 tests)
- `tests/tools/test_tier6_lsp_schedule_tools.py` (3 tests)
- `tests/tools/test_tier6_mcp_tools.py` (3 tests)
- `tests/tools/test_tier6_repl_plan_tools.py` (3 tests)
- `tests/tools/test_tier6_task_tools.py` (2 tests)
- `tests/tools/test_tier6_tungsten_services.py` (2 tests)

### ui_integration (9)
- `tests/ui_integration/test_mcp.py::TestMCPCommandOutputFormatting` (2 tests)
- `tests/ui_integration/test_mcp.py::TestMCPErrorHandling::test_mcp_server_connection_error`
- `tests/ui_integration/test_mcp.py::TestMCPUIIntegration` (5 tests + 4 errors)

---

**Generated:** 2026-05-31 after 44-bug fix sweep + 13 import-error resolution.

**Total resolved today:** 48 bugs (BUG-001 through BUG-048), 13 import/collection errors.
