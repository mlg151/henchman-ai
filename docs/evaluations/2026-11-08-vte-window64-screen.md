# Exploratory 64-row transcript screen — 2026-11-08

This was a small diagnostic, not a release qualification. The candidate changed
only `ORDINARY_WINDOW` from 128 to 64 in a detached checkout of commit
`6db0adfd88aedd458bbbca480052fbefa74c6521`. It was not integrated. The frozen
[plan](../../evals/vte_window64_screen_v1/frozen-plan.json) and
[complete observations](../../evals/vte_window64_screen_v1/cohort-results.json)
are preserved alongside the [compressed candidate test log](../../evals/vte_window64_screen_v1/candidate-tests.txt.gz).
The probe scripts were byte-identical to those in
[vte_window_pair_v1](../../evals/vte_window_pair_v1/).

Four separate local software VTE processes ran in order baseline, candidate,
candidate, baseline, each with a 160 × 50 viewport, 1,000 synthetic messages,
and 20 input plus 20 cancellation measurements. No model or provider was
called. The 95th percentile is the 19th ordered observation out of 20.

| Process | Input p95 (ms) | Cancellation p95 (ms) | Cancellation maximum (ms) |
| --- | ---: | ---: | ---: |
| Baseline 0 | 34.55 | 318.46 | 336.28 |
| Candidate 1 | 43.81 | 154.55 | 164.38 |
| Candidate 2 | 43.95 | 152.52 | 320.32 |
| Baseline 3 | 35.28 | 359.18 | 361.09 |

These measurements suggest a direction for further study, not proof of a fix:
there was one candidate cancellation over 250 ms, input p95 increased by about
9 ms, each process's samples are correlated, and just one of the six planned
viewport/history scenarios was screened on a shared host. The display was
virtual software VTE, with no physical terminal, assistive technology, or human
assessment. All measurement processes and virtual displays were joined, and
the app identities were absent afterward. The 468 source files in each arm were
hash-checked before and after the cohort.

The candidate also failed four of 24 existing transcript-window tests: both
sizes of `test_explicit_history_pages_search_and_live_keep_draft_focus_and_rotation`
expected a row after a single previous-page action; `test_pinned_stream_tool_and_thought_keep_chronology_and_copy_from_older_page`
expected 128 completed rows plus the active stream; and
`test_discarded_thought_cannot_publish_or_rejoin_after_awaited_boundaries[control_mount]`
timed out waiting for its boundary. The first three failures reflect assertions
that assume the existing page size. In a subsequent local Python 3.12 run, the
[test adjustments](../../evals/vte_window64_screen_v1/candidate-test-adjustments.patch.gz)
changed those expectations and started the control-mount case below the new
64-row threshold, so the test could exercise the intended mount boundary. All
24 tests then passed; the [follow-up log](../../evals/vte_window64_screen_v1/candidate-adjusted-tests.txt)
is retained. This supports the test-setup explanation for the timeout, but does
not establish general usability. The candidate still needs navigation and
interaction review and the complete paired gate before it could be considered.
The production page size remains 128.

The plan SHA-256 is
`59f7e0abd5d7f128360a0a2b8260f6d07ee50f5d2c699b1e1f93403a1de2e3d9`,
the results SHA-256 is
`906aef89b4bfb93160fd819865c45dd31366c2d36e5665a62fd4479abc2923ae`,
and the uncompressed test log SHA-256 is
`2fba66e4514f523f86b6c1a13a0fd69a2e835c729fa459274e66126f11347e18`.
The follow-up log SHA-256 is
`ec52690ccff813f42e6f00e33f5abde73feeb2f77dd23ff7f3132d6b10998c85`.
