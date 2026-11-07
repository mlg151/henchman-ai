"""Bounded remote context catalogs and previews, never instruction authority."""

from __future__ import annotations

import asyncio
import base64
import binascii
import copy
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal
from urllib.parse import urlsplit

import anyio

from henchman.mcp.protocol import McpProtocolSession
from henchman.tools.contracts import SchemaContract, SchemaContractError

if TYPE_CHECKING:
    from henchman.mcp.client import McpClient

ContextFamily = Literal["resources", "templates", "prompts"]
_FAMILIES: dict[ContextFamily, tuple[str, str, str, str]] = {
    "resources": ("resources/list", "resources", "uri", "resources"),
    "templates": ("resources/templates/list", "resourceTemplates", "uriTemplate", "resources"),
    "prompts": ("prompts/list", "prompts", "name", "prompts"),
}
MAX_CONTEXT_PAGES = 32
MAX_CONTEXT_ENTRIES = 1024
MAX_CONTEXT_CATALOG_BYTES = 4 * 1024 * 1024
MAX_CONTEXT_BLOCKS = 256
_JSON = SchemaContract(True)


@dataclass(frozen=True)
class McpContextSource:
    server: str
    protocol_version: str
    connection_generation: int
    catalog_generation: int
    operation: str
    identifier: str | None = None
    arguments: dict[str, str] | None = None


@dataclass(frozen=True)
class McpContextCatalog:
    source: McpContextSource
    entries: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class McpContextResult:
    source: McpContextSource
    payload: dict[str, Any]


def _identifier(value: object, *, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum or any(ord(char) < 32 for char in value):
        raise SchemaContractError("mcp_context_identifier")
    return value


def _uri(value: object) -> str:
    uri = _identifier(value)
    try:
        valid = bool(urlsplit(uri).scheme) and not any(char.isspace() for char in uri)
    except ValueError:
        valid = False
    if not valid:
        raise SchemaContractError("mcp_context_uri")
    return uri


def _binary(value: object) -> None:
    try:
        if not isinstance(value, str):
            raise ValueError
        base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error):
        raise SchemaContractError("mcp_context_binary") from None


def _resource(value: dict[str, Any]) -> None:
    _uri(value.get("uri"))
    if ("text" in value) == ("blob" in value):
        raise SchemaContractError("mcp_context_resource_shape")
    if "blob" in value:
        _binary(value["blob"])


class McpContextService:
    """Maintain per-family snapshots behind one client's connection authority."""

    def __init__(self, client: McpClient) -> None:
        self.client = client
        self.catalogs: dict[ContextFamily, McpContextCatalog] = {}
        self.generations: dict[ContextFamily, int] = {}
        self.locks = {family: asyncio.Lock() for family in _FAMILIES}

    def clear(self) -> None:
        self.catalogs.clear()

    def _session(self, capability: str) -> McpProtocolSession:
        self.client._check_credentials()
        session = self.client._session
        if not isinstance(session, McpProtocolSession) or not session.is_connected:
            raise RuntimeError("MCP context requires a connected native client")
        if not session.supports(capability):
            raise RuntimeError("MCP server does not advertise this context capability")
        return session

    def _check(self, session: McpProtocolSession) -> None:
        self.client._check_credentials()
        if self.client._session is not session or not session.is_connected:
            raise RuntimeError("MCP connection changed during context retrieval")

    def _source(self, family: ContextFamily, operation: str, identifier: str | None = None,
                arguments: dict[str, str] | None = None) -> McpContextSource:
        return McpContextSource(self.client.name, self.client.protocol_version or "", self.client.connection_generation,
                                self.generations.get(family, 0), operation, identifier, copy.deepcopy(arguments))

    async def list(self, family: ContextFamily) -> McpContextCatalog:
        try:
            with anyio.fail_after(self.client.config.catalog_timeout_seconds):
                return await self._list(family)
        except TimeoutError:
            raise RuntimeError("MCP context catalog deadline exceeded; previous catalog retained") from None

    async def _list(self, family: ContextFamily) -> McpContextCatalog:
        method, field, identity, capability = _FAMILIES[family]
        async with self.locks[family]:
            session = self._session(capability)
            entries: list[dict[str, Any]] = []
            identities: set[str] = set()
            cursors: set[str] = set()
            cursor: str | None = None
            total = 0
            try:
                with anyio.fail_after(self.client.config.catalog_timeout_seconds):
                    for _ in range(MAX_CONTEXT_PAGES):
                        self._check(session)
                        payload = await session.request_context(method, {"cursor": cursor} if cursor is not None else {})
                        self._check(session)
                        _JSON.validate(payload)
                        total += len(json.dumps(payload, ensure_ascii=True))
                        if total > MAX_CONTEXT_CATALOG_BYTES:
                            raise SchemaContractError("mcp_context_catalog_bytes")
                        for entry in payload[field]:
                            key = _identifier(entry[identity], maximum=128 if family == "prompts" else 4096)
                            _identifier(entry["name"], maximum=128)
                            if family == "resources":
                                _uri(key)
                            if key in identities:
                                raise SchemaContractError("mcp_context_duplicate_entry")
                            identities.add(key)
                            if len(identities) > MAX_CONTEXT_ENTRIES:
                                raise SchemaContractError("mcp_context_entry_limit")
                            if family == "prompts":
                                names = [_identifier(arg["name"], maximum=128) for arg in (entry.get("arguments") or [])]
                                if len(names) != len(set(names)) or len(names) > 128:
                                    raise SchemaContractError("mcp_prompt_argument_declaration")
                            entries.append(copy.deepcopy(entry))
                        cursor = payload.get("nextCursor")
                        if cursor is None:
                            break
                        _identifier(cursor)
                        if cursor in cursors:
                            raise SchemaContractError("mcp_context_cursor_cycle")
                        cursors.add(cursor)
                    else:
                        raise SchemaContractError("mcp_context_page_limit")
            except TimeoutError:
                raise RuntimeError("MCP context catalog deadline exceeded; previous catalog retained") from None
            self._check(session)
            self.generations[family] = self.generations.get(family, 0) + 1
            catalog = McpContextCatalog(self._source(family, method), tuple(entries))
            self.catalogs[family] = catalog
            return copy.deepcopy(catalog)

    async def read(self, uri: str) -> McpContextResult:
        captured = _uri(uri)
        session = self._session("resources")
        source = self._source("resources", "resources/read", captured)
        payload = await session.request_context("resources/read", {"uri": captured})
        self._check(session)
        _JSON.validate(payload)
        if len(payload["contents"]) > MAX_CONTEXT_BLOCKS:
            raise SchemaContractError("mcp_context_block_limit")
        for content in payload["contents"]:
            _resource(content)
        return McpContextResult(source, copy.deepcopy(payload))

    async def prompt(self, name: str, arguments: dict[str, str]) -> McpContextResult:
        try:
            with anyio.fail_after(self.client.config.request_timeout_seconds):
                return await self._prompt(name, arguments)
        except TimeoutError:
            raise RuntimeError("MCP context request deadline exceeded; no automatic retry") from None

    async def _prompt(self, name: str, arguments: dict[str, str]) -> McpContextResult:
        captured_name = _identifier(name, maximum=128)
        _JSON.validate(arguments)
        captured = copy.deepcopy(arguments)
        # Catalog refresh cannot replace the validated declaration while the
        # request waits for transport handoff or its response.
        async with self.locks["prompts"]:
            session = self._session("prompts")
            catalog = self.catalogs.get("prompts")
            if catalog is None or catalog.source.connection_generation != self.client.connection_generation:
                raise RuntimeError("List the current MCP prompt catalog explicitly before retrieving a prompt")
            declaration = next((entry for entry in catalog.entries if entry["name"] == captured_name), None)
            if declaration is None:
                raise SchemaContractError("mcp_unknown_prompt")
            fields = {item["name"]: item for item in (declaration.get("arguments") or [])}
            if (not isinstance(captured, dict) or any(not isinstance(value, str) for value in captured.values())
                or set(captured) - fields.keys()
                or any(item.get("required") and key not in captured for key, item in fields.items())):
                raise SchemaContractError("mcp_prompt_arguments")
            source = self._source("prompts", "prompts/get", captured_name, captured)
            payload = await session.request_context("prompts/get", {"name": captured_name, "arguments": captured})
            self._check(session)
            _JSON.validate(payload)
            if len(payload["messages"]) > MAX_CONTEXT_BLOCKS:
                raise SchemaContractError("mcp_context_block_limit")
            for message in payload["messages"]:
                block = message["content"]
                if block["type"] in {"image", "audio"}:
                    _binary(block["data"])
                elif block["type"] == "resource":
                    _resource(block["resource"])
                elif block["type"] == "resource_link":
                    _uri(block["uri"])
            return McpContextResult(source, copy.deepcopy(payload))
