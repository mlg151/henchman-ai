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

At `c8b0e43`, the new opt-in dynamic route passed 257 focused tests with one
skip on Linux Python 3.11.15 and 258 tests on Linux Python 3.12.13 from a clean
source archive. The Python 3.11 skip is the Python 3.12 eager-task-factory
case. A separately installed Linux Python 3.12 development wheel passed 188
focused tests, importing Henchman from `site-packages`. These include scripted
dynamic child execution, overlapping child proposals, user-edit conflicts,
policy changes, cancellation, stale review authority and separate publication
approval. They do not establish native-platform behavior or live-model quality.

The later CI runs on `303167c` exposed an Anthropic headless-team test failure
on multiple platform jobs. Using the installed `c8b0e43` wheel and a scripted
transport on Linux Python 3.12 with the same long temporary path, the estimated
input was 8,259 tokens plus the 8,192-token output reservation, exceeding the
test's 16,384-token context window. The earlier `cbd99de` wheel passed the same
scenario with 8,085 input tokens. A shorter path passed on the newer wheel with
only 58 tokens remaining. These are local reproductions, not measurements of
the CI machines' exact inputs.

The headless workflow test now uses a 32,768-token window because it tests team
execution and its prompts include variable temporary paths and the evolving tool
catalog. Both previously failing Anthropic output modes passed locally with the
long path; 49 focused request-budget, tool-disclosure and evaluation-harness
tests also passed. This test change does not remove the real 16K capacity
limitation or qualify the fix on Windows and macOS; new CI results are needed.
