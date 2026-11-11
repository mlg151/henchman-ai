"""One pinned HTTP/1.1 pre-header authority boundary for owned OAuth requests."""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from importlib.metadata import version
from types import MappingProxyType

import httpcore2
import httpx2


def require_oauth_http_profile() -> None:
    """Qualify the public trace event immediately before header transmission."""
    from henchman.mcp.oauth import OAuthError

    if version("httpx2") != "2.16.0" or version("httpcore2") != "2.16.0":
        raise OAuthError("Unsupported OAuth HTTP runtime profile; expected httpx2/httpcore2 2.16.0")


def guard_http_request(
    request: httpx2.Request, *, authorize: Callable[[], None], dispatched: Callable[[], None] | None = None,
) -> None:
    """Check before handoff and once after connection setup, before HTTP headers."""
    from henchman.mcp.oauth import OAuthError

    require_oauth_http_profile()
    if set(request.extensions) - {"timeout"}:
        raise OAuthError("OAuth HTTP request contains an unsupported transport extension")
    authorize()
    method = request.method.encode("ascii")
    url = request.url
    destination = httpcore2.URL(scheme=url.raw_scheme, host=url.raw_host, port=url.port, target=url.raw_path)
    attempted = False

    async def trace(event: str, info: dict[str, object]) -> None:
        nonlocal attempted
        if event == "http11.send_request_headers.started":
            if attempted:
                raise OAuthError("OAuth HTTP request replay is unsupported")
            attempted = True
            wire = info.get("request")
            if not isinstance(wire, httpcore2.Request) or wire.method != method or wire.url != destination:
                raise OAuthError("OAuth HTTP request destination changed before dispatch")
            authorize()
            if dispatched is not None:
                dispatched()
        elif event.startswith("http2."):
            raise OAuthError("OAuth HTTP/2 dispatch is not qualified")

    # Only the owned timeout and trace can reach the transport; mutable metadata
    # cannot install another trace or alter the HTTP request target extension.
    extensions = deepcopy(dict(request.extensions))
    extensions["trace"] = trace
    # HTTPX's public RequestExtensions is Mapping, but its attribute is inferred
    # as dict by mypy from the SDK's constructor implementation.
    request.extensions = MappingProxyType(extensions)  # type: ignore[assignment]
