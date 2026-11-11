# Intrusive VTE GC object-type diagnostic

**Textual geometry, style and cache objects appeared among retained unreachable
objects, but this experiment cannot establish which objects caused the normal
collection pauses.** It enabled `gc.DEBUG_SAVEALL` in an owned diagnostic
process and counted type names at generation-2 collection stops. This setting
retains cycles; clearing `gc.garbage` removes the list's references but can
leave cyclic objects to be found again. Later counts can therefore include
objects counted earlier, and are not independent or production heap sizes.

The frozen plan used clean commit `6db0adfd88aedd458bbbca480052fbefa74c6521`,
one 160×50 software VTE window, 1,000 synthetic history messages, and 20 input
plus 20 cancellation trials. All 40 observations completed, and five
generation-2 events were recorded. The probe recorded type names and counts,
not object values or reachability paths. The object scan after each recorded
collection took 17–68 ms; the debug mode and scan invalidate performance
comparisons with normal operation.

| Recorded phase | Saved objects | Selected type counts | Tracked history widgets before → after |
| --- | ---: | --- | ---: |
| Startup | 72,389 | 2,530 `Styles`; 2,137 `LRUCache`; 872 `ChatMessage` | 344 → 128 |
| Probe 2 | 130,864 | 14,896 `Size`; 9,642 `Region`; 7,644 `MapGeometry` | 128 → 122 |
| Probe 7 | 179,477 | 32,198 `Size`; 22,627 `Region`; 16,321 `MapGeometry` | 122 → 111 |
| Probe 13 | 235,035 | 52,506 `Size`; 38,225 `Region`; 26,508 `MapGeometry` | 111 → 98 |
| Probe 18 | 283,791 | 69,569 `Size`; 50,957 `Region`; 35,068 `MapGeometry` | 98 → 88 |

These are cumulative/repeated diagnostic observations, not evidence that a
particular class, screen or history widget caused the uninstrumented tail.
The [prior diagnostic](2026-11-08-vte-cancel-gc-v2.md) separately observed
collections overlapping three slow cancellations without `DEBUG_SAVEALL`.
Neither run establishes a safe GC-policy change or satisfies the latency,
physical-terminal or accessibility gates. No model or user content was used.

The [receipt](2026-11-08-vte-gc-types-v3.json) retains all trial observations,
the top recorded types, frozen plan and raw-artifact hashes. The
[exact scripts](../../evals/vte_gc_types_v3/README.md) are archived; raw
timelines, screenshots and logs remain in the local `vte-cancel-types-6db-v3`
qualification cache. The application and display were joined, the recorded
child PID/start-time identity was absent afterward, and the source remained
clean. No production GC setting was changed.
