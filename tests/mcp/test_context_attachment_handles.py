"""Only bounded, captured MCP previews can authorize a local attachment."""

from __future__ import annotations

import pytest

from henchman.mcp.manager import McpManager
from tests.mcp.context_fixture import context_peer


@pytest.mark.parametrize("transport", ["stdio", "streamable_http"])
async def test_handle_uses_detached_capture_once_without_retrieval(tmp_path, transport):
    async with context_peer(tmp_path, transport) as peer:
        manager = McpManager({"source": peer.config})
        session, agent = object(), object()
        try:
            await manager.connect_server("source")
            result = await manager.read_resource("source", "custom://fixture/readme")
            with pytest.raises(ValueError, match="preview"):
                manager.commit_context_preview(result.preview_id, None, None, lambda _value: pytest.fail("unbound"))
            manager.bind_context_preview(result.preview_id, session, agent)
            original = result.payload["contents"][0]["text"]
            result.payload["contents"][0]["text"] = "caller mutation"
            captured = []
            manager.commit_context_preview(result.preview_id, session, agent, captured.append)
            assert captured[0].payload["contents"][0]["text"] == original
            with pytest.raises(ValueError, match="preview"):
                manager.commit_context_preview(result.preview_id, session, agent, captured.append)
            assert len(captured) == 1
            assert sum(item["method"] == "resources/read" for item in peer.requests()) == 1
        finally:
            await manager.disconnect_all()


@pytest.mark.parametrize("change", ["refresh", "reconnect", "credential", "config", "policy", "target"])
async def test_changed_authority_never_commits_captured_data(tmp_path, change):
    async with context_peer(tmp_path) as peer:
        manager = McpManager({"source": peer.config})
        session, agent = object(), object()
        captured = []
        try:
            await manager.connect_server("source")
            await manager.list_prompts("source")
            result = await manager.get_prompt("source", "review", {"code": "original"})
            manager.bind_context_preview(result.preview_id, session, agent)
            if change == "refresh":
                await manager.list_prompts("source")
            elif change == "reconnect":
                await manager.connect_server("source")
            elif change == "credential":
                manager.set_auth_token("source", "changed-private-token")
            elif change == "config":
                manager.configs["source"].trusted = True
            elif change == "policy":
                def deny():
                    raise PermissionError("policy denied")
                manager.clients["source"].set_access_guard(deny)
            else:
                session = object()
            with pytest.raises((ValueError, RuntimeError, PermissionError)):
                manager.commit_context_preview(result.preview_id, session, agent, captured.append)
            assert captured == []
            assert sum(item["method"] == "prompts/get" for item in peer.requests()) == 1
        finally:
            manager.clients.get("source") and manager.clients["source"].set_access_guard(lambda: None)
            await manager.disconnect_all()


async def test_failed_commit_is_retryable_but_nested_commit_is_denied(tmp_path):
    async with context_peer(tmp_path) as peer:
        manager = McpManager({"source": peer.config})
        session, agent = object(), object()
        try:
            await manager.connect_server("source")
            result = await manager.read_resource("source", "custom://fixture/readme")
            manager.bind_context_preview(result.preview_id, session, agent)
            def fail(_result):
                with pytest.raises(ValueError, match="preview"):
                    manager.commit_context_preview(result.preview_id, session, agent, lambda _value: None)
                raise OSError("save failed")
            with pytest.raises(OSError, match="save failed"):
                manager.commit_context_preview(result.preview_id, session, agent, fail)
            captured = []
            manager.commit_context_preview(result.preview_id, session, agent, captured.append)
            assert len(captured) == 1
        finally:
            await manager.disconnect_all()


async def test_handle_count_bytes_expiry_and_unknown_ids_are_bounded(tmp_path, monkeypatch):
    import henchman.mcp.manager as module

    monkeypatch.setattr(module, "MAX_CONTEXT_PREVIEWS", 2, raising=False)
    clock = [0.0]
    monkeypatch.setattr(module, "monotonic", lambda: clock[0], raising=False)
    async with context_peer(tmp_path) as peer:
        manager = McpManager({"source": peer.config})
        session, agent = object(), object()
        try:
            await manager.connect_server("source")
            results = [await manager.read_resource("source", "custom://fixture/readme") for _ in range(3)]
            for identity in ("unknown", results[0].preview_id):
                with pytest.raises(ValueError, match="preview"):
                    manager.bind_context_preview(identity, session, agent)
            manager.bind_context_preview(results[-1].preview_id, session, agent)
            clock[0] = 601
            with pytest.raises(ValueError, match="preview"):
                manager.commit_context_preview(results[-1].preview_id, session, agent, lambda _result: None)
            monkeypatch.setattr(module, "MAX_CONTEXT_PREVIEW_BYTES", 1, raising=False)
            with pytest.raises(ValueError, match="preview"):
                await manager.read_resource("source", "custom://fixture/readme")
        finally:
            await manager.disconnect_all()
