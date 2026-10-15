# Production team evaluation checkpoint

The overall coding-agent goal remains active. This slice adds measurement through
the production team runtime; it does not establish industry-leading performance.

## Implemented scope

- Explicit `EvalTestRig(profile="team", settings=...)` uses real orchestration,
  specialist scopes, shared builtin registration and headless execution.
- Per-role execution bounds, request/result attribution, root completion and
  recovered child diagnostics remain distinct. Ambiguous outstanding call IDs
  fail closed. Settings are copied; standalone configurations are rejected in
  team mode instead of silently ignored.
- Provider ownership survives partial setup and lazy role construction; the CLI
  closes distinct clients while preserving primary errors and workspace cleanup.
- A Python reuse/CLI scenario independently checks helper reuse, behavior, CLI
  execution, protected fixtures, fixed Ruff lint/format and strict mypy policies.
- `python -m evals.run_team` loads shared provider settings before temporary CWD
  setup, validates limits, redacts known credentials and preserves atomic JSON
  reports outside workspace cleanup. Unmeasured usage and cost remain null.
- Runtime observers permit bounded artifact snapshots on retained events. Scenario
  version 2 requires tests and review after the last observed implementation
  change, including edits through shell or Python. Read-only later commands stay
  valid; unreadable snapshots and protected-file changes fail closed.

## First bounded OpenRouter sample

The user identified their existing key in `~/.bashrc`. A literal-export parser
read it without executing the file, printing the value or persisting it. The
auth endpoint returned HTTP200. Only the live subprocess received the key.

One MiMo `xiaomi/mimo-v2.6-pro` team probe completed with a failed scenario:

- 32,768 raw context, 24,576 conversation target, 8,192 output cap.
- 12 tool rounds per agent; delegation depth 3, turns 12, retries 0; SDK retries 0.
- Global request cap 24, whole-runtime deadline 480 seconds; routing price filters
  bounded eligible provider prices. These limits do not establish billed cost.
- 17 requests started, 16 completed; 33 attributed tool calls. Runtime timed out
  at approximately 480 seconds before required post-edit pytest and review.
- All independent artifact checks passed: behavior, helper reuse, CLI, fixtures,
  changed implementation, artifact stability, Ruff lint, Ruff format and mypy.
- Inspection and engineer implementation were observed; post-edit pytest and
  independent specialist review were absent. Overall success is false.
- Attributed calls: leader 13, explorer 11, engineer 9. The explorer wrote a
  scratch probe and notes; the engineer wrote the two implementation files.
  The four slowest completed requests took approximately 97, 81, 73 and 48
  seconds. These observations motivate latency/coordination investigation; they
  do not isolate a root cause from this one sample.
- Usage is incomplete because the final request was cancelled. No billed total
  or full token aggregate is claimed.

Evidence: `team-python-live-mimo-report.json`, `team-python-live-mimo.log` and
`team-python-live-mimo-artifacts/` in this directory. The probe used scenario
version 1, before artifact-timeline hardening, and was not silently rerun.
No further live calls are planned for this slice.

## Review and verification

Independent review found and owners fixed partial/lazy provider leaks,
client-close cancellation masking primary errors and cleanup, and ambiguous
outstanding actor/call-ID attribution. A later review reproduced shell edits
after tests/review bypassing named-tool timing; artifact tracking addresses it.
The Python mutation regression now delegates to the engineer and asserts tool
execution succeeds, since the canonical leader correctly denies `python_exec`.
Unrelated notes writes preserve verification; later tracked-source writes require
fresh tests and review.

Fresh runtime/runner/helper/discovery/staging gate: 149 passed. Ruff passed on
eight touched implementation/test files; mypy passed on seven checked files.
The final source oracle passed all 29 cases (178 focused source tests combined).
Source gates each report the existing Chroma asyncio deprecation warning.
The final isolated Linux/Python 3.12 installed-wheel gate passed 1,172 tests in
131.87 seconds, including the updated scenario. Both installed CLI aliases and
local vector operations passed. Installed Python/type file bytes match all 323
files in the built wheel. This is Linux evidence, not native macOS/Windows proof.

Logs: `team-evaluation-final-runtime.log`,
`team-evaluation-final-oracle-v2.log`, `team-evaluation-wheel-linux-v2.log`.

## Remaining goal evidence

Improve coordination and latency using the failed live sample, then measure more
than one task/model/provider. Native macOS/Windows behavior, physical16GB memory,
broader Python/DevOps tasks and comparative performance remain unproven. This
host is not the requested 16 GB laptop. No changes were committed or published.
