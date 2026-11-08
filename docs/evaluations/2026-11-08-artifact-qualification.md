# Development artifact qualification — 2026-11-08

The actual release qualification command passed both artifact paths at clean
commit `6ee824bc36ffeaf51fce40fd025155fdd0faa178`. Each installed profile passed
5,460 tests and skipped 25 on Linux/Python 3.12.13. The pipeline wrote a receipt
binding the source identity, helper and artifact hashes; no publication occurred.

| Artifact path | Passed / skipped | Test duration | Result |
| --- | ---: | ---: | --- |
| Built wheel, fresh installed environment | 5,460 / 25 | 881.68 s | Passed |
| Source archive, fresh build and installed environment | 5,460 / 25 | 860.41 s | Passed |

The source archive rebuilt the same wheel hash. The
[retained record](2026-11-08-artifact-qualification.json) contains the original
qualification receipt, artifact SHA-256 values, both log hashes and result counts.
Artifacts were `henchman_ai-0.4.1-py3-none-any.whl` and
`henchman_ai-0.4.1.tar.gz`; this is a development checkpoint for the release
pipeline, not a v0.4.2 release receipt. Both environments exercised the installed
package outside the checkout, including aliases, CLI behavior, offline local RAG
and the scripted workflow cohort.

An earlier attempt at `de521a3` failed on seven outdated output-handler fixtures
and produced no receipt. Those fixtures now provide the real default renderer;
the passing attempt above used the corrected source. Failed and successful
attempts remain distinct.

This profile is smaller than the complete source suite. Current native CI also
found a case-insensitive settings-test assumption and Windows RAG timestamp
comparisons requiring repair. Later fixes, repository search and editor-pilot
changes are outside this receipt. Final source coverage, native matrices, live
local-model and human-facing acceptance gates remain separate under
[#30](https://github.com/mlg151/henchman-ai/issues/30) and its dependencies.
