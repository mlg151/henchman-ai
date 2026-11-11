# Archived VTE transcript-window comparison

These four scripts are exact executed copies for the [2026-11-08 comparison](../../docs/evaluations/2026-11-08-vte-window-pair-v1.md); the [complete receipt](../../docs/evaluations/2026-11-08-vte-window-pair-v1.json) includes the frozen plan, hashes and all 480 observations. They are host-bound scripts, not an automatically runnable benchmark. The candidate failed one cancellation p95 target; physical terminals and accessibility are unqualified.

`measure.py` and `probe_app.py` are byte-identical to the earlier archived probe. The new supervisor accepts a frozen source path and records cleanup; the cohort driver executes the fixed predeclared order and retains failed or unrun cases. All scripts execute at module top level. Do not import or run them in this archive: they create output and start owned Xvfb/app processes.

For an intentional new experiment, use a separate private directory, review all paths/dependencies/cleanup, prepare clean source snapshots, and freeze a new plan and hashes before any observations. Historical absolute interpreter paths, software-rendered X display, fixed workload and shared-host limits are recorded in the report. Neither these files nor their receipt qualify physical devices or provide model-quality evidence.
