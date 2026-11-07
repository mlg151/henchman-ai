"""Exercise the test guard before DNS, synchronous sockets and async transports."""

import asyncio
import os
import socket
from pathlib import Path

import pytest


@pytest.mark.parametrize("host,port", [
    ("api.anthropic.com", 443), ("8.8.8.8", 443),
    ("127.0.0.1", 8081), ("localhost", 11434), ("::1", 11435),
])
def test_default_guard_rejects_external_resolution_and_model_services(host, port):
    with pytest.raises(RuntimeError, match="Offline test blocked"):
        socket.getaddrinfo(host, port)


@pytest.mark.parametrize("method", ["connect", "connect_ex"])
def test_default_guard_rejects_direct_numeric_connect(method):
    with socket.socket() as client, pytest.raises(RuntimeError, match="Offline test blocked"):
        getattr(client, method)(("8.8.8.8", 443))


async def test_default_guard_rejects_async_numeric_connect():
    with pytest.raises(RuntimeError, match="Offline test blocked"):
        await asyncio.get_running_loop().create_connection(asyncio.Protocol, "8.8.8.8", 443)


def test_default_guard_allows_owned_ephemeral_loopback_fixture():
    with socket.socket() as server, socket.socket() as client:
        server.bind(("127.0.0.1", 0))
        server.listen()
        client.connect(server.getsockname())
        connection, _ = server.accept()
        with connection:
            client.sendall(b"fixture")
            assert connection.recv(7) == b"fixture"


def test_default_guard_isolates_user_configuration_and_data(offline_network, tmp_path):
    assert offline_network is not None
    assert Path.home() == offline_network
    assert offline_network.is_relative_to(tmp_path)
    assert Path(os.environ["HOME"]) == offline_network
    assert Path(os.environ["USERPROFILE"]) == offline_network
    for key in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME"):
        assert Path(os.environ[key]).is_relative_to(offline_network)
