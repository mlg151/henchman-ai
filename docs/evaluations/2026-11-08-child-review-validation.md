# Child proposal review validation — 2026-11-08

At the commits evaluated below, the staged proposal coordinator and file tools
were internal and not connected to dynamic subagents. These checks do not
establish delegated model effectiveness or a filesystem sandbox.

At commit `1bb5bb9`, an isolated archive of the committed source passed 103
focused tests on Linux with Python 3.11.15 and Python 3.12.13. The tests cover
worker ownership, staged file tools, parent preview and acknowledgement,
conflict-checked publication, interruption recovery and check invalidation.
The same 103 tests passed against a separately installed development wheel on
Linux Python 3.12.13; the installed package was imported from the test
environment's `site-packages` directory. That wheel reports version 0.4.1 and
is not a release artifact. Ruff and mypy passed for the touched implementation.

At `8ebe011`, a further focused test covers the current context compactor:
when prefix truncation cuts reviewed content, the acknowledgement token at the
end of the preview is also removed. That focused run passed on Linux Python
3.11.15. This does not establish that future delivery paths preserve that
ordering; any integration must maintain the complete-review boundary.

The cross-platform CI run on the earlier commit `cbd99de` does not qualify
these later commits. Native Windows and macOS
coverage, qualification of later live tool routing and parent approval, and
paired local-model delegation evaluation remain outstanding.
