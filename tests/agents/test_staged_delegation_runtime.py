"""The live subagent route stages edits until its parent reviews and approves."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest

from henchman.agents.delegation_admission import DelegationAdmission
from henchman.agents.orchestrator import Orchestrator
from henchman.agents.subagents import BackgroundSubagentManager
from henchman.config.schema import Settings
from henchman.providers.base import FinishReason, Message, StreamChunk, ToolCall
from henchman.providers.ollama import OllamaProvider
from henchman.tools.builtins.file_write import WriteFileTool
from henchman.tools.registry import ToolRegistry


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", ["publish", "conflict", "child_error", "plan_change", "read_policy", "stale"])
async def test_dynamic_child_stages_and_parent_acknowledges_before_publish(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, outcome: str,
) -> None:
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "file.py"
    path.write_text("value = 1\n")
    seen_staged = False

    async def stream(messages: list[Message], **kwargs: Any) -> AsyncIterator[StreamChunk]:
        nonlocal seen_staged
        del kwargs
        if (messages[0].content or "").startswith("staged child\n\n"):
            results = [item for item in messages if item.role == "tool"]
            if not results:
                yield StreamChunk(tool_calls=[ToolCall(
                    id="child-write", name="write_file",
                    arguments={"path": "file.py", "content": "value = 2\n"},
                )], finish_reason=FinishReason.TOOL_CALLS)
            elif outcome == "child_error" and len(results) == 1:
                yield StreamChunk(tool_calls=[ToolCall(
                    id="child-invalid", name="write_file",
                    arguments={"path": "outside.py", "content": "must not be written"},
                )], finish_reason=FinishReason.TOOL_CALLS)
            else:
                assert path.read_text() == "value = 1\n"
                seen_staged = True
                yield StreamChunk(content="Staged the change.", finish_reason=FinishReason.STOP)
            return
        if any(item.tool_call_id == "published" for item in messages):
            published = next(item for item in messages if item.tool_call_id == "published")
            if outcome == "conflict":
                assert "conflict" in (published.content or "").lower()
            if outcome == "plan_change":
                assert "plan mode" in (published.content or "").lower()
            yield StreamChunk(content="Reviewed and published.", finish_reason=FinishReason.STOP)
            return
        reviewed = next((item for item in messages if item.tool_call_id == "review"), None)
        if reviewed is not None:
            if outcome == "child_error":
                assert "unsuccessful" in (reviewed.content or "").lower()
                yield StreamChunk(content="Child work cannot be published.", finish_reason=FinishReason.STOP)
                return
            preview = json.loads(reviewed.content or "")
            assert preview["review"]["files"][0]["after"]["content"] == "value = 2\n"
            assert path.read_text() == "value = 1\n"
            if outcome == "conflict":
                path.write_text("user change\n")
            if outcome == "plan_change":
                registry.set_plan_mode(enabled=True)
            yield StreamChunk(tool_calls=[ToolCall(
                id="published", name="publish_subagent_proposal",
                arguments={"conversation_id": preview["conversation_id"],
                           "review_token": preview["review_token"]},
            )], finish_reason=FinishReason.TOOL_CALLS)
            return
        last = messages[-1]
        if last.role == "user" and "Background subagent updates" in (last.content or ""):
            if outcome == "stale":
                yield StreamChunk(content="Leaving the proposal unresolved.", finish_reason=FinishReason.STOP)
                return
            updates = json.loads((last.content or "").split("\n")[1])
            yield StreamChunk(tool_calls=[ToolCall(
                id="review", name="manage_subagents",
                arguments={"action": "review", "conversation_id": updates[0]["conversation_id"]},
            )], finish_reason=FinishReason.TOOL_CALLS)
            return
        if not any(item.tool_call_id == "launch" for item in messages):
            yield StreamChunk(tool_calls=[ToolCall(
                id="launch", name="invoke_subagent",
                arguments={"task": "Change the value", "role": "editor", "system_prompt": "staged child",
                           "tools": ["write_file"], "write_paths": ["file.py"]},
            )], finish_reason=FinishReason.TOOL_CALLS)
            return
        yield StreamChunk(content="Waiting for the child.", finish_reason=FinishReason.STOP)

    provider = OllamaProvider()
    monkeypatch.setattr(provider, "chat_completion_stream", stream)
    registry = ToolRegistry()
    registry.register(WriteFileTool())
    if outcome == "read_policy":
        registry.set_read_confirmation_required(True)
    for name in ("invoke_subagent", "manage_subagents", "publish_subagent_proposal", "write_file"):
        registry.add_auto_approve_policy(name)
    orch = Orchestrator(provider, tool_registry=registry,
                        settings=Settings.model_validate({"agents": {"allow_delegation": True}}))
    try:
        await asyncio.wait_for(_collect(orch), 8)
        assert seen_staged is (outcome != "read_policy")
        expected = {"publish": "value = 2\n", "conflict": "user change\n", "child_error": "value = 1\n",
                    "plan_change": "value = 1\n", "read_policy": "value = 1\n", "stale": "value = 1\n"}
        assert path.read_text() == expected[outcome]
        assert not (tmp_path / "outside.py").exists()
        if outcome == "read_policy":
            assert not (tmp_path / ".henchman/tungsten/proposals").exists()
        if outcome == "stale":
            child = orch.subagents.list()[0]
            with pytest.raises(RuntimeError):
                await orch.subagents.review_staged(child.conversation_id)
    finally:
        await orch.aclose()


async def _collect(orch: Orchestrator) -> None:
    async for _event in orch.run("Change the file through a reviewed child"):
        pass


async def test_staged_request_rejects_opaque_tools_before_creating_child() -> None:
    def factory(*_args: object) -> object:
        raise AssertionError("Invalid staged scope must not create a child")

    async def runner(*_args: object) -> AsyncIterator[Any]:
        if False:
            yield None

    manager = BackgroundSubagentManager(
        factory, runner, available_tools=lambda _actor: ["shell"],
        admission=DelegationAdmission(allowed=True), staged_factory=factory,
    )
    with pytest.raises(ValueError, match="scoped file tools"):
        manager.spawn("edit", role="editor", system_prompt="edit", tools=["shell"], write_paths=["file.py"])
    assert not manager.list()
    await manager.close()


async def test_failed_worker_binding_cancels_before_dispatch_and_retains_capacity_until_joined() -> None:
    aborted = False

    class RefusedStage:
        def bind(self, _worker: asyncio.Task[Any]) -> None:
            raise RuntimeError("binding failed")

        def abort(self) -> None:
            nonlocal aborted
            aborted = True

    async def runner(*_args: object) -> AsyncIterator[Any]:
        raise AssertionError("Unbound worker must not execute")
        yield None

    admission = DelegationAdmission(limit=1, allowed=True)
    manager = BackgroundSubagentManager(
        lambda *_args: object(), runner, available_tools=lambda _actor: ["write_file"],
        admission=admission, staged_factory=lambda *_args: RefusedStage(),
    )
    with pytest.raises(RuntimeError, match="binding failed"):
        manager.spawn("edit", role="editor", system_prompt="edit", tools=["write_file"], write_paths=["file.py"])
    assert aborted and admission.active == 1
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    assert admission.active == 0
    assert not manager.list()
    await manager.close()


async def test_eager_worker_waits_for_staged_binding() -> None:
    eager = getattr(asyncio, "eager_task_factory", None)
    if eager is None:
        pytest.skip("The eager task factory requires Python 3.12 or newer")
    started = asyncio.Event()
    hold = asyncio.Event()

    class Stage:
        bound = False
        activated = False

        def bind(self, worker: asyncio.Task[Any]) -> None:
            assert not self.activated and not worker.done()
            self.bound = True

        def activate(self, _agent: object) -> None:
            assert self.bound
            self.activated = True

        async def close(self) -> None:
            pass

    stage = Stage()

    async def runner(*_args: object) -> AsyncIterator[Any]:
        assert stage.activated
        started.set()
        await hold.wait()
        yield None

    manager = BackgroundSubagentManager(
        lambda *_args: object(), runner, available_tools=lambda _actor: ["write_file"],
        admission=DelegationAdmission(allowed=True), staged_factory=lambda *_args: stage,
    )
    loop = asyncio.get_running_loop()
    previous = loop.get_task_factory()
    loop.set_task_factory(eager)
    try:
        record = manager.spawn("edit", role="editor", system_prompt="edit",
                               tools=["write_file"], write_paths=["file.py"])
        await asyncio.wait_for(started.wait(), 3)
        await manager.cancel(record.conversation_id)
        assert manager.admission.active == 0
    finally:
        loop.set_task_factory(previous)
        await manager.close()


async def test_cancelling_staged_child_joins_worker_without_publishing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "file.py"
    path.write_text("before\n")
    staged = asyncio.Event()
    hold = asyncio.Event()

    async def stream(messages: list[Message], **_kwargs: Any) -> AsyncIterator[StreamChunk]:
        if (messages[0].content or "").startswith("cancel child\n\n"):
            if not any(item.role == "tool" for item in messages):
                yield StreamChunk(tool_calls=[ToolCall(
                    id="child-write", name="write_file", arguments={"path": "file.py", "content": "after\n"},
                )], finish_reason=FinishReason.TOOL_CALLS)
            else:
                staged.set()
                await hold.wait()
            return
        if not any(item.tool_call_id == "launch" for item in messages):
            yield StreamChunk(tool_calls=[ToolCall(
                id="launch", name="invoke_subagent",
                arguments={"task": "Change the value", "role": "editor", "system_prompt": "cancel child",
                           "tools": ["write_file"], "write_paths": ["file.py"]},
            )], finish_reason=FinishReason.TOOL_CALLS)
        else:
            yield StreamChunk(content="Waiting.", finish_reason=FinishReason.STOP)

    provider = OllamaProvider()
    monkeypatch.setattr(provider, "chat_completion_stream", stream)
    registry = ToolRegistry()
    registry.register(WriteFileTool())
    registry.add_auto_approve_policy("invoke_subagent")
    registry.add_auto_approve_policy("write_file")
    orch = Orchestrator(provider, tool_registry=registry,
                        settings=Settings.model_validate({"agents": {"allow_delegation": True}}))
    run = asyncio.create_task(_collect(orch))
    try:
        await asyncio.wait_for(staged.wait(), 8)
        child = orch.subagents.list()[0]
        result = await orch.subagents.cancel(child.conversation_id)
        assert result.cancelled
        assert orch.subagents.admission.active == 0
        assert path.read_text() == "before\n"
    finally:
        run.cancel()
        await asyncio.gather(run, return_exceptions=True)
        await orch.aclose()


async def test_overlapping_dynamic_children_cannot_overwrite_one_another(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "file.py"
    path.write_text("original\n")
    started: set[str] = set()
    both_started = asyncio.Event()
    updates: list[str] = []
    first_content = ""

    async def stream(messages: list[Message], **_kwargs: Any) -> AsyncIterator[StreamChunk]:
        nonlocal first_content
        system = messages[0].content or ""
        if system.startswith("parallel child "):
            label = system.split("\n", 1)[0].removeprefix("parallel child ")
            if not any(item.role == "tool" for item in messages):
                started.add(label)
                if len(started) == 2:
                    both_started.set()
                await both_started.wait()
                yield StreamChunk(tool_calls=[ToolCall(
                    id=f"write-{label}", name="write_file",
                    arguments={"path": "file.py", "content": f"{label}\n"},
                )], finish_reason=FinishReason.TOOL_CALLS)
            else:
                yield StreamChunk(content=f"Staged {label}.", finish_reason=FinishReason.STOP)
            return
        results = {item.tool_call_id: item for item in messages if item.role == "tool"}
        if "publish-2" in results:
            assert "conflict" in (results["publish-2"].content or "").lower()
            yield StreamChunk(content="The second proposal conflicted.", finish_reason=FinishReason.STOP)
            return
        if "review-2" in results:
            review = json.loads(results["review-2"].content or "")
            yield StreamChunk(tool_calls=[ToolCall(
                id="publish-2", name="publish_subagent_proposal",
                arguments={"conversation_id": review["conversation_id"],
                           "review_token": review["review_token"]},
            )], finish_reason=FinishReason.TOOL_CALLS)
            return
        if "publish-1" in results:
            yield StreamChunk(tool_calls=[ToolCall(
                id="review-2", name="manage_subagents", arguments={"action": "review", "conversation_id": updates[1]},
            )], finish_reason=FinishReason.TOOL_CALLS)
            return
        if "review-1" in results:
            review = json.loads(results["review-1"].content or "")
            first_content = review["review"]["files"][0]["after"]["content"]
            yield StreamChunk(tool_calls=[ToolCall(
                id="publish-1", name="publish_subagent_proposal",
                arguments={"conversation_id": review["conversation_id"],
                           "review_token": review["review_token"]},
            )], finish_reason=FinishReason.TOOL_CALLS)
            return
        last = messages[-1]
        if last.role == "user" and "Background subagent updates" in (last.content or ""):
            for item in json.loads((last.content or "").split("\n")[1]):
                if item["conversation_id"] not in updates:
                    updates.append(item["conversation_id"])
            if len(updates) == 2:
                yield StreamChunk(tool_calls=[ToolCall(
                    id="review-1", name="manage_subagents", arguments={"action": "review", "conversation_id": updates[0]},
                )], finish_reason=FinishReason.TOOL_CALLS)
            else:
                yield StreamChunk(content="Waiting for both children.", finish_reason=FinishReason.STOP)
            return
        if "launch-a" not in results:
            yield StreamChunk(tool_calls=[ToolCall(
                id=f"launch-{label}", name="invoke_subagent",
                arguments={"task": "Edit the file", "role": "editor", "system_prompt": f"parallel child {label}",
                           "tools": ["write_file"], "write_paths": ["file.py"]},
            ) for label in ("a", "b")], finish_reason=FinishReason.TOOL_CALLS)
            return
        yield StreamChunk(content="Waiting for both children.", finish_reason=FinishReason.STOP)

    provider = OllamaProvider()
    monkeypatch.setattr(provider, "chat_completion_stream", stream)
    registry = ToolRegistry()
    registry.register(WriteFileTool())
    for name in ("invoke_subagent", "manage_subagents", "publish_subagent_proposal", "write_file"):
        registry.add_auto_approve_policy(name)
    orch = Orchestrator(provider, tool_registry=registry,
                        settings=Settings.model_validate({"agents": {"allow_delegation": True}}))
    try:
        await asyncio.wait_for(_collect(orch), 12)
        assert first_content in {"a\n", "b\n"}
        assert path.read_text() == first_content
    finally:
        await orch.aclose()
