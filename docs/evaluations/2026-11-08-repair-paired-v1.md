# Local bounded-repair comparison v1

**Negative result: direct execution passed 6/6; bounded repair passed 2/6.**
All 12 fixed attempts used source `929dfc00fe48fdd5140cd6f2332b7ff0ce115de8`.
Four repair attempts corrected the artifact but failed at the controller-only
verification boundary. Those failures remain failures; this result does not
establish live improvement or close #16. The [full receipt and audit](2026-11-08-repair-paired-v1.json)
retain every attempt, pair, worker outcome, usage observation and raw-artifact hash.

| Fixture / repeat | Direct outcome | Requests | Seconds | Repair outcome | Requests | Seconds |
|---|---|---:|---:|---|---:|---:|
| addition-repair / 1 | Pass | 4 | 84.044 | Failed | 3 | 32.115 |
| addition-repair / 2 | Pass | 4 | 53.847 | Failed | 3 | 32.585 |
| pricing-repair / 1 | Pass | 5 | 72.090 | Failed | 3 | 35.653 |
| pricing-repair / 2 | Pass | 4 | 60.314 | Failed | 3 | 36.173 |
| already-correct / 1 | Pass | 3 | 66.283 | Pass | 0 | 4.728 |
| already-correct / 2 | Pass | 3 | 57.172 | Pass | 0 | 4.947 |

Times include setup and joined cleanup. Repair ran second in repeat 1 and first
in repeat 2. Each pair had identical initial files, protected criteria, prompt,
plan identity and settings. No attempt was replaced or omitted. Candidate
`scoped_pass` and final prose could not substitute for the independent current-byte
oracle. All 12 final artifacts passed its finite arithmetic checks, and all
protected criteria remained unchanged.

Both already-correct candidate runs performed their initial controller check
without requesting the model and preserved source bytes. Their functional
acceptance tied the baseline; fewer requests do not establish functional
improvement. Zero-request wire usage fields remain null because there was no
provider response.

Each of the four failed repair runs used an allowed file tool to repair the
source, then requested `verify_plan_execution`. The registry advertised that
tool, and the common task prompt permitted requesting it, but bounded repair
reserves verification for its controller. The runtime correctly raised
`RepairControlError` and retained an incomplete outcome. This exposes a mismatch
between model-visible capabilities and execution scope. The offline dry script
had not attempted this verifier call during repair, so its 12 accepted scripted
attempts did not predict the live failure. Later disclosure fixes must be evaluated
separately without rewriting these results.

The only generation route was the existing local
`http://127.0.0.1:8081/v1/chat/completions`, alias `qwen38-27b-iq3s`.
The borrowed server was unchanged; port 8082 was not used. Before every attempt,
bounded readiness reads required the expected model and one idle slot. Dispatch
rechecked the admitted PID/start-time, argv, listener and model-file metadata.
This is process/alias/file-stat identity, not a fresh GGUF digest or proof of
loaded tensors. The shared endpoint was not exclusively reserved.

All **35 dispatched requests** reported token usage: **224,523 prompt tokens**
and **4,934 completion tokens**. The local route incurred **$0 hosted API spend**;
hardware/electricity cost was not measured. Each attempt had a 300-second whole
attempt bound, 30-second cleanup allowance, 12 shared requests, 10 tool rounds,
zero SDK/delegation retries, 4,096 output tokens and an approximate serialized
input bound. All workers, stream/SDK owners and output readers joined. The audit
checked that the exact captured worker identities were absent afterward.
Process samples exclude the borrowed model server/GPU and do not qualify total
memory use or a 16 GB machine.

This is a separate three-case arithmetic comparison, not the canonical recovery
corpus, general coding reliability or release qualification. Two repeats on a
warm shared server do not establish stable performance. Python 3.12.13 and exact
package versions are archived in the harness provenance. The frozen harness
passed 27 offline fault tests on Python 3.11 and 3.12; root independently reran
all 27 before live use. Those checks support ownership and measurement boundaries,
not model quality.

The [archived reproduction notes](../../evals/repair_paired_v1/REPRODUCE.md)
link the exact 18 frozen files and source manifest. The original private admission
is excluded. All 268 raw artifacts remain inventoried by hash; publication did
not rerun the model or alter the cohort.
