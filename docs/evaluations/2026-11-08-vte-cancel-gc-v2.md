# VTE cancellation timing: instrumented GC diagnostic

**All three cancellations above 250 ms overlapped a generation-2 collection
on the application main thread before the Escape handler ran.** This identifies
a timing lead, not a qualified fix or proof about the earlier paired run. The
collection callbacks and weak-reference scans themselves perturb execution.

The diagnostic used clean source commit `6db0adfd88aedd458bbbca480052fbefa74c6521`,
one 160×50 VTE window with 1,000 synthetic history messages, an Xvfb software
display and 20 fixed input plus 20 cancellation observations. Each cancellation
used the original worker-ready eligibility rule and joined a scripted one-second
cleanup. No model was called. The 20 inputs had p95 53.0 ms; cancellation p95
was **305.7 ms**, with a 329.4 ms maximum. These instrumented observations are
not a substitute for the [paired latency gate](2026-11-08-vte-window-pair-v1.md).
The plan did not predeclare a p95 analysis; those summary values are exploratory
descriptions produced by the copied probe, not qualification criteria here.

| Trial | Cancellation to sampled pixels | Overlapping generation-2 collection | Handler entry after input |
| --- | ---: | ---: | ---: |
| 1 | 305.7 ms | 154.7 ms | 250.7 ms |
| 11 | 329.4 ms | 188.5 ms | 275.4 ms |
| 17 | 284.5 ms | 141.3 ms | 251.1 ms |

Each collection was recorded within a layout refresh and completed before the
handler entry. The other 17 cancellation observations were below 250 ms; their
maximum was 181.9 ms. Weak-reference counts fell by 5, 9 and 13 history widgets
across the three collections, while the collectors reported thousands of total
objects. Those counts do not identify which object graphs caused the pauses.
One shared-host process, the added tracing, sampling overhead and lack of a
paired control limit any general conclusion. Physical terminals, screen readers,
people and overall memory behavior remain unqualified. No GC policy was changed.

The [bounded receipt](2026-11-08-vte-cancel-gc-v2.json) records all 40 samples,
timing summaries, the frozen plan and raw-artifact hashes. The
[exact diagnostic scripts](../../evals/vte_cancel_gc_v2/README.md) are archived
separately; the raw event timelines, screenshots and logs remain in the local
qualification cache under `vte-cancel-diagnostic-6db-v2`. The supervisor joined
the application and display, and the recorded child PID/start-time identity
was absent afterward. The checkout remained clean.
