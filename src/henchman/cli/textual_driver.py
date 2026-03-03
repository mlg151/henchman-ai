from __future__ import annotations

import sys

if sys.platform == "linux":
    try:
        from textual.drivers.linux_driver import LinuxDriver
    except ImportError:
        LinuxDriver = object  # type: ignore

    class RobustLinuxDriver(LinuxDriver):  # type: ignore
        """A Linux driver that handles Unicode decode errors gracefully."""

        def process_selector_events(self, selector_events: list[tuple[int, int]], final: bool = False) -> None:  # noqa: E501
            """Process selector events with error handling."""
            try:
                super().process_selector_events(selector_events, final)
            except UnicodeDecodeError:
                # If we get a decode error, it means the input stream contains invalid UTF-8 bytes.
                # We can try to recover by reading and ignoring the bad bytes, or just logging it.
                # Since we can't easily modify the internal buffer of the driver,
                # catching the exception prevents a crash but might leave the driver in a bad state.
                # However, usually these errors are transient (e.g. startup garbage).
                pass
            except Exception:
                raise

else:
    RobustLinuxDriver = None
