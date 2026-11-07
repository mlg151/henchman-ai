"""Independent owned TLS OAuth metadata peer; never an external login service."""

import asyncio
import json
from contextlib import suppress


class OAuthPeer:
    def __init__(self, tls_context):
        self.context = tls_context
        self.routes = {}
        self.requests = []
        self.tasks = set()
        self.writers = set()
        self.closing = False

    async def __aenter__(self):
        self.server = await asyncio.start_server(self.accept, "127.0.0.1", 0, ssl=self.context)
        self.origin = f"https://127.0.0.1:{self.server.sockets[0].getsockname()[1]}"
        self.endpoint = self.origin + "/mcp"
        self.issuer = self.origin + "/issuer"
        self.resource_path = "/.well-known/oauth-protected-resource/mcp"
        self.issuer_path = "/.well-known/oauth-authorization-server/issuer"
        self.resource = {"resource": self.endpoint, "authorization_servers": [self.issuer], "scopes_supported": ["read"]}
        self.metadata = {"issuer": self.issuer, "authorization_endpoint": self.origin + "/authorize",
                         "token_endpoint": self.origin + "/token", "code_challenge_methods_supported": ["S256"],
                         "response_types_supported": ["code"], "token_endpoint_auth_methods_supported": ["none"],
                         "authorization_response_iss_parameter_supported": True}
        self.routes[self.resource_path] = (200, self.resource, {}, 0)
        self.routes[self.issuer_path] = (200, self.metadata, {}, 0)
        return self

    def accept(self, reader, writer):
        if self.closing:
            writer.close()
            writer.transport.abort()
            return
        self.writers.add(writer)
        task = asyncio.create_task(self.handle(reader, writer))
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    async def handle(self, reader, writer):
        try:
            header = (await reader.readuntil(b"\r\n\r\n")).decode("ascii")
            lines = header.split("\r\n")
            method, path, _ = lines[0].split(" ")
            headers = dict(line.lower().split(": ", 1) for line in lines[1:] if ": " in line)
            self.requests.append((method, path, headers))
            status, data, extra, delay = self.routes.get(path, (404, {}, {}, 0))
            await asyncio.sleep(delay)
            raw = data if isinstance(data, bytes) else json.dumps(data).encode()
            fields = {"Content-Type": "application/json", "Content-Length": str(len(raw)), "Connection": "close", **extra}
            writer.write(f"HTTP/1.1 {status} Fixture\r\n".encode()
                         + "".join(f"{key}: {value}\r\n" for key, value in fields.items()).encode() + b"\r\n" + raw)
            await writer.drain()
        except (ConnectionError, asyncio.IncompleteReadError):
            pass
        finally:
            writer.close()
            with suppress(ConnectionError):
                await writer.wait_closed()
            self.writers.discard(writer)

    async def __aexit__(self, *_args):
        self.closing = True
        self.server.close()
        while self.tasks or self.writers:
            tasks = tuple(self.tasks)
            for writer in tuple(self.writers):
                writer.close()
                writer.transport.abort()
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            self.writers.clear()
        await self.server.wait_closed()
