"""Compatibility MCP manager with lightweight server lifecycle support."""

from __future__ import annotations

import asyncio
import copy
import logging
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import TYPE_CHECKING
from weakref import WeakSet

from henchman.config.schema import McpServerConfig
from henchman.mcp.auth import McpAuthService
from henchman.mcp.client import McpClient, McpClientProtocol
from henchman.mcp.credentials import environment_references, reference_values, resolve_environment
from henchman.mcp.tool import McpTool
from henchman.utils.evidence_redaction import EvidenceRedactor

logger = logging.getLogger(__name__)
_NativeMcpClient = McpClient

if TYPE_CHECKING:
    from henchman.config.schema import Settings
    from henchman.mcp.client import McpToolDefinition


ClientFactory = Callable[[str, McpServerConfig, bool], McpClientProtocol]


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
            if not mcp_logging_enabled:
                env = cls._build_logging_env(server_name, config, env)
            configs[server_name] = config.model_copy(update={"env": env})

        manager = cls(configs, verbose=mcp_logging_enabled)
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
        lock = self._connection_locks.setdefault(server_name, asyncio.Lock())
        async with lock:
            await self.disconnect_server(server_name)
            config = self._client_config(server_name)
            environment = resolve_environment(config.env)
            self._remember_environment(config.env, environment)
            generation = self._generations.get(server_name, 0)
            identity = (config.command, tuple(config.args), config.trusted, dict(config.env))

            def guard() -> None:
                if self._generations.get(server_name, 0) != generation:
                    raise RuntimeError("MCP credentials or connection changed; reconnect the server before dispatch")
                try:
                    if server_name in self.configs:
                        current_config = self._client_config(server_name)
                        current_identity = (
                            current_config.command, tuple(current_config.args),
                            current_config.trusted, current_config.env,
                        )
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
                client.set_dispatch_guard(guard)
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

    def _client_config(self, server_name: str) -> McpServerConfig:
        config = self.configs[server_name]
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

    def _invalidate(self, server_name: str) -> None:
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
            config = self.configs.get(server_name, McpServerConfig(command="true"))
            for tool_definition in client.get_tools():
                wrapped.append(
                    McpTool(
                        mcp_tool=tool_definition,
                        client=client,
                        server_name=server_name,
                        trusted=config.trusted,
                        before_call=self._guards.get(server_name),
                    ),
                )
        return wrapped

    def get_server_names(self) -> list[str]:
        """Return names of all configured servers.

        Returns:
            List of server name strings.
        """
        return list(self.configs.keys())

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

        command = config.command
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
