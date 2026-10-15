"""Scripted provider transports exercise actual headless Python team execution."""

import copy
import io
import json
import os
import shlex
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from rich.console import Console
from tests.e2e.test_coding_loop import anthropic_response, compatible_response

from henchman.advanced.plans import PlanExecutionService
from henchman.agents.orchestrator import Orchestrator
from henchman.cli import app
from henchman.cli.json_output import event_to_dict
from henchman.config.schema import ProviderSettings, Settings
from henchman.providers.factory import create_configured_provider
from henchman.tools.builtins.file_edit import EditFileTool
from henchman.tools.builtins.file_read import ReadFileTool
from henchman.tools.builtins.shell import ShellTool
from henchman.tools.builtins.tier6_tools import VerifyPlanExecutionTool
from henchman.tools.registry import ToolRegistry


@pytest.mark.parametrize("provider_name", ["openrouter", "openai_compat", "deepseek", "ollama", "anthropic"])
@pytest.mark.parametrize("output_mode", ["events", "json-complete"])
@pytest.mark.parametrize("attempt_unlisted_write", [False, True])
async def test_headless_team_inspects_reuses_edits_tests_and_reviews(
    tmp_path, monkeypatch, provider_name, output_mode, attempt_unlisted_write,
):
    """Research and implementation use separate histories and real shared artifacts."""
    monkeypatch.setenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
    monkeypatch.setenv("PYTHONDONTWRITEBYTECODE", "1")
    helper = tmp_path / "math_helpers.py"
    helper.write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    source = tmp_path / "arithmetic.py"
    source.write_text("from math_helpers import add\n\ndef total(a, b):\n    return a - b\n", encoding="utf-8")
    (tmp_path / "test_arithmetic.py").write_text(
        "from arithmetic import total\n\ndef test_total():\n"
        "    assert total(2, 3) == 5\n    assert total(-4, 2) == -2\n", encoding="utf-8",
    )
    service = PlanExecutionService(tmp_path)
    plan = service.create_plan(steps=["Find helper", "Repair total", "Review and verify"], checks=[
        {"kind": "file_changed", "path": "arithmetic.py"},
        {"kind": "file_contains", "path": "arithmetic.py", "text": "return add(a, b)"},
        {"kind": "pytest", "path": "test_arithmetic.py", "timeout": 20},
    ])
    pytest_argv = [sys.executable, "-m", "pytest", "-q", "test_arithmetic.py"]
    command = subprocess.list2cmdline(pytest_argv) if os.name == "nt" else shlex.join(pytest_argv)
    script = [
        ("research", "delegate_task", {"agent": "explorer", "task": "Find the existing addition helper."}),
        ("shared-call", "read_file", {"path": str(helper)}),
        None,
        ("implement", "delegate_task", {
            "agent": "engineer", "task": "Reuse math_helpers.add in arithmetic.total, run tests before and after.",
        }),
        ("shared-call", "read_file", {"path": str(source)}),
        ("before", "shell", {"command": command, "cwd": str(tmp_path), "timeout": 20, "background": False}),
        ("fix", "edit_file", {"path": str(source), "old_str": "return a - b", "new_str": "return add(a, b)"}),
        ("after", "shell", {"command": command, "cwd": str(tmp_path), "timeout": 20, "background": False}),
        None,
        ("review", "delegate_task", {"agent": "explorer", "task": "Review arithmetic.total now reuses math_helpers.add."}),
        ("review-read", "read_file", {"path": str(source)}),
        None,
        ("acceptance", "verify_plan_execution", {"action": "verify", "plan_id": plan.plan_id}),
        None,
    ]
    if attempt_unlisted_write:
        script.insert(0, ("blocked-write", "edit_file", {
            "path": str(source), "old_str": "return a - b", "new_str": "return a + 99",
        }))
    saved = {"api_key": "offline-test", "model": "coding-test"}
    if provider_name == "anthropic":
        saved["tokens_per_minute"] = 1_000_000_000
    if provider_name == "openai_compat":
        saved["base_url"] = "https://offline.invalid/v1"
    if provider_name == "ollama":
        saved.pop("api_key")
    providers = ProviderSettings(default=provider_name, **{provider_name: saved})
    provider = create_configured_provider(providers)
    requests = []

    def next_response(**kwargs):
        requests.append(copy.deepcopy(kwargs))
        assert len(requests) <= len(script), "Unexpected model call"
        call = script[len(requests) - 1]
        return anthropic_response(call) if provider_name == "anthropic" else compatible_response(call)

    if provider_name == "anthropic":
        monkeypatch.setattr(provider._client.messages, "stream", next_response)
    else:
        monkeypatch.setattr(provider._client.chat.completions, "create", AsyncMock(side_effect=next_response))
    registry = ToolRegistry()
    verification = VerifyPlanExecutionTool()
    verification.bind_runtime(project_root=tmp_path)
    for tool in (ReadFileTool(), EditFileTool(), ShellTool(), verification):
        registry.register(tool)
    approvals = []

    async def approve(request):
        approvals.append(request.tool_name)
        return True

    registry.set_confirmation_handler(approve)
    # Canonical team prompts, tool schemas and output reservations exceed 8K.
    # Exercise a declared 16K request window rather than relying on input-only accounting.
    settings = Settings(providers=providers, context={"max_tokens": 16384})
    settings.agents.max_delegation_retries = 0
    orch = Orchestrator(default_provider=provider, tool_registry=registry, settings=settings)
    repl = SimpleNamespace(orchestrator=orch, agent=orch.tech_lead, tool_registry=registry,
                           initialize_mcp=AsyncMock(), rag_system=None)
    try:
        if output_mode == "json-complete":
            output = io.StringIO()
            monkeypatch.setattr(app, "console", Console(file=output, width=10000, highlight=False, markup=False))
            await app._run_headless_json_complete(repl, "Repair totals using existing code with specialist review")
            events = json.loads(output.getvalue())
        else:
            raw = []
            assert await app._run_headless_json_mode(repl, "Repair totals with specialist review", raw.append), [
                event_to_dict(event) for event in raw if event.type.value == "error"
            ]
            events = [event_to_dict(event) for event in raw]
    finally:
        await provider._client.close()
    assert len(requests) == len(script)
    assert source.read_text() == "from math_helpers import add\n\n\ndef total(a, b):\n    return add(a, b)\n"
    assert helper.read_text() == "def add(a, b):\n    return a + b\n"
    results = [event for event in events if event["type"] == "tool_call_result"]
    shared = [event for event in results if event["data"]["tool_call_id"] == "shared-call"]
    assert {event["source_agent"] for event in shared} == {"explorer", "engineer"}
    by_id = {event["data"]["tool_call_id"]: event["data"] for event in results}
    if attempt_unlisted_write:
        assert not by_id["blocked-write"]["success"]
        assert "not found" in by_id["blocked-write"]["result"]
    assert not by_id["before"]["success"]
    assert by_id["after"]["success"]
    assert by_id["acceptance"]["success"]
    assert service.get_plan(plan.plan_id).last_verification["checks_passed"]
    assert orch.ledger is not None
    assert [entry.agent for entry in orch.ledger.delegations] == ["explorer", "engineer", "explorer"]
    assert all(entry.status.value == "completed" for entry in orch.ledger.delegations)
    assert approvals.count("delegate_task") == 3
    assert approvals.count("shell") == 2
    assert "edit_file" in approvals and "verify_plan_execution" in approvals
    assert [event["type"] for event in events].count("finished") == 1
    assert events[-1]["type"] == "finished"
    assert events[-1]["data"]["finish_reason"] == "stop"
    assert events[-1]["task_verified"] is False
    root = [event["data"] for event in events if event["type"] == "agent_completed"
            and event["data"].get("scope") == "run"]
    assert len(root) == 1 and root[0]["status"] == "completed"
    expected_calls = 4 + int(attempt_unlisted_write)  # Three delegations, acceptance, optional denial.
    assert root[0]["evidence"]["tool_calls"] == expected_calls
    assert root[0]["evidence"]["successful_tool_calls"] == 4
    assert orch.tech_lead.turn.tool_count == expected_calls
    assert orch.tech_lead.turn.iteration == expected_calls
    assert orch.pool.get_agent("engineer").provider is provider
    assert orch.pool.get_agent("explorer").provider is provider
