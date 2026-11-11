# Workflow process recovery and import order — 2026-11-08

Commit `b066f10` fixes a fresh-interpreter import cycle between session workflow,
the infrastructure package and the CLI updater. The public `AutoUpdater`
export stays available and discoverable. It also adds a process-death regression:
an owned child persists a goal and two inputs, claims the first and records a
synthetic effect, then is killed. A new runtime opens the durable session,
reports the first input as outcome unknown, holds the second and refuses goal
continuation until explicit user dispositions. The test does not execute the
synthetic input or establish behavior of arbitrary external side effects.

A later test-only extension also verifies that the saved goal policy and bound
check identity survive process death. Changing a checked file after reopening
makes the recorded pass stale and blocks model completion until verification
is rerun. This extended case passed on Linux Python 3.11 from source and Python
3.12 against the installed development wheel described below.

On Linux Python 3.11.15 and 3.12.13, 93 focused workflow, session persistence,
updater and import-order tests passed for the implementation. The strengthened
two-order import assertions also passed separately on both versions. Another 17
installed-wheel smoke harness tests passed on Python 3.11. Ruff passed for the
touched code and tests; mypy passed for the infrastructure package export.

A separate Linux Python 3.12 development wheel passed the three new import and
process-death cases in an isolated environment that asserted its Henchman import
came from `site-packages`. The wheel was built from source `17d7122` with the
`b066f10` infrastructure export applied; its packaged export bytes match that
commit. Its SHA-256 is
`aeca70ffe77d35ad79a2980b3fa1ec8a1467c342b89daa1385c8515a09bd46ca`.
It reports version 0.4.1 and is not a release artifact.

The regression is included in the installed-wheel smoke matrix for future
native runs. These local checks do not qualify Windows/macOS process handling,
the complete session-recovery issue or a release candidate.
An attempted offline Python 3.13 wheel setup could not resolve an `aiohttp`
dependency from the local cache, so no Python 3.13 test ran in that environment.
