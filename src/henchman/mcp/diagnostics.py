"""Project SDK transport diagnostics under the creating client's credentials."""

from __future__ import annotations

import logging
import traceback
from collections.abc import Iterable, Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar

from henchman.utils.evidence_redaction import EvidenceRedactor

_policy: ContextVar[EvidenceRedactor | None] = ContextVar("henchman_mcp_diagnostics", default=None)


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
