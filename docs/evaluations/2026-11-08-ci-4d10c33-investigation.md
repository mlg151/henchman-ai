# Windows wheel-smoke failure under investigation

The Windows/Python 3.11 installed-wheel job in
[CI run 42492539633](https://github.com/mlg151/henchman-ai/actions/runs/42492539633)
for head `4d10c336c6f5cf7ff7506f2ecb5331b2224c7c64` failed with
**1 failed, 5,943 passed and 236 skipped**. The failing scripted Anthropic
context-discovery test reported `Provider error: Connection error.` The complete
job log has SHA-256
`f127d08968a81b8a932b6db279f0a1e39cb76176680c8ff31aff27c2190bf137` and is
retained in the local qualification cache. Other jobs were still running when
this note was written; this is not a successful aggregate run.

An initial Linux reproduction used the job's Anthropic SDK 2.6.0 but an
incomplete temporary environment: the pytest subprocess could not import
Henchman. In that invalid setup, fixture diagnostics exposed an assertion
wrapped by the SDK as a connection error: `edit_file` was not among the
context-sized schemas. Additional searches then exceeded the 8K window because
the failed subprocess produced long import tracebacks. These observations do
not establish the cause of the native Windows failure. An attempted run of the
original fixture outside the repository also lacked asyncio configuration and
did not execute the test; a corrected original-fixture run passed locally.

The revised fixture makes the scripted model search for each required tool
before using it and includes callback errors in failure diagnostics. This
matches the existing replacement semantics for tool-search priorities. It
retains the 8K estimated window, 1,024-token output reservation, failed
pre-edit check and passing post-edit check. On Linux, all five scripted adapters
passed both with the locked Anthropic SDK 0.83.0 and with 2.6.0 in a separate
environment reusing local dependencies. No hosted inference was used.
Those focused results do not prove the native failure fixed; a fresh Windows
wheel run is required. Logs for the local attempts are retained alongside the
job log in `ci-4d10c33-42492539633` under the local qualification cache.

The Windows/Python 3.14 wheel job subsequently failed the same test with the
same surfaced connection error: **1 failed, 5,943 passed and 236 skipped**.
Its retained job log SHA-256 is
`11c16de8200daff1d5d3a124cad3e11272a820b263fb1ee5caf224a2b1c6133e`.
The matching surface alone does not establish that both jobs share a cause.

The Windows/Python 3.12 wheel job failed a separate pending-decision export
test: **1 failed, 5,943 passed and 236 skipped**. The test saw no export file,
and an export completion callback raised `NoMatches` after review widgets were
removed. The retained job log SHA-256 is
`3218c360699b84721f5bb43b1969ac073520f8a4c9291a897e7fc3870ef8621d`.
The log does not identify which format was missing or prove the cause of the
missing file. A deterministic local regression reproduced a completion refresh
after closing; the subsequent change guards that refresh and waits for each
export task to settle in the two-format test. Native verification remains open.

The revised tool-discovery fixture also passed all five scripted adapters on
Linux with the 2.6.0 SDK and a longer temporary project path. This does not
substitute for the Windows wheel jobs.
