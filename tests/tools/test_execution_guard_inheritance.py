"""Live scoped dispatch must retain every ancestor's deferral authority."""

import asyncio

import pytest

from henchman.tools.access_policy import check_network_access
from henchman.tools.base import ToolResult
from henchman.tools.builtins.web_fetch import WebFetchTool
from henchman.tools.registry import ToolRegistry
from henchman.tools.scoped_registry import ScopedToolRegistry
from henchman.utils.retry import RetryConfig
from tests.tools.test_live_tool_scopes import NamedTool


def scopes():
    parent = ToolRegistry(retry_config=RetryConfig(max_retries=0))
    child = ScopedToolRegistry(parent, None, inherit_auto_approve=True)
    leaf = ScopedToolRegistry(child, None, inherit_auto_approve=True)
    tool = NamedTool("effect")
    parent.register(tool)
    parent.add_auto_approve_policy("effect")
    return parent, child, leaf, tool


@pytest.mark.parametrize("level", [0, 1, 2])
async def test_all_live_ancestor_guards_defer_nested_dispatch(level):
    parent, child, leaf, tool = scopes()
    calls = []
    denied = False

    def guard(candidate, _params):
        calls.append(candidate)
        return ToolResult("held", success=False) if denied else None

    (parent, child, leaf)[level].bind_execution_guard(guard)
    assert (await leaf.execute("effect", {})).success
    denied = True
    assert not (await leaf.execute("effect", {})).success
    assert tool.calls == 1 and calls


async def test_live_guard_replacement_and_removal_apply_without_recreating_scope():
    parent, _, leaf, tool = scopes()
    parent.bind_execution_guard(lambda *_: ToolResult("held", success=False))
    assert not (await leaf.execute("effect", {})).success
    parent.bind_execution_guard(lambda *_: None)
    assert (await leaf.execute("effect", {})).success
    parent.bind_execution_guard(None)
    assert (await leaf.execute("effect", {})).success
    assert tool.calls == 2


async def test_existing_parent_guard_rechecks_after_awaited_approval():
    parent, _, leaf, tool = scopes()
    parent._auto_approve_policies.clear()
    entered, release = asyncio.Event(), asyncio.Event()
    denied = False
    parent.bind_execution_guard(lambda *_: ToolResult("held", success=False) if denied else None)

    async def approve(_request):
        entered.set()
        await release.wait()
        return True

    parent.set_confirmation_handler(approve)
    task = asyncio.create_task(leaf.execute("effect", {}))
    await asyncio.wait_for(entered.wait(), 2)
    denied = True
    release.set()
    assert not (await task).success and tool.calls == 0


async def test_ancestor_guard_rechecks_after_formatter_lock_wait(monkeypatch):
    parent, _, leaf, tool = scopes()
    entered, release = asyncio.Event(), asyncio.Event()
    denied = False
    parent.bind_execution_guard(lambda *_: ToolResult("held", success=False) if denied else None)

    async def run(_tool, _params, invoke, **_kwargs):
        entered.set()
        await release.wait()
        return await invoke()

    monkeypatch.setattr(leaf._effective_formatter, "run", run)
    task = asyncio.create_task(leaf.execute("effect", {}))
    await asyncio.wait_for(entered.wait(), 2)
    denied = True
    release.set()
    assert not (await task).success and tool.calls == 0


async def test_network_lease_rechecks_ancestor_without_duplicate_walk(monkeypatch):
    from henchman.tools.builtins import web_fetch

    parent, child, leaf, _ = scopes()
    parent.register(WebFetchTool())
    parent.add_auto_approve_policy("web_fetch")
    calls = []
    denied = False

    def guard(_tool, _params):
        calls.append("parent")
        return ToolResult("held", success=False) if denied else None

    parent.bind_execution_guard(guard)
    child.bind_execution_guard(lambda *_: calls.append("child"))

    async def fetch(_params):
        nonlocal denied
        calls.clear()
        check_network_access("example.test")
        assert calls == ["child", "parent"]
        denied = True
        check_network_access("example.test")
        pytest.fail("revoked network lease continued")

    monkeypatch.setattr(web_fetch, "_fetch_content_with_aiohttp", fetch)
    assert not (await leaf.execute("web_fetch", {"url": "https://example.test"})).success


async def test_local_denial_short_circuits_parent_guard():
    parent, _, leaf, tool = scopes()
    calls = []
    parent.bind_execution_guard(lambda *_: calls.append("unexpected"))
    leaf.bind_execution_guard(lambda *_: ToolResult("local hold", success=False))
    assert not (await leaf.execute("effect", {})).success
    assert calls == [] and tool.calls == 0
