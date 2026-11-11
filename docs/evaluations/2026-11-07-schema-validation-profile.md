# Schema-validation attribution profile — 2026-11-07

Repeated schema meta-validation dominated one scripted small-edit fixture.
A bounded cache reduced these checks while preserving every observed live
authorization revalidation. The [comparison record](2026-11-07-schema-validation-profile.json)
retains source identities, candidate code hash, artifact hashes and host load.

| Profiled run | Baseline wall time | Candidate wall time | Meta-checks before / after | Authorization checks before / after |
| --- | ---: | ---: | ---: | ---: |
| Cold schema cache | 33.27 s | 11.53 s | 588 / 8 | 526 / 526 |
| Warm schema cache | 32.13 s | 11.50 s | 588 / 0 | 526 / 526 |

Each run created an isolated project and runtime, executed the original failing
then passing criteria, made two mocked SDK requests, completed three operation
records, preserved the protected criteria and rejected a wrong-result mutant.
Warm imports and tokenization did not reuse verification evidence. No local or
hosted model inference ran; the actual SDK parser used an HTTP mock transport.

The change memoizes successful schema meta-validation only. Current schemas are
detached and bounded before lookup; validators, resolvers, value checks and
authorization remain fresh. Invalid schemas never populate the cache. Keys retain
at most 4 MiB of canonical schema bytes across 64 entries; larger admitted schemas
would validate without caching. Mutation, approval revocation, invalid references,
type distinctions, eviction and concurrent construction have focused regressions.

Both profiles used Python 3.12.13 on the same Linux host with 56 available CPUs.
They ran from development checkouts with concurrent work, and the recorded load
was lower during the candidate profile. cProfile adds substantial overhead; these
two runs per revision establish attribution and call counts, not production
p50/p95 latency, a native responsiveness result or a completed #26 qualification.
The cache's correctness gate is independent of those timing observations.

A subsequent [20-pair unprofiled comparison](2026-11-08-paired-schema-latency.md)
retains p50/p95 fixture measurements and passes its declared regression gate.
Native responsiveness and wider workload qualification remain open.
