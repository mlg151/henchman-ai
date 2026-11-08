# Archived intrusive VTE GC type diagnostic

These are the exact executed scripts for the
[report](../../docs/evaluations/2026-11-08-vte-gc-types-v3.md) and
[receipt](../../docs/evaluations/2026-11-08-vte-gc-types-v3.json). They execute
at module top level, enable `gc.DEBUG_SAVEALL`, create files and start native
processes. They include historical absolute paths. Do not import or run these
archived copies.

The debug mode retains otherwise unreachable cycles and can cause repeated
counts, so this is not a performance measurement or object-ownership proof.
A new experiment requires a separate private directory, reviewed source and
cleanup, and a newly frozen plan before observations.
