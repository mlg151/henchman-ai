"""A native loopback callback has one owner and never reflects authorization data."""

import asyncio
import traceback
from contextlib import suppress
from urllib.parse import urlencode, urlsplit

import pytest

from henchman.mcp.oauth import OAuthError
from henchman.utils.evidence_redaction import EvidenceRedactor


def callback(**kwargs):
    from henchman.mcp.oauth_callback import OAuthCallback

    return OAuthCallback(state="expected-state-canary", issuer="https://issuer.example/tenant", require_iss=True,
                         evidence=EvidenceRedactor(), authorize=lambda: None, **kwargs)


async def send_callback(uri, values=None, *, target=None, method="GET", headers=None):
    parsed = urlsplit(uri)
    reader, writer = await asyncio.open_connection(parsed.hostname, parsed.port)
    target = target or parsed.path + "?" + urlencode(values or {})
    fields = {"Host": parsed.netloc, "Connection": "close", **(headers or {})}
    writer.write(f"{method} {target} HTTP/1.1\r\n".encode()
                 + "".join(f"{key}: {value}\r\n" for key, value in fields.items()).encode() + b"\r\n")
    await writer.drain()
    data = await asyncio.wait_for(reader.read(), 2)
    writer.close()
    await writer.wait_closed()
    return data.decode()


def valid(**overrides):
    return {"code": "authorization-code-canary", "state": "expected-state-canary",
            "iss": "https://issuer.example/tenant", **overrides}


async def test_owned_callback_consumes_exactly_one_code_and_closes_listener():
    async with callback() as listener:
        uri = listener.redirect_uri
        response = await send_callback(uri, valid())
        assert response.startswith("HTTP/1.1 200")
        assert "canary" not in response and "issuer.example" not in response
        code = await listener.wait_code()
        assert code.code == "authorization-code-canary"
        assert "canary" not in repr(code)
        with pytest.raises(OAuthError):
            await listener.wait_code()
    parsed = urlsplit(uri)
    with pytest.raises(OSError):
        await asyncio.open_connection(parsed.hostname, parsed.port)
    assert not [task for task in asyncio.all_tasks() if task.get_name().startswith("henchman-oauth-callback")]


@pytest.mark.parametrize("mutation", ["state", "host", "path", "method", "origin", "duplicate", "malformed_escape", "body"])
async def test_invalid_callback_is_rejected_without_consuming_valid_response(mutation):
    async with callback() as listener:
        args = {"values": valid()}
        if mutation == "state":
            args["values"] = valid(state="attacker-state-canary")
        elif mutation == "host":
            args["headers"] = {"Host": "attacker.example"}
        elif mutation == "path":
            args["target"] = "/other?" + urlencode(valid())
        elif mutation == "method":
            args["method"] = "POST"
        elif mutation == "origin":
            args["headers"] = {"Origin": "https://attacker.example"}
        elif mutation == "duplicate":
            args["target"] = "/oauth/callback?" + urlencode(valid()) + "&code=second-private-canary"
        elif mutation == "malformed_escape":
            args["target"] = "/oauth/callback?" + urlencode(valid()) + "&extra=%ZZ"
        else:
            args["headers"] = {"Content-Length": "1"}
        response = await send_callback(listener.redirect_uri, **args)
        assert response.startswith("HTTP/1.1 400")
        assert "canary" not in response
        await send_callback(listener.redirect_uri, valid())
        assert (await listener.wait_code()).code == "authorization-code-canary"


@pytest.mark.parametrize("values", [valid(iss="https://issuer.example/tenant/"),
                                    {"code": "code-private-canary", "state": "expected-state-canary"},
                                    {"error": "access_denied", "error_description": "private-error-canary",
                                     "state": "expected-state-canary", "iss": "https://wrong.example"}])
async def test_issuer_mismatch_and_advertised_absence_fail_without_exposing_details(values):
    async with callback() as listener:
        response = await send_callback(listener.redirect_uri, values)
        with pytest.raises(OAuthError) as caught:
            await listener.wait_code()
        assert "canary" not in response
        assert "canary" not in "".join(traceback.format_exception(caught.value))


async def test_cancellation_joins_slow_accepted_callback_connections():
    entered = asyncio.Event()
    location = []

    async def own_listener():
        async with callback() as listener:
            location.append(listener.redirect_uri)
            entered.set()
            await listener.wait_code()

    owner = asyncio.create_task(own_listener())
    await asyncio.wait_for(entered.wait(), 1)
    parsed = urlsplit(location[0])
    reader, writer = await asyncio.open_connection(parsed.hostname, parsed.port)
    writer.write(b"GET /oauth/callback?state=partial-private-canary")
    await writer.drain()
    owner.cancel()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(owner, 2)
    # Closing an accepted socket with unread request bytes may report RST
    # instead of EOF on native kernels (observed on macOS/Python 3.11).
    # Both prove closure; a timeout or response bytes still fail this check.
    with suppress(ConnectionResetError):
        assert await asyncio.wait_for(reader.read(), 1) == b""
    writer.close()
    with suppress(ConnectionResetError):
        await writer.wait_closed()
    assert not [task for task in asyncio.all_tasks() if task.get_name().startswith("henchman-oauth-callback")]


async def test_request_deadline_closes_partial_headers(monkeypatch):
    from henchman.mcp import oauth_callback

    monkeypatch.setattr(oauth_callback, "CALLBACK_REQUEST_TIMEOUT", .03)
    async with callback() as listener:
        parsed = urlsplit(listener.redirect_uri)
        reader, writer = await asyncio.open_connection(parsed.hostname, parsed.port)
        writer.write(b"GET /oauth/callback HTTP/1.1\r\n")
        await writer.drain()
        assert "canary" not in (await asyncio.wait_for(reader.read(), 1)).decode()
        writer.close()
        await writer.wait_closed()


async def test_repeated_cancellation_joins_owned_cleanup_before_propagating(monkeypatch):
    from henchman.mcp.oauth_callback import OAuthCallback

    cleanup_started, release_cleanup, entered = asyncio.Event(), asyncio.Event(), asyncio.Event()
    original = OAuthCallback._close_owned

    async def delayed_cleanup(self):
        cleanup_started.set()
        await release_cleanup.wait()
        await original(self)

    monkeypatch.setattr(OAuthCallback, "_close_owned", delayed_cleanup)

    async def own_listener():
        async with callback() as listener:
            entered.set()
            await listener.wait_code()

    owner = asyncio.create_task(own_listener())
    await asyncio.wait_for(entered.wait(), 1)
    owner.cancel()
    await asyncio.wait_for(cleanup_started.wait(), 1)
    owner.cancel()
    await asyncio.sleep(0)
    assert not owner.done()
    release_cleanup.set()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(owner, 2)
    assert not [task for task in asyncio.all_tasks() if task.get_name().startswith("henchman-oauth-callback")]


async def test_request_flood_fails_bounded_without_consuming_secret(monkeypatch):
    from henchman.mcp import oauth_callback

    monkeypatch.setattr(oauth_callback, "CALLBACK_MAX_REQUESTS", 2)
    async with callback() as listener:
        await send_callback(listener.redirect_uri, valid(state="invalid-state"))
        await send_callback(listener.redirect_uri, valid(state="invalid-state"))
        parsed = urlsplit(listener.redirect_uri)
        reader, writer = await asyncio.open_connection(parsed.hostname, parsed.port)
        assert await asyncio.wait_for(reader.read(), 1) == b""
        writer.close()
        await writer.wait_closed()
        with pytest.raises(OAuthError, match="request limit"):
            await listener.wait_code()


async def test_cleanup_retires_joined_tasks_without_waiting_for_scheduled_done_callbacks(monkeypatch):
    # Python 3.12 gather may complete synchronously for already-done tasks.
    # Emulate that path on every supported interpreter, failing rather than
    # spinning forever if ownership still depends on queued done callbacks.
    listener = callback()
    done = asyncio.create_task(asyncio.sleep(0))
    await done
    listener._tasks.add(done)
    done.add_done_callback(listener._tasks.discard)
    calls = 0

    def gather_completed(*tasks, **_kwargs):
        nonlocal calls
        calls += 1
        assert calls == 1, "cleanup attempted to rejoin completed tasks without yielding"
        assert all(task.done() for task in tasks)
        result = asyncio.get_running_loop().create_future()
        result.set_result([None for _ in tasks])
        return result

    monkeypatch.setattr(asyncio, "gather", gather_completed)
    await listener._close_owned()
    assert not listener._tasks
