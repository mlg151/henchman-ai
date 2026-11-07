"""Explicit manager OAuth operations; no transport activation or implicit replay."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

from henchman.config.schema import McpServerConfig, Settings
from henchman.mcp.auth import McpAuthService
from henchman.mcp.oauth import OAuthBinding, OAuthError
from henchman.mcp.oauth_flow import login_oauth, refresh_oauth
from henchman.mcp.oauth_store import OAuthStatus
from henchman.mcp.oauth_transport import OAuthHttpAuthority
from henchman.utils.evidence_redaction import EvidenceRedactor


class McpOAuthRuntime:
    """Bind a retained store to one settings owner and captured project root.

    A caller guard is mandatory for every public operation. The trusted embedding
    application must raise when its user/project authority changes; a configured
    server's tool-trust flag never substitutes for that authority.
    """

    def __init__(
        self, settings: Settings, project_root: Path, *, check_access: Callable[[], None],
        invalidate: Callable[[str], None], generation: Callable[[str], int], evidence: EvidenceRedactor,
    ) -> None:
        self._settings = settings
        self._project_root = project_root.resolve()
        self._check_access = check_access
        self._invalidate, self._generation = invalidate, generation
        self._evidence = evidence
        self._store = McpAuthService(self._project_root).oauth_store()
        self._pending: set[str] = set()
        self._teardown_depth = 0
        self._http_epoch = 0
        self.register_evidence(evidence)

    def matches(self, settings: Settings, project_root: Path) -> bool:
        return self._settings is settings and self._project_root == project_root.resolve()

    def register_evidence(self, evidence: EvidenceRedactor) -> None:
        """Retain observed old and new credentials in every bound evidence policy."""
        self._store.register_evidence(evidence)

    @staticmethod
    def _caller(authorize: Callable[[], object]) -> None:
        try:
            if not callable(authorize) or authorize() is not None:
                raise ValueError
        except Exception:
            raise OAuthError("OAuth requires current explicit trusted caller authority") from None

    def _configuration(self, server: str) -> McpServerConfig:
        try:
            configured = self._settings.mcp_servers[server]
            result = McpServerConfig.model_validate(configured.model_dump())
            OAuthBinding.from_config(server, result)
            return result
        except (KeyError, TypeError, ValueError, AttributeError):
            raise OAuthError("OAuth server configuration is missing or invalid") from None

    def _policy(self) -> None:
        try:
            self._check_access()
        except Exception:
            raise OAuthError("OAuth network access is unsupported under the current runtime policy") from None

    def status(self, server: str, *, authorize: Callable[[], None]) -> OAuthStatus:
        """Inspect the live configuration without writing, connecting or refreshing."""
        self._caller(authorize)
        binding = OAuthBinding.from_config(server, self._configuration(server))
        status, _authority = self._store.bound_status(binding)
        return status

    def capture_http(self, server: str, *, authorize: Callable[[], None]) -> OAuthHttpAuthority:
        """Capture ready authority for an explicit client; never connect or refresh."""
        self._caller(authorize)
        self._policy()
        if self._teardown_depth or server in self._pending:
            raise OAuthError("OAuth HTTP authority is unavailable during a pending operation or teardown")
        config = self._configuration(server)
        identity = config.model_dump()
        binding = OAuthBinding.from_config(server, config)
        status, authority = self._store.bound_status(binding)
        if authority is None or status.state != "ready" or self._store.credentials(authority) is None:
            raise OAuthError("OAuth HTTP requires a current ready access credential")
        generation = self._generation(server)
        http_epoch = self._http_epoch

        def common() -> None:
            self._caller(authorize)
            self._policy()
            if self._configuration(server).model_dump() != identity:
                raise OAuthError("OAuth runtime configuration changed")

        def active() -> None:
            if self._teardown_depth or self._http_epoch != http_epoch or self._generation(server) != generation:
                raise OAuthError("OAuth HTTP connection authority changed")

        return OAuthHttpAuthority(binding, self._store, authority, common, active)

    def logout(self, server: str, *, authorize: Callable[[], None]) -> OAuthStatus:
        """Revoke locally even after configuration removal or network restriction."""
        self._caller(authorize)
        # Read and validate the identity before invalidating the local manager.
        # The store learns retained credentials before replacing the record.
        self._store.status(server)
        self._invalidate(server)
        self._store.logout(server)
        return self._store.status(server)

    @contextmanager
    def teardown(self) -> Iterator[None]:
        """Revoke active flows before any await and fence admission until teardown exits."""
        self._teardown_depth += 1
        self._http_epoch += 1
        try:
            for server in tuple(self._pending):
                self._invalidate(server)
            yield
        finally:
            self._teardown_depth -= 1

    def _prepare(self, server: str, authorize: Callable[[], None]) -> tuple[OAuthBinding, Callable[[], None]]:
        self._caller(authorize)
        if self._teardown_depth:
            raise OAuthError("OAuth operations are unavailable during manager teardown")
        self._policy()
        config = self._configuration(server)
        if server in self._pending:
            raise OAuthError("OAuth operation is already pending for this server")
        identity = config.model_dump()
        binding = OAuthBinding.from_config(server, config)
        self._invalidate(server)
        generation = self._generation(server)

        def guard() -> None:
            self._caller(authorize)
            self._policy()
            if self._generation(server) != generation or self._configuration(server).model_dump() != identity:
                raise OAuthError("OAuth runtime configuration or connection authority changed")

        return binding, guard

    async def login(
        self, server: str, *, authorize: Callable[[], None], browser_opener: Callable[[str], Awaitable[None]],
        challenge: str | None = None,
    ) -> OAuthStatus:
        """Run one explicitly requested login with a caller-owned async browser."""
        if not callable(browser_opener):
            raise OAuthError("OAuth login requires an explicit async browser opener")
        binding, guard = self._prepare(server, authorize)
        self._pending.add(server)
        try:
            authority = await login_oauth(binding, self._store, authorize=guard, browser_opener=browser_opener,
                                          evidence=self._evidence, challenge=challenge)
            guard()
            status, matching = self._store.bound_status(binding)
            if matching != authority:
                raise OAuthError("OAuth completed authority changed before status publication")
            return status
        finally:
            self._pending.discard(server)

    async def refresh(self, server: str, *, authorize: Callable[[], None]) -> OAuthStatus:
        """Refresh one matching persisted authority once, without login fallback."""
        binding, guard = self._prepare(server, authorize)
        self._pending.add(server)
        try:
            _status, authority = self._store.bound_status(binding)
            if authority is None:
                raise OAuthError("OAuth credentials do not match current configuration; explicit login is required")
            current = await refresh_oauth(self._store, authority, authorize=guard, evidence=self._evidence)
            guard()
            status, matching = self._store.bound_status(binding)
            if matching != current:
                raise OAuthError("OAuth completed authority changed before status publication")
            return status
        finally:
            self._pending.discard(server)
