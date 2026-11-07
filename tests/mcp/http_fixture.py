"""Owned loopback HTTP peer implementing JSON-RPC without the MCP SDK."""

from __future__ import annotations

import asyncio
import json
from contextlib import suppress


class HttpPeer:
    def __init__(self, *, version="2026-07-28", mode="json", ssl_context=None):
        self.version = version
        self.mode = mode
        self.requests = []
        self.effects = 0
        self.behavior = "complete"
        self.cleanup_behavior = "complete"
        self.delays = {}
        self.capabilities = {"tools": {}}
        self.context_pages = {}
        self.context_results = {}
        self.ssl_context = ssl_context
        self.pages = {"": {"tools": [{"name": "effect", "inputSchema": {
            "type": "object", "properties": {"region": {"type": "string", "x-mcp-header": "region"}},
        }}]}}
        self.tasks = set()
        self.writers = set()
        self.closing = False
        self.server = None
        self.url = ""

    async def __aenter__(self):
        self.server = await asyncio.start_server(self._accept, "127.0.0.1", 0, ssl=self.ssl_context)
        port = self.server.sockets[0].getsockname()[1]
        scheme = "https" if self.ssl_context is not None else "http"
        self.url = f"{scheme}://127.0.0.1:{port}/mcp"
        return self

    async def __aexit__(self, *_args):
        self.closing = True
        self.server.close()
        # Python 3.12+ waits for accepted transports as well as the listener.
        # Settle owned connections first, including callbacks already queued.
        await self._close_clients()
        await self.server.wait_closed()
        await self._close_clients()

    def _accept(self, reader, writer):
        self.writers.add(writer)
        if self.closing:
            # A connection_made callback can have been queued before close().
            # Abort immediately so wait_closed never depends on its handler.
            writer.close()
            writer.transport.abort()
            return
        task = asyncio.create_task(self._handle(reader, writer))
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    async def _close_clients(self):
        while self.tasks or self.writers:
            tasks, writers = tuple(self.tasks), tuple(self.writers)
            for writer in writers:
                writer.close()
                writer.transport.abort()
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            for writer in writers:
                with suppress(ConnectionError):
                    await writer.wait_closed()
                self.writers.discard(writer)

    async def _handle(self, reader, writer):
        try:
            if self.closing:
                return
            header_bytes = await reader.readuntil(b"\r\n\r\n")
            lines = header_bytes.decode("iso-8859-1").split("\r\n")
            verb, target, _ = lines[0].split(" ", 2)
            headers = {key.lower(): value.strip() for line in lines[1:] if ":" in line
                       for key, value in [line.split(":", 1)]}
            raw = await reader.readexactly(int(headers.get("content-length", "0")))
            request = json.loads(raw) if raw else {}
            self.requests.append({"verb": verb, "target": target, "headers": headers, "body": request})
            if verb == "DELETE":
                if self.cleanup_behavior == "drop":
                    return
                if self.cleanup_behavior == "stall":
                    await asyncio.sleep(30)
                    return
                if self.cleanup_behavior == "redirect":
                    await self._respond(writer, 307, b"", headers={"Location": self.url + "/private-cleanup-canary"})
                    return
                await self._respond(writer, 204, b"")
                return
            if verb != "POST":
                await self._respond(writer, 405, b"")
                return
            method = request.get("method")
            if method in self.delays:
                await asyncio.sleep(self.delays[method])
            if "id" not in request:
                await self._respond(writer, 202, b"")
                return
            error = None
            extra_headers = {}
            if self.behavior == "unauthorized":
                await self._respond(writer, 401, b"private-auth-error-canary",
                                    headers={"WWW-Authenticate": 'Bearer resource_metadata="https://untrusted.invalid/meta"'})
                return
            if self.behavior == "redirect":
                await self._respond(writer, 307, b"", headers={"Location": self.url + "/elsewhere"})
                return
            if method == "server/discover":
                if self.version == "2026-07-28":
                    result = {"supportedVersions": [self.version], "capabilities": self.capabilities}
                else:
                    error = {"code": -32601, "message": "Method not found"}
            elif method == "initialize":
                result = {"protocolVersion": self.version, "capabilities": self.capabilities,
                          "serverInfo": {"name": "independent-http", "version": "1"}}
                extra_headers["Mcp-Session-Id"] = "fixture-session-private"
            elif method == "tools/list":
                cursor = request.get("params", {}).get("cursor", "")
                result = dict(self.pages[cursor])
                extra_headers["Set-Cookie"] = "unwanted=private-cookie; Path=/"
            elif method in self.context_pages:
                result = dict(self.context_pages[method][request.get("params", {}).get("cursor", "")])
            elif method in self.context_results:
                result = dict(self.context_results[method])
            elif method == "tools/call":
                self.effects += 1
                if self.behavior == "accepted_without_result":
                    await self._respond(writer, 202, b"")
                    return
                if self.behavior == "drop":
                    return
                if self.behavior == "stall":
                    await asyncio.sleep(30)
                    return
                if self.behavior == "oversize":
                    await self._respond(writer, 200, b"x" * (1024 * 1024 + 1))
                    return
                if self.behavior == "chunked_oversize":
                    writer.write(b"HTTP/1.1 200 Fixture\r\nContent-Type: application/json\r\nTransfer-Encoding: chunked\r\n\r\n")
                    for _ in range(18):
                        chunk = b"x" * 65536
                        writer.write(f"{len(chunk):x}\r\n".encode() + chunk + b"\r\n")
                        await writer.drain()
                    writer.write(b"0\r\n\r\n")
                    return
                if self.behavior == "sse_oversize":
                    await self._respond(writer, 200, b"data: " + b"x" * (1024 * 1024 + 1) + b"\n\n",
                                        content_type="text/event-stream")
                    return
                if self.behavior == "sse_aggregate":
                    notification = {"jsonrpc":"2.0","method":"notifications/progress",
                                    "params":{"progressToken":"fixture","progress":1,"message":"x" * 64000}}
                    await self._respond(writer, 200, (b"data: " + json.dumps(notification).encode() + b"\n\n") * 70,
                                        content_type="text/event-stream")
                    return
                if self.behavior == "sse_drop_with_id":
                    await self._respond(writer, 200, b"id: private-resumption-id\nevent: message\ndata:\n\n",
                                        content_type="text/event-stream")
                    return
                if self.behavior == "compressed":
                    import gzip
                    await self._respond(writer, 200, gzip.compress(b"private-compressed-canary"),
                                        headers={"Content-Encoding":"gzip"})
                    return
                result = {"content": [{"type": "text", "text": "http executed"}], "structuredContent": None}
            else:
                error = {"code": -32601, "message": "Method not found"}
            if error is None and self.version == "2026-07-28":
                result.setdefault("resultType", "complete")
                if method in {"server/discover", "tools/list", "resources/list", "resources/templates/list", "resources/read", "prompts/list"}:
                    result.update({"ttlMs": 0, "cacheScope": "private"})
            response = {"jsonrpc": "2.0", "id": request["id"]}
            if self.behavior == "wrong_id":
                response["id"] = "private-unrelated-id"
            response["error" if error is not None else "result"] = error if error is not None else result
            data = json.dumps(response).encode()
            if self.mode == "sse":
                data = b"event: message\ndata: " + data + b"\n\n"
                content_type = "text/event-stream"
            else:
                content_type = "application/json"
            status = 500 if self.behavior == "http_error_success_body" else 200
            await self._respond(writer, status, data, content_type=content_type, headers=extra_headers)
        except (ConnectionError, asyncio.IncompleteReadError):
            pass
        finally:
            writer.close()
            with suppress(ConnectionError):
                await writer.wait_closed()
            self.writers.discard(writer)

    @staticmethod
    async def _respond(writer, status, body, *, content_type="application/json", headers=None):
        fields = {"Content-Type": content_type, "Content-Length": str(len(body)), "Connection": "close", **(headers or {})}
        response = f"HTTP/1.1 {status} Fixture\r\n" + "".join(f"{key}: {value}\r\n" for key, value in fields.items())
        writer.write(response.encode() + b"\r\n" + body)
        await writer.drain()
