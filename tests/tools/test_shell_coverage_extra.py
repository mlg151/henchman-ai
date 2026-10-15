"""Additional tests for shell.py — targets missing coverage lines.

These tests complement the existing test_shell_tool.py,
test_shell_advanced.py, test_shell_interactive.py, and
test_shell_sudo_logic.py files.
"""

from __future__ import annotations

import asyncio
import contextlib
import errno as errno_module
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from henchman.tools.base import ToolResult
from henchman.tools.builtins.shell import (
    MAX_OUTPUT_CHARS,
    ShellParams,
    ShellTool,
    _drain_pty,
    _drain_readers,
    _force_close_pipes,
    _format_output,
    _handle_pty_io,
    _handle_pty_read,
    _handle_pty_stdin_write,
    _is_process_dead,
    _reap_process,
    _run_sudo_with_pty,
)

# ---------------------------------------------------------------------------
# _format_output  (line 162 — truncation branch)
# ---------------------------------------------------------------------------


class TestFormatOutput:
    """Tests for _format_output."""

    def test_output_truncated_when_exceeds_max_chars(self) -> None:
        """Output is truncated when it exceeds MAX_OUTPUT_CHARS."""
        long_text = "x" * (MAX_OUTPUT_CHARS + 100)
        result = _format_output(long_text, "")
        assert len(result) > MAX_OUTPUT_CHARS  # includes the suffix message
        assert "truncated" in result
        assert str(MAX_OUTPUT_CHARS) in result

    def test_output_not_truncated_when_within_limit(self) -> None:
        """Short output is returned unchanged."""
        result = _format_output("hello", "world")
        assert "hello" in result
        assert "world" in result
        assert "truncated" not in result

    def test_no_output_returns_placeholder(self) -> None:
        """Empty stdout and stderr return '(no output)'."""
        result = _format_output("", "")
        assert result == "(no output)"

    def test_only_stderr_included(self) -> None:
        """Stderr-only output is returned."""
        result = _format_output("", "error message")
        assert "error message" in result


# ---------------------------------------------------------------------------
# _is_process_dead  (lines 260-261 — generic Exception branch)
# ---------------------------------------------------------------------------


class TestIsProcessDead:
    """Tests for _is_process_dead."""

    def test_returns_true_for_nonexistent_pid(self) -> None:
        """Returns True for a PID that doesn't exist."""
        result = _is_process_dead(999999999)
        assert result is True

    def test_returns_false_for_current_process(self) -> None:
        """Returns False for the current (alive) process."""
        import os
        result = _is_process_dead(os.getpid())
        assert result is False

    def test_handles_generic_exception(self) -> None:
        """Returns False when an unexpected exception occurs reading /proc."""
        with patch("builtins.open", side_effect=PermissionError("denied")):
            result = _is_process_dead(1234)
            assert result is False


# ---------------------------------------------------------------------------
# _force_close_pipes  (lines 289, 292->290, 294-295)
# ---------------------------------------------------------------------------


class TestForceClosePipes:
    """Tests for _force_close_pipes."""

    def test_handles_none_transport(self) -> None:
        """Returns early when process._transport is None."""
        mock_process = MagicMock()
        mock_process._transport = None
        _force_close_pipes(mock_process)  # Should not raise

    def test_closes_open_pipe_transports(self) -> None:
        """Closes pipe transports when they exist."""
        mock_pipe = MagicMock()
        mock_transport = MagicMock()
        mock_transport.get_pipe_transport.return_value = mock_pipe
        mock_process = MagicMock()
        mock_process._transport = mock_transport
        _force_close_pipes(mock_process)
        assert mock_pipe.close.call_count >= 1

    def test_handles_none_pipe_transport(self) -> None:
        """Skips closing when get_pipe_transport returns None."""
        mock_transport = MagicMock()
        mock_transport.get_pipe_transport.return_value = None
        mock_process = MagicMock()
        mock_process._transport = mock_transport
        _force_close_pipes(mock_process)  # Should not raise

    def test_handles_exception_during_close(self) -> None:
        """Silently handles exceptions raised during pipe closing."""
        mock_process = MagicMock()
        mock_process._transport = MagicMock(side_effect=Exception("fail"))
        # _transport itself raises when accessed
        type(mock_process)._transport = property(
            lambda _self: (_ for _ in ()).throw(Exception("fail"))  # noqa: E731
        )
        _force_close_pipes(mock_process)  # Should not raise


# ---------------------------------------------------------------------------
# _reap_process  (lines 306-308 — asyncio.TimeoutError branch)
# ---------------------------------------------------------------------------


class TestReapProcess:
    """Tests for _reap_process."""

    @pytest.mark.anyio
    async def test_reap_kills_on_timeout(self) -> None:
        """Kills the process when reaping times out."""
        mock_process = AsyncMock()
        mock_process.wait = AsyncMock(side_effect=asyncio.TimeoutError)
        mock_process.kill = MagicMock()
        await _reap_process(mock_process)
        mock_process.kill.assert_called_once()

    @pytest.mark.anyio
    async def test_reap_kills_handles_process_lookup_error(self) -> None:
        """Handles ProcessLookupError when killing during reap timeout."""
        mock_process = AsyncMock()
        mock_process.wait = AsyncMock(side_effect=asyncio.TimeoutError)
        mock_process.kill = MagicMock(side_effect=ProcessLookupError)
        await _reap_process(mock_process)  # Should not raise

    @pytest.mark.anyio
    async def test_reap_succeeds_normally(self) -> None:
        """Reaps successfully when process exits within timeout."""
        mock_process = AsyncMock()
        mock_process.wait = AsyncMock(return_value=0)
        await _reap_process(mock_process)  # Should not raise
        mock_process.wait.assert_called_once()


# ---------------------------------------------------------------------------
# _drain_readers  (exception branch already covered by other tests,
#                  but let's ensure the timeout/exception path is covered)
# ---------------------------------------------------------------------------


class TestDrainReaders:
    """Tests for _drain_readers."""

    @pytest.mark.anyio
    async def test_returns_true_when_readers_finish(self) -> None:
        """Returns True when all reader tasks complete within timeout."""
        async def fast_reader() -> None:
            await asyncio.sleep(0)

        task = asyncio.create_task(fast_reader())
        result = await _drain_readers(task)
        assert result is True

    @pytest.mark.anyio
    async def test_returns_false_on_timeout(self) -> None:
        """Returns False when readers time out."""
        async def slow_reader() -> None:
            await asyncio.sleep(100)

        task = asyncio.create_task(slow_reader())
        with patch("henchman.tools.builtins.shell._DRAIN_TIMEOUT", 0.01):
            result = await _drain_readers(task)
        assert result is False
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


# ---------------------------------------------------------------------------
# PTY helpers  (lines 412-472)
# ---------------------------------------------------------------------------


class TestDrainPty:
    """Tests for _drain_pty."""

    def test_reads_data_until_eof(self) -> None:
        """Reads chunks until empty bytes received."""
        read_calls = [b"chunk1", b"chunk2", b""]
        accumulator: list[str] = []
        with patch("os.read", side_effect=read_calls):
            _drain_pty(99, accumulator)
        assert "chunk1" in accumulator
        assert "chunk2" in accumulator

    def test_handles_oserror(self) -> None:
        """Silently handles OSError during drain."""
        accumulator: list[str] = []
        with patch("os.read", side_effect=OSError("EIO")):
            _drain_pty(99, accumulator)  # Should not raise

    def test_appends_decoded_chunks(self) -> None:
        """Decoded chunks are appended to accumulator."""
        accumulator: list[str] = []
        with patch("os.read", side_effect=[b"hello", b""]):
            _drain_pty(99, accumulator)
        assert accumulator == ["hello"]


class TestHandlePtyRead:
    """Tests for _handle_pty_read."""

    def test_reads_chunk_and_writes_to_stdout(self) -> None:
        """Reads a chunk and writes it to stdout."""
        accumulator: list[str] = []
        with (
            patch("os.read", return_value=b"output data"),
            patch("sys.stdout") as mock_stdout,
        ):
            _handle_pty_read(99, accumulator)
        assert "output data" in accumulator
        mock_stdout.write.assert_called_once_with("output data")
        mock_stdout.flush.assert_called_once()

    def test_returns_early_on_empty_chunk(self) -> None:
        """Returns early when no data is read."""
        accumulator: list[str] = []
        with patch("os.read", return_value=b""):
            _handle_pty_read(99, accumulator)
        assert accumulator == []

    def test_handles_eio_error(self) -> None:
        """Silently handles EIO errors (normal PTY EOF)."""
        accumulator: list[str] = []
        eio_error = OSError()
        eio_error.errno = errno_module.EIO
        with patch("os.read", side_effect=eio_error):
            _handle_pty_read(99, accumulator)  # Should not raise
        assert accumulator == []

    def test_raises_non_eio_oserror(self) -> None:
        """Re-raises non-EIO OSErrors."""
        accumulator: list[str] = []
        perm_error = OSError()
        perm_error.errno = errno_module.EACCES
        with patch("os.read", side_effect=perm_error), pytest.raises(OSError):
            _handle_pty_read(99, accumulator)


class TestHandlePtyStdinWrite:
    """Tests for _handle_pty_stdin_write."""

    def test_forwards_stdin_data(self) -> None:
        """Reads from stdin and writes to master_fd."""
        with (
            patch("os.read", return_value=b"input data"),
            patch("os.write") as mock_write,
            patch("sys.stdin") as mock_stdin,
        ):
            mock_stdin.fileno.return_value = 0
            _handle_pty_stdin_write(99)
        mock_write.assert_called_once_with(99, b"input data")

    def test_no_write_when_empty_stdin(self) -> None:
        """Does not write when stdin returns empty bytes."""
        with (
            patch("os.read", return_value=b""),
            patch("os.write") as mock_write,
            patch("sys.stdin") as mock_stdin,
        ):
            mock_stdin.fileno.return_value = 0
            _handle_pty_stdin_write(99)
        mock_write.assert_not_called()

    def test_handles_oserror(self) -> None:
        """Silently handles OSError."""
        with (
            patch("os.read", side_effect=OSError("broken pipe")),
            patch("sys.stdin") as mock_stdin,
        ):
            mock_stdin.fileno.return_value = 0
            _handle_pty_stdin_write(99)  # Should not raise


class TestHandlePtyIo:
    """Tests for _handle_pty_io."""

    def test_reads_when_master_fd_ready(self) -> None:
        """Calls _handle_pty_read when master_fd is in ready list."""
        master_fd = 99
        accumulator: list[str] = []
        with patch(
            "henchman.tools.builtins.shell._handle_pty_read"
        ) as mock_read, patch(
            "henchman.tools.builtins.shell._handle_pty_stdin_write"
        ) as mock_write:
            _handle_pty_io(master_fd, [master_fd], accumulator)
        mock_read.assert_called_once_with(master_fd, accumulator)
        mock_write.assert_not_called()

    def test_writes_when_stdin_ready(self) -> None:
        """Calls _handle_pty_stdin_write when sys.stdin is in ready list."""
        master_fd = 99
        accumulator: list[str] = []
        with patch(
            "henchman.tools.builtins.shell._handle_pty_read"
        ) as mock_read, patch(
            "henchman.tools.builtins.shell._handle_pty_stdin_write"
        ) as mock_write:
            _handle_pty_io(master_fd, [sys.stdin], accumulator)
        mock_read.assert_not_called()
        mock_write.assert_called_once_with(master_fd)

    def test_both_read_and_write_when_both_ready(self) -> None:
        """Calls both helpers when both fd and stdin are ready."""
        master_fd = 99
        accumulator: list[str] = []
        with patch(
            "henchman.tools.builtins.shell._handle_pty_read"
        ) as mock_read, patch(
            "henchman.tools.builtins.shell._handle_pty_stdin_write"
        ) as mock_write:
            _handle_pty_io(master_fd, [master_fd, sys.stdin], accumulator)
        mock_read.assert_called_once()
        mock_write.assert_called_once()

    def test_no_action_when_nothing_ready(self) -> None:
        """Does nothing when neither fd nor stdin is in ready list."""
        master_fd = 99
        accumulator: list[str] = []
        with patch(
            "henchman.tools.builtins.shell._handle_pty_read"
        ) as mock_read, patch(
            "henchman.tools.builtins.shell._handle_pty_stdin_write"
        ) as mock_write:
            _handle_pty_io(master_fd, [], accumulator)
        mock_read.assert_not_called()
        mock_write.assert_not_called()


# ---------------------------------------------------------------------------
# _run_sudo_with_pty  (lines 484-555)
# ---------------------------------------------------------------------------


class TestRunSudoWithPty:
    """Tests for _run_sudo_with_pty."""

    def _make_params(
        self,
        command: str = "sudo echo test",
        timeout: float | None = None,
    ) -> ShellParams:
        return ShellParams(
            command=command,
            env={"HENCHMAN_CLI": "1"},
            cwd=None,
            timeout=timeout,
        )

    @pytest.mark.anyio
    async def test_returns_error_on_exception(self) -> None:
        """Returns ToolResult with error when an exception occurs."""
        params = self._make_params()
        with patch("pty.openpty", side_effect=OSError("no pty")):
            result = await _run_sudo_with_pty(params)
        assert result.success is False
        assert "error" in result.content.lower() or "no pty" in result.content

    @pytest.mark.anyio
    async def test_successful_pty_execution(self) -> None:
        """Successfully executes a command via PTY."""
        params = self._make_params()

        mock_process = MagicMock()
        # returncode returns 0 on first access (process already done)
        mock_process.returncode = 0
        mock_process.wait = AsyncMock(return_value=0)
        mock_process.kill = MagicMock()

        with (
            patch("pty.openpty", return_value=(10, 11)),
            patch("os.setsid"),
            patch("asyncio.create_subprocess_shell", return_value=mock_process),
            patch("os.close"),
            patch("fcntl.fcntl", return_value=0),
            patch("sys.stdin") as mock_stdin,
            patch("termios.tcgetattr", return_value=[]),
            patch("termios.tcsetattr"),
            patch("tty.setraw"),
            patch("select.select", return_value=([], [], [])),
            patch("henchman.tools.builtins.shell._drain_pty"),
            patch("henchman.tools.builtins.shell._handle_pty_io"),
            patch("asyncio.get_running_loop") as mock_get_loop,
        ):
            mock_stdin.fileno.return_value = 0
            mock_loop = MagicMock()
            mock_loop.time.return_value = 0.0
            mock_get_loop.return_value = mock_loop
            result = await _run_sudo_with_pty(params)
        assert isinstance(result, ToolResult)

    @pytest.mark.anyio
    async def test_pty_timeout_kills_process(self) -> None:
        """Process is killed when PTY command times out."""
        params = self._make_params(timeout=0.01)

        mock_process = MagicMock()
        mock_process.returncode = None
        mock_process.kill = MagicMock()
        mock_process.wait = AsyncMock(return_value=None)

        loop_time = [0.0]

        def fake_time() -> float:
            loop_time[0] += 0.1
            return loop_time[0]

        mock_loop = MagicMock()
        mock_loop.time = fake_time

        with (
            patch("pty.openpty", return_value=(10, 11)),
            patch("os.setsid"),
            patch("asyncio.create_subprocess_shell", return_value=mock_process),
            patch("os.close"),
            patch("fcntl.fcntl", return_value=0),
            patch("sys.stdin") as mock_stdin,
            patch("termios.tcgetattr", return_value=[]),
            patch("termios.tcsetattr"),
            patch("tty.setraw"),
            patch("asyncio.get_running_loop", return_value=mock_loop),
            patch("select.select", return_value=([], [], [])),
        ):
            mock_stdin.fileno.return_value = 0
            result = await _run_sudo_with_pty(params)
        assert result.success is False
        assert "timeout" in result.content.lower() or "timeout" in (result.error or "").lower()
        mock_process.kill.assert_called()

    @pytest.mark.anyio
    async def test_pty_output_truncated_when_too_long(self) -> None:
        """PTY output is truncated when it exceeds MAX_OUTPUT_CHARS."""
        params = self._make_params()

        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.wait = AsyncMock(return_value=0)
        mock_process.kill = MagicMock()

        long_output = "x" * (MAX_OUTPUT_CHARS + 500)

        def fake_drain_pty(_fd: int, accumulator: list[str]) -> None:
            accumulator.append(long_output)

        with (
            patch("pty.openpty", return_value=(10, 11)),
            patch("os.setsid"),
            patch("asyncio.create_subprocess_shell", return_value=mock_process),
            patch("os.close"),
            patch("fcntl.fcntl", return_value=0),
            patch("sys.stdin") as mock_stdin,
            patch("termios.tcgetattr", return_value=[]),
            patch("termios.tcsetattr"),
            patch("tty.setraw"),
            patch("asyncio.get_running_loop") as mock_get_loop,
            patch("select.select", return_value=([], [], [])),
            patch(
                "henchman.tools.builtins.shell._drain_pty",
                side_effect=fake_drain_pty,
            ),
        ):
            mock_stdin.fileno.return_value = 0
            mock_loop = MagicMock()
            mock_loop.time.return_value = 0.0
            mock_get_loop.return_value = mock_loop
            result = await _run_sudo_with_pty(params)
        assert "truncated" in result.content


# ---------------------------------------------------------------------------
# ShellTool._execute_interactive_sudo  (line 614)
# ---------------------------------------------------------------------------


class TestShellToolExecuteInteractiveSudo:
    """Tests for ShellTool._execute_interactive_sudo."""

    @pytest.mark.anyio
    async def test_delegates_to_run_sudo_with_pty(self) -> None:
        """_execute_interactive_sudo calls _run_sudo_with_pty."""
        tool = ShellTool()
        params = ShellParams(
            command="sudo echo test",
            env={"HENCHMAN_CLI": "1"},
            cwd=None,
            timeout=60.0,
        )
        mock_result = ToolResult(content="output", success=True, error=None)
        with patch(
            "henchman.tools.builtins.shell._run_sudo_with_pty",
            return_value=mock_result,
        ) as mock_pty:
            result = await tool._execute_interactive_sudo(params)
        mock_pty.assert_called_once_with(params)
        assert result is mock_result


# ---------------------------------------------------------------------------
# ShellTool.execute  (lines 664-665 — command validation failure)
# ---------------------------------------------------------------------------


class TestShellToolExecuteValidation:
    """Tests for ShellTool.execute security validation failure paths."""

    @pytest.mark.anyio
    async def test_command_injection_returns_error(self) -> None:
        """CommandInjectionError in sanitize_command returns error result."""
        tool = ShellTool()
        # Backtick substitution triggers CommandInjectionError
        result = await tool.execute(background=False, command="echo `id`")
        assert result.success is False
        assert "Security validation failed" in result.content

    @pytest.mark.anyio
    async def test_empty_command_returns_error(self) -> None:
        """Empty command triggers ValueError and returns error result."""
        tool = ShellTool()
        result = await tool.execute(background=False, command="")
        assert result.success is False
        assert "Security validation failed" in result.content

    @pytest.mark.anyio
    async def test_execute_interactive_when_tty_and_sudo(self) -> None:
        """Uses interactive path when stdin is a TTY and command is sudo."""
        tool = ShellTool()
        mock_result = ToolResult(content="sudo output", success=True, error=None)
        with (
            patch("sys.stdin") as mock_stdin,
            patch.object(tool, "_execute_interactive_sudo", return_value=mock_result) as mock_exec,
        ):
            mock_stdin.isatty.return_value = True
            result = await tool.execute(background=False, command="sudo echo test")
        mock_exec.assert_called_once()
        assert result.success is True
        assert result.content == "sudo output"

    @pytest.mark.anyio
    async def test_execute_interactive_when_interactive_kwarg_and_tty(self) -> None:
        """Uses interactive path when interactive=True and stdin is a TTY."""
        tool = ShellTool()
        mock_result = ToolResult(content="interactive output", success=True, error=None)
        with (
            patch("sys.stdin") as mock_stdin,
            patch.object(tool, "_execute_interactive_sudo", return_value=mock_result) as mock_exec,
        ):
            mock_stdin.isatty.return_value = True
            result = await tool.execute(background=False, command="echo test", interactive=True)
        mock_exec.assert_called_once()
        assert result is mock_result


# ---------------------------------------------------------------------------
# _run_sudo_with_pty — select/handle_pty_io branch (lines 527-533)
# Test when process.returncode is None on first pass (loop iterates once)
# ---------------------------------------------------------------------------


class TestRunSudoWithPtyLoopIteration:
    """Tests that cover the PTY I/O loop select/handle iteration."""

    @pytest.mark.anyio
    async def test_pty_loop_iterates_once_before_process_exits(self) -> None:
        """PTY loop runs select/handle iteration when returncode is None first."""
        from henchman.tools.builtins.shell import ShellParams

        params = ShellParams(
            command="sudo echo hi",
            env={"HENCHMAN_CLI": "1"},
            cwd=None,
            timeout=None,
        )

        mock_process = MagicMock()
        # Return None on first access, then 0 — simulates process finishing
        rc_values = [None, 0]

        def get_rc(_self: object) -> int | None:
            if rc_values:
                return rc_values.pop(0)
            return 0

        type(mock_process).returncode = property(get_rc)
        mock_process.wait = AsyncMock(return_value=0)
        mock_process.kill = MagicMock()

        with (
            patch("pty.openpty", return_value=(10, 11)),
            patch("os.setsid"),
            patch("asyncio.create_subprocess_shell", return_value=mock_process),
            patch("os.close"),
            patch("fcntl.fcntl", return_value=0),
            patch("sys.stdin") as mock_stdin,
            patch("termios.tcgetattr", return_value=[]),
            patch("termios.tcsetattr"),
            patch("tty.setraw"),
            patch("asyncio.get_running_loop") as mock_get_loop,
            patch("select.select", return_value=([], [], [])) as mock_select,
            patch("henchman.tools.builtins.shell._drain_pty"),
            patch("henchman.tools.builtins.shell._handle_pty_io") as mock_handle_io,
        ):
            mock_stdin.fileno.return_value = 0
            mock_loop = MagicMock()
            mock_loop.time.return_value = 0.0
            mock_get_loop.return_value = mock_loop
            result = await _run_sudo_with_pty(params)

        # Both select and handle_pty_io were called (the loop ran at least once)
        assert mock_select.called
        assert mock_handle_io.called
        assert isinstance(result, ToolResult)
