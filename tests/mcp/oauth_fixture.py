"""Independent owned TLS OAuth metadata peer; never an external login service."""

import asyncio
import base64
import hashlib
import json
import uuid
from contextlib import suppress
from urllib.parse import parse_qsl, urlencode, urlsplit


class OAuthPeer:
    def __init__(self, tls_context):
        self.context = tls_context
        self.routes = {}
        self.requests = []
        self.tasks = set()
        self.writers = set()
        self.closing = False
        self.oauth_enabled = False
        self.codes = {}
        self.token_forms = []
        self.token_response = {"access_token": "issued-access-private-canary", "token_type": "Bearer",
                               "refresh_token": "issued-refresh-private-canary", "expires_in": 300, "scope": "read"}
        self.valid_refresh_token = None
        self.token_disconnect = False

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

    def enable_oauth(self):
        self.oauth_enabled = True
        self.routes["/token"] = (200, self.token_response, {}, 0)

    def auth_route(self, method, target, raw):
        path = urlsplit(target).path
        if path == "/authorize" and method == "GET":
            query = dict(parse_qsl(urlsplit(target).query))
            assert query["resource"] == self.endpoint and query["client_id"] == "public-client"
            assert query["response_type"] == "code" and query["code_challenge_method"] == "S256"
            code = "fixture-code-private-canary-" + uuid.uuid4().hex
            self.codes[code] = query
            location = query["redirect_uri"] + "?" + urlencode({"code": code, "state": query["state"], "iss": self.issuer})
            return 302, {}, {"Location": location}, 0
        if path == "/token" and method == "POST":
            form = dict(parse_qsl(raw.decode()))
            self.token_forms.append(form)
            valid = form.get("resource") == self.endpoint and form.get("client_id") == "public-client"
            if form.get("grant_type") == "authorization_code":
                authorization = self.codes.pop(form.get("code"), None)
                challenge = base64.urlsafe_b64encode(hashlib.sha256(form.get("code_verifier", "").encode()).digest()).decode().rstrip("=")
                valid = valid and authorization is not None and authorization["code_challenge"] == challenge and authorization["redirect_uri"] == form.get("redirect_uri")
            elif form.get("grant_type") == "refresh_token":
                valid = valid and self.valid_refresh_token is not None and form.get("refresh_token") == self.valid_refresh_token
            else:
                valid = False
            if not valid:
                return 400, {"error": "invalid_grant"}, {}, 0
            result = self.routes["/token"]
            if isinstance(result[1], dict) and result[1].get("refresh_token"):
                self.valid_refresh_token = result[1]["refresh_token"]
            return result
        return None

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
            body = await reader.readexactly(int(headers.get("content-length", "0")))
            self.requests.append((method, path, headers))
            route = self.auth_route(method, path, body) if self.oauth_enabled else None
            status, data, extra, delay = route or self.routes.get(path, (404, {}, {}, 0))
            if path == "/token" and self.token_disconnect:
                return
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
            tasks, writers = tuple(self.tasks), tuple(self.writers)
            for writer in writers:
                writer.close()
                writer.transport.abort()
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            self.tasks.difference_update(tasks)
            self.writers.difference_update(writers)
        await self.server.wait_closed()
