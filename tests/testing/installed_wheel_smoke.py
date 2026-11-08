"""Install and verify a wheel on Linux, macOS, or Windows, outside the checkout.

Run with ``python tests/testing/installed_wheel_smoke.py --wheel-dir dist`` in a
fresh CI Python environment. This intentionally installs into the active Python.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import sysconfig
import tempfile
import zipfile
from pathlib import Path

_ORIGIN_CHECK = '''from importlib.metadata import distribution
from pathlib import Path
import henchman

expected = distribution("henchman-ai").locate_file("henchman/__init__.py").resolve()
actual = Path(henchman.__file__).resolve()
assert actual == expected, f"Expected installed wheel at {expected}; imported {actual}"
print(f"Verified installed package: {actual}")
'''

_RAG_CHECK = '''import chromadb
import henchman.rag

client = chromadb.EphemeralClient()
collection = client.create_collection("portable_smoke")
collection.add(ids=["1"], embeddings=[[1.0, 0.0]], documents=["operational"])
result = collection.query(query_embeddings=[[1.0, 0.0]], n_results=1)
assert collection.count() == 1
assert result["ids"] == [["1"]]
print("Verified RAG import and local vector operations without model downloads")
'''


def find_wheel(directory: Path) -> Path:
    """Select one built wheel instead of relying on shell glob expansion."""
    wheels = sorted(directory.glob("*.whl"))
    if len(wheels) != 1:
        raise ValueError(f"Expected exactly one wheel in {directory}, found {len(wheels)}")
    return wheels[0]


def verify_wheel_contents(wheel: Path, installation: Path) -> None:
    """Reject stale same-version installs before exercising their workflows."""
    with zipfile.ZipFile(wheel) as archive:
        names = [name for name in archive.namelist() if name.startswith("henchman/") and not name.endswith("/")]
        if not names:
            raise ValueError("Wheel contains no Henchman package files")
        for name in names:
            if ".." in Path(name).parts:
                raise ValueError("Wheel contains an invalid package path")
            try:
                matches = (installation / name).read_bytes() == archive.read(name)
            except OSError:
                matches = False
            if not matches:
                raise RuntimeError(
                    f"Installed package does not match artifact ({name}); use a fresh environment or force reinstall"
                )
    print(f"Verified exact wheel bytes for {len(names)} package files", flush=True)


def smoke_environment(environment: dict[str, str]) -> dict[str, str]:
    """Prevent source-tree injection and make CLI output deterministic."""
    result = dict(environment)
    result.pop("PYTHONPATH", None)
    result.pop("PYTHONHOME", None)
    # Child tools invoking `python` must use this installed artifact environment,
    # even when the wrapper was launched through another checkout's uv process.
    result["PATH"] = os.pathsep.join(filter(None, (sysconfig.get_path("scripts"), result.get("PATH"))))
    result.update(PYTEST_DISABLE_PLUGIN_AUTOLOAD="1", NO_COLOR="1")
    return result


def isolated_runtime_environment(environment: dict[str, str], directory: Path) -> dict[str, str]:
    """Exercise a fresh offline install independently of user config and caches."""
    result = dict(environment)
    for key in (
        "HENCHMAN_SETTINGS_PATH", "HENCHMAN_PROVIDER", "HENCHMAN_MODEL",
        "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "DEEPSEEK_API_KEY", "OPENROUTER_API_KEY",
        "TOGETHER_API_KEY", "GROQ_API_KEY", "FIREWORKS_API_KEY", "HENCHMAN_API_KEY",
    ):
        result.pop(key, None)
    for key, relative in (
        ("HOME", "home"), ("USERPROFILE", "home"),
        ("XDG_CONFIG_HOME", "home/.config"), ("XDG_DATA_HOME", "home/.local/share"),
        ("XDG_CACHE_HOME", "home/.cache"), ("TIKTOKEN_CACHE_DIR", "token-cache"),
        ("DATA_GYM_CACHE_DIR", "token-cache"),
    ):
        path = directory / relative
        path.mkdir(parents=True, exist_ok=True)
        result[key] = str(path)
    return result


def retain_build_cache(environment: dict[str, str]) -> dict[str, str]:
    """Keep only uv's existing build cache across the cold HOME boundary."""
    result = dict(environment)
    cache = subprocess.run(["uv", "--no-config", "cache", "dir"], env=result,
                           capture_output=True, text=True, check=True, timeout=5)
    result["UV_CACHE_DIR"] = str(Path(cache.stdout.strip()).resolve())
    return result


def stage_workflow_tests(repository: Path, target: Path, *, include_package: bool = False) -> None:
    """Copy offline coding and terminal workflows, never production source code."""
    for relative in (
        "tests/offline_network.py",
        "tests/testing/test_offline_network.py",
        "tests/e2e/test_coding_loop.py",
        "tests/e2e/provider_transport.py",
        "tests/e2e/test_leader_requests.py",
        "tests/e2e/test_team_verification_routing.py",
        "tests/e2e/test_team_mission_context.py",
        "tests/agents/test_leader_configuration.py",
        "tests/agents/test_prompts.py",
        "tests/agents/test_thinking_protocol.py",
        "tests/agents/test_active_agent_delegation.py",
        "tests/agents/test_orchestrator_interruption.py",
        "tests/agents/test_orchestrator.py",
        "tests/cli/test_leader_provider_switch.py",
        "tests/cli/test_active_provider_display.py",
        "tests/cli/test_repl.py",
        "tests/cli/test_repl_output_context.py",
        "tests/cli/test_repl_background_goals.py",
        "tests/cli/test_textual_background_goals.py",
        "tests/cli/test_background_discovery.py",
        "tests/cli/commands/test_goal.py",
        "tests/core/test_goals.py",
        "tests/tools/test_background_execution.py",
        "tests/tools/test_task_evidence.py",
        "tests/tools/test_task_evidence_identity.py",
        "tests/advanced/test_task_restart.py",
        "tests/advanced/test_task_store.py",
        "tests/advanced/test_task_authority.py",
        "tests/contracts/test_task_authority_contract.py",
        "tests/advanced/test_checkpoints.py",
        "tests/advanced/test_child_proposal_helpers.py",
        "tests/advanced/test_checkpoint_verification.py",
        "tests/advanced/test_checkpoint_windows.py",
        "tests/cli/test_checkpoint_command.py",
        "tests/tools/test_tier6_task_tools.py",
        "tests/config/test_agent_overrides.py",
        "tests/e2e/test_context_tool_discovery.py",
        "tests/core/test_tool_disclosure.py",
        "tests/tools/test_schema_discovery.py",
        "tests/tools/test_schema_contracts.py",
        "tests/tools/test_registry_contracts.py",
        "tests/tools/test_schema_contract_cache.py",
        "tests/agents/test_scoped_tool_discovery.py",
        "tests/tools/test_live_tool_scopes.py",
        "tests/agents/test_leader_tool_scope.py",
        "tests/cli/test_actor_tool_scope.py",
        "tests/contracts/test_tool_executor_contracts.py",
        "tests/cli/test_tool_executor_asyncio_gather.py",
        "tests/cli/test_headless_loop.py",
        "tests/cli/test_headless_protocol.py",
        "tests/cli/test_headless_control.py",
        "tests/cli/test_headless_runtime.py",
        "tests/cli/test_headless_stdio.py",
        "tests/integrations/test_blueprints.py",
        "tests/integrations/test_neovim_scope.py",
        "tests/integrations/test_neovim_pilot.py",
        "tests/cli/test_console_entrypoint.py",
        "tests/rag/test_current_evidence.py",
        "tests/tools/test_repository_pattern_search.py",
        "tests/core/test_event_evidence_identity.py",
        "tests/tools/test_execution_guard_inheritance.py",
        "tests/cli/test_input_output_portability.py",
        "tests/cli/test_output_stream_coverage.py",
        "tests/cli/test_output_mode_rendering.py",
        "tests/cli/test_repl_output_modes.py",
        "tests/cli/test_repl_keyboard_mode.py",
        "tests/cli/test_draft_editor.py",
        "tests/cli/test_repl_draft_editor.py",
        "tests/cli/test_textual_draft_editor.py",
        "tests/e2e/test_headless_team.py",
        "tests/cli/test_headless_orchestration.py",
        "tests/cli/test_headless_team_streaming.py",
        "tests/cli/test_switch_context_limit.py",
        "tests/cli/test_chat_session_reasoning.py",
        "tests/cli/test_workflow_discovery.py",
        "tests/cli/test_ui_controls_discovery.py",
        "tests/team/test_collaboration_services.py",
        "tests/team/test_workflow_execution_truth.py",
        "tests/cli/test_provider_switch.py",
        "tests/cli/commands/test_model.py",
        "tests/cli/commands/test_model_context.py",
        "tests/cli/commands/test_model_large_context.py",
        "tests/core/test_request_budget.py",
        "tests/core/test_run_budget.py",
        "tests/core/test_usage_summary.py",
        "tests/core/test_run_budget_state.py",
        "tests/core/test_session_accounting_reference.py",
        "tests/core/test_session_run_accounting.py",
        "tests/core/test_operation_recovery.py",
        "tests/core/test_session_operations.py",
        "tests/core/test_session_operation_compaction.py",
        "tests/core/test_workflow_state.py",
        "tests/core/test_session_workflow.py",
        "tests/core/test_goal_workflow_runtime.py",
        "tests/core/test_workflow_run_correlation.py",
        "tests/cli/test_workflow_binding.py",
        "tests/cli/test_workflow_commands.py",
        "tests/cli/test_workflow_execution.py",
        "tests/cli/test_frontend_workflow.py",
        "tests/cli/test_frontend_command_routing.py",
        "tests/ops/test_workflow_store.py",
        "tests/contracts/test_workflow_contract.py",
        "tests/core/test_continuation_lifecycle.py",
        "tests/providers/test_continuation_envelope.py",
        "tests/providers/test_continuation_transport.py",
        "tests/agents/test_continuation_control.py",
        "tests/contracts/test_continuation_contract.py",
        "tests/tools/test_checkpoint_capture.py",
        "tests/advanced/test_checkpoint_correlation.py",
        "tests/advanced/test_verification_freshness.py",
        "tests/advanced/test_verification_repair.py",
        "tests/agents/test_verification_repair_runtime.py",
        "tests/agents/test_repair_tool_disclosure.py",
        "tests/core/test_controller_operations.py",
        "tests/e2e/test_bounded_repair.py",
        "tests/tools/test_formatting_controls.py",
        "tests/metrics/test_evidence_redaction.py",
        "tests/advanced/test_verification_evidence.py",
        "tests/advanced/test_project_verification.py",
        "tests/config/test_verification_settings.py",
        "tests/core/test_typed_tool_results.py",
        "tests/agents/test_operation_runtime.py",
        "tests/agents/test_primary_subagent_runtime.py",
        "tests/agents/test_operation_control.py",
        "tests/cli/test_recovery_command.py",
        "tests/config/test_operation_settings.py",
        "tests/ops/test_operation_store.py",
        "tests/ops/test_run_budget_store.py",
        "tests/ops/test_run_budget_inspection.py",
        "tests/api/helpers.py",
        "tests/api/test_run_accounting.py",
        "tests/api/test_api.py",
        "tests/api/test_bug036_auth.py",
        "tests/api/test_bug038_sse_header.py",
        "tests/mcp/test_stdio_profiles.py",
        "tests/mcp/test_protocol_compat.py",
        "tests/mcp/http_fixture.py",
        "tests/mcp/oauth_fixture.py",
        "tests/mcp/test_oauth_foundation.py",
        "tests/mcp/test_oauth_discovery.py",
        "tests/mcp/test_oauth_store.py",
        "tests/mcp/test_oauth_evidence.py",
        "tests/mcp/test_oauth_callback.py",
        "tests/mcp/test_oauth_flow.py",
        "tests/cli/test_oauth_browser.py",
        "tests/cli/test_oauth_controller.py",
        "tests/cli/test_oauth_frontends.py",
        "tests/cli/test_textual_density_settings.py",
        "tests/cli/test_textual_output_modes.py",
        "tests/cli/test_textual_context.py",
        "tests/cli/test_session_activation.py",
        "tests/cli/test_textual_decision_review.py",
        "tests/cli/test_textual_session_resume.py",
        "tests/cli/test_textual_work.py",
        "tests/cli/test_work_command.py",
        "tests/cli/test_work_interrupt.py",
        "tests/cli/test_textual_workspace_owners.py",
        "tests/cli/test_oauth_command_privacy.py",
        "tests/mcp/test_oauth_connect.py",
        "tests/mcp/test_oauth_manager.py",
        "tests/mcp/test_oauth_transport.py",
        "tests/mcp/test_oauth_dispatch.py",
        "tests/mcp/context_fixture.py",
        "tests/mcp/test_context_catalog.py",
        "tests/mcp/test_context_attachment_handles.py",
        "tests/cli/test_mcp_context_attachment.py",
        "tests/core/test_context_attachments.py",
        "tests/utils/test_context_attachment_compaction.py",
        "tests/contracts/test_context_attachment_contract.py",
        "tests/cli/test_mcp_context_commands.py",
        "tests/mcp/test_http_transport.py",
        "tests/config/test_mcp_transport_settings.py",
        "tests/contracts/test_mcp_transport_contracts.py",
        "tests/mcp/test_auth_storage.py",
        "tests/mcp/test_credential_lifecycle.py",
        "tests/mcp/test_evidence_binding.py",
        "tests/mcp/test_client.py",
        "tests/mcp/test_catalog_fidelity.py",
        "tests/mcp/test_filtered_stream.py",
        "tests/mcp/test_tool.py",
        "tests/mcp/test_manager.py",
        "tests/mcp/test_config.py",
        "tests/agents/test_request_capacity.py",
        "tests/providers/test_request_budget.py",
        "tests/providers/test_required_tool_schemas.py",
        "tests/providers/test_schema_projections.py",
        "tests/providers/test_usage_reporting.py",
        "tests/providers/test_runtime_budget.py",
        "tests/utils/test_compaction_budget.py",
        "tests/config/test_usage_settings.py",
        "tests/config/test_runtime_settings.py",
        "tests/cli/test_live_settings.py",
        "tests/cli/test_runtime_config_commands.py",
        "tests/cli/test_usage_command.py",
        "tests/cli/test_headless_budget_ownership.py",
        "tests/cli/test_subagent_lifecycle.py",
        "tests/cli/test_settings_write_boundaries.py",
        "tests/ops/test_cost_provenance.py",
        "tests/agents/test_orchestrator_streaming.py",
        "tests/agents/test_pool_context_settings.py",
        "tests/agents/test_subagent_context_settings.py",
        "tests/agents/test_pool_accounting_identity.py",
        "tests/agents/test_orchestrator_round_budget.py",
        "tests/agents/test_delegation_budget_disclosure.py",
        "tests/agents/test_delegation_mission_context.py",
        "tests/agents/test_delegation_error_isolation.py",
        "tests/agents/test_team_tool_discovery.py",
        "tests/agents/test_run_completion_scope.py",
        "tests/agents/test_budget_exhaustion.py",
        "tests/agents/test_agent_budget_scope.py",
        "tests/agents/test_automatic_run_accounting.py",
        "tests/agents/test_direct_run_accounting.py",
        "tests/agents/test_background_budget_control.py",
        "tests/agents/test_background_subagents.py",
        "tests/agents/test_delegation_admission.py",
        "tests/agents/test_workspace_ownership.py",
        "tests/agents/test_delegation_opt_in.py",
        "tests/agents/test_delegation_policies.py",
        "tests/providers/stream_helpers.py",
        "tests/providers/test_stream_safety.py",
        "tests/providers/test_keyless_compatibility.py",
        "tests/tools/test_shell_portability.py",
        "tests/tools/test_shell_quoted_python.py",
        "tests/tools/test_shell_recovery_guidance.py",
        "tests/tools/test_security.py",
        "tests/tools/test_web_fetch_security.py",
        "tests/tools/test_restricted_web_fetch.py",
        "tests/config/test_network_host_settings.py",
        "tests/tools/test_security_bug013_shell_injection.py",
        "tests/tools/test_plan_mode_transition_authority.py",
        "tests/tools/test_plan_mode_operation_effects.py",
        "tests/tools/test_effective_policy.py",
        "tests/tools/test_restricted_access_policy.py",
        "tests/tools/test_configured_tool_controls.py",
        "tests/tools/test_restricted_execution_effects.py",
        "tests/config/test_tool_access_settings.py",
        "tests/tools/test_approval_grant_reuse.py",
        "tests/tools/test_registry.py",
        "tests/cli/test_plan_mode_resume.py",
        "tests/cli/test_session_grant_boundary.py",
        "tests/agents/test_subagent_plan_mode_prompt.py",
        "tests/tools/test_file_tools.py",
        "tests/tools/test_atomic_text_portability.py",
        "tests/tools/test_atomic_write_security.py",
        "tests/tools/test_text_file_roundtrip.py",
        "tests/tools/test_numbered_file_read.py",
        "tests/tools/test_edit_recovery.py",
        "tests/tools/test_python_exec.py",
        "tests/tools/test_python_exec_recovery.py",
        "tests/tools/test_automatic_formatting.py",
        "tests/tools/test_registry_formatting.py",
        "tests/tools/test_lint_fix_policy.py",
        "tests/tools/test_code_format.py",
        "tests/tools/test_python_verification_integrity.py",
        "tests/rag/test_concurrency_platforms.py",
        "tests/cli/test_repl_questions.py",
        "tests/cli/test_textual_question_channel.py",
        "tests/cli/ui_scenarios.py",
        "tests/cli/test_textual_interaction_contract.py",
        "tests/cli/test_textual_transcript_window.py",
        "tests/cli/test_textual_tool_activity.py",
        "tests/cli/test_textual_activity_state.py",
        "tests/cli/test_textual_queue.py",
        "tests/cli/test_textual_mouse_settings.py",
        "tests/cli/test_textual_motion_settings.py",
        "tests/cli/test_textual_widgets_bugs.py",
        "tests/cli/test_textual_phase1.py",
        "tests/cli/test_textual_phase3.py",
        "tests/cli/test_tui_bugs_028_035.py",
        "tests/cli/test_question_monitor.py",
        "tests/cli/test_key_monitor_input.py",
        "tests/tools/test_python_quality.py",
        "tests/analysis/test_quality_scan_limits.py",
        "tests/agents/test_completion_integrity.py",
        "tests/agents/test_response_completion.py",
        "tests/agents/test_delegation_completion_requirements.py",
        "tests/agents/test_delegation_result_reporting.py",
        "tests/cli/test_completion_rendering.py",
        "tests/cli/test_json_output.py",
        "tests/cli/test_json_stdout.py",
        "tests/core/test_agent_stall_lifecycle.py",
        "tests/tools/test_delegate.py",
        "tests/tools/test_bounded_subprocess.py",
        "tests/advanced/test_acceptance_checks.py",
        "tests/advanced/test_plan_acceptance.py",
        "tests/testing/test_pytest_reporter.py",
        "tests/testing/test_eval_helpers.py",
        "tests/testing/test_eval_fixture_encoding.py",
        "tests/testing/test_eval_profiles.py",
        "tests/testing/test_team_eval_profile.py",
        "tests/testing/test_team_environment_context.py",
        "tests/testing/test_eval_tool_observations.py",
        "tests/testing/test_team_eval_runner.py",
        "tests/testing/test_team_workflow_oracle.py",
        "tests/testing/test_artifact_observation.py",
        "tests/testing/test_counter_eval_contract.py",
        "tests/testing/test_edit_eval_contract.py",
        "evals/release_corpus.py",
        "tests/testing/test_release_corpus.py",
        "tests/testing/test_baseline_runs.py",
        "tests/testing/test_baseline_report_redaction.py",
        "tests/testing/test_syntax_scenario.py",
        "tests/testing/test_syntax_eval_contract.py",
        "evals/helpers.py",
        "evals/artifact_observation.py",
        "evals/package_oracle.py",
        "evals/models.py",
        "evals/baseline_runs.py",
        "evals/team_runtime.py",
        "evals/run_team.py",
        "evals/test_python_reuse.py",
        "evals/test_team_python_workflow.py",
        "evals/test_team_python_package.py",
        "evals/test_coding_tasks.py",
        "evals/test_edit_precision.py",
        "tests/utils/test_file_lock.py",
        "tests/testing/test_fibonacci_scenario.py",
        "tests/testing/test_eval_bytecode_freshness.py",
        "tests/config/test_ui_unknown_fields.py",
        "tests/config/test_settings_snapshot.py",
        "tests/config/test_settings_numeric_parsing.py",
        "tests/cli/test_config_money_precision.py",
        "tests/cli/test_doctor_core_command.py",
        "tests/config/test_settings_control_transfer.py",
        "tests/cli/test_config_control_transfer.py",
        "tests/contracts/test_config_sync_contracts.py",
        "tests/contracts/schemas/config/sync_payload.json",
        "tests/config/test_config_export_evidence.py",
        "tests/testing/test_pytest_evidence_helper.py",
        "tests/testing/test_python_reuse_scenario.py",
        "tests/config/test_settings_inspection.py",
        "tests/config/test_session_settings_overrides.py",
        "tests/config/test_strict_setting_fields.py",
        "tests/config/test_grouped_settings_inspection.py",
        "tests/config/test_unknown_group_error_origin.py",
        "tests/config/test_portable_agents_context.py",
        "tests/config/test_context_discovery_boundaries.py",
        "tests/config/test_context_snapshot.py",
        "tests/config/test_context_snapshot_scopes.py",
        "tests/config/test_context_symlink_boundaries.py",
        "tests/config/test_context_target_refresh.py",
        "tests/config/test_context_truncation.py",
        "tests/config/test_context_precedence.py",
        "tests/core/test_instruction_provenance.py",
        "tests/core/test_instruction_context_runtime.py",
        "tests/cli/test_instruction_context_runtime.py",
        "tests/tools/test_patch_scope_boundaries.py",
        "tests/tools/test_test_gen_templates.py",
        "tests/core/test_instruction_policy_boundary.py",
        "tests/agents/test_delegation_provenance.py",
        "tests/agents/test_handoff_evidence.py",
        "tests/cli/test_session_manager_provenance.py",
        "tests/core/test_compaction_recovery.py",
        "tests/core/test_session_enhanced.py",
        "tests/core/test_session_memory_controls.py",
        "tests/core/test_session_persistence.py",
        "tests/core/test_session_project_boundary.py",
        "tests/cli/test_session_project_boundary.py",
        "tests/cli/test_session_startup_recovery.py",
        "tests/cli/test_session_redaction.py",
        "tests/core/test_session_redaction.py",
        "tests/utils/test_evidence_redaction.py",
        "tests/utils/test_evidence_stream_redaction.py",
        "tests/cli/test_json_evidence_redaction.py",
        "tests/cli/test_terminal_evidence_redaction.py",
        "tests/cli/test_textual_evidence_redaction.py",
        "tests/cli/test_textual_direct_evidence.py",
        "tests/cli/test_failure_evidence_redaction.py",
        "tests/core/test_failure_evidence.py",
        "tests/core/test_diagnostic_evidence_boundaries.py",
        "tests/chat/test_chat_content_evidence.py",
        "tests/chat/test_chat_bug046_empty_content.py",
        "tests/ops/test_ops_event_evidence_redaction.py",
        "tests/cli/test_history_evidence_redaction.py",
        "tests/cli/test_direct_failure_evidence.py",
        "tests/cli/test_textual_workspace_evidence.py",
        "tests/cli/test_textual_checkpoints.py",
        "tests/core/test_session_tier2_services.py",
        "tests/cli/test_session_context_command.py",
        "tests/contracts/conftest.py",
        "tests/contracts/helpers.py",
        "tests/contracts/test_advanced_contracts.py",
        "tests/contracts/schemas/advanced/task_record.json",
        "tests/contracts/schemas/advanced/plan_record.json",
        "tests/contracts/schemas/advanced/cron_schedule.json",
        "tests/contracts/schemas/advanced/repl_session.json",
        "tests/contracts/schemas/advanced/tungsten_snapshot.json",
        "tests/contracts/test_control_settings_contracts.py",
        "tests/contracts/test_api_contracts.py",
        "tests/contracts/schemas/api/chat_request.json",
        "tests/contracts/schemas/api/chat_response.json",
        "tests/contracts/schemas/api/chat_stream_chunk.json",
        "tests/contracts/schemas/api/error_response.json",
        "tests/contracts/schemas/api/health_response.json",
        "tests/contracts/schemas/api/metrics_response.json",
        "tests/contracts/schemas/api/oauth_authorize_response.json",
        "tests/contracts/schemas/api/oauth_token_response.json",
        "tests/contracts/schemas/api/remote_session_response.json",
        "tests/contracts/schemas/api/run_budget_snapshot.json",
        "tests/contracts/schemas/api/usage_response.json",
        "tests/contracts/schemas/config/settings.json",
        "tests/contracts/schemas/config/mcp_server_config.json",
        "tests/contracts/schemas/config/tool_settings.json",
        "tests/contracts/schemas/runtime/session.json",
        "tests/contracts/schemas/runtime/message.json",
        "tests/contracts/schemas/runtime/stream_chunk.json",
        "tests/contracts/schemas/runtime/session_message.json",
        "tests/contracts/schemas/runtime/session_memory_record.json",
        "tests/contracts/schemas/runtime/session_metadata.json",
        "tests/contracts/schemas/runtime/turn_summary_record.json",
        "tests/contracts/schemas/providers/message.json",
        "tests/contracts/test_session_contracts.py",
        "tests/contracts/test_operation_contracts.py",
        "tests/cli/test_repl_instruction_provenance.py",
        "tests/cli/test_subagent_provenance.py",
        "tests/config/test_ui_terminal_settings.py",
        "tests/cli/test_config_ui_terminal_sync.py",
        "tests/cli/test_config_write_command.py",
        "tests/cli/test_config_group_values.py",
        "tests/cli/test_config_header_redaction.py",
        "tests/cli/test_config_environment_origins.py",
        "tests/cli/test_runtime_settings_snapshot.py",
        "tests/cli/test_textual_settings_snapshot.py",
        "tests/cli/test_tui_injected_settings.py",
        "tests/utils/test_source_files.py",
        "tests/utils/test_offline_tokenizers.py",
        "evals/test_test_docs.py",
        "evals/test_package_lifecycle.py",
        "tests/testing/test_test_docs_oracle.py",
        "tests/testing/test_test_docs_documentation.py",
        "tests/testing/test_test_docs_scenario.py",
        "tests/testing/test_semantic_bug_scenario.py",
        "evals/test_tool_failure_recovery.py",
        "tests/testing/test_tool_failure_recovery_scenario.py",
        "evals/test_interruption_recovery.py",
        "tests/testing/test_interruption_recovery_scenario.py",
    ):
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(repository / relative, destination)
    if include_package:
        for name in (
            "test_package_oracle.py", "test_team_package_scenario.py",
            "test_package_runtime_observer.py",
            "test_package_lifecycle_scenario.py",
        ):
            package_relative = Path("tests/testing") / name
            shutil.copyfile(repository / package_relative, target / package_relative)
    for relative in (
        "tests", "tests/e2e", "tests/providers", "tests/tools", "tests/rag", "tests/cli", "tests/cli/commands",
        "tests/analysis", "tests/agents", "tests/config", "tests/contracts", "tests/core", "tests/advanced", "tests/utils", "tests/testing", "tests/team", "evals",
    ):
        (target / relative / "__init__.py").touch()
    # The repository conftest prepends src/. This replacement asserts the wheel
    # origin inside the exact pytest process that runs the coding workflow.
    (target / "tests/conftest.py").write_text(
        _ORIGIN_CHECK + '\npytest_plugins = ["tests.offline_network"]\n', encoding="utf-8",
    )
    (target / "pytest.ini").write_text(
        "[pytest]\nasyncio_mode = auto\nasyncio_default_fixture_loop_scope = function\n"
        "markers =\n    always_passes: live evaluation policy\n    usually_passes: live evaluation policy\n"
        "    anyio: async test also executed by asyncio auto mode\n",
        encoding="utf-8",
    )


def check_aliases(directory: Path, environment: dict[str, str]) -> None:
    """Exercise installed entrypoints, including unsuccessful command handling."""
    scripts = Path(sysconfig.get_path("scripts"))
    for alias in ("henchman", "mlg"):
        executable = scripts / (f"{alias}.exe" if os.name == "nt" else alias)
        for arguments, expected_code, expected_text in (
            (["--version"], 0, "version"),
            (["--help"], 0, "Commands:"),
            (["definitely-not-a-command"], 2, "No such command 'definitely-not-a-command'"),
        ):
            result = subprocess.run(
                [str(executable), *arguments], cwd=directory, env=environment,
                capture_output=True, timeout=60, check=False,
            )
            output = result.stdout + result.stderr
            if result.returncode != expected_code or expected_text.encode("ascii") not in output:
                raise RuntimeError(f"{alias} {arguments} exited {result.returncode}:\n{output!r}")
            print(f"Verified {alias} {' '.join(arguments)}", flush=True)


def main() -> None:
    """Install the artifact and run isolated entrypoint and coding-loop checks."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheel-dir", type=Path, required=True)
    parser.add_argument("--include-package", action="store_true",
                        help="Include the full package-lifecycle walkthrough for release qualification")
    args = parser.parse_args()
    wheel = find_wheel(args.wheel_dir).resolve()
    repository = Path(__file__).resolve().parents[2]
    environment = smoke_environment(dict(os.environ))
    if args.include_package:
        environment = retain_build_cache(environment)
    subprocess.run(
        [sys.executable, "-m", "pip", "install", str(wheel), "pytest>=8", "pytest-asyncio>=0.23",
         "ruff>=0.4", "mypy>=1.10"],
        env=environment, check=True, timeout=900,
    )
    verify_wheel_contents(wheel, Path(sysconfig.get_path("purelib")))
    with tempfile.TemporaryDirectory(prefix="henchman-wheel-smoke-") as scratch:
        directory = Path(scratch)
        environment = isolated_runtime_environment(environment, directory)
        stage_workflow_tests(repository, directory, include_package=args.include_package)
        subprocess.run(
            [sys.executable, "-I", "-c", _ORIGIN_CHECK], cwd=directory,
            env=environment, check=True, timeout=60,
        )
        check_aliases(directory, environment)
        subprocess.run(
            [sys.executable, "-I", "-c", _RAG_CHECK], cwd=directory,
            env=environment, check=True, timeout=120,
        )
        subprocess.run(
            [sys.executable, "-I", "-m", "pytest", "-p", "pytest_asyncio.plugin", "-q",
             "--maxfail=10", "--tb=short", "--durations=15",
             "tests/"],
            # The expanded cohort exceeded 1200s at 80% on Windows/Python 3.11.
            # This aggregate watchdog does not change per-operation deadlines.
            cwd=directory, env=environment, check=True, timeout=1800,
        )


if __name__ == "__main__":
    main()
