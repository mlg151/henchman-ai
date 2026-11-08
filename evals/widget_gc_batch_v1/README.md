# Synthetic widget GC batch screening

This separately planned local process created 1,000 synthetic, unmounted
`ChatMessage` instances per arm and retained only the newest 128. It used
Python 3.11.15, Textual 8.0.0 and clean source commit
`6db0adfd88aedd458bbbca480052fbefa74c6521`. Automatic GC was disabled inside
each arm; the three collection arms explicitly collected after every 32
evictions. A full cleanup ran after each observation.

| Explicit collection | Collections | Evicted widgets still alive before cleanup | Retained widgets alive |
| --- | ---: | ---: | ---: |
| None | 0 | 872/872 | 128/128 |
| Generation 0 | 27 | 840/872 | 128/128 |
| Generation 1 | 27 | 840/872 | 128/128 |
| Generation 2 | 27 | 8/872 | 128/128 |

All observed widgets were gone after each full cleanup. These sequential,
single-process synthetic observations do not establish how a running UI with
automatic GC behaves, measure input/cancellation latency, or justify an
application policy. Explicit collection is process-wide and can run unrelated
finalizers. In particular, the generation-2 arm's apparent lifetime reduction
does not establish that 27 full collections would be safe or responsive. No
production GC or widget behavior was changed. The proposed young-generation
screen did not release most evicted widgets here, so no native latency claim
was made for it.

The [frozen plan](plan.json), [receipt](receipt.json) and
[executed script](run.py) are retained; the receipt SHA-256 is
`c8a2734b2d705bea868f68c81609108e25ce3f757f403e188ac9eaf34162d235`.
Ruff and mypy passed for the script. The isolated home and log remain in the
local `widget-gc-batch-6db-v1` qualification cache. The separate
[widget-cycle probe](../widget_cycle_diagnostic_v1/README.md) and
[VTE latency trace](../../docs/evaluations/2026-11-08-vte-cancel-gc-v2.md)
remain unchanged.
