# Archived VTE cancellation GC diagnostic

These scripts are the exact executed copies for the
[diagnostic report](../../docs/evaluations/2026-11-08-vte-cancel-gc-v2.md) and
[receipt](../../docs/evaluations/2026-11-08-vte-cancel-gc-v2.json). They contain
historical absolute paths, execute at module top level, create files and launch
owned native processes. Do not import or run these archived copies.

The frozen 20-trial plan and hashes precede the observations. This is an
instrumented single-process diagnostic on a shared-host software display, not
a paired performance gate or physical-terminal/accessibility qualification.
For a new experiment, use a separate private directory, review paths,
dependencies and cleanup, prepare a clean source snapshot, and freeze a new
plan before observing results.

Ruff checked both v2 and v3 archives together and reported 22 findings in
these as-run copies (including import ordering, GI's required import sequence,
semicolon style, and a synchronously called loop-local helper). They are kept
byte-identical to the executed evidence. The combined log is retained in each
local qualification-cache directory with SHA-256
`82432a27da51fd5d3ceaf6c32d3f55b2e21943f37c3362e32c17844edc8d8927`.
