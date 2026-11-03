# Terminal UI research and improvement plan

Research date: **2026-10-15**. Status: **research complete; implementation proposed**.

Henchman's next UI investment should make active work easy to follow, inspect and control. The strongest recurring problems in the sampled feedback concern scrolling, copying, input, review, approvals and status visibility. Visual polish should reinforce those behaviors.

## Scope and strength of evidence

This is qualitative desk research across public user discussions, issue reports and official project documentation. It is not a representative survey of “everyone,” a popularity ranking, or a benchmark of competing products. Issue trackers overrepresent failures; community threads overrepresent engaged users; launch threads and wrapper announcements can be promotional. Multiple reports support a design concern without establishing its prevalence.

We distinguish firsthand preferences, reported failures, documented capabilities and our recommendations. Historical reports retain their version/date where available. A closed issue remains useful as a regression scenario, but does not establish a current defect. Product documentation verifies a feature, not whether users like it. No live competitor evaluation or rendered Henchman usability audit was performed in this task.

The scope includes Codex CLI, Claude Code, Cline CLI and its VS Code extension, Antigravity CLI and desktop/IDE workflows, OpenCode, Aider and historical Gemini CLI feedback. Terminal, editor and desktop evidence must stay distinct. Model quality, subscription pricing and rate limits are excluded except where the interface must explain their effects.

## What the feedback implies

| Preference or frustration | Henchman design implication | Evidence strength |
|---|---|---|
| Terminal users value keyboard flow, separate sessions and freedom to use their existing editor. Other users prefer an IDE's visible diffs and file navigation. | Preserve the classic REPL and improve the Textual workspace around shared task state. Offer an external-editor review path. | Direct competing preferences in the [Codex discussion](https://www.reddit.com/r/codex/comments/1o2xzkx/why_do_most_people_prefer_cli_over_vscode/). |
| Streaming can pull users away from the history or plan they are reading. | Separate “follow live” from “reading history”; only explicit navigation resumes following. | Version-specific [Codex scroll report](https://github.com/openai/codex/issues/30489), corroborated by other products below. |
| A plan that cannot be copied is difficult to review before approval. | Keep plans, commands, outputs and diffs selectable/exportable even while a question or approval is pending. | [Codex Windows report](https://github.com/openai/codex/issues/50417), Oct 2, 2026; closed completed Oct 3. |
| Quiet output and detailed observability are both wanted. | Summarize successful routine actions, retain full detail on demand, and expose errors immediately. Keep filenames, operation and status in the collapsed summary. | Cross-product evidence below; the exact default density needs local testing. |
| Inconsistent approval controls and partial keyboard emulation break learned workflows. | One approval interaction contract across tools; contextual shortcut hints and tested editing behavior. | Historical [Gemini feedback](https://github.com/google-gemini/gemini-cli/discussions/7432), Sep/Dec 2025. |
| Animation and repeated redraws can interrupt screen-reader output. | Provide a plain, quiet interaction path and validate it with actual screen readers. | Firsthand [Orca report](https://github.com/openai/codex/issues/15938) and [VoiceOver request](https://github.com/openai/codex/issues/20489). |

## Coding-agent comparisons

### Codex CLI

**Liked:** users describe keyboard convenience, separate terminal sessions and flexibility alongside their preferred IDE. The same discussion contains a clear opposing preference for GUI diffs and clickable code references. Neither preference should dictate one compulsory layout for everyone. [User discussion](https://www.reddit.com/r/codex/comments/1o2xzkx/why_do_most_people_prefer_cli_over_vscode/).

**Disliked in specific reports:** scrolling that snaps back during generation (0.142.2, June 2026, now closed); inability to reliably copy a plan before approving implementation (Windows 0.160.0, October 2026, now closed); and unstable cursor/composer positioning under streaming (0.99.0 alpha, February 2026). Treat these as interaction failure scenarios, not claims that today's release has every defect. [Scrolling](https://github.com/openai/codex/issues/30489), [plan copying](https://github.com/openai/codex/issues/50417), [cursor stability](https://github.com/openai/codex/issues/11063).

**Borrow:** a focused terminal loop with inspectable commands/diffs, saved-session recovery, explicit permissions and external-editor composition. These are documented capabilities; user satisfaction must be assessed separately. [Official CLI documentation](https://learn.chatgpt.com/docs/codex/cli).

### Claude Code

**Liked:** terminal users describe a lighter workflow alongside their existing editor. Desktop users in the same June 2026 discussion prefer session tracking, file viewing, formatting and easier copy/paste. This supports retaining different ways to work rather than assuming terminal familiarity. [User discussion](https://www.reddit.com/r/ClaudeCode/comments/1ugrgyu/terminal_or_ide_for_claude_code_which_do_you/).

**Disliked:** users objected when collapsed tool rows hid paths and search terms, making mistakes harder to catch. A February 11, 2026 maintainer response documents a verbosity option restoring paths; full output is available through Ctrl+O. An April alternate-screen report describes lost native scrollback; it was closed as a duplicate, not demonstrated fixed. [Tool visibility dispute and remedy](https://github.com/anthropics/claude-code/issues/21151), [scrollback report](https://github.com/anthropics/claude-code/issues/43082).

**Borrow:** compact output with meaningful targets still visible, plus expandable details. Do not make users choose between opaque summaries and an overwhelming debug transcript.

### Cline CLI and VS Code extension

**Liked:** the author of a May 2026 CLI thread calls the new TUI attractive while criticizing permission interruptions, file-search relevance and light-theme colors. This is a useful example of attractive presentation coexisting with frustrating interaction. The maintainer reports a light-theme fix in 3.0.5, which the author acknowledges. [CLI feedback](https://www.reddit.com/r/CLine/comments/1te9qho/this_new_cline_tui_is_cool_looking_but_has/).

**Disliked:** a CLI 3.0.3 report describes lost initials-based filename matching; it was fixed May 19. Separately, extension users protested removal of foreground terminal interaction because they lost useful Ctrl+C and interactive-command workflows; a maintainer reports restoration in extension 3.82.0. These are resolved historical regressions on different surfaces. [Filename selection](https://github.com/cline/cline/issues/10798), [foreground terminal discussion](https://www.reddit.com/r/CLine/comments/1sycwkn/why_did_you_remove_foreground_terminal/).

**Borrow:** understandable permission scope, relevant file completion and accessible subprocess controls. Compare against the [actual CLI](https://docs.cline.bot/usage/cli-overview), while treating extension interactions as adjacent lessons.

### Antigravity CLI, IDE and Agent Manager

Antigravity CLI is a real terminal product, introduced May 19, 2026; current documentation exposes agent and artifact navigation. It must be evaluated separately from the IDE and desktop Agent Manager. [Official introduction](https://www.antigravity.google/blog/introducing-google-antigravity-cli), [CLI reference](https://www.antigravity.google/docs/cli/reference/).

**Liked:** one recent CLI user explicitly values its terminal feel alongside remote web control. Earlier IDE feedback praises artifacts and the agent-oriented workflow while requesting trustworthy model identification. The latter does not prove the user's suspicion of silent model switching. [CLI preference](https://www.reddit.com/r/GoogleAntigravityIDE/comments/1x47t0d/looking_for_the_ultimate_age_clidesktop_setup_to/), [IDE artifact/model feedback](https://discuss.ai.google.dev/t/question-how-can-we-verify-which-model-antigravity-actually-used-for-a-given-response/119658).

**Disliked:** a July 9, 2026 CLI report asks for an explanation of what an approval enables and describes shortcut conflicts with the host terminal; a May 19–21 report describes wrapped login URLs acquiring spaces/newlines when copied over SSH. Separately, desktop users complain about hidden terminal activity and transient controls. Fix status for these reports was not established. [CLI approvals](https://github.com/google-antigravity/antigravity-cli/issues/572), [CLI URL copying](https://discuss.ai.google.dev/t/antigravity-cli-displays-auth-url-with-spaces-and-carriage-returns/145562), [desktop visibility](https://discuss.ai.google.dev/t/learn-from-vscode-antigravity-ui-is-lacking/168985).

**Borrow:** persistent, navigable plans and artifacts; explicit model/task state; approval rationale and exact scope; copyable links and ordinary input alternatives when shortcuts conflict. Evidence for CLI appreciation is thinner here than for its specific failure scenarios.

### OpenCode

**Liked:** users cite tmux, remote sessions, keyboard customization and switching quickly between existing tools. The same discussion includes users who find a GUI more comfortable. Reported resource advantages are perceptions, not benchmarks. [TUI/GUI discussion](https://www.reddit.com/r/opencode/comments/1w1vyk8/tui_vs_gui/).

**Disliked:** one SSH/mosh user on an iPhone could not scroll the chat using expected touch gestures. Current documentation offers mouse-capture and scrolling controls; their effectiveness for this reported environment was not verified. [Remote-scroll report](https://www.reddit.com/r/opencodeCLI/comments/1tfmyil/is_there_a_way_to_use_native_scrolling_in/), [current TUI documentation](https://opencode.ai/docs/tui/).

**Borrow:** configurable mouse behavior, external-editor composition, transcript export, separate detail toggles and width-aware diffs. These documented features are design references, not measured favorites.

### Aider

**Liked:** an April 2025 appreciation thread praises a lightweight, understandable interface, explicit context selection and compatibility with tmux/vim; replies value reversible commits. **Disliked:** a Windows user reports multiline paste submitting line by line, with `/paste` offered as a workaround. [User discussion](https://www.reddit.com/r/LocalLLaMA/comments/1k63o9h/aider_appreciation_post/).

A separate cancellation/input-mode regression is closed and labeled fixed. Current documentation includes `/editor`, `/paste`, multiline controls, `/diff`, `/undo` and `/tokens`; it would be inaccurate to claim Aider lacks these capabilities. [Historical cancellation issue](https://github.com/Aider-AI/aider/issues/2992), [commands](https://aider.chat/docs/usage/commands.html).

**Borrow:** explicit context and recovery commands, a good composer and an external-editor escape hatch. Recovery should state exactly what it reverses.

### Gemini CLI: historical interaction lessons

Users described inconsistent review/approval controls and incomplete Vim behavior in September and December 2025. A February 2026 maintainer task also recorded flicker when tool-output height conflicted with small terminal dimensions; that task is closed. Borrow the regression scenarios: consistent shortcuts and layouts tested at actual small terminal sizes. Do not use this older evidence to characterize current Antigravity CLI satisfaction. [User discussion](https://github.com/google-gemini/gemini-cli/discussions/7432), [layout task](https://github.com/google-gemini/gemini-cli/issues/20217).

## Python terminal applications worth studying

“Favorite” here means a useful exemplar with identifiable appreciation or adoption signals, not a measured ranking. Apps and the libraries that implement them are separate categories. Version and implementation-language changes matter.

| Application | What users appreciate | Friction and lesson for Henchman |
|---|---|---|
| **Posting 1/2** — Python/Textual HTTP client | Users who tried the early app praised responsive interaction, SSH use and local request files. | Early users could not find ordinary create/quit actions or request naming. Put everyday actions in the palette and distinguish selection from activation. [July 2024 feedback](https://news.ycombinator.com/item?id=40926211). **Current Posting 3 beta is Go/Terma**, so use the Python versions as historical references. [Repository](https://github.com/darrenburns/posting). |
| **Harlequin** — Python/Textual database workbench | A user describes replacing a collection of SQL/editor/pager tools; other discussion shows enthusiasm for polished terminal results. | Installation isolation and adapter support need clear explanations. Borrow optional coordinated panes and truthful integration availability. [Firsthand use](https://news.ycombinator.com/item?id=40926211), [discussion](https://news.ycombinator.com/item?id=38882526), [project](https://github.com/tconbeer/harlequin). |
| **VisiData** — Python tabular explorer | Users describe frequent CSV/SQLite inspection, counts, deduplication and fast drill-down. | Powerful composable keys also create a learning curve; menus/tutorials help. Borrow filterable lists and drill-down for files, sessions and tool activity. [User recommendations and disagreements](https://www.reddit.com/r/commandline/comments/ss9s99/tell_one_terminal_app_you_use_everyday_but_no_one/), [project](https://github.com/saulpw/visidata). |
| **ranger** — Python/curses file manager | A user explicitly values its multicolumn context and file previews. | Preview/navigation lag undermines those benefits. Make previews asynchronous and cancellable; cursor movement must not wait on Git or file processing. Historical environment-dependent reports, not a current speed benchmark. [User discussion](https://www.reddit.com/r/ranger/comments/fd0eyd/make_ranger_faster_without_disabling_features/), [project](https://github.com/ranger/ranger). |
| **dooit** — Python task manager | Launch feedback likes the visual organizer and requests task movement and interoperability. | Early users could not tell how to switch panes or save. Make focus, draft state and session persistence explicit. This is launch-era interest, not broad adoption evidence. [Appreciation](https://www.reddit.com/r/commandline/comments/vfwp4t/oc_doit_a_todo_manager_that_you_didnt_ask_for_but/), [friction](https://www.reddit.com/r/unixporn/comments/vfwe9x/), [project](https://github.com/dooit-org/dooit). |
| **bpytop** — Python resource monitor | A reporter values its per-core view for understanding workload. | The same December 2020 issue (1.0.52, now closed) reports excessive CPU use. Borrow glanceable status, while measuring idle CPU and refresh cost. Positive evidence is comparatively sparse. Its successor **btop is C++**. [User report](https://github.com/aristocratos/bpytop/issues/223), [project](https://github.com/aristocratos/bpytop). |
| **pgcli** — Python/prompt-toolkit SQL REPL | A user chooses it for completion and staying in their existing keyboard/terminal workflow. | A December 2018 huge-value rendering report (now closed) shows why output needs bounds and paging. Borrow completion, history and visible editing modes for the classic REPL. [User preference](https://www.reddit.com/r/PostgreSQL/comments/1kmi7am/why_do_developers_use_psql_so_frequently_im/), [historical issue](https://github.com/dbcli/pgcli/issues/976), [project](https://github.com/dbcli/pgcli). |

For a focused design study, start with **Posting 1/2 for discovery**, **Harlequin for optional workspaces**, **VisiData for inspection**, and **pgcli for input**. Use ranger, dooit and bpytop for specific preview, hierarchy and status lessons. This is a recommendation based on Henchman's needs, not a ranking of popularity. Textual, Rich and prompt-toolkit are libraries; none substitutes for validating the actual application workflow.

## Henchman's current starting point

This is a source and test inventory, not a rendered UX verdict. Existing Tier 10 completion means components exist; it does not establish that the overall experience is easy to use.

| Existing implementation | What to improve or verify |
|---|---|
| [Textual app](../src/henchman/cli/textual_app.py) composes Chat, Thinking, Tools, Context and Workspace tabs plus input, footer and status bar. | Test whether important running/blocked state remains visible without tab switching. Compare an optional inspector against the existing tabs before replacing navigation. |
| [ChatPane](../src/henchman/cli/textual_widgets.py) calls `_scroll_to_bottom()` unconditionally from `append_agent_chunk()`. | First behavior candidate: reproduce scrolling away during streaming, then add explicit follow/hold state. |
| Tool messages already have compact arguments and expandable content in [textual_widgets.py](../src/henchman/cli/textual_widgets.py). | Improve summary information and error visibility; verify copy/export and stable expansion rather than rebuilding collapsible cards. |
| [Input handling](../src/henchman/cli/textual_mixins.py) queues ordinary submissions during processing and displays a queue notice; `/goal` and `/quit` have live handling. | Make queued content inspectable/editable/cancellable. Clearly distinguish a queued next turn from immediate steering. Do not advertise immediate steering without runtime support. |
| Escape cancellation, questions, session recovery, search, permissions and model/theme dialogs already have tests. | Extend them with realistic concurrent interaction scenarios and native terminal checks. Avoid reimplementing existing surfaces. |
| The [REPL chat tests](../tests/cli/test_repl_chat_ui.py) enforce transient activity status instead of permanent metadata spam. | Preserve this useful separation of current status from durable conversation history. |

Use the existing Python stack: `prompt-toolkit`, Rich and Textual are already declared in [pyproject.toml](../pyproject.toml). A framework rewrite is not justified by this research. First measure responsiveness and isolate rendering costs. Preserve the architecture and runtime capability boundaries documented in [architecture](architecture.md), [configuration](configuration.md) and the [capability matrix](../src/henchman/cli/commands/discovery_capabilities.py).

## Proposed interaction contract

These are design recommendations, not shipped behavior or observed user consensus.

1. **Stable conversation and input.** Keep the composer anchored. Scrolling upward pauses following; show a small new-activity count and an explicit return-to-live action. Expanding an old tool result must not jump the viewport. Preserve drafts through search, dialogs, resize and recoverable errors.
2. **Useful activity summaries.** Show operation, target, agent, duration and outcome when known. Collapse repetitive successful output; expose failures and approval requests immediately. Full arguments/output remain available. Group by task or turn without destroying chronological evidence.
3. **A small persistent status area.** Prioritize running, waiting for approval, waiting for an answer, retrying, cancelling, failed and idle. Put detailed model/context/cost information in an inspector, with a compact summary where space permits. Mark unavailable or estimated values honestly. “Finished execution” must not become “task verified” without acceptance evidence.
4. **Clear user control.** Label whether input is a draft, queued follow-up or immediate instruction. Keep stop, quit, dismiss and clear separate in visible help; resolve shortcut behavior by focus and state. Test existing bindings before changing them. Never silently lose a prompt on interruption.
5. **Reviewable permissions.** Show the exact action, affected scope, working directory where relevant and requested permission duration. Let the user inspect/copy the proposal while deciding. Reduce duplicate prompts only when the underlying authorization permits reuse. UI convenience must not broaden policy.
6. **Changes and recovery.** A changed-file list should lead to a diff, verification evidence and an accurately scoped recovery operation. Clearly distinguish restoring conversation, restoring agent edits and reverting all workspace changes. Preserve unrelated user work.
7. **Optional workspace detail.** On wide terminals, test an inspector for changes, tasks/agents, context and sessions. On narrow terminals, show one focused surface. Search and command discovery should expose capabilities available in the current runtime, with consistent names and shortcuts.
8. **Accessible terminal behavior.** Offer quiet/plain output, reduced motion, adequate light/dark contrast and labels that do not rely on color or emoji. Keep copyable text free of decorative prefixes where possible. Respect terminal selection conventions and validate screen-reader behavior rather than assuming the framework solves it.

## Phased implementation roadmap

This extends Tier 10 quality work while preserving foundations-first sequencing. All five phases are now authorized v0.4.2 subtasks under [epic #11](https://github.com/mlg151/henchman-ai/issues/11): [UI-0 #32](https://github.com/mlg151/henchman-ai/issues/32), [UI-1 #33](https://github.com/mlg151/henchman-ai/issues/33), [UI-2 #34](https://github.com/mlg151/henchman-ai/issues/34), [UI-3 #35](https://github.com/mlg151/henchman-ai/issues/35) and [UI-4 #36](https://github.com/mlg151/henchman-ai/issues/36). They share existing policy, persistence, review, privacy, budget and agent services. The epic now has 24 subtasks, and release #30 depends on all five UI tasks. UI-0 is in wave 1, UI-1 in wave 5, UI-2/UI-3 in wave 6, UI-4 in wave 7 and final release verification in wave 8; these are dependency stages, not calendar estimates.

| Phase | Work | Exit criteria |
|---|---|---|
| **UI-0 — Establish the baseline** | Inventory existing behavior, reproduce the scroll issue, record keyboard/state contracts and representative terminal sessions. | A scripted slow-provider fixture exercises stream, tool, approval, question, error and cancel; findings distinguish code evidence, automated checks and manual observations. |
| **UI-1 — Reliable interaction** | Follow/hold scrolling, copy/export, stable composer and drafts, predictable input and cancellation, quiet accessible output. | Reading position survives streaming and resize; a long plan can be copied while approval is pending; multiline paste never submits accidentally; cancellation preserves usable session state. |
| **UI-2 — Understand the work** | Improve existing tool cards, expose blocked/failure state, visible queued input, changes/diff/verification navigation. | A user can identify the current action, why work stopped, what changed and which checks ran without searching raw logs. Every displayed result maps to actual runtime evidence. |
| **UI-3 — Navigate a workspace** | Searchable session resume, task/agent inspector, context/budget explanation, command discovery and optional layouts. | Keyboard-only participants can resume the correct session and inspect a specific task; narrow terminals remain usable; no capability appears as available when its runtime is absent. |
| **UI-4 — Polish and qualify** | Consistent spacing, typography hierarchy, theme contrast, focused onboarding, long-session performance and cross-platform qualification. | Representative users complete the scenarios below; recorded terminal/platform results support release claims; unresolved limitations are documented. |

Accessibility starts in UI-1 and is checked throughout. Visual consistency starts with interaction components rather than waiting for a final reskin. Each behavior change should begin with a failing test in the nearest existing test module.

## Verification and user research plan

Use deterministic provider/tool fixtures to test the interface independently of model quality. Then run a small formative study with terminal experts, occasional terminal users and screen-reader users. Include users of Windows Terminal/PowerShell, macOS terminals and Linux terminals, plus tmux/SSH where supported. Such a study finds usability problems; it does not estimate market-wide preference.

Representative tasks:

- Write and edit a multiline prompt; paste a large block; change focus and resize without losing the draft.
- Read and copy an earlier result while a response and background task stream new output.
- Review a long plan or diff during an approval prompt, deny an operation, then recover.
- Queue a follow-up, inspect it, cancel the current action and understand what will run next.
- Find a failing test, identify which agent ran it and distinguish execution success from verified correctness.
- Resume a prior session, inspect context and recover an agent change without removing unrelated edits.
- Complete the same reading/approval flow using keyboard-only navigation and a screen reader.

Record completion, assistance needed, wrong actions, lost text, viewport jumps, ability to explain task state and time to locate the relevant evidence. Collect preference separately from performance. As initial engineering targets, measure local input-to-paint p95 under 100 ms and visible cancellation acknowledgement under 250 ms on a documented machine; these are proposed targets, not industry benchmarks or provider-stop guarantees. Establish baseline memory and render cost with a long transcript before setting a regression budget.

Automated checks should cover Textual interaction/state behavior, prompt-toolkit parity, terminal resize and output safety. Exercise 80×24, 120×40 and a wide split-terminal layout, light/dark/no-color modes, Unicode and long paths. Use actual terminal recordings/manual checks for selection, clipboard, tmux, SSH, IME and assistive technology where headless tests cannot prove behavior. Unit-test success is not evidence of native usability.

Roadmap status belongs in [FEATURE_TODO.md](../FEATURE_TODO.md#tier-10-ui-textual-enhancements) and [TODOS.md](../TODOS.md).
