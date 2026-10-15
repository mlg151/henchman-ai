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


def smoke_environment(environment: dict[str, str]) -> dict[str, str]:
    """Prevent source-tree injection and make CLI output deterministic."""
    result = dict(environment)
    result.pop("PYTHONPATH", None)
    result.pop("PYTHONHOME", None)
    result.update(PYTEST_DISABLE_PLUGIN_AUTOLOAD="1", NO_COLOR="1")
    return result


def stage_workflow_tests(repository: Path, target: Path, *, include_package: bool = False) -> None:
    """Copy offline coding and terminal workflows, never production source code."""
    for relative in (
        "tests/e2e/test_coding_loop.py",
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
        "tests/cli/test_repl_background_goals.py",
        "tests/cli/test_textual_background_goals.py",
        "tests/cli/test_background_discovery.py",
        "tests/cli/commands/test_goal.py",
        "tests/core/test_goals.py",
        "tests/tools/test_background_execution.py",
        "tests/tools/test_tier6_task_tools.py",
        "tests/config/test_agent_overrides.py",
        "tests/e2e/test_context_tool_discovery.py",
        "tests/core/test_tool_disclosure.py",
        "tests/tools/test_schema_discovery.py",
        "tests/agents/test_scoped_tool_discovery.py",
        "tests/tools/test_live_tool_scopes.py",
        "tests/agents/test_leader_tool_scope.py",
        "tests/cli/test_actor_tool_scope.py",
        "tests/contracts/test_tool_executor_contracts.py",
        "tests/cli/test_tool_executor_asyncio_gather.py",
        "tests/cli/test_headless_loop.py",
        "tests/cli/test_output_stream_coverage.py",
        "tests/e2e/test_headless_team.py",
        "tests/cli/test_headless_orchestration.py",
        "tests/cli/test_headless_team_streaming.py",
        "tests/cli/test_switch_context_limit.py",
        "tests/cli/test_chat_session_reasoning.py",
        "tests/cli/test_workflow_discovery.py",
        "tests/team/test_workflow_execution_truth.py",
        "tests/cli/test_provider_switch.py",
        "tests/cli/commands/test_model.py",
        "tests/cli/commands/test_model_context.py",
        "tests/cli/commands/test_model_large_context.py",
        "tests/core/test_request_budget.py",
        "tests/agents/test_request_capacity.py",
        "tests/providers/test_request_budget.py",
        "tests/providers/test_required_tool_schemas.py",
        "tests/agents/test_orchestrator_streaming.py",
        "tests/agents/test_pool_context_settings.py",
        "tests/agents/test_orchestrator_round_budget.py",
        "tests/agents/test_delegation_budget_disclosure.py",
        "tests/agents/test_delegation_mission_context.py",
        "tests/agents/test_delegation_error_isolation.py",
        "tests/agents/test_team_tool_discovery.py",
        "tests/agents/test_run_completion_scope.py",
        "tests/agents/test_delegation_policies.py",
        "tests/providers/stream_helpers.py",
        "tests/providers/test_stream_safety.py",
        "tests/providers/test_keyless_compatibility.py",
        "tests/tools/test_shell_portability.py",
        "tests/tools/test_shell_quoted_python.py",
        "tests/tools/test_shell_recovery_guidance.py",
        "tests/tools/test_security.py",
        "tests/tools/test_security_bug013_shell_injection.py",
        "tests/tools/test_file_tools.py",
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
        "tests/core/test_agent_stall_lifecycle.py",
        "tests/tools/test_delegate.py",
        "tests/tools/test_bounded_subprocess.py",
        "tests/advanced/test_acceptance_checks.py",
        "tests/advanced/test_plan_acceptance.py",
        "tests/testing/test_pytest_reporter.py",
        "tests/testing/test_eval_helpers.py",
        "tests/testing/test_eval_profiles.py",
        "tests/testing/test_team_eval_profile.py",
        "tests/testing/test_team_environment_context.py",
        "tests/testing/test_eval_tool_observations.py",
        "tests/testing/test_team_eval_runner.py",
        "tests/testing/test_team_workflow_oracle.py",
        "tests/testing/test_artifact_observation.py",
        "tests/testing/test_counter_eval_contract.py",
        "tests/testing/test_edit_eval_contract.py",
        "evals/helpers.py",
        "evals/artifact_observation.py",
        "evals/package_oracle.py",
        "evals/models.py",
        "evals/team_runtime.py",
        "evals/run_team.py",
        "evals/test_python_reuse.py",
        "evals/test_team_python_workflow.py",
        "evals/test_team_python_package.py",
        "evals/test_coding_tasks.py",
        "evals/test_edit_precision.py",
        "tests/utils/test_file_lock.py",
        "tests/utils/test_source_files.py",
    ):
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(repository / relative, destination)
    if include_package:
        for name in ("test_package_oracle.py", "test_team_package_scenario.py"):
            package_relative = Path("tests/testing") / name
            shutil.copyfile(repository / package_relative, target / package_relative)
    for relative in (
        "tests", "tests/e2e", "tests/providers", "tests/tools", "tests/rag", "tests/cli", "tests/cli/commands",
        "tests/analysis", "tests/agents", "tests/config", "tests/contracts", "tests/core", "tests/advanced", "tests/utils", "tests/testing", "tests/team", "evals",
    ):
        (target / relative / "__init__.py").touch()
    # The repository conftest prepends src/. This replacement asserts the wheel
    # origin inside the exact pytest process that runs the coding workflow.
    (target / "tests/conftest.py").write_text(_ORIGIN_CHECK, encoding="utf-8")
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
    args = parser.parse_args()
    wheel = find_wheel(args.wheel_dir).resolve()
    repository = Path(__file__).resolve().parents[2]
    environment = smoke_environment(dict(os.environ))
    subprocess.run(
        [sys.executable, "-m", "pip", "install", str(wheel), "pytest>=8", "pytest-asyncio>=0.23",
         "ruff>=0.4", "mypy>=1.10"],
        env=environment, check=True, timeout=900,
    )
    with tempfile.TemporaryDirectory(prefix="henchman-wheel-smoke-") as scratch:
        directory = Path(scratch)
        stage_workflow_tests(repository, directory)
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
             "tests/"],
            cwd=directory, env=environment, check=True, timeout=600,
        )


if __name__ == "__main__":
    main()
