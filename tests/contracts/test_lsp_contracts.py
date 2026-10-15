"""Contract tests for the LSP (Language Server Protocol) service."""

from __future__ import annotations

import json
from typing import Any, Protocol, runtime_checkable
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from henchman.lsp.service import LspService


@runtime_checkable
class LspServerProtocol(Protocol):
    """Protocol defining the expected behavior of an LSP server process."""

    async def send_message(self, message: dict[str, Any]) -> None:
        """Send a message to the server's stdin."""
        ...

    async def receive_message(self) -> dict[str, Any]:
        """Receive a message from the server's stdout."""
        ...


@pytest.fixture(autouse=True)
def clear_lsp_runtimes():
    """Clear LspService runtimes before each test to avoid state leakage."""
    LspService._runtimes.clear()
    yield
    LspService._runtimes.clear()


@pytest.mark.asyncio
async def test_lsp_service_registration_contract(tmp_path) -> None:
    """LspService must correctly register and persist server configurations."""
    with patch("henchman.lsp.service.resolve_project_settings_path") as mock_path:
        mock_path.return_value = tmp_path

        service = LspService(project_root=tmp_path / "project")

        record = service.register_server(
            server="pyright",
            command="pyright-langserver",
            args=["--stdio"],
            language="python"
        )

        assert record.server == "pyright"
        assert record.command == "pyright-langserver"
        assert record.args == ("--stdio",)
        assert record.language == "python"
        assert record.running is False

        # Verify it shows up in list
        servers = service.list_servers()
        assert len(servers) == 1
        assert servers[0].server == "pyright"


@pytest.mark.asyncio
async def test_lsp_service_orchestration_contract(tmp_path) -> None:
    """LspService must correctly orchestrate initialization and custom requests."""
    with patch("henchman.lsp.service.resolve_project_settings_path") as mock_path:
        mock_path.return_value = tmp_path
        service = LspService(project_root=tmp_path / "project")

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = MagicMock()
            mock_process.stdin = MagicMock()
            mock_process.stdout = AsyncMock()
            mock_exec.return_value = mock_process

            with (
                patch.object(service, "_write_message", new_callable=AsyncMock) as mock_write,
                patch.object(service, "_read_message", new_callable=AsyncMock) as mock_read,
            ):
                service.register_server(server="test", command="test-cmd")

                # Mock response for 'initialize'
                mock_read.return_value = {"jsonrpc": "2.0", "id": 0, "result": {"capabilities": {}}}
                await service.start_server("test")

                mock_write.assert_any_call(mock_process, {
                    "jsonrpc": "2.0", "id": 0, "method": "initialize",
                    "params": {"processId": None, "rootUri": (tmp_path / "project").as_uri(), "capabilities": {}}
                })
                mock_write.assert_any_call(mock_process, {"jsonrpc": "2.0", "method": "initialized", "params": {}})

                # Mock response for custom request
                mock_read.return_value = {"jsonrpc": "2.0", "id": 1, "result": "done"}
                assert await service.request("test", "testMethod", {}) == "done"


@pytest.mark.asyncio
async def test_lsp_service_wire_protocol_contract(tmp_path) -> None:
    """LspService must correctly parse the Content-Length header and JSON body."""
    with patch("henchman.lsp.service.resolve_project_settings_path") as mock_path:
        mock_path.return_value = tmp_path
        service = LspService(project_root=tmp_path / "project")

        # Mock process with reader/writer
        mock_process = MagicMock()
        mock_process.stdout = AsyncMock()
        mock_process.stdin = MagicMock()

        # 1. Test _read_message with standard CRLF
        body = json.dumps({"jsonrpc": "2.0", "id": 1, "result": "ok"}).encode("utf-8")
        mock_process.stdout.readline.side_effect = [
            b"Content-Length: " + str(len(body)).encode() + b"\r\n",
            b"\r\n"
        ]
        mock_process.stdout.readexactly.return_value = body

        response = await service._read_message(mock_process)
        assert response["id"] == 1
        mock_process.stdout.readexactly.assert_called_with(len(body))

        # 2. Test _read_message with extra headers (LSP allows this)
        mock_process.stdout.readline.side_effect = [
            b"Content-Type: application/vscode-jsonrpc; charset=utf-8\r\n",
            b"Content-Length: " + str(len(body)).encode() + b"\r\n",
            b"\r\n"
        ]
        response = await service._read_message(mock_process)
        assert response["id"] == 1

        # 3. Test _read_message with invalid JSON (Contract: raise JSONDecodeError)
        mock_process.stdout.readline.side_effect = [
            b"Content-Length: 5\r\n",
            b"\r\n"
        ]
        mock_process.stdout.readexactly.return_value = b"not-json"
        with pytest.raises(json.JSONDecodeError):
            await service._read_message(mock_process)

        # 4. Test _write_message (Contract: must include Content-Length and CRLF CRLF)
        payload = {"method": "test"}
        mock_process.stdin.drain = AsyncMock()
        await service._write_message(mock_process, payload)

        # Check what was written to stdin
        calls = [c.args[0] for c in mock_process.stdin.write.call_args_list]
        full_output = b"".join(calls)

        expected_body = json.dumps(payload).encode("utf-8")
        assert b"Content-Length: " + str(len(expected_body)).encode() + b"\r\n\r\n" in full_output
        assert full_output.endswith(expected_body)


@pytest.mark.asyncio
async def test_lsp_service_error_handling_contract(tmp_path) -> None:
    """LspService must correctly handle JSON-RPC errors from the server."""
    with patch("henchman.lsp.service.resolve_project_settings_path") as mock_path:
        mock_path.return_value = tmp_path
        service = LspService(project_root=tmp_path / "project")

        # Inject a mock session
        mock_process = MagicMock()
        mock_process.stdin = MagicMock()
        from henchman.lsp.service import _LspSession
        service._runtime.sessions["test-server"] = _LspSession(process=mock_process, next_id=10)

        # Mock _read_message to return a JSON-RPC error
        error_payload = {
            "jsonrpc": "2.0",
            "id": 10,
            "error": {"code": -32601, "message": "Method not found"}
        }

        with (
            patch.object(service, "_read_message", AsyncMock(return_value=error_payload)),
            patch.object(service, "_write_message", AsyncMock()),
            pytest.raises(ValueError) as exc,
        ):
            await service.request("test-server", "unknownMethod", {})

        assert '{"code": -32601, "message": "Method not found"}' in str(exc.value)
