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
| Composer selection | F6 selects the current line and F7 selects all text. Application navigation keeps those editor bindings available. |
| Escape in the composer | Requests cancellation during work; otherwise dismisses search. It does not erase the draft. |
| Escape in an approval/question | Denies/dismisses that decision according to the existing prompt channel; it does not approve work. |
| Return to a pending decision | F4 focuses the existing answer field or approval's No button. An unrelated overlay stays open; close it first to return. |
| Saved input queue | F9 opens inspection and explicit edit, remove, reorder and Send controls. Opening or editing never grants dispatch permission. |
| Context and usage | The Context tab opens a read-only snapshot. F5 explicitly refreshes; Escape/Back restores focus without changing the composer or session. |
| Cancellation | `Cancelling...` is acknowledgement only. Completion is shown after the existing worker cleanup finishes. |
| Quit | Existing Ctrl+Q/Ctrl+C quit behavior is retained for this slice. |

Hosts may intercept extended keys or encode them identically. The visible return
button and ordinary Tab/Enter activation are the fallback when Alt+End does not
arrive. Shift+Enter/Ctrl+Enter availability, native selection, terminal scrollback
and clipboard support require the native checks below. `ui.mouse_capture: false`
disables application mouse reporting at the next Textual launch; explicit Python
`mouse=False` remains restrictive. It does not establish native clipboard or
scrollback behavior. Keyboard history navigation and the return-to-live control
remain available with capture disabled.

`ui.reduced_motion: true` takes effect at driver startup: transitions finish
immediately, loading feedback stays visible without animation, and focused
composer/dialog editors use steady cursors. Streaming, pending decisions, status,
joined cancellation and evidence refresh remain active. Later setting changes
take effect on the next launch.

`ui.detail_density` is also captured at startup. Compact tightens transcript
spacing; normal retains the default presentation; detailed expands new tool rows
using their existing bounded, redacted evidence. Manual row toggles persist
through updates and resize. Density does not change the held reading position,
draft/focus ownership, outcome labels, approval authority or retention limits.

`ui.output_mode` is captured at Textual startup. Plain/quiet transcript and
command content stays literal, including Markdown, bracketed text and long lines.
Quiet hides typed routine welcome/delegation/thinking rows while preserving
thinking inspection and mounted tool cards. Routine details start collapsed;
failed/unknown/interrupted outcomes expand unless the user already chose a state.
Answers, commands, warnings, compaction, decisions and cancellation/status remain
visible. This does not alter stored evidence or qualify native accessibility.

The classic REPL also captures `ui.keyboard_mode` at prompt creation: `standard`
preserves its existing editing bindings and `vim` selects prompt-toolkit Vim
editing. Idle Vim Escape preserves the draft and enters normal mode; active-turn
Escape/Ctrl+C retain cancellation priority. Bracketed multiline paste does not
submit automatically. The [pipe-key regressions](../tests/cli/test_repl_keyboard_mode.py)
exercise actual dispatch, but do not qualify native terminals or screen readers.
Textual's keyboard-profile consumer remains pending.

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
| Questions and approval lifetime | [Question channel](../tests/cli/test_textual_question_channel.py), [lifecycle and F4](../tests/cli/test_textual_activity_state.py) | Screen-reader question/rationale and focus announcements |
| Cancellation acknowledgement and cleanup | [Interaction tests](../tests/cli/test_textual_interaction_contract.py), [Escape](../tests/cli/test_escape_cancellation.py), [background execution](../tests/tools/test_background_execution.py) | Native visual acknowledgement latency, runtime cleanup |
| Queued input and recovery | [F9 queue controls](../tests/cli/test_textual_queue.py), [shared workflow](../tests/core/test_session_workflow.py), [Textual goals](../tests/cli/test_textual_background_goals.py), [REPL goals](../tests/cli/test_repl_background_goals.py) | Cancellation/resume disposition and draft-loss observation |
| Failure, large output, tool evidence and identity | [Tool inspection](../tests/cli/test_textual_tool_activity.py), [completion](../tests/cli/test_completion_rendering.py); compact correlated rows and bounded evidence | Find a failed check and explain its actual evidence |
| Sessions, tasks and project boundaries | [Sessions](../tests/cli/test_textual_session_management.py), [workspace evidence](../tests/cli/test_textual_workspace_evidence.py); interactive inspectors remain pending | Find/resume the intended session, Back navigation |
| Checkpoint file/hunk review | [F8 review](../tests/cli/test_textual_checkpoints.py), narrow/wide navigation, preview/Apply, conflicts, draft/focus and joined shutdown | Native keys, screen-reader navigation and evidence comprehension |
| Provider/context/budget truth | [Context inspector](../tests/cli/test_textual_context.py), [provider display](../tests/cli/test_active_provider_display.py), [usage](../tests/cli/test_usage_command.py) | Distinguish unknown, estimated and reported values |
| Width, theme, Unicode and long paths | 80×24, 120×40 and 160×50 in the [new harness](../tests/cli/ui_scenarios.py) | Light/dark/no-color native contrast and focused narrow layout |
| Quiet output, reduced motion, keyboard mode, mouse preference | [Plain/quiet rendering](../tests/cli/test_textual_output_modes.py), [typed settings](../tests/cli/test_config_ui_terminal_sync.py); [mouse startup and keyboard fallback](../tests/cli/test_textual_mouse_settings.py) and [reduced-motion lifecycle](../tests/cli/test_textual_motion_settings.py) implemented, other consumers pending | Actual assistive technology, terminal/tmux/remote checks |

The implemented resize anchor retains a message and its visual row while earlier
messages reflow. The anchor uses the displayed row, including when focus scrolling
has a fractional internal position. Deferred scrolling to the same position keeps
that anchor through pending layout work; actual navigation selects a new anchor.
Exact character anchoring within one rewrapped long message is
not yet implemented. Full approval inspection, external-editor composition,
clipboard behavior and the remaining UI settings are separate open work; this
slice does not complete issue #33.

## Context and usage inspection

Open **Context → Context and usage** to inspect the selected project session.
Context, Retention and Usage are separate views with capture and read-completion
times. F5/Refresh reads the current selection explicitly; a changed session,
provider, effective model or accounting owner invalidates the previous snapshot.
Back/Escape returns to the previous focused control, preserving the composer
draft and selection. Close any pending decision or other dialog first.

The inspector reads the shared session-context and session-accounting services.
It separates configured request capacity and conversation budget from estimated
session-history tokens, and separates observed token counts, held estimates and
reported billing. Missing usage, prices and disk-save acknowledgement remain
unavailable. Usage names models observed on actual requests, which may differ
from the current selection. Cache/reasoning counts are subsets of total tokens.
Retention reports compaction and memory-extraction policy without displaying
retained content, reasoning or opaque continuation payloads.

Each section is limited to 64 KiB and 128 detail rows with visible omissions.
Session-copy admission is limited to 2 MiB of strings, 25,000 nodes and depth 24;
oversized evidence produces unavailable retention estimates rather than partial
counts. Per-model summaries stop above 4,096 request records while shared totals
remain available. These are display/admission limits, not hard latency or memory
guarantees for the underlying shared accounting read. Credential rotation is
rechecked before display. Back and shutdown join outstanding reads. Inspection
does not select, save, compact or resume a session, prepare a provider request,
or verify a task. Broader session/task navigation and native accessibility remain
separate work.

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
These tests provide no native terminal, clipboard or assistive-technology
qualification.

## Activity status and pending decisions

The persistent status names foreground work separately from provider/context
details and transient search notices. It shows Running, Waiting for answer or
approval, Cancelling, Closing, Idle, Cancelled or Stopped with error. Closing and
cancellation take priority over queued decisions; cancellation remains visible
until worker cleanup settles. Idle means foreground work has settled and makes
no claim about verification. Agent prose cannot replace these lifecycle states.

F4 returns focus to an actual pending decision without answering it, replacing
the draft or dismissing an unrelated overlay. The focusable status also offers
Enter when a decision is available. Questions focus the answer field; approvals
focus No. A cancelled prompt hidden by another dialog retires when that dialog
closes, before the next queued decision opens. Expired decisions lose their
action, and callbacks from older workers or prompts cannot clear newer status.
The [mounted regressions](../tests/cli/test_textual_activity_state.py) cover these
lifetimes at 80×24 and 120×40; native keys, assistive technology and performance
remain unqualified under #34/#36.

## Saved input queue

F9 opens a snapshot of saved input without changing the composer draft or its
selection. Enter inspects an input, Tab reaches its actions, F5 refreshes the
snapshot, and Escape goes Back. Existing questions and approvals stay current;
close an unrelated dialog before opening the queue. Narrow layouts show the list
and detail in separate stages.

Queued, held, dispatched, completed and uncertain input have distinct labels.
Edit saves a complete replacement and leaves it held. Back from an edit offers
Keep edit or Discard; it never submits the composer. Remove requires a separate
confirmation and applies only before dispatch. Reorder also leaves changed input
held. Only explicit Send permits a future turn. Goal continuation uses `/goal
resume`; uncertain effects require inspection through the existing recovery
controls. Completed input is not evidence that requirements passed.

Every change binds the observed revision, session and current runtime. A changed
session, storage wait, cancellation or intervening decision invalidates old
controls. Back and shutdown join the owned storage worker. A completed commit
remains visible even if cancellation arrives afterward, but it grants no dispatch
permission. Read-only previews use current credential projection; masked evidence
never becomes executable input, and unavailable original text requires a complete
replacement. The screen requires Refresh after concurrent changes or errors.

Mounted tests cover 80×24 and 120×40, draft/selection preservation, stale edits,
credential rotation and cancellation around storage commits. Native terminal,
accessibility and input-to-paint performance qualification remain open.

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
