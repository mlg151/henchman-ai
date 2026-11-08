"""Explicit repair uses real adapters, guarded tools and current-file checks offline."""

import asyncio
import copy
import subprocess
import sys

import pytest
from tests.e2e.provider_transport import bind_scripted_transport

from henchman.advanced.plans import PlanExecutionService
from henchman.advanced.verification_repair import RepairRequest
from henchman.agents.orchestrator import Orchestrator
from henchman.config.schema import AgentConfig, ProviderSettings, Settings
from henchman.tools.builtins.file_edit import EditFileTool
from henchman.tools.builtins.file_read import ReadFileTool
from henchman.tools.builtins.file_write import WriteFileTool
from henchman.tools.builtins.tier6_tools import VerifyPlanExecutionTool
from henchman.tools.registry import ToolRegistry

PROVIDERS = ["openrouter", "openai_compat", "deepseek", "ollama", "anthropic"]


async def make_runtime(tmp_path, monkeypatch, provider_name, script, *, approve=True):
    from henchman.providers.factory import create_configured_provider

    monkeypatch.chdir(tmp_path)
    (tmp_path / "target.py").write_text("def add(a, b):\n    return a - b\n")
    (tmp_path / "criteria.py").write_text(
        "from pathlib import Path\n"
        "namespace = {}\n"
        "exec(compile(Path('target.py').read_text(), 'target.py', 'exec'), namespace)\n"
        "values = [namespace['add'](2, 3), namespace['add'](-4, 2)]\n"
        "print(values)\n"
        "assert values == [5, -2], values\n"
    )
    saved = {"api_key": "offline-test", "model": "repair-model"}
    if provider_name == "openai_compat":
        saved["base_url"] = "https://offline.invalid/v1"
    if provider_name == "anthropic":
        saved["tokens_per_minute"] = 1_000_000_000
    if provider_name == "ollama":
        saved.pop("api_key")
    providers = ProviderSettings(default=provider_name, **{provider_name: saved})
    settings = Settings(providers=providers, context={"max_tokens": 32768})
    settings.agents.agents["engineer"] = AgentConfig(
        name="Bounded engineer", role="engineer", description="Repair only the explicit files",
        tools=["read_file", "edit_file", "write_file", "verify_plan_execution"],
    )
    provider = create_configured_provider(providers)
    requests = []

    def response(**kwargs):
        requests.append(copy.deepcopy(kwargs))
        assert len(requests) <= len(script), "Unexpected model request"
        return script[len(requests) - 1]

    await bind_scripted_transport(provider, response)
    registry = ToolRegistry()
    verify = VerifyPlanExecutionTool(settings=settings)
    verify.bind_runtime(project_root=tmp_path)
    for tool in (ReadFileTool(), EditFileTool(), WriteFileTool(), verify):
        registry.register(tool)
    approvals = []

    async def confirmation(request):
        approvals.append(request)
        return approve

    registry.set_confirmation_handler(confirmation)
    service = PlanExecutionService(tmp_path, settings=settings)
    plan = service.create_plan(steps=["Repair addition"], checks=[{
        "kind": "command", "argv": [sys.executable, "-B", "criteria.py"],
        "inputs": ["target.py", "criteria.py"], "timeout": 20,
    }])
    request = RepairRequest(plan_id=plan.plan_id, edit_paths=("target.py",),
                            protected_paths=("criteria.py",), max_repairs=2, max_identical_failures=3)
    orch = Orchestrator(provider, settings=settings, tool_registry=registry)
    return orch, provider, service, request, requests, approvals


@pytest.mark.parametrize("provider_name", PROVIDERS)
async def test_bounded_repair_retries_tools_and_checks_current_files(tmp_path, monkeypatch, provider_name):
    script = [
        ("read", "read_file", {"path": "target.py"}),
        ("bad-edit", "edit_file", {"path": "target.py", "old_str": "missing", "new_str": "ignored"}),
        ("wrong", "edit_file", {"path": "target.py", "old_str": "a - b", "new_str": "a * b"}),
        None,
        ("correct", "edit_file", {"path": "target.py", "old_str": "a * b", "new_str": "a + b"}),
        None,
    ]
    orch, provider, service, request, calls, approvals = await make_runtime(tmp_path, monkeypatch, provider_name, script)
    criterion = (tmp_path / "criteria.py").read_bytes()
    events = []

    async def observe(event):
        events.append(event)

    try:
        report = await orch.repair_direct("engineer", "Repair addition using the existing criteria", request, on_event=observe)
        assert report.status == "scoped_pass" and report.task_verified is False
        assert report.repairs_started == 2
        assert [item.status for item in report.observations] == ["fail", "fail", "pass"]
        assert service.get_plan(request.plan_id).last_repair == report.to_dict()
        assert len(calls) == len(script)
        assert orch.last_budget_scope.ledger.snapshot().consumed_requests == len(script)
        operations = orch.operation_runtime.report().records
        assert len(operations) == 7
        assert len({item.context.run_id for item in operations}) == 1
        assert len({item.operation_id for item in operations}) == 7
        assert all(item.state == "completed" for item in operations)
        assert sum(item.result.success is False for item in operations) == 3
        controller = [item for item in operations if item.context.agent_id == "runtime:verification"]
        assert len(controller) == 3
        assert all(item.tool_name == "verify_plan_execution" for item in controller)
        session = orch.operation_runtime.current_session
        assert all(message.agent_role != "runtime_controller" for message in session.messages)
        conversations = [item for item in session.operations.conversations if ":controller:" in item.id]
        assert len(conversations) == 3
        assert all(item.messages[0].agent_role == "runtime_controller" for item in conversations)
        assert all([message.role for message in item.messages] == ["assistant", "tool"] for item in conversations)
        results = {event.data["tool_call_id"]: event.data for event in events if event.type.value == "tool_call_result"}
        assert results["bad-edit"]["success"] is False
        assert results["correct"]["success"] is True
        assert any(item.tool_name == "verify_plan_execution" for item in approvals)
        assert (tmp_path / "criteria.py").read_bytes() == criterion
        observed = subprocess.run([sys.executable, "-B", "criteria.py"], cwd=tmp_path, capture_output=True, timeout=20)
        assert observed.returncode == 0, observed.stderr.decode()
        (tmp_path / "target.py").write_text("def add(a, b):\n    return 5\n")
        mutant = subprocess.run([sys.executable, "-B", "criteria.py"], cwd=tmp_path, capture_output=True, timeout=20)
        assert mutant.returncode != 0, "Independent current-file oracle accepted a wrong-result mutant"
    finally:
        await orch.aclose()
        await provider._client.close()


@pytest.mark.parametrize("provider_name", PROVIDERS)
async def test_repair_verification_denial_starts_no_model_or_check(tmp_path, monkeypatch, provider_name):
    orch, provider, service, request, calls, approvals = await make_runtime(tmp_path, monkeypatch, provider_name, [], approve=False)
    try:
        with pytest.raises(RuntimeError, match="verification|Verification|denied"):
            await orch.repair_direct("engineer", "Repair", request)
        assert calls == []
        assert service.get_plan(request.plan_id).last_verification is None
        assert approvals and approvals[0].tool_name == "verify_plan_execution"
        assert (tmp_path / "target.py").read_text() == "def add(a, b):\n    return a - b\n"
    finally:
        await orch.aclose()
        await provider._client.close()


@pytest.mark.parametrize("provider_name", PROVIDERS)
async def test_repair_cancelled_model_iteration_closes_ownership(tmp_path, monkeypatch, provider_name):
    orch, provider, service, request, calls, _ = await make_runtime(tmp_path, monkeypatch, provider_name, [None])
    entered = asyncio.Event()

    async def observe(event):
        if event.type.value == "content":
            entered.set()
            await asyncio.Event().wait()

    task = asyncio.create_task(orch.repair_direct("engineer", "Repair", request, on_event=observe))
    ready = asyncio.create_task(entered.wait())
    try:
        # Real verification, admission and persistence precede model content.
        # Race the owned task so an early failure is not hidden as an event
        # timeout; startup speed is not the cancellation behavior under test.
        done, _ = await asyncio.wait(
            {task, ready}, return_when=asyncio.FIRST_COMPLETED,
            timeout=request.timeout_seconds + 10,
        )
        if task in done:
            report = await task
            pytest.fail(f"Repair ended before model observation: {report.status}/{report.reason}")
        assert ready in done, "Repair did not reach model observation within its bounded run deadline"
        task.cancel("stop repair")
        with pytest.raises(asyncio.CancelledError, match="stop repair"):
            await task
        assert len(calls) == 1
        assert not orch._public_run_active
        assert not orch.pool._execution_claims
        stored = service.get_plan(request.plan_id).last_repair
        assert stored["status"] == "incomplete" and stored["reason"] == "cancelled"
    finally:
        if not task.done():
            task.cancel()
        ready.cancel()
        await asyncio.gather(task, ready, return_exceptions=True)
        await orch.aclose()
        await provider._client.close()


@pytest.mark.parametrize("provider_name", PROVIDERS)
async def test_repair_transport_failure_never_retries_or_claims_a_pass(tmp_path, monkeypatch, provider_name):
    from henchman.tools.repair_scope import RepairControlError

    orch, provider, service, request, calls, _ = await make_runtime(tmp_path, monkeypatch, provider_name, [])
    try:
        # The zero-length script raises inside the SDK's MockTransport, before
        # any response. Its with_options copy still owns this offline transport.
        with pytest.raises(RepairControlError, match="did not finish"):
            await orch.repair_direct("engineer", "Repair", request)
        assert len(calls) == 1
        snapshot = orch.last_budget_scope.ledger.snapshot()
        assert snapshot.consumed_requests == 1
        assert snapshot.unknown_dispatched_requests == 1
        assert service.get_plan(request.plan_id).last_repair["status"] == "incomplete"
    finally:
        await orch.aclose()
        await provider._client.close()
