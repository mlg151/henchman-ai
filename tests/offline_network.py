"""Offline pytest defaults: real fixtures stay local and model transports are mocked."""

import asyncio
import ipaddress
import os
import socket

import pytest

_MODEL_PORTS = frozenset({"8081", "8082", "11434", "11435"})
_PROVIDER_KEYS = (
    "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "DEEPSEEK_API_KEY", "OPENROUTER_API_KEY",
    "TOGETHER_API_KEY", "GROQ_API_KEY", "FIREWORKS_API_KEY", "HENCHMAN_API_KEY",
)


def _check_destination(host, port):
    if host in (None, "", b""):
        return
    name = host.decode("ascii") if isinstance(host, bytes) else str(host)
    try:
        loopback = ipaddress.ip_address(name).is_loopback
    except ValueError:
        loopback = name.lower().rstrip(".") == "localhost"
    if not loopback:
        raise RuntimeError("Offline test blocked external network; use an explicit mock transport")
    if str(port) in _MODEL_PORTS:
        raise RuntimeError("Offline test blocked an existing local model service; use a mock transport")


@pytest.fixture(autouse=True)
def offline_network(monkeypatch):
    """Block accidental SDK traffic while allowing owned loopback HTTP/TLS fixtures."""
    original_resolve = socket.getaddrinfo
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    original_create = asyncio.BaseEventLoop.create_connection

    def resolve(host, port, *args, **kwargs):
        _check_destination(host, port)
        return original_resolve(host, port, *args, **kwargs)

    def connect(sock, address):
        if sock.family in (socket.AF_INET, socket.AF_INET6):
            _check_destination(address[0], address[1])
        return original_connect(sock, address)

    def connect_ex(sock, address):
        if sock.family in (socket.AF_INET, socket.AF_INET6):
            _check_destination(address[0], address[1])
        return original_connect_ex(sock, address)

    async def create(loop, protocol_factory, host=None, port=None, *args, **kwargs):
        _check_destination(host, port)
        return await original_create(loop, protocol_factory, host, port, *args, **kwargs)

    monkeypatch.setattr(socket, "getaddrinfo", resolve)
    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", connect_ex)
    monkeypatch.setattr(asyncio.BaseEventLoop, "create_connection", create)
    for key in _PROVIDER_KEYS:
        if key in os.environ:
            monkeypatch.setenv(key, "offline-test-key")
