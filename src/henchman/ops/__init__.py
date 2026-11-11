"""Tier 8 infrastructure primitives."""

from typing import TYPE_CHECKING

from henchman.ops.flags import FeatureFlagService
from henchman.ops.migrations import Migration, MigrationRunner
from henchman.ops.native import NativeBindings
from henchman.ops.observability import (
    AnalyticsService,
    CostTrackingService,
    DiagnosticTrackingService,
    TelemetryService,
)
from henchman.ops.rate_limits import ParsedRateLimit, RateLimiter, parse_rate_limit
from henchman.ops.state import AppStateStore
from henchman.ops.store import OpsStore
from henchman.ops.sync import SettingsSyncBackend

if TYPE_CHECKING:
    from henchman.ops.updater import AutoUpdater

__all__ = [
    "AnalyticsService",
    "AppStateStore",
    "AutoUpdater",
    "CostTrackingService",
    "DiagnosticTrackingService",
    "FeatureFlagService",
    "Migration",
    "MigrationRunner",
    "NativeBindings",
    "OpsStore",
    "ParsedRateLimit",
    "RateLimiter",
    "SettingsSyncBackend",
    "TelemetryService",
    "parse_rate_limit",
]


def __getattr__(name: str) -> object:
    """Load the CLI-dependent updater only when its public export is requested."""
    if name == "AutoUpdater":
        from henchman.ops.updater import AutoUpdater

        return AutoUpdater
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    """Keep the lazy public export visible to introspection."""
    return sorted({*globals(), "AutoUpdater"})
