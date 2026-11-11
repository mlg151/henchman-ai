"""Run one guarded local-only staged-delegation comparison attempt."""

from __future__ import annotations

import argparse
import ast
import asyncio
import hashlib
import json
import os
import sys
import time
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any

try:
    import resource
except ImportError:  # pragma: no cover - this comparison runs on Linux only
    resource = None  # type: ignore[assignment]

import httpx
from openai import AsyncOpenAI

from henchman.agents.orchestrator import Orchestrator
from henchman.agents.subagents import current_subagent_actor
from henchman.config.schema import Settings
from henchman.providers.openai_compat import OpenAICompatibleProvider
from henchman.tools.base import Tool, ToolResult
from henchman.tools.builtins.file_edit import EditFileTool
from henchman.tools.builtins.file_read import ReadFileTool
from henchman.tools.builtins.file_write import WriteFileTool
from henchman.tools.registry import ToolRegistry

PLAN_SHA256 = "2ad6873979579a3769bcaf15e1751ccb1afbef6192e6435107069540c0ef59ae"


def load_plan(path: Path) -> dict[str, Any]:
    """Reject modified plans before any model request or fixture creation."""
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PLAN_SHA256:
        raise ValueError("The frozen comparison plan changed")
    plan: dict[str, Any] = json.loads(raw)
    if plan["endpoint"] != "http://127.0.0.1:8081" or plan["model"] != "qwen38-27b-iq3s":
        raise ValueError("The comparison requires its fixed local endpoint and model")
    return plan


class _SerializedStream(httpx.AsyncByteStream):
    def __init__(self, stream: httpx.AsyncByteStream, lock: asyncio.Lock) -> None:
        self._stream = stream
        self._lock = lock
        self._released = False

    def _release(self) -> None:
        if not self._released:
            self._released = True
            self._lock.release()

    async def __aiter__(self) -> AsyncIterator[bytes]:
        try:
            async for chunk in self._stream:
                yield chunk
        finally:
            self._release()

    async def aclose(self) -> None:
        try:
            await self._stream.aclose()
        finally:
            self._release()


class LocalTransport(httpx.AsyncBaseTransport):
    """Admit only the fixed local route and serialize this attempt's streams."""

    def __init__(self, plan: dict[str, Any]) -> None:
        self._plan = plan
        self._inner = httpx.AsyncHTTPTransport(retries=0, trust_env=False)
        self._lock = asyncio.Lock()
        self.requests = 0
        self.errors: list[str] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        await self._lock.acquire()
        handed_off = False
        try:
            url = request.url
            if (request.method != "POST" or url.scheme != "http" or url.host != "127.0.0.1"
                    or url.port != 8081 or url.path != "/v1/chat/completions" or url.query):
                raise RuntimeError("Local-only transport denied the destination")
            payload = json.loads(request.content)
            if (payload.get("model") != self._plan["model"] or payload.get("stream") is not True
                    or type(payload.get("max_tokens")) is not int
                    or payload["max_tokens"] > self._plan["output_token_ceiling"]
                    or ("max_completion_tokens" in payload and (
                        type(payload["max_completion_tokens"]) is not int
                        or payload["max_completion_tokens"] > self._plan["output_token_ceiling"]))):
                raise RuntimeError("Local-only transport denied the request profile")
            if self.requests >= self._plan["request_limit"]:
                raise RuntimeError("Local transport request limit reached")
            async with httpx.AsyncClient(trust_env=False, timeout=4, follow_redirects=False) as client:
                models = (await client.get(self._plan["endpoint"] + "/v1/models")).json()
                if self._plan["model"] not in {item.get("id") for item in models.get("data", [])}:
                    raise RuntimeError("Expected local model is unavailable")
                for _ in range(15):
                    slots = (await client.get(self._plan["endpoint"] + "/slots")).json()
                    if isinstance(slots, list) and any(not item.get("is_processing", True) for item in slots):
                        break
                    await asyncio.sleep(0.2)
                else:
                    raise RuntimeError("Local model has no idle slot")
            self.requests += 1
            response = await self._inner.handle_async_request(request)
            if not isinstance(response.stream, httpx.AsyncByteStream):
                await response.aclose()
                raise RuntimeError("Local transport returned a non-async stream")
            response.stream = _SerializedStream(response.stream, self._lock)
            handed_off = True
            return response
        except Exception as error:
            self.errors.append(f"{type(error).__name__}: {error}"[:300])
            raise
        finally:
            if not handed_off:
                self._lock.release()

    async def aclose(self) -> None:
        await self._inner.aclose()


def scope_guard(arm: str, target: str) -> Callable[[Tool, dict[str, object]], ToolResult | None]:
    """Allow only the fixture and the explicitly selected execution route."""
    def check(tool: Tool, params: dict[str, object]) -> ToolResult | None:
        name = tool.name
        if name in {"read_file", "write_file", "edit_file"}:
            if params.get("path") != target:
                return ToolResult("Fixture path denied.", success=False, error="scope")
            child = current_subagent_actor() not in (None, "tech_lead")
            if name != "read_file" and (child != (arm == "staged")):
                return ToolResult("Fixture execution route denied.", success=False, error="scope")
            return None
        if arm == "staged" and name == "invoke_subagent":
            allowed = {"read_file", "write_file", "edit_file"}
            tools = params.get("tools")
            if (params.get("write_paths") == [target] and isinstance(tools, list)
                    and all(isinstance(item, str) for item in tools) and set(tools) <= allowed):
                return None
        if arm == "staged" and name in {"manage_subagents", "publish_subagent_proposal"}:
            return None
        return ToolResult("Fixture tool denied.", success=False, error="scope")
    return check


def prompt_for(fixture: dict[str, str], arm: str) -> str:
    if arm == "direct":
        return fixture["task"] + " Work directly with the file tools; do not delegate. Report the outcome briefly."
    return (fixture["task"] + " Use the staged child workflow: call invoke_subagent with write_paths "
            f'[{json.dumps(fixture["path"])}] and tools ["read_file", "edit_file", "write_file"]. '
            "Instruct the child to inspect and edit only that file. When the child completes, use "
            "manage_subagents action review, inspect the complete proposal, then call "
            "publish_subagent_proposal with its conversation_id and review_token. Do not edit the file directly. "
            "Report the outcome briefly.")


async def attempt(plan: dict[str, Any], fixture: dict[str, str], arm: str, root: Path) -> dict[str, Any]:
    if resource is None or sys.platform != "linux":
        raise RuntimeError("This comparison requires Linux client RSS accounting")
    started = time.monotonic()
    project = root / "project"
    project.mkdir()
    target = project / fixture["path"]
    target.write_text(fixture["initial"], encoding="utf-8")
    initial_hash = hashlib.sha256(target.read_bytes()).hexdigest()
    prompt = prompt_for(fixture, arm)
    os.chdir(project)
    settings = Settings.model_validate({
        "agents": {"allow_delegation": True, "max_concurrent_delegations": 1,
                   "max_delegation_turns": 8, "max_delegation_retries": 0},
        "usage": {"persistence": "process", "limits": {"max_requests": plan["request_limit"],
                                                         "max_seconds": float(plan["timeout_seconds"])}},
        "operations": {"persistence": "process"},
        "context": {"max_tokens": 16384, "auto_compact": False},
    })
    transport = LocalTransport(plan)
    provider = OpenAICompatibleProvider("local-only", plan["endpoint"] + "/v1", plan["model"], temperature=0)
    await provider._client.close()
    provider._client = AsyncOpenAI(api_key="local-only", base_url=plan["endpoint"] + "/v1", max_retries=0,
        http_client=httpx.AsyncClient(transport=transport, trust_env=False, follow_redirects=False,
                                      timeout=httpx.Timeout(plan["timeout_seconds"], connect=4)))
    registry = ToolRegistry()
    for tool in (ReadFileTool(), WriteFileTool(), EditFileTool()):
        registry.register(tool)
    registry.bind_execution_guard(scope_guard(arm, fixture["path"]))
    for name in ("invoke_subagent", "manage_subagents", "publish_subagent_proposal", "write_file", "edit_file"):
        registry.add_auto_approve_policy(name)
    orch = Orchestrator(provider, tool_registry=registry, settings=settings)
    orch.tech_lead.max_tokens = 2048
    orch.tech_lead.context_window = 16384
    calls: list[dict[str, object]] = []
    outcome, error = "completed", None
    try:
        async def collect() -> None:
            async for event in orch.run(prompt):
                if event.type.value == "tool_call_request":
                    calls.append({"event": "request", "tool": getattr(event.data, "name", None)})
                elif event.type.value == "tool_call_result" and isinstance(event.data, dict):
                    calls.append({"event": "result", "tool": event.data.get("tool_name"),
                                  "success": event.data.get("success")})
                elif event.type.value == "agent_message" and isinstance(event.data, dict):
                    calls.append({"event": "child", "status": event.data.get("status")})
        await asyncio.wait_for(collect(), timeout=plan["timeout_seconds"])
    except BaseException as exc:
        outcome, error = type(exc).__name__, str(exc)[:500]
    finally:
        try:
            await orch.aclose()
        finally:
            await provider._client.close()
    content = target.read_text(encoding="utf-8")
    try:
        same_ast = ast.dump(ast.parse(content), include_attributes=False) == ast.dump(
            ast.parse(fixture["expected"]), include_attributes=False)
    except SyntaxError:
        same_ast = False
    return {"outcome": outcome, "error": error, "completion": orch.last_completion_status.value,
            "transport_attempts": transport.requests, "transport_errors": transport.errors,
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "client_peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "result_sha256": hashlib.sha256(content.encode()).hexdigest(),
            "initial_sha256": initial_hash,
            "task_sha256": hashlib.sha256(fixture["task"].encode()).hexdigest(),
            "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
            "exact_ast": same_ast, "events": calls[:200], "events_truncated": len(calls) > 200}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--arm", choices=("direct", "staged"), required=True)
    parser.add_argument("--root", required=True)
    args = parser.parse_args()
    plan = load_plan(Path(args.plan))
    fixture = next(item for item in plan["fixtures"] if item["id"] == args.case)
    root = Path(args.root).resolve(strict=True)
    result = asyncio.run(attempt(plan, fixture, args.arm, root))
    temporary = root / "worker.json.tmp"
    temporary.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    temporary.replace(root / "worker.json")
    print(json.dumps({"case": args.case, "arm": args.arm, "outcome": result["outcome"],
                      "completion": result["completion"], "exact_ast": result["exact_ast"]}), flush=True)


if __name__ == "__main__":
    main()
