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

import contextlib
import sys

if sys.platform == "linux":
    from textual.drivers.linux_driver import LinuxDriver

    class RobustLinuxDriver(LinuxDriver):
        """A Linux driver that handles Unicode decode errors gracefully."""

        def run_input_thread(self) -> None:
            """Run Textual input processing while tolerating invalid UTF-8."""
            with contextlib.suppress(UnicodeDecodeError):
                super().run_input_thread()
else:  # pragma: no cover
    RobustLinuxDriver = None
