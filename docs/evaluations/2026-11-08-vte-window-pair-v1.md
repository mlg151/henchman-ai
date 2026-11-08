# Native VTE transcript-window comparison

**The candidate failed the 250 ms cancellation p95 target at 160×50 with 1,000 messages.** All 12 fixed scenarios completed and all 480 input/cancellation observations are retained. The candidate met the p95 targets in the other five scenarios. The result does not close the latency or terminal accessibility issues.

The baseline was `4dbefe2b41e22777f0f23cecd9e0193bf982091f`; the candidate was `8117c739f7489f797e8461bba4687349a1a84558`. Each scenario used a fresh owned Xvfb/VTE/app process, with alternating baseline/candidate order. Each process produced 20 input and 20 cancellation observations, plus excluded calibration. The table reports p95 (19th of 20) and maximum cancellation latency in milliseconds.

| Viewport / history | Baseline input p95 | Candidate input p95 | Baseline cancel p95 / max | Candidate cancel p95 / max |
|---|---:|---:|---:|---:|
| 80×24 / 40 | 36.7 | 34.0 | 131.8 / 134.7 | 144.6 / 150.2 |
| 80×24 / 1000 | 34.2 | 33.4 | 394.1 / 456.9 | 171.7 / 338.9 |
| 120×40 / 40 | 33.8 | 35.8 | 146.1 / 230.0 | 147.5 / 150.7 |
| 120×40 / 1000 | 35.3 | 54.0 | 530.5 / 565.5 | 185.6 / 299.8 |
| 160×50 / 40 | 39.1 | 48.7 | 266.8 / 397.8 | 153.9 / 437.8 |
| 160×50 / 1000 | 35.7 | 49.5 | 218.8 / 219.9 | 265.8 / 345.2 |

Input p95 was below 100 ms in all 12 scenarios. Cancellation p95 was below 250 ms in five candidate and three baseline scenarios. The candidate had individual cancellations above 250 ms even in some scenarios whose p95 passed. The baseline passed the 160×50/1,000 scenario in this cohort; results vary and do not establish a uniform improvement.

The probe retained the original worker-ready eligibility rule, measured before `xdotool` launch through matching sampled native pixels, and joined the one-second scripted cleanup. This is an Xvfb software display on a shared host, not a physical terminal, accessibility, human, or model evaluation. Samples within each process are correlated; there is one process per arm/scenario, no confidence interval or guaranteed performance claim. Focused development tests and Ruff/mypy ran concurrently; their available timestamps are retained in the JSON. Source bytecode caches could warm across scenarios. All app, measurement, and display processes joined; no model calls were made.

The [full receipt](2026-11-08-vte-window-pair-v1.json) includes the frozen plan, every observation, per-case cleanup, load observations, source and harness hashes, and the raw artifact inventory. The [exact scripts](../../evals/vte_window_pair_v1/README.md) are retained separately. The earlier [240-observation baseline](2026-11-08-vte-latency-v1.md) and diagnostic prototype remain distinct and unchanged.
