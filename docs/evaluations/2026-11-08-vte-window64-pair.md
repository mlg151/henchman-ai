# Six-scenario 64-row VTE follow-up — 2026-11-08

**The 64-row candidate failed the cancellation p95 target in both 160 × 50
scenarios.** It remains an unintegrated prototype. All 12 predeclared cases and
480 input/cancellation observations completed and are retained in the
[receipt](../../evals/vte_window64_pair_v1/cohort-results.json), along with the
[frozen plan](../../evals/vte_window64_pair_v1/frozen-plan.json) and
[package list](../../evals/vte_window64_pair_v1/application-packages.txt).

The candidate changed `ORDINARY_WINDOW` from 128 to 64 in a detached checkout
of `6db0adfd88aedd458bbbca480052fbefa74c6521`. This follow-up was planned after
the earlier [single-scenario screen](2026-11-08-vte-window64-screen.md), so
candidate selection was informed by that screen. The scripts were identical to
the [archived comparison scripts](../../evals/vte_window_pair_v1/README.md).
Each arm/scenario had one fresh Xvfb/VTE/app process and 20 observations per
action; baseline/candidate order alternated. The p95 is the 19th ordered value.

| Viewport / history | Baseline input p95 | Candidate input p95 | Baseline cancellation p95 / max | Candidate cancellation p95 / max |
| --- | ---: | ---: | ---: | ---: |
| 80 × 24 / 40 | 35.0 | 35.1 | 152.7 / 360.3 | 146.0 / 335.9 |
| 80 × 24 / 1,000 | 36.6 | 33.5 | 208.3 / 473.6 | 154.5 / 413.0 |
| 120 × 40 / 40 | 35.0 | 34.8 | 149.0 / 153.7 | 162.8 / 167.9 |
| 120 × 40 / 1,000 | 50.7 | 35.0 | 160.6 / 168.5 | 147.0 / 360.6 |
| 160 × 50 / 40 | 47.8 | 47.8 | 171.4 / 418.2 | **276.6 / 356.8** |
| 160 × 50 / 1,000 | 35.3 | 33.1 | 357.3 / 478.7 | **323.3 / 403.8** |

All input p95 values were below 100 ms. The predeclared cancellation p95 limit
was 250 ms. Several individual observations exceeded 250 ms even when p95
passed. Samples within each process are correlated; this is a shared-host,
software-display experiment rather than a physical-terminal, accessibility,
human, or model evaluation. It does not qualify the current release source.
Python 3.12.13 and the recorded packages differ from the earlier Python 3.11
screen. No other local tests or builds ran during this cohort. All 12 measurement
processes and virtual displays joined and the app identities were absent.

Plan SHA-256: `e5521aac67e1d039b41b25faef6d0c0f42a5120b86b8c2859cefd83016a644f5`.
Receipt SHA-256: `ba70ab32ba29422a4849f5b48a3dd25e1d6864417a1c6d196111ddc69a7e3a88`.
Package list SHA-256: `3606adb299287eff1e3869b720e4061589e004c162ab96913e15e1910a0faf36`.
