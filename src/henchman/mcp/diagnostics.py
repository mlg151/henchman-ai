"""Project SDK transport diagnostics under the creating client's credentials."""

from __future__ import annotations

import logging
import traceback
from collections.abc import Iterable, Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar

from henchman.utils.evidence_redaction import EvidenceRedactor

_policy: ContextVar[EvidenceRedactor | None] = ContextVar("henchman_mcp_diagnostics", default=None)
_http_private: ContextVar[bool] = ContextVar("henchman_mcp_http_diagnostics", default=False)


class _HttpDiagnostics(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # Transport debug records include raw URLs, headers and exception reprs.
        # Owned HTTP operations supply their own value-free failure diagnostics.
        return not _http_private.get()


for _http_logger_name in ("httpx2", "httpcore2.connection", "httpcore2.http11", "httpcore2.http2",
                          "httpcore2.proxy", "httpcore2.socks"):
    logging.getLogger(_http_logger_name).addFilter(_HttpDiagnostics())


@contextmanager
def http_diagnostics() -> Iterator[None]:
    """Suppress sensitive HTTP internals only inside an owned MCP operation."""
    token = _http_private.set(True)
    try:
        yield
    finally:
        _http_private.reset(token)


class _ScopedDiagnostics(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        policy = _policy.get()
        if policy is None:
            return True
        record.msg = policy.text(record.getMessage())
        record.args = ()
        if record.exc_info is not None:
            record.exc_text = policy.text("".join(traceback.format_exception(*record.exc_info)))
            record.exc_info = None
        elif record.exc_text:
            record.exc_text = policy.text(record.exc_text)
        if record.stack_info:
            record.stack_info = policy.text(record.stack_info)
        return True


# Logger filters run before every handler, including inherited root handlers.
# The filter carries no credentials; each SDK reader task inherits its own scope.
for _logger_name in (
    "mcp.client.stdio", "mcp.client.client", "mcp.shared.jsonrpc_dispatcher",
    "client",  # SDK 2.3 ClientSession deliberately uses this unqualified name.
):
    logging.getLogger(_logger_name).addFilter(_ScopedDiagnostics())


@contextmanager
def sdk_diagnostics(environment: Mapping[str, str], *, secrets: Iterable[str] = ()) -> Iterator[None]:
    """Capture credentials for child transport tasks without leaking caller scope."""
    policy = EvidenceRedactor(secrets)
    policy.register_config(environment)
    token = _policy.set(policy)
    try:
        yield
    finally:
        _policy.reset(token)
