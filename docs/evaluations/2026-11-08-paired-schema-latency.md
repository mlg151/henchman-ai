# Paired schema-cache latency — 2026-11-08

The bounded schema meta-validation cache passed its preregistered local fixture
gate: all correctness checks passed, and candidate p95 stayed below 1.10 times
baseline in both first-run and warm cohorts. This unprofiled comparison follows
the [attribution profile](2026-11-07-schema-validation-profile.md).

| Workload | Baseline p50 | Candidate p50 | Baseline p95 | Candidate p95 |
| --- | ---: | ---: | ---: | ---: |
| First run after imports | 10.470 s | 2.949 s | 11.156 s | 3.026 s |
| Second run, fresh workspace | 9.884 s | 2.481 s | 10.133 s | 2.763 s |

All 20 planned pairs ran: 40 successful worker processes, 80 observations, zero
failed workers or timeouts. Each revision has 20 observations per cache state.
Order alternated baseline/candidate then candidate/baseline, ten pairs each way.
The separate diagnostic pair is excluded. P50 is the median; p95 is nearest
rank, observation 19 of 20. Candidate p95 was 0.2712 and 0.2727 times baseline,
respectively, and every matched pair was faster in both states.

Baseline was `ef52db915df214299cb98e0a5b975e8dad77a3f9`; candidate was
`247f348fcbd6dffdceb0364ed2445e5d32665339`. The production difference is the
schema-validation cache. Both clean worktrees used identical bounded-repair and
HTTP fixture sources, dependency versions and hardware: Python 3.12.13, Linux,
Intel Xeon Gold 6132 at 2.60 GHz, with 56 available CPUs. The shared host also ran
other work; recorded one-minute load ranged from 4.5 to 9.843.

Each observation constructed a fresh project/runtime, repaired subtraction into
addition through the actual tool/SDK path, observed the original failing then
passing criteria, preserved the criteria bytes, recorded two requests and three
completed operations, and closed the orchestrator and provider. An independent
subprocess executed the frozen criterion again and rejected a wrong-result
mutant. These external outcomes are retained as asserted flags, without separate
stdout or exit-code transcripts. Independent review checked all 80 saved
production verification records and checkpoint bytes against the expected
failing/passing results and source hashes.

The [machine-readable record](2026-11-08-paired-schema-latency.json) retains all
80 raw timings and event-loop samples, process outcomes, source/harness hashes,
plan, dependencies, host load, and the exact frozen launcher and worker source.
The launcher uses a private environment and fresh process per revision; its
absolute interpreter path identifies the original host environment. Reproduction
requires equivalent isolated dependencies and clean worktrees at the named
commits; a changed launcher is a new experiment. No credentials were supplied,
and a Python audit hook refused network operations. The Ollama adapter used an
HTTP mock transport: no local or hosted model inference ran, and API spend was
zero.

The primary timer includes heartbeat/patch setup, fixture construction, repair,
evidence assertions and runtime/provider cleanup. It excludes interpreter
startup, imports and the separate oracle/mutant subprocesses. Recorded phase
durations overlap and must not be summed. “Cold” labels in the raw record mean
the first workload after imports in a fresh process/private home; they do not
mean a cold OS page cache or a measured empty schema cache. The second workload
uses a new workspace in the same process.

Event-loop stalls remain material: p95 of each run's maximum heartbeat delay
fell from 1.584/1.280 seconds to 0.299/0.291 seconds for first/warm workloads.
Those observations are scheduling delays, not UI input-to-paint latency. Twenty
correlated observations on a shared host provide no confidence interval, live
model speed claim, native responsiveness qualification or general release
qualification. Issue #26 remains open for its wider workload and native gates.
