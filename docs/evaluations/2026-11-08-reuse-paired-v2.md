# Repository-evidence comparison on a local model

All 12 fixed attempts ran on the local `qwen38-27b-iq3s` server. Under the
[v2 harness rules](../../evals/repository_reuse_paired_v2/README.md), the
combined-search baseline was accepted in **3 of 6** attempts and the
repository-evidence arm in **5 of 6**. Repository evidence was ahead in three
pairs, the baseline in one, and two pairs tied. This is a small, post-v1
follow-up on one model and three fixtures; it does not establish general
reliability or complete issue #17.

| Fixture and repeat | Combined baseline | Repository evidence |
| --- | --- | --- |
| Labels 1 | Accepted | Unaccepted: verifier status call denied |
| Labels 2 | Unaccepted: file read denied | Accepted |
| Invoice 1 | Timed out | Accepted |
| Invoice 2 | Timed out | Accepted |
| Events 1 | Accepted | Accepted |
| Events 2 | Accepted | Accepted |

Both unaccepted label artifacts passed the narrow current-file oracle and had
current correlated verification; their denied calls made them unaccepted under
the frozen rules. Both invoice baseline attempts hit the 450-second limit and
had no accepted current artifact or current verification. Those outcomes,
including guard denials, remain in the denominator. All 12 workers and their
owned cleanup joined. The earlier [v1 run](2026-11-08-reuse-paired-v1.md)
remains separately recorded and is not replaced by this follow-up.

The baseline's `combined` search and the candidate's `repository` search both
used actual tool output. An independent audit checked that each pair had the
same initial fixture bytes, Git commit, settings, task, system message and tool
catalog, with only the declared user-message evidence differing. It reran the
bounded AST/helper oracle against current retained files, checked verification
run correlation after cleanup, and verified the frozen source and harness.
The oracle uses finite examples and harness-defined helper behavior; it does
not execute candidate code or prove general correctness.

The local transport dispatched 58 requests. Fifty-six had complete usage;
the two timed-out requests did not, so total usage is unknown. Known reported
usage was 449,732 prompt tokens and 33,964 completion tokens, with cached prompt
tokens included in the per-request reports. No hosted inference was used;
hardware cost and model-server memory were not measured. Other local development
tests overlapped this shared-server run, so its elapsed times are not controlled
performance comparisons or evidence of a CPU or 16 GB laptop profile.

The source was `d195ac18d3c2d586e30f29f218c7813e97c97269`. The live receipt
SHA-256 is `402b255efb90255c812f9e4461247ab25f59be463b20fa3797e1df29ebb9130f`;
the audit of 812 retained raw files has SHA-256
`61af821eafb2c7afdad3d36932128b0033b68afb47419708ff0f5d96ddd24f0b`.
Raw files remain in the local release-qualification cache. The separately
versioned [audit script](../../evals/audit_repository_reuse_v2.py) reproduces
that exact audit when given the retained qualification directory and a new
output path; run it without Python optimization.
