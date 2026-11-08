# Synthetic unmounted widget cycle diagnostic

Two separately planned local processes examined 100 synthetic, unmounted
`ChatMessage` instances per arm using Python 3.11.15 and Textual 8.0.0 from
source commit `6db0adfd88aedd458bbbca480052fbefa74c6521`. Automatic GC was
disabled while observing each arm, followed by an explicit collection. No model,
native display or user content was involved.

| Arm | Alive before collection | Alive after collection | Style-node identity changes |
| --- | ---: | ---: | ---: |
| Normal | 100/100 | 0/100 | 0/300 |
| Experimental weak proxies | 0/100 | 0/100 | 300/300 |

Each normal widget had three Textual style objects whose `node` was the widget.
The experimental arm replaced those private references with weak proxies while
the widget was alive. It could update the synthetic content, but every direct
`style.node is widget` identity check changed. This isolates one cycle in this
specific construction path; it does not prove that the cycles caused the
observed terminal latency, cover mounted or retained widgets, establish
compatibility across Textual versions, or justify using private weak proxies in
the application. No production code or GC policy was changed.

The [first frozen plan](plan_v1.json) used the byte-identical
[observed script](run_v1_observed.txt). Afterward mypy identified an unchecked
optional module path in that script. The [second plan](plan_v2.json) froze a
separate repeat using [the corrected script](run.py); Ruff and mypy passed for
that version. Both receipts are retained separately ([first](receipt_v1.json),
[second](receipt_v2.json)) and happen to be byte-identical. Private logs and
isolated homes remain in `widget-cycle-6db-v1` and `widget-cycle-6db-v2` under
the local qualification cache. The linked
[VTE timing diagnostic](../../docs/evaluations/2026-11-08-vte-cancel-gc-v2.md)
remains distinct and does not establish a release pass.
