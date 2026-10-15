"""Tests for BUG-021: REPL Main Loop Does Not Log Exception Tracebacks.

Verifies that repl.py logs exceptions with tracebacks instead of
only printing the error message.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _patch_broken_imports() -> None:
    """Patch broken McpClientProtocol import so the repl module can load."""
    import henchman.mcp.client as mcp_client

    if not hasattr(mcp_client, "McpClientProtocol"):

        class _FakeProtocol:
            pass

        mcp_client.McpClientProtocol = _FakeProtocol  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_repl_logger_exception_on_turn_error() -> None:
    """When _run_agent_with_monitor catches an Exception, logger.exception should be called."""
    import henchman.cli.repl as repl_mod

    provider = MagicMock()
    app = repl_mod.Repl(provider=provider)

    async def empty_stream() -> object:
        return
        yield  # pragma: no cover

    with (
        patch.object(repl_mod, "_run_monitored_task", side_effect=RuntimeError("REPL crash")),
        patch.object(repl_mod, "_cleanup_monitor", new=AsyncMock()),
        patch("henchman.cli.input.KeyMonitor") as mock_monitor_cls,
        patch.object(repl_mod.logger, "exception") as mock_log_exc,
    ):
        mock_monitor = MagicMock()
        mock_monitor.monitor = AsyncMock()
        mock_monitor_cls.return_value = mock_monitor

        await app._run_agent_with_monitor(
            empty_stream(),
            app.agent,
            [],
            "test status",
        )

    mock_log_exc.assert_called_once()


def test_repl_module_has_logger() -> None:
    """The repl module should have a module-level logger."""
    import henchman.cli.repl as repl_mod

    assert hasattr(repl_mod, "logger"), "repl module must have a logger attribute"
    assert repl_mod.logger.name == "henchman.cli.repl", "logger name should match module"
