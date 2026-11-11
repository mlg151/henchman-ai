# Offline source suite at `6db0adf`

A clean detached worktree at
`6db0adfd88aedd458bbbca480052fbefa74c6521` ran the full `tests/` suite
on Linux with Python 3.11.15 and pytest 9.0.2: **12,665 passed, 91 skipped**
in 1,554.50 seconds. The command used `--no-cov`; this is not a coverage
measurement. The checkout was clean after the run. The retained pytest log
SHA-256 is `23ed19ec86b14fa3d0da6e892ad83e768bfd74a3b7f4a013aa1cb06e73b5a114`.

The run used a private home, XDG directories and temporary directory, the
existing local development dependencies and cached build backends, with uv and
pip offline. The suite's offline-network fixture blocks external SDK traffic in
the test process; model adapters in these tests use fixtures, not live inference.
Five warnings
were reported: an unawaited `AsyncMock` coroutine in a compaction test and four
Pydantic deprecation warnings in an extension test. These are retained in the
log and do not change the reported test outcome.

An initial attempt was interrupted after 28 passing tests when its empty
packaging cache was noticed. Its exit status was 130; it is not a full-suite
result. Its separate log and the completed run's log, exit status, worktree and
private runtime directories remain in the local qualification cache under
`source-6db0adf`. Later commits changed one regression-test line and release
evidence documentation. This observation does not qualify those later commits,
native Windows/macOS behavior, coverage, or the final release artifacts.
