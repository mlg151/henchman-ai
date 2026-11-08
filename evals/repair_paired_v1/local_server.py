"""Explicit borrowed-server authority; never starts, changes or stops the server."""

from __future__ import annotations
import asyncio
import json
import os
import re
import time
from copy import deepcopy
from importlib.metadata import version
from pathlib import Path
from types import MappingProxyType
import httpcore
import httpx
import contract as c
from memory_sampler import MemorySampler

READ_PATHS = ("/health", "/v1/models", "/slots")
ORIGIN = "http://127.0.0.1:8081"


def require_profile():
    if version("httpx") != "0.28.1" or version("httpcore") != "1.0.9":
        raise c.Denied("Unqualified local HTTP trace profile")


def guard(request, authorize):
    require_profile()
    if set(request.extensions) - {"timeout"}:
        raise c.Denied("Unexpected request extension")
    authorize()
    method = request.method.encode("ascii")
    url = request.url
    destination = httpcore.URL(
        scheme=url.raw_scheme, host=url.raw_host, port=url.port, target=url.raw_path
    )
    sent = False

    async def trace(event, info):
        nonlocal sent
        if event == "http11.send_request_headers.started":
            if sent:
                raise c.Denied("HTTP replay denied")
            sent = True
            wire = info.get("request")
            if (
                not isinstance(wire, httpcore.Request)
                or wire.method != method
                or wire.url != destination
            ):
                raise c.Denied("HTTP target changed")
            authorize()
        elif event.startswith("http2."):
            raise c.Denied("HTTP2 outside reviewed path")

    request.extensions = MappingProxyType({**deepcopy(dict(request.extensions)), "trace": trace})


class AuthorityTransport(httpx.AsyncBaseTransport):
    def __init__(self, authorize, *, readiness=False, delegate=None):
        require_profile()
        self.authorize = authorize
        self.readiness = readiness
        self.delegate = (
            delegate
            if delegate is not None
            else httpx.AsyncHTTPTransport(retries=0, trust_env=False, http1=True, http2=False)
        )

    async def handle_async_request(self, request):
        allowed = (
            request.method == "GET" and str(request.url) in {ORIGIN + p for p in READ_PATHS}
            if self.readiness
            else request.method == "POST" and str(request.url) == c.ENDPOINT + "/chat/completions"
        )
        if not allowed:
            raise c.Denied("Local authority route denied")
        guard(request, self.authorize)
        return await self.delegate.handle_async_request(request)

    async def aclose(self):
        await self.delegate.aclose()


class Lease:
    def __init__(self, admission):
        if admission is None:
            raise c.Denied("Explicit reviewed admission file is required")
        path = Path(admission).absolute()
        if (
            path.resolve() != path
            or not path.is_file()
            or path.stat().st_size > 32768
            or path.stat().st_mode & 0o077
        ):
            raise c.Denied("Admission must be a bounded physical file")
        self.path = path
        self.raw = path.read_bytes()
        self.value = json.loads(self.raw)
        required = {
            "version",
            "approved",
            "source_commit",
            "source_manifest_sha256",
            "harness_sha256",
            "endpoint",
            "model",
            "expires_unix",
            "server",
            "model_file",
        }
        if (
            set(self.value) != required
            or self.value["version"] != c.VERSION
            or self.value["approved"] is not True
        ):
            raise c.Denied("Invalid explicit admission")
        c.require_target(self.value["endpoint"], self.value["model"])
        if self.value["source_commit"] != c.COMMIT or self.value[
            "source_manifest_sha256"
        ] != c.digest((c.HERE / "source-manifest.json").read_bytes()):
            raise c.Denied("Admission source differs")
        from launch import harness_manifest

        if self.value["harness_sha256"] != c.digest(c.json_bytes(harness_manifest())):
            raise c.Denied("Admission harness differs")
        if (
            type(self.value["expires_unix"]) not in (int, float)
            or not 0 < self.value["expires_unix"] - time.time() <= 7200
        ):
            raise c.Denied("Admission expiration unavailable")
        self.authorize()

    def authorize(self):
        if (
            self.path.is_symlink()
            or self.path.read_bytes() != self.raw
            or time.time() >= self.value["expires_unix"]
        ):
            raise c.Denied("Reviewed admission changed/expired")
        server = self.value["server"]
        if (
            set(server) != {"pid", "start_ticks", "cmdline_sha256"}
            or type(server["pid"]) is not int
            or type(server["start_ticks"]) is not int
        ):
            raise c.Denied("Server identity invalid")
        current = MemorySampler().stat(server["pid"])
        if current["start_ticks"] != server["start_ticks"]:
            raise c.Denied("Borrowed server replaced")
        proc = Path("/proc") / str(server["pid"])
        command = (proc / "cmdline").read_bytes()
        if c.digest(command) != server["cmdline_sha256"]:
            raise c.Denied("Borrowed server arguments changed")
        inodes = {
            fields[9]
            for line in Path("/proc/net/tcp").read_text().splitlines()[1:]
            if (fields := line.split())[1] == "0100007F:1F91" and fields[3] == "0A"
        }
        sockets = set()
        for fd in (proc / "fd").iterdir():
            try:
                match = re.fullmatch(r"socket:\[(\d+)\]", os.readlink(fd))
                if match:
                    sockets.add(match[1])
            except OSError:
                pass
        if not inodes or not inodes.issubset(sockets):
            raise c.Denied("8081 listener does not match reviewed process")
        model = self.value["model_file"]
        path = Path(model["path"])
        if (
            set(model) != {"path", "device", "inode", "size", "mtime_ns"}
            or path.resolve() != path
            or not path.is_file()
        ):
            raise c.Denied("Model file binding invalid")
        validate_command(command, str(path))
        stat = path.stat()
        if (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns) != (
            model["device"],
            model["inode"],
            model["size"],
            model["mtime_ns"],
        ):
            raise c.Denied("Model file binding changed")

    def transport(self):
        return AuthorityTransport(self.authorize)

    async def readiness(self):
        result = {}
        async with asyncio.timeout(15):
            async with httpx.AsyncClient(
                transport=AuthorityTransport(self.authorize, readiness=True),
                trust_env=False,
                follow_redirects=False,
                timeout=5,
            ) as client:
                for path in READ_PATHS:
                    self.authorize()
                    raw = bytearray()
                    async with client.stream("GET", ORIGIN + path) as response:
                        async for chunk in response.aiter_raw():
                            raw.extend(chunk)
                            if len(raw) > 32768:
                                raise c.Denied("Readiness response too large")
                        if response.status_code != 200:
                            raise c.Denied(f"Readiness {path} returned HTTP {response.status_code}")
                    result[path] = json.loads(raw)
        validate_readiness(result)
        self.authorize()
        return result


def validate_readiness(result):
    if result.get("/health") != {"status": "ok"}:
        raise c.Denied("Borrowed server not ready")
    models = result.get("/v1/models", {}).get("data", [])
    if len(models) != 1 or models[0].get("id") != c.MODEL:
        raise c.Denied("Served model identity differs")
    slots = result.get("/slots")
    if not isinstance(slots, list) or len(slots) != 1 or slots[0].get("is_processing") is not False:
        raise c.Denied("Borrowed server is busy or idle status unavailable")


def validate_command(raw, model_path):
    """Bind reviewed model bytes to the actual borrowed process argument vector."""
    parts = raw.decode("utf-8", errors="strict").rstrip("\0").split("\0")

    def one(flags):
        found = [parts[index + 1] for index, part in enumerate(parts[:-1]) if part in flags]
        if len(found) != 1:
            raise c.Denied("Ambiguous local process model identity")
        return found[0]

    if one(("-m", "--model")) != model_path or one(("--alias", "-a")) != c.MODEL:
        raise c.Denied("Borrowed model path/alias differs from reviewed identity")
    if any(part in ("--hf-repo", "-hf", "--model-url", "-mu") for part in parts):
        raise c.Denied("Remote model resolution is outside the comparison")
