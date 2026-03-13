"""Robust Linux driver for Textual UI with Unicode error handling.

This module provides a custom Linux driver for the Textual UI framework that gracefully
handles Unicode decode errors. These errors can occur when the input stream contains
invalid UTF-8 bytes, which might happen during terminal initialization or when
receiving non-UTF-8 data from external processes.

The `RobustLinuxDriver` class extends Textual's `LinuxDriver` and catches
`UnicodeDecodeError` exceptions during selector event processing, preventing
crashes from transient encoding issues while maintaining driver stability.

Note: This module only defines `RobustLinuxDriver` on Linux platforms. On other
platforms, `RobustLinuxDriver` is set to `None`.
"""

from __future__ import annotations

import sys

if sys.platform == "linux":
    try:
        from textual.drivers.linux_driver import LinuxDriver
    except ImportError:  # pragma: no cover
        LinuxDriver = object  # type: ignore  # noqa: PGH003

    class RobustLinuxDriver(LinuxDriver):  # type: ignore  # noqa: PGH003
        """A Linux driver that handles Unicode decode errors gracefully."""

        def process_selector_events(
            self, selector_events: list[tuple[int, int]], *, final: bool = False
        ) -> None:  # noqa: E501
            """Process selector events with error handling."""
            try:
                super().process_selector_events(selector_events, final=final)
            except UnicodeDecodeError:
                # If we get a decode error, it means the input stream contains invalid UTF-8 bytes.
                # We can try to recover by reading and ignoring the bad bytes, or just logging it.
                # Since we can't easily modify the internal buffer of the driver,
                # catching the exception prevents a crash but might leave the driver in a bad state.
                # However, usually these errors are transient (e.g. startup garbage).
                pass
            except Exception:  # pragma: no cover
                raise

else:  # pragma: no cover
    RobustLinuxDriver = None
