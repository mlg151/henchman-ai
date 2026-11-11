# Native VTE latency baseline v1

**All 240 fixed observations completed; three cancellation p95 criteria failed.**
This baseline does not qualify an issue or release. It measures source
`06828897485caad09899606e98d8318d0ff9c715` in actual VTE/GTK terminal windows on
an owned Xvfb software display. No model was called and publication did not
rerun the measurements. The [full observations and audit](2026-11-08-vte-latency-v1.json)
retain all six receipts, original summaries, calibration, exclusions and hashes.

| Terminal cells | Initial messages | Input p95, ms | Input maximum, ms | Cancellation p95, ms | Cancellation maximum, ms | Cancellation p95 <250 ms |
|---|---:|---:|---:|---:|---:|---|
| 80×24 | 40 | 32.924386 | 33.512361 | 136.317913 | 138.250351 | Met |
| 80×24 | 1,000 | 36.984835 | 38.101769 | **372.766001** | 393.273011 | **Failed** |
| 120×40 | 1,000 | 34.834246 | 109.855469 | **534.107502** | 549.762647 | **Failed** |
| 120×40 | 40 | 33.870962 | 40.540409 | 148.480757 | 227.740803 | Met |
| 160×50 | 40 | 42.531839 | 45.718922 | 150.260725 | 152.486240 | Met |
| 160×50 | 1,000 | 48.841419 | 49.154550 | **486.997680** | 536.212450 | **Failed** |

Each row contains 20 input and 20 cancellation observations, in the frozen
execution order above. p95 is the 19th sorted value, `ceil(0.95 × 20)`; criteria
are strictly below 100 ms for input and 250 ms for cancellation. All six input
p95 values met their criterion, although one input sample reached 109.855469 ms.
There were 18 cancellation samples at or above 250 ms: 5, 7 and 6 in the three
1,000-message cases. No fixed observation was dropped, retried or replaced.

The raw observation status `PASS` means the expected terminal text **and**
calibrated native pixels were observed. All six processes exited 0 because
measurement completed and the app was joined; exit 0 does not require the
latency criteria to pass. The final supervisor publications follow successful
Xvfb `wait()` calls. All six app receipts report `app_joined: true`.

Timing begins immediately before launching `xdotool` and ends at the first
matching native-window pixel sample after GTK event processing. It includes
command launch, X11 delivery and sampling overhead, including the polling loop.
It is an observed upper bound from synthetic command launch, not an internal
paint timestamp or physical key-to-monitor latency. Cancellation measures the
first visible **Cancelling** acknowledgement; separately retained
`joined_cleanup_ms` includes the scripted one-second worker cleanup delay.

Each scenario starts a fresh app/VTE/Xvfb process set, calibrates one input and
one cancellation action, then measures 20 input and 20 cancellation actions
sequentially. The 12 calibration actions are excluded from the 240-observation
denominator. These are not 240 independent fresh processes, and submitted
cancellation turns can grow the transcript. The 40-message fixture includes
Unicode and long paths; the 1,000-message fixture uses numbered readable text.
The comparison therefore does not isolate history length as a causal factor.
The pre-freeze `smoke`, `smoke2`, `prototype-80x24-40`,
`prototype2-80x24-40`, and `prototype3-80x24-40` runs are explicitly excluded.
Both incomplete timeout prototypes and the completed prototype remain listed
in the JSON; none contributes to this cohort's percentiles.

The host was shared Linux on an Intel Xeon Gold 6132 at 2.60 GHz, 56 logical
CPUs and approximately **123.13 GiB RAM**. The frozen manifest records
concurrent verification and no affinity or load isolation. VTE 0.84.0 and GTK
3.24.52 used Monospace 12 with 10×19-pixel cells; the supervisor requested
software rendering. Retained Xvfb logs include `/dev/dri` permission warnings.
This is not physical-monitor, macOS, Windows, assistive-technology, remote
terminal, IME, clipboard, 16 GB device, memory-use, or model-performance evidence.
Twenty observations per case provide a descriptive baseline, not a confidence
interval or demonstrated optimization.

The audit verified all three executed script hashes, all six receipt hashes,
all 18 calibration pixel hashes against screenshot crops, all 12 percentile
summaries, and all six supervisor publications. The frozen source remains
tracked-clean. The JSON inventories all 112 original files; original artifacts
were left untouched and screenshots are referenced by hash rather than copied.

| Executed file | SHA256 |
|---|---|
| `measure.py` | `74383732dde7f6efabe8ecf904100223a3b328d8337bcaeedea1306a911facc9` |
| `probe_app.py` | `65bbe0570f56bd0f222a20cf381293238c999861183ef5bb4376ce618a74df96` |
| `run_measure.py` | `b59ae6b7b803add2ba424c4dd994f35b2fe9fa18cc6b7985d135979804ee70a6` |

Original cohort manifest SHA256:
`eb6e1c3a737f3fb2c38b137b71a56b7533c65059af2c92dd3953e84df099f0eb`.
Original results SHA256:
`c37fffdee0eb42b6a39de61e757a4696445de30fb3c71d4d6948295cb1942329`.

The [archived harness and reproduction instructions](../../evals/vte_latency_v1/README.md)
preserve the executed bytes and explain the host-specific paths. Repointing
source or interpreter changes the harness identity and requires new hashes.
The next concrete gap is to attribute the long-history acknowledgement delay
across app rendering, terminal processing and measurement overhead before
comparing a separately frozen candidate. This receipt establishes the failed
criteria, not their cause or a promise that a particular change will fix them.
