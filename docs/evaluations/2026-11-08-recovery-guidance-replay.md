# Local recovery-guidance replay — 2026-11-08

This one-step diagnostic **does not establish a live coding improvement**. The
frozen scorer accepted both baseline edit actions and rejected both candidate
edit actions; both arms chose `task_list` in both task-ID trials. Subsequent
inspection showed that the rejected candidate edit actions were also valid for
the synthetic fixture: each used a shorter unique match and produced exactly
the same syntactically valid file. The original scores are retained unchanged.

| Case | Baseline accepted | Candidate accepted | Follow-up inspection |
| --- | ---: | ---: | --- |
| Unmatched edit | 2/2 | 0/2 | Both candidate calls produce the same valid fixture as the baseline calls |
| Incomplete task ID | 2/2 | 2/2 | All four calls requested `task_list`; no task was read |

The [frozen plan](../../evals/recovery_replay_v1/plan.json),
[runner](../../evals/recovery_replay_v1/run.py), and complete
[receipt](../../evals/recovery_replay_v1/receipt.json) retain all eight
observations in their planned alternating order. The scorer accepted only one
specific complete edit replacement, even though a shorter exact replacement
can be equally valid. The post-hoc inspection checked that the candidate's
`old_str` occurred once, that replacing it produced the same bytes as the
planned replacement, and that Python could compile those bytes. This inspection
does not retroactively change the predeclared scores.

The scenarios reproduce the two failure shapes in the
[CPU readiness audit](2026-11-08-cpu-readiness-v6.md), using synthetic text and
an isolated task ID. The baseline messages reflect commit `f59f51a`; candidate
messages reflect `0c28f1e`. The single loopback endpoint reported model
`qwen38-27b-iq3s` and fingerprint `b1-6cb3e67` for all eight responses. Each
request used temperature zero, a 256-token cap, no retry, and a 60-second
timeout. No proposed tool was executed. The eight responses reported 4,376
input and 356 output tokens. Two separate short readiness probes preceded the
cohort; the first exhausted a 16-token cap without a final answer, and the
second returned `READY` with thinking disabled. API spend was zero; hardware
and electricity costs were not estimated.

The model ran on the existing GPU-backed host, not a 16 GB CPU laptop. The
replay used only two simplified available tool declarations per case, did not
execute a full tool loop, and used two correlated repeats selected after the
original failures. It cannot establish whether the guidance improves end-to-end
task outcomes, nor does it satisfy the readiness, hardware, native-platform or
release gates. Model weights were not independently hashed in this replay.

- Plan SHA-256: `29c1698f46634732d0c6c06a0bcd082d8a4e9a213aae9c6050b069c36bafd4d8`.
- Runner SHA-256: `c4cc9847a2b284f58c74db872e892ec1767ee830ec552bfea36a4c4b46af3f4b`.
- Receipt SHA-256: `016f3ef384d4b360c0bfa2b892243a82ee9184d3666b271b8c80d0f6b9336009`.
