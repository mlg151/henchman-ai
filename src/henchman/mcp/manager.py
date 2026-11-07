"""Compatibility MCP manager with lightweight server lifecycle support."""

from __future__ import annotations

import asyncio
import copy
import json
import logging
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from time import monotonic
from typing import TYPE_CHECKING
from uuid import uuid4
from weakref import WeakKeyDictionary, WeakSet

from henchman.config.schema import McpServerConfig
from henchman.mcp.auth import McpAuthService
from henchman.mcp.client import McpClient, McpClientProtocol
from henchman.mcp.credentials import environment_references, reference_values, resolve_environment
from henchman.mcp.tool import McpTool
from henchman.utils.evidence_redaction import EvidenceRedactor

logger = logging.getLogger(__name__)
_NativeMcpClient = McpClient
MAX_CONTEXT_PREVIEWS = 16
MAX_CONTEXT_PREVIEW_BYTES = 4 * 1024 * 1024
CONTEXT_PREVIEW_TTL_SECONDS = 600.0

if TYPE_CHECKING:
    from henchman.config.schema import Settings
    from henchman.mcp.client import McpToolDefinition
    from henchman.mcp.context import ContextFamily, McpContextCatalog, McpContextResult
    from henchman.tools.registry import ToolRegistry


ClientFactory = Callable[[str, McpServerConfig, bool], McpClientProtocol]


@dataclass
class _ContextPreview:
    client: McpClient
    result: McpContextResult
    captured_at: float
    size: int
    session: object | None = None
    agent: object | None = None
    claimed: bool = False


def _create_mcp_client(
    name: str,
    config: McpServerConfig,
    verbose: bool,
) -> McpClient:
    """Adapt the concrete client's keyword-only flag to ``ClientFactory``."""
    return McpClient(name, config, verbose=verbose)


class McpManager:
    """Manage configured MCP clients and expose their wrapped tools."""

    def __init__(
        self,
        configs: dict[str, McpServerConfig] | None = None,
        *,
        verbose: bool = False,
        client_factory: ClientFactory | None = None,
    ) -> None:
        """Initialize the manager with server configurations."""

        self.configs = dict(configs or {})
        self.clients: dict[str, McpClientProtocol] = {}
        self._verbose = verbose
        self._auth_tokens: dict[str, str] = {}
        self._revoked_auth: set[str] = set()
        self._generations: dict[str, int] = {}
        self._guards: dict[str, Callable[[], None]] = {}
        self._connection_locks: dict[str, asyncio.Lock] = {}
        self._connecting: dict[str, McpClientProtocol] = {}
        self._evidence = EvidenceRedactor()
        self._evidence_policies: WeakSet[EvidenceRedactor] = WeakSet()
        self._client_factory = client_factory or _create_mcp_client
        self._catalog_generations: dict[str, int] = {}
        self._registries: WeakKeyDictionary[ToolRegistry, dict[str, dict[str, McpTool]]] = WeakKeyDictionary()
        self._access_guard: Callable[[], None] | None = None
        self._context_previews: dict[str, _ContextPreview] = {}
        for config in self.configs.values():
            self._remember_environment(config.env)

    def register_evidence(self, redactor: EvidenceRedactor) -> None:
        """Bind display/persistence evidence, including earlier credentials after revocation."""
        for config in self.configs.values():
            self._remember_environment(config.env)
        self._evidence_policies.add(redactor)
        redactor.register_policy(self._evidence)

    def _remember_environment(
        self, environment: Mapping[str, str], resolved: Mapping[str, str] | None = None,
    ) -> None:
        self._evidence.register_config(environment)
        self._evidence.register_config({"secret": environment_references(environment)})
        if resolved is not None:
            self._evidence.register_config(resolved)
            for value in reference_values(environment, resolved):
                self._evidence.register_secret(value)
        for policy in self._evidence_policies:
            policy.register_policy(self._evidence)

    @classmethod
    def create_from_settings(
        cls,
        settings: Settings | None,
        mcp_logging_enabled: bool = False,
        *,
        project_root: Path | None = None,
    ) -> McpManager | None:
        """Create a manager from application settings.

        Args:
            settings: Application settings, or None.
            mcp_logging_enabled: Whether to enable verbose MCP logging.
            project_root: Optional project root for auth token resolution.

        Returns:
            A new McpManager instance, or None when *settings* is None
            or has no MCP servers configured.
        """
        if settings is None or settings.mcp_servers is None:
            return None

        if not settings.mcp_servers:
            return None

        # Clone configs and inject logging-suppression environment variables
        configs: dict[str, McpServerConfig] = {}
        for server_name, config in settings.mcp_servers.items():
            env = dict(config.env)
            if not mcp_logging_enabled and config.transport == "stdio":
                env = cls._build_logging_env(server_name, config, env)
            configs[server_name] = config.model_copy(update={"env": env})

        manager = cls(configs, verbose=mcp_logging_enabled)
        initial_tools = copy.deepcopy(settings.tools)

        def check_access() -> None:
            from henchman.tools.access_policy import ToolAccessError, validate_tool_backend

            for controls in (initial_tools, settings.tools):
                validate_tool_backend(controls)
                if (controls.network_access == "disabled" or controls.filesystem_read_roots is not None
                    or controls.filesystem_write_roots is not None):
                    raise ToolAccessError("MCP transport is unsupported under restricted filesystem/network policy")

        manager._access_guard = check_access
        auth_service = McpAuthService(project_root)
        for server_name in configs:
            token = auth_service.get_token(server_name)
            if token:
                manager.set_auth_token(server_name, token)
        return manager

    async def connect_all(self) -> None:
        """Attempt to connect every configured MCP server."""

        for server_name in self.configs:
            try:
                await self.connect_server(server_name)
            except Exception as error:
                logger.warning(
                    "Failed to connect to MCP server %r: %s",
                    self._evidence.text(server_name), self._evidence.text(str(error)),
                )
                continue

    async def connect_server(self, server_name: str) -> None:
        """Connect one configured MCP server."""
        if self._access_guard is not None:
            self._access_guard()
        lock = self._connection_locks.setdefault(server_name, asyncio.Lock())
        async with lock:
            await self.disconnect_server(server_name)
            config = self._client_config(server_name)
            environment = resolve_environment(config.env)
            self._remember_environment(config.env, environment)
            generation = self._generations.get(server_name, 0)
            identity = self._config_identity(config)

            def guard() -> None:
                if self._generations.get(server_name, 0) != generation:
                    raise RuntimeError("MCP credentials or connection changed; reconnect the server before dispatch")
                try:
                    if server_name in self.configs:
                        current_config = self._client_config(server_name)
                        current_identity = self._config_identity(current_config)
                        current = resolve_environment(current_config.env)
                        self._remember_environment(current_config.env, current)
                    else:
                        current_identity = None
                        current = None
                except ValueError:
                    self._invalidate(server_name)
                    raise
                if current_identity != identity or current != environment:
                    self._invalidate(server_name)
                    raise RuntimeError("MCP configuration or environment changed; reconnect the server before dispatch")

            client = self._client_factory(server_name, config, self._verbose)
            if isinstance(client, _NativeMcpClient):
                # The native owner increments on successful negotiation. Seed
                # it from this manager so replacement clients cannot reuse a
                # prior connection's context provenance generation.
                client.connection_generation = generation - 1
                client.set_dispatch_guard(guard)
                if self._access_guard is not None:
                    client.set_access_guard(self._access_guard)
            self._connecting[server_name] = client
            try:
                await client.connect()
                guard()
            except BaseException:
                await client.disconnect()
                raise
            finally:
                if self._connecting.get(server_name) is client:
                    self._connecting.pop(server_name)
            self.clients[server_name] = client
            self._guards[server_name] = guard
            try:
                self._update_bound_server(server_name)
            except BaseException:
                await self.disconnect_server(server_name)
                raise

    def _client_config(self, server_name: str) -> McpServerConfig:
        config = self.configs[server_name]
        if config.transport == "streamable_http" and self._auth_tokens.get(server_name):
            raise RuntimeError("MCP stdio tokens cannot authenticate HTTP; OAuth is not configured")
        environment = dict(config.env)
        if server_name in self._revoked_auth:
            environment.pop("HMN_MCP_AUTH_TOKEN", None)
        elif token := self._auth_tokens.get(server_name):
            environment["HMN_MCP_AUTH_TOKEN"] = token
        # The public MCP package still exports a legacy dataclass config.
        # Both it and the settings model support an independent copied env.
        client_config = copy.deepcopy(config)
        client_config.env = environment
        return client_config

    @staticmethod
    def _config_identity(config: McpServerConfig) -> tuple[object, ...]:
        return (config.transport, config.command, tuple(config.args), config.url, config.trusted, dict(config.env),
                config.request_timeout_seconds, config.negotiation_timeout_seconds, config.catalog_timeout_seconds)

    def _invalidate(self, server_name: str) -> None:
        self._context_previews = {key: item for key, item in self._context_previews.items()
                                  if item.result.source.server != server_name}
        self._generations[server_name] = self._generations.get(server_name, 0) + 1
        client = self.clients.get(server_name)
        if isinstance(client, _NativeMcpClient):
            client.invalidate_credentials()
        starting = self._connecting.get(server_name)
        if isinstance(starting, _NativeMcpClient):
            starting.invalidate_credentials()

    def _connection_valid(self, server_name: str) -> bool:
        if server_name not in self.clients:
            return False
        client = self.clients[server_name]
        if isinstance(client, _NativeMcpClient) and not client.is_connected:
            return False
        guard = self._guards.get(server_name)
        try:
            if guard is not None:
                guard()
        except (ValueError, RuntimeError):
            return False
        return True

    async def disconnect_all(self) -> None:
        """Disconnect all active MCP clients."""
        failures: list[BaseException] = []
        for server_name in set(self.clients) | set(self._connecting):
            try:
                await self.disconnect_server(server_name)
            except BaseException as error:
                failures.append(error)
        if len(failures) == 1:
            raise failures[0]
        if failures:
            raise BaseExceptionGroup("MCP shutdown failures", failures)

    async def disconnect_server(self, server_name: str) -> None:
        """Disconnect one active MCP client."""
        self._invalidate(server_name)
        self._guards.pop(server_name, None)
        for registry, servers in self._registries.items():
            for name, tool in servers.pop(server_name, {}).items():
                if registry.get(name) is tool:
                    registry.unregister(name)
        client = self.clients.pop(server_name, None)
        starting = self._connecting.get(server_name)
        if starting is not None:
            await starting.disconnect()
        if client is None:
            return
        await client.disconnect()

    def get_all_tools(self) -> list[McpTool]:
        """Return wrapped tools from all connected clients."""

        wrapped: list[McpTool] = []
        for server_name, client in self.clients.items():
            if not self._connection_valid(server_name):
                continue
            wrapped.extend(self._wrap_tools(server_name, client.get_tools()))
        return wrapped

    def _wrap_tools(self, server_name: str, definitions: list[McpToolDefinition]) -> list[McpTool]:
        client = self.clients[server_name]
        generation = self._catalog_generations.get(server_name, 0)
        connection_guard = self._guards.get(server_name)

        def guard() -> None:
            if self._catalog_generations.get(server_name, 0) != generation:
                raise RuntimeError("MCP catalog changed; resolve a current tool before dispatch")
            if self.clients.get(server_name) is not client:
                raise RuntimeError("MCP connection changed; reconnect the server before dispatch")
            if connection_guard is not None:
                connection_guard()

        config = self.configs.get(server_name, McpServerConfig(command="true"))
        return [McpTool(definition, client, server_name, trusted=config.trusted, before_call=guard)
                for definition in definitions]

    @staticmethod
    def _check_registration(
        registry: ToolRegistry, names: list[str], owned: dict[str, McpTool],
    ) -> None:
        if len(set(names)) != len(names):
            raise ValueError("MCP catalog has conflicting registered names")
        for name in names:
            existing = registry.get(name)
            if existing is not None and existing is not owned.get(name):
                raise ValueError("MCP catalog conflicts with a separately registered tool")

    def bind_registry(self, registry: ToolRegistry) -> None:
        """Bind a parent catalog; restricted live views retain their own allowlists."""
        from henchman.tools.scoped_registry import ScopedToolRegistry

        if isinstance(registry, ScopedToolRegistry):
            raise ValueError("Bind the MCP catalog to a parent registry, not a scoped tool view")
        servers = {name: {tool.name: tool for tool in self._wrap_tools(name, client.get_tools())}
                   for name, client in self.clients.items() if self._connection_valid(name)}
        owned = {name: tool for tools in self._registries.get(registry, {}).values() for name, tool in tools.items()}
        names = [name for tools in servers.values() for name in tools]
        self._check_registration(registry, names, owned)
        for name, tool in owned.items():
            if registry.get(name) is tool:
                registry.unregister(name)
        for tools in servers.values():
            for tool in tools.values():
                registry.register(tool)
        self._registries[registry] = servers

    def _update_bound_server(self, server_name: str) -> None:
        definitions = self.clients[server_name].get_tools()
        names = [f"mcp_{server_name}_{tool.name}" for tool in definitions]
        for registry, servers in self._registries.items():
            self._check_registration(registry, names, servers.get(server_name, {}))
        wrapped = self._wrap_tools(server_name, definitions)
        for registry, servers in self._registries.items():
            for name, old in servers.get(server_name, {}).items():
                if registry.get(name) is old:
                    registry.unregister(name)
            for tool in wrapped:
                registry.register(tool)
            servers[server_name] = {tool.name: tool for tool in wrapped}

    async def refresh_server(self, server_name: str) -> list[McpToolDefinition]:
        """Atomically refresh a native catalog and invalidate prior wrapper grants."""
        lock = self._connection_locks.setdefault(server_name, asyncio.Lock())
        async with lock:
            if not self._connection_valid(server_name):
                raise RuntimeError("MCP server is not connected; connect before refreshing its catalog")
            client = self.clients[server_name]
            if not isinstance(client, _NativeMcpClient):
                raise RuntimeError("This MCP client does not support atomic catalog refresh")
            async with client._discovery_lock:
                definitions = await client.prepare_tools()
                names = [f"mcp_{server_name}_{tool.name}" for tool in definitions]
                for registry, servers in self._registries.items():
                    self._check_registration(registry, names, servers.get(server_name, {}))
                # No await from publication through registry replacement: a
                # cancellation or malformed later page cannot publish a subset.
                client.publish_tools(definitions)
                self._catalog_generations[server_name] = self._catalog_generations.get(server_name, 0) + 1
                self._update_bound_server(server_name)
                return client.get_tools()

    def get_server_names(self) -> list[str]:
        """Return names of all configured servers.

        Returns:
            List of server name strings.
        """
        return list(self.configs.keys())

    def _context_client(self, server_name: str) -> McpClient:
        """Require the current native connection without connecting implicitly."""
        if not self._connection_valid(server_name):
            raise RuntimeError("MCP server is not connected; connect before retrieving context")
        client = self.clients[server_name]
        if not isinstance(client, _NativeMcpClient):
            raise RuntimeError("This MCP client does not support context retrieval")
        return client

    async def list_resources(self, server_name: str) -> McpContextCatalog:
        """Explicitly refresh one connected server's resource catalog."""
        return await self._context_client(server_name).list_resources()

    async def list_resource_templates(self, server_name: str) -> McpContextCatalog:
        """Explicitly refresh one server's URI template descriptions."""
        return await self._context_client(server_name).list_resource_templates()

    async def list_prompts(self, server_name: str) -> McpContextCatalog:
        """Explicitly refresh one connected server's prompt catalog."""
        return await self._context_client(server_name).list_prompts()

    async def read_resource(self, server_name: str, uri: str) -> McpContextResult:
        """Retrieve data from an explicitly selected server and opaque URI."""
        client = self._context_client(server_name)
        return self._capture_context_preview(client, await client.read_resource(uri))

    async def get_prompt(self, server_name: str, name: str, arguments: dict[str, str]) -> McpContextResult:
        """Retrieve a previously discovered prompt as untrusted data."""
        client = self._context_client(server_name)
        return self._capture_context_preview(client, await client.get_prompt(name, arguments))

    def _check_context_preview(self, preview: _ContextPreview) -> None:
        source = preview.result.source
        client = self._context_client(source.server)
        family: ContextFamily = "resources" if source.operation == "resources/read" else "prompts"
        if (client is not preview.client or source.connection_generation != client.connection_generation
            or source.catalog_generation != client._context.generations.get(family, 0)):
            raise ValueError("MCP preview is stale; explicitly retrieve a new preview")
        client._check_credentials()

    def _expire_context_previews(self) -> None:
        now = monotonic()
        self._context_previews = {key: item for key, item in self._context_previews.items()
                                  if item.claimed or now - item.captured_at < CONTEXT_PREVIEW_TTL_SECONDS}

    def _capture_context_preview(self, client: McpClient, result: McpContextResult) -> McpContextResult:
        self._expire_context_previews()
        captured = replace(copy.deepcopy(result), preview_id=uuid4().hex)
        size = len(json.dumps(asdict(captured), ensure_ascii=True, allow_nan=False).encode("utf-8"))
        if size > MAX_CONTEXT_PREVIEW_BYTES:
            raise ValueError("MCP preview exceeds the retained preview byte limit")
        preview = _ContextPreview(client, captured, monotonic(), size)
        self._check_context_preview(preview)
        while (len(self._context_previews) >= MAX_CONTEXT_PREVIEWS
               or sum(item.size for item in self._context_previews.values()) + size > MAX_CONTEXT_PREVIEW_BYTES):
            evict = next((key for key, item in self._context_previews.items() if not item.claimed), None)
            if evict is None:
                raise ValueError("MCP preview capacity is busy; retry the explicit retrieval later")
            del self._context_previews[evict]
        assert captured.preview_id is not None
        self._context_previews[captured.preview_id] = preview
        return copy.deepcopy(captured)

    def _context_preview(self, identity: str | None) -> _ContextPreview:
        self._expire_context_previews()
        preview = self._context_previews.get(identity) if isinstance(identity, str) else None
        if preview is None or preview.claimed:
            raise ValueError("MCP preview is unknown, expired, consumed or busy; retrieve a new preview")
        self._check_context_preview(preview)
        return preview

    def bind_context_preview(self, identity: str | None, session: object, agent: object) -> None:
        """Bind a displayed capture to one exact live session and history owner."""
        preview = self._context_preview(identity)
        if session is None or agent is None:
            raise ValueError("MCP preview requires a current session and agent")
        if preview.session is not None and (preview.session is not session or preview.agent is not agent):
            raise ValueError("MCP preview belongs to another session or agent")
        preview.session, preview.agent = session, agent

    def commit_context_preview(
        self, identity: str | None, session: object, agent: object,
        append: Callable[[McpContextResult], None],
    ) -> None:
        """Commit synchronously once; a failed append leaves the handle usable."""
        preview = self._context_preview(identity)
        if preview.session is None or preview.agent is None or preview.session is not session or preview.agent is not agent:
            raise ValueError("MCP preview belongs to another session or agent")
        preview.claimed = True
        try:
            append(copy.deepcopy(preview.result))
        except BaseException:
            preview.claimed = False
            raise
        assert identity is not None
        self._context_previews.pop(identity, None)

    def is_trusted(self, server_name: str) -> bool:
        """Check whether a configured server is trusted.

        Args:
            server_name: Name of the server to check.

        Returns:
            True if the server config has trusted=True.
        """
        config = self.configs.get(server_name)
        return config.trusted if config else False

    def list_servers(self) -> list[dict[str, object]]:
        """Return status metadata for all configured servers."""

        return [
            {
                "name": server_name,
                "connected": self._connection_valid(server_name),
                "trusted": config.trusted,
                "auth_configured": server_name in self._auth_tokens,
            }
            for server_name, config in self.configs.items()
        ]

    async def call_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: dict[str, object],
    ) -> object:
        """Call a tool on one connected server.

        Args:
            server_name: Name of the server to call.
            tool_name: Name of the tool to invoke.
            arguments: Tool arguments dictionary.

        Returns:
            Tool result.

        Raises:
            KeyError: If *server_name* is not connected.
        """
        client = self.clients.get(server_name)
        if client is None:
            msg = f"Unknown MCP server: {server_name}"
            raise KeyError(msg)
        guard = self._guards.get(server_name)
        if guard is not None:
            guard()
        return await client.call_tool(tool_name, arguments)

    @staticmethod
    def _build_logging_env(
        server_name: str,
        config: McpServerConfig,
        env: dict[str, str],
    ) -> dict[str, str]:
        """Build MCP server logging environment variables.

        Args:
            server_name: Name of the server.
            config: Server configuration.
            env: Existing environment variables.

        Returns:
            Enriched environment variables for logging/disabling color.
        """
        result = dict(env)
        result["NO_COLOR"] = "1"
        result["TERM"] = "dumb"

        command = config.command or ""
        is_python = "python" in command or command in ("uvx", "uv")
        is_node = "node" in command or command in ("npx",)

        if is_python:
            result.setdefault("PYTHONWARNINGS", "ignore")
            result.setdefault("LOGLEVEL", "WARNING")
            result.setdefault("PYTHON_LOG_LEVEL", "WARNING")
            if "serena" in server_name.lower() or "serena" in " ".join(
                getattr(config, "args", []) or [],
            ):
                result.setdefault("SERENA_LOG_LEVEL", "WARNING")
        elif is_node:
            result.setdefault("NODE_ENV", "production")

        return result

    def discover_tools(self, server_name: str | None = None) -> list[McpToolDefinition]:
        """Return discovered tool definitions for one or all servers."""

        if server_name is not None:
            if not self._connection_valid(server_name):
                return []
            client = self.clients.get(server_name)
            if client is None:
                return []
            return list(client.get_tools())

        discovered: list[McpToolDefinition] = []
        for name, client in self.clients.items():
            if self._connection_valid(name):
                discovered.extend(client.get_tools())
        return discovered

    def set_auth_token(self, server_name: str, token: str) -> None:
        """Store an in-memory auth token for one server."""

        self._auth_tokens[server_name] = token
        self._remember_environment({"HMN_MCP_AUTH_TOKEN": token})
        self._revoked_auth.discard(server_name)
        self._invalidate(server_name)

    def clear_auth_token(self, server_name: str) -> None:
        """Remove an in-memory auth token for one server."""

        self._auth_tokens.pop(server_name, None)
        for policy in self._evidence_policies:
            policy.register_policy(self._evidence)
        self._revoked_auth.add(server_name)
        self._invalidate(server_name)
