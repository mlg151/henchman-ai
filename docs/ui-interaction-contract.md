# Terminal interaction contract, UI-0.1

This version fixes the intended behavior before the first UI-1 comparison. It
implements part of [the terminal UI workstream](terminal-ui-research.md), not
native-terminal or accessibility qualification. The classic REPL keeps its
transcript workflow; this first implementation slice changes Textual only.

## Reading and input states

| State/action | Contract |
|---|---|
| Live transcript | New content follows the bottom without moving composer focus. |
| Reading history | Scrolling away, searching history or expanding an older card holds the reading position. New chunks never resume following automatically, even if the viewport reaches the bottom. |
| New activity while reading | A persistent text label announces new activity. The transcript remains intact and the composer draft is unchanged. |
| Return to live | A visible, keyboard-focusable button, Alt+End, or End while the chat pane has focus explicitly resumes following. |
| Keyboard history scrolling | Page Up/Down in the chat pane, or Alt+Page Up/Down from the composer, scrolls history without submitting or changing the draft. |
| Submit | Enter and Ctrl+Enter submit the composer. Empty input does nothing. |
| Newline/paste | Shift+Enter and Ctrl+J insert a newline. Bracketed multiline paste inserts one draft and does not submit its individual lines. |
| Escape in the composer | Requests cancellation during work; otherwise dismisses search. It does not erase the draft. |
| Escape in an approval/question | Denies/dismisses that decision according to the existing prompt channel; it does not approve work. |
| Cancellation | `Cancelling...` is acknowledgement only. Completion is shown after the existing worker cleanup finishes. |
| Quit | Existing Ctrl+Q/Ctrl+C quit behavior is retained for this slice. |

Hosts may intercept extended keys or encode them identically. The visible return
button and ordinary Tab/Enter activation are the fallback when Alt+End does not
arrive. Shift+Enter/Ctrl+Enter availability, native selection, terminal scrollback
and clipboard support require the native checks below. Application mouse capture
is not made configurable by this slice.

## Versioned scenarios

The deterministic rendered [harness](../tests/cli/ui_scenarios.py) is version
`UI-0.1`. It uses local scripted events and isolated settings; it never invokes a
model. The [interaction tests](../tests/cli/test_textual_interaction_contract.py) exercise the real Textual
widget tree and key dispatch. Existing checks remain authoritative for their
runtime boundaries.

| Concern | Automated fixture/test | Required additional validation |
|---|---|---|
| Follow/hold, concurrent streams, resize, expanded history | [Interaction tests](../tests/cli/test_textual_interaction_contract.py), three viewport sizes | Native wheel/scrollbar, tmux and SSH/mosh |
| Submit, multiline paste, history and unsent draft | [Interaction tests](../tests/cli/test_textual_interaction_contract.py), [integration](../tests/cli/test_textual_integration.py), [input bindings](../tests/cli/test_input_bindings.py) | Actual terminal paste, host key conflicts and IME |
| Long plans, wrapped links, selection/copy while approval is pending | [Question channel](../tests/cli/test_textual_question_channel.py), [direct evidence](../tests/cli/test_textual_direct_evidence.py); richer inspection remains pending | Clipboard/selection, keyboard and remote-safe copy/export |
| Questions and approval lifetime | [Question channel](../tests/cli/test_textual_question_channel.py) | Screen-reader question/rationale and focus announcements |
| Cancellation acknowledgement and cleanup | [Interaction tests](../tests/cli/test_textual_interaction_contract.py), [Escape](../tests/cli/test_escape_cancellation.py), [background execution](../tests/tools/test_background_execution.py) | Native visual acknowledgement latency, runtime cleanup |
| Queued input and recovery | [Textual goals](../tests/cli/test_textual_background_goals.py), [REPL goals](../tests/cli/test_repl_background_goals.py); queue editing remains pending | Cancellation/resume disposition and draft-loss observation |
| Failure, large output, tool evidence and identity | [Tool inspection](../tests/cli/test_textual_tool_activity.py), [completion](../tests/cli/test_completion_rendering.py); compact correlated rows and bounded evidence | Find a failed check and explain its actual evidence |
| Sessions, tasks and project boundaries | [Sessions](../tests/cli/test_textual_session_management.py), [workspace evidence](../tests/cli/test_textual_workspace_evidence.py); interactive inspectors remain pending | Find/resume the intended session, Back navigation |
| Checkpoint file/hunk review | [F8 review](../tests/cli/test_textual_checkpoints.py), narrow/wide navigation, preview/Apply, conflicts, draft/focus and joined shutdown | Native keys, screen-reader navigation and evidence comprehension |
| Provider/context/budget truth | [Provider display](../tests/cli/test_active_provider_display.py), [usage](../tests/cli/test_usage_command.py) | Distinguish unknown, estimated and reported values |
| Width, theme, Unicode and long paths | 80×24, 120×40 and 160×50 in the [new harness](../tests/cli/ui_scenarios.py) | Light/dark/no-color native contrast and focused narrow layout |
| Quiet output, reduced motion, keyboard mode, mouse preference | [Typed settings](../tests/cli/test_config_ui_terminal_sync.py) only; runtime consumers pending | Actual assistive technology, terminal/tmux/remote checks |

The implemented resize anchor retains a message and its visual row while earlier
messages reflow. Exact character anchoring within one rewrapped long message is
not yet implemented. Full approval inspection, external-editor composition,
clipboard behavior and the remaining UI settings are separate open work; this
slice does not complete issue #33.

## Tool observations and inspection

Textual groups observed requests and results by call and agent within each
forwarded stream. Each call has a compact keyboard-focusable row. Enter opens a
read-only inspector; Space expands the row. Escape or Back returns to the row
while preserving the composer draft and held reading position.

Rows distinguish Requested, Succeeded, Failed, Unknown and Interrupted. Only an
explicit boolean result establishes success or failure; missing or malformed
outcomes remain Unknown. Repeated requests/results sharing an identity retain
their evidence and become Unknown. Results without call identity stay separate;
missing requests never acquire guessed arguments or timing. Stream closure marks
unanswered requests Interrupted, with possible effects still uncertain.

The inspector retains arguments, multiline output and typed result evidence.
Elapsed time measures request observation to result observation, including waits;
it is not actual execution duration. Tool success does not establish requirements
acceptance. Runtime retry counts and actual dispatch timing remain unavailable.

Display evidence is limited to 32 KiB per entry, 64 KiB and 16 entries per call,
and 2 MiB across retained call payloads. Clipping and eviction show omissions;
correlation and compact rows remain available after payload eviction. The Tools
tab uses the same bounded store and current credential projection, showing at
most 64 recent calls, 64 KiB of evidence frames and 1,000 logical body lines, with
visible omissions. Inspection
rechecks known credentials, including rotation while open. These are display
limits; session persistence and runtime control keep their own contracts.

The mounted tests cover 80×24 and 120×40 layouts, interleaved agents, repeated
identities, long output, credential rotation, retention, resize and draft/focus.
Pending-decision navigation and lifecycle status remain separate work under #34.
These tests provide no native terminal, clipboard or assistive-technology
qualification.

## Baseline and qualification boundary

The pre-change rendered probe used revision `a1516ae`, Python 3.11.15, Textual
8.0.0, Linux 7.0.0-38-generic x86_64/glibc 2.43. The widget source SHA-256 was
`6bffe617cc9f4914e0dd4bf81ffa92452d2f01b63864bf87a259c9d821baf442`.
This was a headless Textual Pilot, with no terminal emulator, native clipboard,
screen reader or participant. It is source-behavior evidence only.

Workload: 40 history messages of a numbered prefix plus eight repeats of
`readable text `; one active response; scroll to row 20; then three 30-ms-spaced
chunks. At 80×24, the viewport jumped from 20 to 101 (maximum 102); at 120×40,
it jumped from 20 to 85 (maximum 86). A separate mounted composer probe found
Enter inserted a newline, Ctrl+Enter submitted, and Escape selected clear-search
instead of cancellation. These failures precede the first implementation.

The frozen engineering targets are local input-to-paint p95 below 100 ms and
visible cancellation acknowledgement below 250 ms on named hardware. The
existing runtime cancellation gate remains one second with bounded cleanup.
Provider latency is measured separately. This document supplies no passing
performance measurement: native terminal/version and hardware qualification,
long-transcript memory/idle-CPU baseline and an explicit regression budget remain
outstanding release evidence. Record failures and unsupported paths as results.

Native Windows, macOS and Linux terminals, tmux/SSH/mosh, IME, clipboard and
screen-reader scenarios remain unqualified. The formative study must include
terminal experts, occasional users and screen-reader users; record assistance,
wrong actions, lost drafts, viewport jumps, task-state comprehension and evidence
location time separately from subjective preference. Passing headless tests
cannot close those criteria in issues #32 or #36.
