# Headless transcript resource baseline

Six fresh Python processes observed the fixed `UI-RESOURCE-0.1` workload at
`c8d67a3b413efb5f36bb0c6c193278c328794df4`. All six completed. No model was
called. This measures the existing Textual headless fixture, including its
Python/pytest overhead, rather than a terminal emulator or full model runtime.
The [receipt](2026-11-08-ui-resource-baseline.json) retains every observation,
source/harness identity, log hash and qualification limit.

Hardware/software: Intel Xeon Gold 6132 at 2.60 GHz, Linux, Python 3.12.13,
Textual 8.0.0. Each process used isolated user settings and the offline transport
guard. The fixed rich/default-density/default-motion UI received either 40 or
1,000 numbered Unicode/long-path user messages, settled layout, then idled for
five seconds with an empty composer. The source checkout's tracked files remained
unchanged. Host load was shared, with no CPU affinity or load isolation.

| Dimensions | Messages | End-idle PSS, MiB | Idle CPU, % of one core | History load, seconds |
|---|---:|---:|---:|---:|
| 80×24 | 40 | 139.03 | 0.69 | 0.12 |
| 80×24 | 1,000 | 164.93 | 1.22 | 2.04 |
| 120×40 | 40 | 136.34 | 0.87 | 0.32 |
| 120×40 | 1,000 | 165.63 | 1.19 | 1.98 |
| 160×50 | 40 | 137.19 | 0.66 | 0.25 |
| 160×50 | 1,000 | 166.68 | 1.22 | 1.97 |

PSS comes from `/proc/self/smaps_rollup`; idle CPU is the process CPU-time delta
divided by measured wall time. History-load time includes insertion and the
existing two-frame layout settlement. It is **not input-to-paint latency**.
Peak RSS and pre-history/post-unmount samples remain in the receipt. These are
single observations per case, so the differences are descriptive, not an
established performance gain or a statistical result.

For future headless screening on matching hardware, dependencies, dimensions and
workload, freeze a 10% end-idle PSS growth limit and a 0.5-percentage-point idle
CPU growth limit against the 1,000-message observations above. Compare the median
of three fresh processes and investigate over-budget results. These provisional
engineering limits are separate from the existing native p95 input-to-paint
target below 100 ms and visible cancellation acknowledgement below 250 ms.
Neither native target was measured here.

The [probe](../../evals/ui_resource_baseline.py) is opt-in. Set
`HENCHMAN_UI_RESOURCE_OUTPUT` to an existing absolute output directory and
`HENCHMAN_UI_RESOURCE_REVISION` to the checked-out commit; use a fresh process
for each parameter:

```bash
uv run --frozen --extra dev python -m pytest --no-cov -o asyncio_mode=auto \
  'evals/ui_resource_baseline.py::test_headless_transcript_resources[80x24-1000]' -q
```

Other parameter IDs are `80x24-40`, `120x40-40`, `120x40-1000`, `160x50-40`
and `160x50-1000`. To reproduce the historical source with a later harness,
copy the probe outside the checkout and set `PYTHONPATH` to the frozen
checkout's `src` and root; the probe asserts the imported runtime's revision.

Native Windows/macOS/Linux terminals, tmux/SSH/mosh, clipboard, IME, assistive
technology, representative participants, streaming responsiveness and whole-app
model memory remain unqualified. This resource baseline does not close #32,
#33 or #36 and is not 16 GB local-model qualification.
