"""Tests for BUG-022: LspService subprocesses orphaned on garbage collection.

Ensures subprocesses are terminated when LspService is cleaned up,
either via explicit stop_all(), class-level cleanup_all(), or __del__ finalizer.
"""

from __future__ import annotations

import gc
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from henchman.lsp.service import LspService


@pytest.fixture(autouse=True)
def clear_runtimes():
    """Clear shared LspService runtimes before and after each test."""
    LspService._runtimes.clear()
    yield
    LspService._runtimes.clear()


@patch("henchman.lsp.service.resolve_project_settings_path")
def test_stop_all_terminates_all_sessions(mock_resolve: MagicMock, tmp_path: Path) -> None:
    """LspService.stop_all must terminate all running server sessions."""
    mock_resolve.return_value = tmp_path
    service = LspService(project_root=tmp_path)

    mock_process_a = MagicMock()
    mock_process_a.returncode = None
    mock_process_b = MagicMock()
    mock_process_b.returncode = None

    # Inject sessions directly
    from henchman.lsp.service import _LspSession
    service._runtime.sessions["server-a"] = _LspSession(process=mock_process_a)
    service._runtime.sessions["server-b"] = _LspSession(process=mock_process_b)

    # Patch stop_server to call terminate synchronously
    with patch.object(service, "stop_server", autospec=True) as mock_stop:
        mock_stop.return_value = None

        import asyncio
        asyncio.run(service.stop_all())

        assert mock_stop.call_count == 2
        assert "server-a" in mock_stop.call_args_list[0].args
        assert "server-b" in mock_stop.call_args_list[1].args


@patch("henchman.lsp.service.resolve_project_settings_path")
def test_cleanup_all_classmethod_terminates_all_runtimes(mock_resolve: MagicMock, tmp_path: Path) -> None:
    """LspService.cleanup_all must terminate ALL sessions across ALL runtimes."""
    mock_resolve.return_value = tmp_path

    mock_process_a = MagicMock()
    mock_process_a.returncode = None
    mock_process_b = MagicMock()
    mock_process_b.returncode = None

    from henchman.lsp.service import _LspRuntime, _LspSession

    # Create two runtimes with sessions
    LspService._runtimes[tmp_path / "runtime1"] = _LspRuntime(
        sessions={"srv1": _LspSession(process=mock_process_a)}
    )
    LspService._runtimes[tmp_path / "runtime2"] = _LspRuntime(
        sessions={"srv2": _LspSession(process=mock_process_b)}
    )

    LspService.cleanup_all()

    # Both processes should have been terminated
    mock_process_a.terminate.assert_called_once()
    mock_process_b.terminate.assert_called_once()

    # Both runtimes should be cleaned up
    assert LspService._runtimes == {}


@patch("henchman.lsp.service.resolve_project_settings_path")
def test_cleanup_all_skips_already_exited_processes(mock_resolve: MagicMock, tmp_path: Path) -> None:
    """cleanup_all must not terminate processes that have already exited."""
    mock_resolve.return_value = tmp_path

    from henchman.lsp.service import _LspRuntime, _LspSession

    mock_running = MagicMock()
    mock_running.returncode = None
    mock_exited = MagicMock()
    mock_exited.returncode = 0  # Already exited

    LspService._runtimes[tmp_path] = _LspRuntime(
        sessions={
            "running": _LspSession(process=mock_running),
            "exited": _LspSession(process=mock_exited),
        }
    )

    LspService.cleanup_all()

    mock_running.terminate.assert_called_once()
    mock_exited.terminate.assert_not_called()


@patch("henchman.lsp.service.resolve_project_settings_path")
def test_del_terminates_subprocesses(mock_resolve: MagicMock, tmp_path: Path) -> None:
    """LspService.__del__ must terminate orphaned subprocesses on GC."""
    mock_resolve.return_value = tmp_path

    mock_process = MagicMock()
    mock_process.returncode = None

    service = LspService(project_root=tmp_path)

    from henchman.lsp.service import _LspSession
    service._runtime.sessions["test-server"] = _LspSession(process=mock_process)

    # Delete reference and trigger GC
    del service
    gc.collect()

    # The process should have been terminated
    mock_process.terminate.assert_called_once()


@patch("henchman.lsp.service.resolve_project_settings_path")
def test_del_skips_if_no_runtime(mock_resolve: MagicMock, tmp_path: Path) -> None:
    """__del__ must not raise when called on a partially-initialized object."""
    mock_resolve.return_value = tmp_path

    # Create service with no runtime
    service = LspService.__new__(LspService)
    # Don't call __init__ — simulate early GC before __init__ completes

    # Should not raise
    del service
    gc.collect()


@patch("henchman.lsp.service.resolve_project_settings_path")
def test_del_skips_already_exited_processes(mock_resolve: MagicMock, tmp_path: Path) -> None:
    """__del__ must not terminate processes that have already exited."""
    mock_resolve.return_value = tmp_path

    mock_process = MagicMock()
    mock_process.returncode = 0  # Already exited

    service = LspService(project_root=tmp_path)

    from henchman.lsp.service import _LspSession
    service._runtime.sessions["test-server"] = _LspSession(process=mock_process)

    del service
    gc.collect()

    mock_process.terminate.assert_not_called()
