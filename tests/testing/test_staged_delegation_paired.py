"""Safety and independent-oracle checks for the local paired comparison."""

from __future__ import annotations

import asyncio
import hashlib
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from evals.staged_delegation_paired import runner
from evals.staged_delegation_paired.runner import oracle, route_observed
from evals.staged_delegation_paired.worker import LocalTransport, load_plan, scope_guard

from henchman.agents.subagents import subagent_actor

PLAN = Path(__file__).resolve().parents[2] / "evals/staged_delegation_paired/plan.json"


def test_plan_has_fixed_balanced_denominator_and_rejects_modification(tmp_path: Path) -> None:
    plan = load_plan(PLAN)
    assert len(plan["fixtures"]) == 3
    assert len(plan["arm_order"]) == 12
    assert len({tuple(item) for item in plan["arm_order"]}) == 12
    for fixture in plan["fixtures"]:
        attempts = [item for item in plan["arm_order"] if item[0] == fixture["id"]]
        assert {(item[1], item[2]) for item in attempts} == {
            (1, "direct"), (1, "staged"), (2, "direct"), (2, "staged")}
        assert fixture["path"] == "target.py"
    changed = tmp_path / "plan.json"
    changed.write_text(json.dumps({**plan, "endpoint": "https://example.invalid"}))
    with pytest.raises(ValueError, match="plan changed"):
        load_plan(changed)


async def test_transport_rejects_external_route_without_dispatch() -> None:
    transport = LocalTransport(load_plan(PLAN))
    request = httpx.Request("POST", "https://example.invalid/v1/chat/completions", json={})
    try:
        with pytest.raises(RuntimeError, match="destination"):
            await transport.handle_async_request(request)
        assert transport.requests == 0
        assert transport.errors
        assert not transport._lock.locked()
        bad_model = httpx.Request("POST", "http://127.0.0.1:8081/v1/chat/completions",
                                  json={"model": "unexpected", "stream": True, "max_tokens": 1})
        with pytest.raises(RuntimeError, match="profile"):
            await transport.handle_async_request(bad_model)
        assert transport.requests == 0 and not transport._lock.locked()
    finally:
        await transport.aclose()


async def test_transport_serializes_streams_until_the_first_is_consumed(monkeypatch) -> None:
    class Stream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b"{}"

    class Inner:
        async def handle_async_request(self, request):
            return httpx.Response(200, stream=Stream(), request=request)

        async def aclose(self):
            pass

    class Probe:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            pass

        async def get(self, url):
            if url.endswith("/v1/models"):
                return SimpleNamespace(json=lambda: {"data": [{"id": "qwen38-27b-iq3s"}]})
            assert url.endswith("/slots")
            return SimpleNamespace(json=lambda: [{"is_processing": False}])

    transport = LocalTransport(load_plan(PLAN))
    await transport._inner.aclose()
    transport._inner = Inner()
    monkeypatch.setattr(httpx, "AsyncClient", lambda **_kwargs: Probe())

    def request():
        return httpx.Request("POST", "http://127.0.0.1:8081/v1/chat/completions",
                             json={"model": "qwen38-27b-iq3s", "stream": True, "max_tokens": 4096})

    try:
        first = await transport.handle_async_request(request())
        waiting = asyncio.create_task(transport.handle_async_request(request()))
        await asyncio.sleep(0)
        assert not waiting.done()
        assert await first.aread() == b"{}"
        second = await waiting
        assert await second.aread() == b"{}"
        assert transport.requests == 2 and not transport.errors
    finally:
        await transport.aclose()


def test_scope_guard_separates_parent_and_child_and_denies_other_paths() -> None:
    write = SimpleNamespace(name="write_file")
    invoke = SimpleNamespace(name="invoke_subagent")
    target = {"path": "target.py", "content": "replacement"}
    staged = scope_guard("staged", "target.py")
    direct = scope_guard("direct", "target.py")
    assert staged(write, target) is not None
    assert direct(write, target) is None
    with subagent_actor("child"):
        assert staged(write, target) is None
        assert direct(write, target) is not None
        assert staged(write, {"path": "../outside", "content": "replacement"}) is not None
    assert staged(invoke, {"write_paths": ["target.py"], "tools": ["edit_file"]}) is None
    assert staged(invoke, {"write_paths": ["target.py"], "tools": ["shell"]}) is not None
    assert direct(invoke, {"write_paths": ["target.py"], "tools": ["edit_file"]}) is not None


def test_oracle_reads_current_bytes_without_executing_generated_code(tmp_path: Path) -> None:
    path = tmp_path / "target.py"
    expected = "def add(a, b):\n    return a + b\n"
    path.write_text("def add(a,b):\n return a+b\n")
    matches, digest = oracle(path, expected)
    assert matches and digest
    path.write_text("raise RuntimeError('must never execute')\n")
    assert oracle(path, expected)[0] is False


def test_route_evidence_requires_observed_success() -> None:
    direct = [{"event": "result", "tool": "edit_file", "success": True}]
    assert route_observed("direct", direct)
    assert not route_observed("staged", direct)
    staged = [{"event": "result", "tool": name, "success": True} for name in
              ("invoke_subagent", "manage_subagents", "publish_subagent_proposal")]
    assert route_observed("staged", staged)
    staged[-1]["success"] = False
    assert not route_observed("staged", staged)


def test_launcher_records_all_fixed_attempts_without_network(tmp_path: Path, monkeypatch) -> None:
    plan = load_plan(PLAN)
    fixtures = {item["id"]: item for item in plan["fixtures"]}
    monkeypatch.setattr(runner, "verify_wheel", lambda *_args: None)

    def scripted(command, **_kwargs):
        args = {command[index]: command[index + 1] for index in range(2, len(command), 2)}
        root = Path(args["--root"])
        fixture = fixtures[args["--case"]]
        project = root / "project"
        project.mkdir()
        content = fixture["expected"]
        (project / fixture["path"]).write_text(content)
        names = (["edit_file"] if args["--arm"] == "direct" else
                 ["invoke_subagent", "manage_subagents", "publish_subagent_proposal"])
        result = {"outcome": "completed", "completion": "completed", "transport_errors": [], "events_truncated": False,
                  "result_sha256": hashlib.sha256(content.encode()).hexdigest(),
                  "initial_sha256": hashlib.sha256(fixture["initial"].encode()).hexdigest(),
                  "task_sha256": hashlib.sha256(fixture["task"].encode()).hexdigest(),
                  "prompt_sha256": hashlib.sha256(runner.prompt_for(fixture, args["--arm"]).encode()).hexdigest(),
                  "events": [{"event": "result", "tool": name, "success": True} for name in names]}
        (root / "worker.json").write_text(json.dumps(result))
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(runner.subprocess, "run", scripted)
    output = tmp_path / "results"
    runner.run_live(plan, output, tmp_path / "unused.whl")
    report = json.loads((output / "report.json").read_text())
    assert report["planned"] == report["executed"] == report["accepted"] == 12
    assert all(row["status"] == "accepted" and row["independent_exact_ast"] for row in report["rows"])


def test_launcher_preserves_unrun_rows_if_interrupted(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(runner, "verify_wheel", lambda *_args: None)

    def interrupt(*_args, **_kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(runner.subprocess, "run", interrupt)
    output = tmp_path / "interrupted"
    with pytest.raises(KeyboardInterrupt):
        runner.run_live(load_plan(PLAN), output, tmp_path / "unused.whl")
    report = json.loads((output / "report.json").read_text())
    assert report["planned"] == 12
    assert report["rows"][0]["status"] == "interrupted_unknown"
    assert all(row["status"] == "not_run" for row in report["rows"][1:])
