# Issue 1: snippet-only Python formatting

Scope: isolate `python_exec` Black formatting to the submitted string; retain
execution when formatting fails or exceeds its short deadline, with no workspace
source tracking. Worktree: `codex/issue-1-snippet-formatting`.

Status: PR #6 targets `0.4.1`. The branch includes current main's independently merged CI PR #4; refreshed checks passed 140 tests (Python execution/snippet/workspace/manual formatting and prompt coverage). Shared prompt guidance explicitly describes generated-file formatting.

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
- No production API calls, GitHub mutations, or source-repository edits.
