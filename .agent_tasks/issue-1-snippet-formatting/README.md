# Issue 1: snippet-only Python formatting

Scope: isolate `python_exec` Black formatting to the submitted string; retain
execution when formatting fails or exceeds its short deadline, with no workspace
source tracking. Worktree: `codex/issue-1-snippet-formatting`.

Status: PR #6 targets `0.4.1`. The branch includes current main's independently merged CI PR #4; refreshed checks passed 140 tests (Python execution/snippet/workspace/manual formatting and prompt coverage). Shared prompt guidance explicitly describes generated-file formatting.

Review (2026-10-15): focused review passed 140 tests, Ruff and
Mypy. Found that Black can expand a 229-byte nested-list expression to 44,039
bytes, exceeding Windows' process command-line limit. Added failing regressions
for both execution modes, then capped captured/formatted output at 12 KiB with
warning fallback to original source. All 19 snippet tests now pass; durable tool
docs and changelog describe the limit. Native Windows verification remains CI's
responsibility; local coverage checks the actual Black expansion and both argv
dispatch paths.

Final review verification after merging staging CI commit `ac05eab`: 166 tests
passed across snippet/execution/recovery, automatic/manual/registry formatting,
background execution, prompts and package surface. Ruff passed touched Python
files; Mypy passed all four changed production modules. Whitespace checks passed.
Review fix: `414a333`; staging merge: `d32e15a`.
Latest staging (merged standards PR #5 at `8d9327b`) is also integrated as
`1af662e`. Its docs-only changes merged cleanly while retaining standards, CI and
snippet changelog entries; 42 final snippet/documentation/package checks passed.

Integration follow-up: reproduced the stale package scenario's failure at
`wheel_matches_source`: Python execution now intentionally leaves generated
sources unchanged, so the combined mutation/build no longer creates a stale
wheel. Switched only `build_before_format` to a foreground shell invocation,
whose real workspace formatting occurs after its build. Kept `late_edit` on
Python execution and added an assertion that the engineer's shell succeeded.
The repaired single scenario passed, then all nine real package-scenario tests
passed on the final test code. Focused Ruff, Mypy and whitespace checks passed.

## Findings and implementation

- Foreground calls previously entered shared workspace snapshots before running;
  the 5,000-source cap could reject otherwise valid snippets.
- Both execution modes now share an isolated Black string-API worker with a
  300 ms deadline and bounded input/output. Larger inputs and formatting failures
  warn and run unchanged. Existing execution failures and cancellation remain real.
- Python snippet calls bypass workspace tracking. File-write, generic command,
  shell and explicit formatting contracts retain their existing backend.
- Durable tool docs, changelog and roadmap describe generated-file formatting
  as explicit work in either Python execution mode.

## Validation

- TDD baseline: new focused tests produced 11 failures and 1 pass before code.
- Initial implementation: 12 new tests passed; existing workspace-formatter
  coverage adapted to a generic command tool, with 25 tests passing.
- Focused regression run passed 103 tests across Python execution/recovery,
  snippet formatting, registry/workspace formatting, background jobs and manual
  formatting. Final serialization refinement passed the 65 affected tests,
  including Python-based verification waiting for an in-flight file edit.
- Ruff passed all touched Python modules/tests; Mypy passed the three touched
  production modules. `git diff --check` passed.
- No production API calls. Review fixes are committed and pushed only to the
  authorized PR branch; merge is handled by the parent release task.
