"""One owned arithmetic attempt. Real mode requires an explicit reviewed lease."""

from __future__ import annotations
import argparse
import asyncio
import hashlib
import json
import os
import signal
import sys
import time
from contextlib import aclosing
from pathlib import Path
from unittest.mock import patch
from uuid import UUID
import httpx
import contract as c
import fixtures
from transport import GateTransport, build_provider, joined_close, serial, write_json


def synthetic_response(call):
    def chunk(delta, finish=None):
        return {
            "id": "offline-completion",
            "object": "chat.completion.chunk",
            "created": 1,
            "model": c.MODEL,
            "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
        }

    if call is None:
        chunks = [chunk({"content": "Observed the current arithmetic implementation."}, "stop")]
    else:
        name, params = call
        chunks = [
            chunk(
                {
                    "tool_calls": [
                        {
                            "index": 0,
                            "id": "call-" + str(time.monotonic_ns()),
                            "type": "function",
                            "function": {"name": name, "arguments": json.dumps(params)},
                        }
                    ]
                }
            ),
            chunk({}, "tool_calls"),
        ]
    chunks.append(
        {
            "id": "offline-completion",
            "object": "chat.completion.chunk",
            "created": 1,
            "model": c.MODEL,
            "choices": [],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
    )
    return (
        "".join("data: " + json.dumps(row) + "\n\n" for row in chunks) + "data: [DONE]\n\n"
    ).encode()


def scripted(case, arm, plan_id):
    value = fixtures.spec(case)
    calls = [("read_file", {"path": value["target"]})]
    if case != "already-correct":
        calls.append(("write_file", {"path": value["target"], "content": value["correct"]}))
    if arm == "direct":
        calls.append(("verify_plan_execution", {"action": "verify", "plan_id": plan_id}))
    calls.append(None)

    async def respond(request):
        if not calls:
            raise c.Denied("Script exhausted; no fallback")
        return httpx.Response(
            200,
            content=synthetic_response(calls.pop(0)),
            headers={"content-type": "text/event-stream"},
        )

    return httpx.MockTransport(respond)


def bind_guard(registry, root, case, plan_id, denials):
    from henchman.tools.base import ToolResult
    from henchman.tools.builtins.file_read import ReadFileTool
    from henchman.tools.builtins.file_write import WriteFileTool
    from henchman.tools.builtins.file_edit import EditFileTool
    from henchman.tools.builtins.tier6_tools import VerifyPlanExecutionTool
    from henchman.utils.retry import RetryConfig

    allowed = (ReadFileTool, WriteFileTool, EditFileTool, VerifyPlanExecutionTool)
    identities = {
        tool.name: (tool, getattr(tool.execute, "__func__", None))
        for tool in registry._tools.values()
    }
    expected = fixtures.spec(case)
    target = expected["target"]

    def guard(tool, params):
        reason = None
        if (
            Path.cwd() != root
            or type(tool) not in allowed
            or identities.get(tool.name) != (tool, getattr(tool.execute, "__func__", None))
        ):
            reason = "Tool/working directory escaped held comparison"
        elif (root / "criteria.py").is_symlink() or (root / "criteria.py").read_bytes() != expected[
            "criteria"
        ].encode():
            reason = "Protected criteria changed"
        elif type(tool) is VerifyPlanExecutionTool:
            if params != {"action": "verify", "plan_id": plan_id}:
                reason = "Only held verifier invocation is available"
        else:
            raw = params.get("path")
            if not isinstance(raw, str) or not raw or "\x00" in raw:
                reason = "Explicit fixture path required"
            else:
                path = Path(os.path.abspath(Path(raw).expanduser()))
                allowed_paths = (
                    (root / target, root / "criteria.py")
                    if type(tool) is ReadFileTool
                    else (root / target,)
                )
                if (
                    path not in allowed_paths
                    or path.resolve() != path
                    or not path.is_file()
                    or path.stat().st_nlink != 1
                ):
                    reason = "Fixture path outside held comparison"
                if len(json.dumps(params).encode()) > 16384:
                    reason = "Tool arguments exceed comparison bound"
        if reason:
            denials.append(reason)
            return ToolResult(content=reason, success=False, error=reason)
        return None

    registry.bind_execution_guard(guard)
    registry.set_retry_config(RetryConfig(max_retries=0))

    async def confirm(_request):
        return True

    registry.set_confirmation_handler(confirm)
    return guard


async def run_attempt(root, case, arm, repeat, *, dry, lease=None, setup_failure=False):
    from henchman.config.schema import Settings
    from henchman.advanced.plans import PlanExecutionService
    from henchman.advanced.verification_repair import RepairRequest
    from henchman.agents.orchestrator import Orchestrator
    from henchman.tools.registry import ToolRegistry
    from henchman.tools.builtins.file_read import ReadFileTool
    from henchman.tools.builtins.file_write import WriteFileTool
    from henchman.tools.builtins.file_edit import EditFileTool
    from henchman.tools.builtins.tier6_tools import VerifyPlanExecutionTool
    from henchman.core.run_budget import BudgetLimits, RunBudgetLedger
    from henchman.providers.runtime_budget import RunBudgetScope

    if case not in fixtures.CASES or arm not in ("direct", "repair") or repeat not in (1, 2):
        raise c.Denied("Invalid fixed attempt")
    root = Path(root).absolute()
    workspace = root / "workspace"
    start = time.monotonic()
    result = {
        "state": "failed",
        "fixture": case,
        "arm": arm,
        "repeat": repeat,
        "dry": dry,
        "cleanup_joined": False,
        "task_verified_by_runtime": False,
        "source_commit": c.COMMIT,
        "settings_sha256": c.digest(c.json_bytes(c.settings_data())),
    }
    gate = provider = orch = None
    denials = []
    events = []
    event_bytes = 0
    primary = None
    ledger = RunBudgetLedger(
        limits=BudgetLimits(max_requests=c.REQUESTS, max_seconds=c.ATTEMPT_SECONDS)
    )
    scope = RunBudgetScope(ledger, default_output_tokens=c.OUTPUT)
    try:
        spec = fixtures.prepare(workspace, case)
        os.chdir(workspace)
        result["fixture_before"] = {
            p.name: c.digest(p.read_bytes())
            for p in (workspace / spec["target"], workspace / "criteria.py")
        }
        settings = Settings.model_validate(c.settings_data())
        # Preserve v1 fixture/prompt identity; this is not admission authority.
        plan_key = hashlib.sha256(f"bounded-repair-paired-v1:{case}:{repeat}".encode()).hexdigest()[:32]
        with patch("henchman.advanced.plans.uuid4", return_value=UUID(plan_key)):
            plan = PlanExecutionService(workspace, settings=settings).create_plan(
                steps=["Meet the immutable arithmetic criteria"],
                checks=[
                    {
                        "kind": "command",
                        "argv": [sys.executable, "-B", "criteria.py"],
                        "inputs": [spec["target"], "criteria.py"],
                        "timeout": 20,
                    }
                ],
            )
        prompt = fixtures.prompt(case, plan.plan_id)
        result["prompt_sha256"] = c.digest(prompt.encode())
        write_json(
            root / "input.json",
            {"prompt": prompt, "settings": c.settings_data(), "plan_id": plan.plan_id},
        )
        if not dry and lease is None:
            raise c.Denied("Live transport requires reviewed authority")
        delegate = scripted(case, arm, plan.plan_id) if dry else lease.transport()
        gate = GateTransport(
            alias=c.MODEL,
            base_url=c.ENDPOINT,
            delegate=delegate,
            artifacts=root / "wire",
            authorize=(lambda: None) if dry else lease.authorize,
        )
        provider = await build_provider(gate)
        if setup_failure:
            raise c.Denied("Injected setup failure")
        registry = ToolRegistry()
        verify = VerifyPlanExecutionTool(settings=settings)
        verify.bind_runtime(project_root=workspace)
        for tool in (ReadFileTool(), WriteFileTool(), EditFileTool(), verify):
            registry.register(tool)
        bind_guard(registry, workspace, case, plan.plan_id, denials)
        orch = Orchestrator(provider, settings=settings, tool_registry=registry)
        actor = orch.pool.get_agent("engineer")
        actor.base_tool_iterations = 10
        if actor.provider is not provider:
            raise c.Denied("Unexpected role provider")
        result["actor"] = {
            "identity": actor.identity.id,
            "provider": actor.provider.name,
            "model": actor.provider.default_model,
            "tool_round_limit": actor.base_tool_iterations,
            "context_max_tokens": actor.context_window,
        }

        async def observe(event):
            nonlocal event_bytes
            row = serial(event)
            size = len(c.json_bytes(row))
            event_bytes += size
            if event_bytes > c.RAW_LIMIT:
                raise c.Denied("Event evidence bound exceeded")
            events.append(row)

        async with asyncio.timeout(max(0, c.ATTEMPT_SECONDS - (time.monotonic() - start))):
            if arm == "repair":
                request = RepairRequest(
                    plan_id=plan.plan_id,
                    edit_paths=(spec["target"],),
                    protected_paths=("criteria.py",),
                    max_repairs=2,
                    max_identical_failures=2,
                    timeout_seconds=c.ATTEMPT_SECONDS,
                )
                report = await orch.repair_direct(
                    "engineer", prompt, request, on_event=observe, budget_scope=scope
                )
                result["repair"] = report.to_dict()
            else:
                async with aclosing(
                    orch.run_direct("engineer", prompt, budget_scope=scope)
                ) as stream:
                    async for event in stream:
                        await observe(event)
        result["runtime_status"] = str(orch.last_completion_status)
        result["state"] = (
            "finished"
            if orch.last_completion_status.value in ("completed", "responded")
            else "failed"
        )
    except BaseException as exc:
        from henchman.utils.exception_evidence import exception_text
        from henchman.utils.evidence_redaction import EvidenceRedactor

        result["error"] = exception_text(exc, EvidenceRedactor(), include_traceback=True)
        primary = exc
        result["state"] = (
            "cancelled"
            if isinstance(exc, asyncio.CancelledError)
            else "timeout"
            if isinstance(exc, TimeoutError)
            else "failed"
        )
        result["error_type"] = type(exc).__name__
    finally:
        result["operation_elapsed_seconds"] = time.monotonic() - start

        async def finish():
            errors = []
            for close in (
                (orch.aclose if orch else None),
                (provider._client.close if provider else None),
                (gate.aclose if gate else None),
            ):
                if close:
                    try:
                        await close()
                    except BaseException as exc:
                        errors.append(type(exc).__name__)
            result["cleanup_errors"] = errors
            result["cleanup_joined"] = not errors

        cleanup = asyncio.create_task(finish())
        try:
            await joined_close(cleanup)
        except asyncio.CancelledError as exc:
            if primary is None:
                primary = exc
                result["state"] = "cancelled"
                result["error_type"] = "CancelledError"
        except BaseException as exc:
            result["cleanup_errors"] = [type(exc).__name__]
        result["budget"] = serial(ledger.snapshot())
        result["transport_usage"] = (
            gate.usage_summary()
            if gate
            else {"dispatched_requests": 0, "all_dispatched_requests_have_complete_usage": False}
        )
        result["requests"] = gate.receipts if gate else []
        result["denials"] = denials + (gate.denials if gate else [])
        result["oracle"] = fixtures.oracle(workspace, case)
        result["elapsed_including_cleanup_seconds"] = time.monotonic() - start
        # Keep final bytes and workspace, even on failure. No removal can race an
        # owned verifier/SDK child; supervisor proves whole-process settlement.
        result["workspace_retained"] = True
        write_json(root / "events.json", events)
        write_json(root / "worker.json", result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case", choices=fixtures.CASES, required=True)
    parser.add_argument("--arm", choices=["direct", "repair"], required=True)
    parser.add_argument("--repeat", type=int, choices=[1, 2], required=True)
    parser.add_argument("--dry", action="store_true")
    parser.add_argument("--admission", type=Path)
    args = parser.parse_args()
    os.umask(0o077)
    c.verify_source()

    def offline(event, values):
        if event == "socket.connect":
            address = values[1]
            if (
                args.dry
                or not isinstance(address, tuple)
                or len(address) != 2
                or address != ("127.0.0.1", 8081)
            ):
                raise c.Denied("Network destination outside held local experiment")
        elif event == "socket.getaddrinfo":
            if args.dry or values[0] != "127.0.0.1" or values[1] != 8081:
                raise c.Denied("DNS/fallback outside held local experiment")
        elif event == "subprocess.Popen":
            argv = values[1]
            cwd = values[2]
            target = fixtures.spec(args.case)["target"]
            allowed = (
                [sys.executable, "-B", "criteria.py"],
                [
                    sys.executable,
                    "-I",
                    "-m",
                    "black",
                    "--quiet",
                    "--workers",
                    "1",
                    "--safe",
                    "--",
                    str(args.output.absolute() / "workspace" / target),
                ],
            )
            if (
                list(argv) not in allowed
                or Path(cwd or os.getcwd()) != args.output.absolute() / "workspace"
            ):
                raise c.Denied("Subprocess outside held verifier/formatter")

    sys.addaudithook(offline)

    async def owned():
        task = asyncio.current_task()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, task.cancel, "paired attempt interrupted")
        lease = None
        if not args.dry:
            from local_server import Lease

            lease = Lease(args.admission)
        result = await run_attempt(
            args.output, args.case, args.arm, args.repeat, dry=args.dry, lease=lease
        )
        return 0 if result["state"] == "finished" and result["cleanup_joined"] else 1

    return asyncio.run(owned())


if __name__ == "__main__":
    raise SystemExit(main())
