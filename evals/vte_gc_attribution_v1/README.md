# Archived VTE GC attribution diagnostic

These scripts are exact executed copies for the [diagnostic report](../../docs/evaluations/2026-11-08-vte-gc-attribution-v1.md) and [receipt](../../docs/evaluations/2026-11-08-vte-gc-attribution-v1.json). They run at module top level, create files and launch owned native processes. Do not import or run them in this archive.

This is a six-trial, instrumented diagnostic, not a latency qualification. Reproduction requires a new private directory, a reviewed source snapshot, compatible local dependencies and a newly frozen plan; the recorded absolute paths and shared-host software display are historical. Weak references do not retain history widgets, but sampling and tracing perturb timing and do not classify all GC objects. The original paired cohort is separate.
