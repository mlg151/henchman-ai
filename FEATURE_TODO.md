# Feature TODO — Henchman Roadmap

Organized by priority tiers. Each item is a discrete feature to implement.

## v0.4.2 delivery plan (in progress)

Cold offline startup now uses [packaged tokenizer vocabularies](docs/providers.md#offline-token-estimates)
for context estimates and RAG chunking. Native artifact tests isolate user settings,
interpreter lookup and empty token caches. Current model testing is local-only by
user instruction; hosted-provider qualification remains unverified.

Repository retrieval under #17 now separates worktree caches and validates
bounded semantic candidates against current tracked-file bytes before returning
snippets. Legacy/stale indexes require explicit reindexing; see
[current-file RAG evidence](docs/tools.md#rag_search). Explicit
[`pattern_search` repository mode](docs/tools.md#pattern_search) now adds fresh
Python implementation, test/reference and scoped instruction evidence with
current-byte provenance and retained typed results. Static relationships remain
candidates; live retrieval comparisons and broader performance qualification
remain open.

MCP catalogs now refresh atomically across bounded pagination, preserving schemas,
annotations and typed results through provider text projection and session
retention while invalidating stale handles and keeping scoped allowlists. P0/P1
[schema/client compatibility](docs/standards.md#implemented-compatibility-foundation-v042-work)
has native fixture evidence; modern auth/context and real-account qualification
remain under #25, with final release qualification under #30.
The exact SDK 2.3.0 pin now supports bounded native stdio across four legacy
revisions and 2026-07-28, with no implicit mutating replay and explicit telemetry
privacy refusal. Bounded unauthenticated Streamable HTTP now covers four
revisions with JSON/SSE and policy-checked cleanup. Explicit resource/template/
prompt catalogs and previews now preserve untrusted source data without changing
conversation history; continuation is rejected before SDK normalization. Explicit
attachment consumes a current session-bound preview as saved user context while
idle, preserving source evidence and untrusted roles across compaction. OAuth
configuration, bounded discovery, generation-bound storage and explicit library
callback/token flows and explicitly guarded manager operations are implemented;
manager teardown invalidates pending OAuth work before transport cleanup.
Explicit Python clients now support credential-scoped HTTP requests with a pinned
pre-header guard and cleanup uncertainty handling.
The same pinned guard now checks discovery and token exchange after connection
setup, retaining uncertain post-boundary claims without replay.
An owned browser helper now bounds desktop handoff and rechecks authority before
transferring the URL, with cancellation and cleanup tested using synthetic launchers.
A runtime-only user-intent controller and explicit manager connection now bind
actions to current frontend/session/project ownership, with one-shot admission,
joined cancellation and guarded catalog publication. Automatic OAuth connections
remain refused. Fresh REPL/Textual submissions now own login/refresh/status/logout
and a separate connect action, with private command history and shutdown joins
even after queue-save failures. Real browser/account and final native qualification
remain open under #25.

Configured plan checks now retain explicit input fingerprints and requirement
tags. A read-only status API detects later edits and reports stale, incomplete or
unverified checks; historical results remain intact. Explicit `verification.checks`
now adds required assertions to new plans and revokes current evidence when the
configuration changes. A library repair coordinator now pins explicit edit and
criterion scope, bounds attempts/repeated diagnostics and preserves incomplete
outcomes. Explicit `Orchestrator.repair_direct` now enforces that scope through
the existing registry, one usage budget and correlated model/controller operations.
Interactive controls and live acceptance remain open under #16.
Known credentials are now projected from verification evidence, with sensitive
saved specifications unavailable for execution and explicit locked sanitation.
Metric storage and exports now project known credentials and marked metadata;
legacy reads remain non-mutating. Baseline evaluation reports now share that
policy, retaining observed credentials
around each attempt and validating identities before preserving them.
Broader privacy qualification remains under #20.

Runtime registration now rejects invalid input/output contracts before publishing
tools, binds schema snapshots to approval, and validates successful structured
results before recording completion. Invalid output is a failed observation of
the completed attempt, not permission to replay its effects.

The [operation journal](docs/operation-recovery.md) now commits correlated tool
attempts before dispatch, binds public runtime/session recovery and exposes explicit
revision-checked user resolution/retry. Versioned provider continuation now retains
qualified opaque profiles and refuses incompatible replay. Shared goal/queue
authority now drives both interactive frontends, with explicit restored-input
disposition, current-revision goal completion and correlated run/operation evidence.
Native/live acceptance and further restart qualification remain under #23.
Notification-driven primary turns now preserve ordered request/result correlation
and text-only turns through child questions, parent replies and durable reload.
Recovered running task records now expose unknown outcomes and refuse unowned
process control. Versioned intent and per-record conditional updates now preserve
concurrent task evidence; unresolved observers leave live logs intact. Queued
intent is never automatically dispatched; detached process recovery and replay remain unsupported.

The [content checkpoint foundation](docs/checkpoints.md) now captures explicit
before/after file scopes and supports revision-bound review, conflict-checked
POSIX restore, interrupted-restore recovery and private bounded retention.
CLI and interactive `/checkpoint` commands now share file/hunk review, preview,
apply, recovery and retention. Content-changing restores revoke plan-check success
and concurrent-save authority; pending restores block verification. Runtime ownership
capture now covers declared write/edit/patch/test targets; unknown scopes remain
explicitly unavailable. Textual F8 now provides staged file/hunk review, preview
and idle-only Apply; native usability remains incomplete under #34/#36. The Windows
NTFS content-only backend has explicit private-ACL semantics and
[completed native service regressions](docs/evaluations/2026-11-08-native-service-evidence.md).
The recorded aggregate CI failure and final release qualification remain separate.

The [v0.4.2 implementation epic #11](https://github.com/mlg151/henchman-ai/issues/11)
turns [feature-demand research #10](https://github.com/mlg151/henchman-ai/issues/10)
and [terminal UI research #31](https://github.com/mlg151/henchman-ai/issues/31)
into 24 dependency-ordered subtasks in the
[v0.4.2 milestone](https://github.com/mlg151/henchman-ai/milestone/2).
The epic owns detailed scope, acceptance criteria, dependencies and release gates;
these are planned outcomes, not completed capabilities.

Implementation is in progress on the release integration branch. Foundation
[issue #12](https://github.com/mlg151/henchman-ai/issues/12) is complete at
`55fd66b`: all 20 jobs passed in the [qualified CI run](https://github.com/mlg151/henchman-ai/actions/runs/41758021286),
including full Linux Python 3.11–3.14 tests, enforced Python 3.12 coverage,
12 native installed-wheel cohorts and the aggregate gate. Later feature changes
and final release artifacts still require qualification under #30.
The reviewed evaluator increment connects twelve independent scenarios, including
syntax repair, semantic bug repair, tool-failure recovery, interruption/recovery,
Fibonacci implementation, package lifecycle and test/documentation delivery with
independent correctness and runtime checks. The complete twelve-case corpus is
frozen; hosted baselines remain unverified under local-only testing. The baseline runner now
applies one deadline to the complete scenario; iteration caps remain per turn.
Expired work cannot be recorded as verified success, though cooperative cleanup
can extend elapsed time. Reported latency includes setup and cleanup for all
outcomes. See [evaluation bounds](evals/README.md).
The [first local development cohort](docs/evaluations/2026-11-07-local-baseline.md)
completed all 22 planned attempts with 22 timeouts and no verified successes.
The raw report is retained; inference readiness and successful model qualification
remain open, with no paid model calls used. A [CPU follow-up](docs/evaluations/2026-11-07-cpu-readiness.md) retains four failed syntax attempts and one independently verified diagnostic; it does not establish general CPU-profile qualification.
The portable `AGENTS.md` increment is integrated: default discovery includes
`AGENTS.md` after Henchman's own filenames, physical-path deduplication rejects
aliases escaping the global/repository boundary, and immutable instruction
provenance snapshots capture paths, scopes, kinds, order, sizes, truncation
state and SHA-256 digests. Sessions attached through the CLI record a
content-free provenance record in session metadata; dynamic background
subagents receive a bounded provenance appendix. Per-target refresh rejects
outside-boundary targets before reading, sibling subtrees cannot leak
instructions, and repository text cannot widen tool policy or approvals.
Runtime consumers now refresh before requests and at supported tool targets,
including generated output paths, parsed patch files and formatter descendants.
Changed instructions defer mutations until presented to the model; checks repeat
after approval and formatter waits. Delegated agents retain private scoped text
and bounded provenance. Directory lint fixes require explicit file targets;
shell/Python embedded paths remain cwd-scoped. Issue #15 passed native qualification
on Python 3.11–3.14 across Linux/macOS/Windows ([CI evidence](https://github.com/mlg151/henchman-ai/actions/runs/42386583146));
final release qualification remains under #30. See [runtime refresh](docs/configuration.md#context-files-henchmanmd-and-agentsmd).
Session persistence under #23 now uses versioned atomic replacement, integrity
checks, one recoverable prior copy and native locking with stale-writer rejection.
Legacy files migrate on save; corrupted current files recover with explicit warnings.
Process-termination and simultaneous-writer regressions join the native installed
wheel suite. Goal/queue/operation recovery and continuation qualification remain open.
The #20 session-selector boundary now covers full IDs, prefixes, current pointers,
memory/context lookup and derived exports/branches/templates. Shared credential
redaction now covers session persistence and retained backups, JSON/Markdown
exports, templates and new playback recordings. Interactive runtimes register
configured keys and provider rotation; live execution inputs stay unchanged.
Structural session fields and identities remain usable with short credentials;
marker-containing values, Bearer whitespace and legacy backup-only credentials
are covered by additional regressions.
Headless JSON output now shares the credential policy, masks split streamed
values across independent agent channels, derives previews after redaction, and
flushes pending evidence before completion or on interruption without changing
execution inputs. REPL/Textual event streams, tool displays/approvals, Textual
command output and direct chat/status/history displays now share that policy.
Interactive failure logs project tracebacks without attaching raw exceptions.
Provider/forwarded-stream cleanup and delegation diagnostics now use the shared
exception projection while preserving original cancellation. Operational event
SQLite writes and legacy read copies redact known credentials; execution and
authority tables remain outside evidence projection.
Config mutation responses and sync exports now redact credential echoes while
retaining raw settings and runtime inputs. Background task output now redacts
before disk capture, bounds private logs and safely migrates eligible indexed
legacy evidence with explicit diagnostics; see [background execution](docs/tools.md#background-execution).
Other logs/UI panels/metrics/handoffs
and broader restricted filesystem/network execution still require implementation
and qualification.
Approval scope now includes registration, project and physical target identity,
with fresh checks after approval, formatter waits and retry delays. Restricted
root settings now mediate qualified builtin file reads/writes through directory
handles, deny unqualified tools and fail closed on unsupported platforms.
Web fetch now checks DNS answers, connected peers and redirects without weakening
TLS or forwarding credentials across origins. Exact host restrictions and live
registry authorization checks cover the qualified fetch implementation, with
explicit refusal when per-socket mediation is unavailable. Native qualification,
other network tools and custom dispatcher boundaries remain open under #20; see
[restricted access](docs/configuration.md#restricted-tool-access).
Provider usage under [closed #24](https://github.com/mlg151/henchman-ai/issues/24)
preserves reported/unknown provenance and cache
subsets, including Anthropic and compatible trailing usage snapshots. Explicit
prices distinguish estimates from provider billing; unknown costs stay unknown
and zero prices remain valid. A reviewed process-lifetime ledger now implements
atomic reservations, single-dispatch claims and conservative reconciliation;
explicit Python scopes now connect it to compatible/Anthropic transport attempts
and summary calls. Typed limits and exact provider/model prices are available;
durable SQLite claims/reconciliation and session bindings now pass crash and
concurrency tests. Public orchestrator/CLI runs now share scopes through delegates,
summaries and continuations, with trusted goal transitions, durable session
bindings and `/usage`/headless aggregates. Grouped model observations now retain
per-field request coverage and exact configured price provenance, including
unknown-priced attempts, without changing holds. Standalone API process runs now isolate
caller histories and retain budgets through tool-result continuation; durable
API binding fails explicitly. A [local budget probe](docs/evaluations/2026-11-07-local-budget-qualification.md)
retained one failed request and unknown token hold across restart, with both
follow-ups denied before HTTP. A separate [CPU request](docs/evaluations/2026-11-07-cpu-budget-reconciliation.md)
settled 29 reported tokens, released its hold and retained usage through restart;
both follow-ups were denied before HTTP at USD 0 spend. Its usage/budget criteria
are complete; final artifact/native qualification remains under #30 and remaining
UI presentation under #35. See [task accounting](docs/providers.md#automatic-task-accounting).
The release gates below are not yet satisfied.
Current model testing is local-only by user instruction; hosted-provider
qualification remains explicitly unverified.
For #26, a bounded schema meta-validation cache removes repeated compilation
while preserving fresh authorization and verification. The
[profiled fixture](docs/evaluations/2026-11-07-schema-validation-profile.md)
attributes the improvement; a subsequent
[20-pair unprofiled comparison](docs/evaluations/2026-11-08-paired-schema-latency.md)
passes its local regression gate with all 80 observations retained. Wider
workloads and native responsiveness remain unqualified.
A separate [CPU corpus readiness run](docs/evaluations/2026-11-07-cpu-corpus-readiness.md)
passed two protocol probes but timed out before the first coding response; all
twelve corpus cases remained unrun. Its failed evidence and cleanup verification
are retained without changing the earlier cohorts.
A [separate revised readiness diagnostic](docs/evaluations/2026-11-07-cpu-corpus-readiness-v2.md)
passed syntax repair with complete per-request usage and cleanup. The subsequent
[twelve-case CPU corpus](docs/evaluations/2026-11-07-cpu-corpus.md) retained eight
oracle passes, three timeouts and one tool-round-limit failure. Its 12/12 target
was not met; partial usage and a late receipt-finalization discrepancy are
retained explicitly. Model and target-hardware qualification remain outstanding.
MCP/schema P0/P1 compatibility evidence and remaining #25 qualification gates are
recorded above and in the [compatibility foundation](docs/standards.md#implemented-compatibility-foundation-v042-work).
Automatic compaction now respects the configured disable flag across primary,
specialist, dynamic child and API agents while retaining explicit hard-capacity
checks. Remaining Textual presentation consumers belong to #33/#35.
REPL/Textual now retain a shared live settings snapshot with accurate session
origins for config/doctor inspection, provider switching and resume. Explicit file
scopes remain independent, and theme/context shortcuts persist only named keys.
Read-confirmation policy now reaches primary/scoped registries; unsupported
Docker sandbox requests fail explicitly. File transfer now supports explicit
opt-in usage, operation persistence and verification controls; credential-bearing
operational values are refused without changing their meaning or live authority.
Remaining Textual presentation consumers stay under #33/#35; final artifact
qualification stays under #30. File transfer remains limited to the documented
UI and explicit usage/operations/verification groups.
See [control transfer](docs/configuration.md#local-importexport-sync).

- [ ] Establish the actual Python/native-package baseline and independent coding-task evaluations.
- [ ] Deliver shared controls, scoped repository instructions/context, fresh verification, controlled planning, review and recovery.
- [ ] Validate privacy boundaries, shared usage budgets, responsiveness and bounded delegation.
- [ ] Deliver the scoped MCP client work and one Neovim pilot; qualify an optional CPU-local profile.
  Legacy headless JSON framing now preserves long and Unicode payloads regardless
  of console width. The opt-in v1 editor protocol now binds shared one-run
  authority over POSIX pipes, isolates descriptors before CLI imports and joins
  runtime, startup and provider cleanup. Bounded frames, absolute write deadlines
  and correlated decisions retain explicit delivery failures. Windows transport
  is unsupported. The [Neovim 0.12.6/Linux pilot](docs/neovim.md) now exports an
  opt-in client with saved-file selection, explicit new/resume, correlated
  decisions, cancellation and read-only operation-backed checkpoint review.
  Its installed-wheel gate passed 132 tests, including 56 actual editor cases;
  independent review also passed 48 adversarial probes. These scripted checks do
  not establish live model quality, human accessibility or broader editor/platform
  support. MCP, CPU-model and final release qualification in this combined item
  remain separate; see [editor stdio](docs/api.md#editor-stdio-protocol-v1).
- [ ] Deliver UI-0–UI-4: interaction baselines, reliable terminal controls, work visibility, workspace navigation and native/accessibility qualification.
- [ ] Verify integrated outcomes and the exact release artifacts before publication.
  The release workflow now requires installed wheel/source-archive checks and
  matching qualification receipts before upload and tagging. Final release
  evidence remains outstanding; see the [release process](CONTRIBUTING.md#-release-process).

Keep the foundations-first tier ordering below. Existing v0.4.1 issues retain
their history; cloud settings sync, inbound servers, A2A, broad IDE support and
unvalidated bundled model weights are outside this release plan.

## Supported recovery baseline

- [x] Python 3.11–3.14 is the supported CI/runtime range.
- [x] RAG installs require `chromadb>=1.5.9`; PageRank knowledge-graph queries have a direct `scipy>=1.11.2` dependency.
- [x] Non-Git context discovery stops at the current working directory and does not scan parent or child directories.
- [x] CI tests the supported Python matrix, builds the wheel, and smoke-installs it on Python 3.11 and 3.14 with CLI-entry-point and ephemeral-Chroma checks.
- [x] Help, doctor, and tool discovery classifications derive from `src/henchman/cli/commands/discovery_capabilities.py` and live registration where applicable.

## Coding-agent reliability and portability

Priority: a reliable coding loop and provider portability, with OpenRouter as a
primary integration while preserving independent provider adapters.

- [x] Offline stream-safety coverage for OpenRouter, generic compatible endpoints, DeepSeek, Ollama, and native Anthropic: object-only tool arguments, explicit error reporting, final text preservation, and safe handling of truncated calls.
- [x] Preserve compatible `reasoning`/`reasoning_content` text through streamed tool turns and the next request, with SDK-shaped regressions across four compatible adapters. This does not prove a latency improvement.
- [ ] Preserve structured or encrypted reasoning blocks required by routed models through tool turns, context accounting and session persistence.
- [x] Consolidate provider construction so explicit selection and saved settings are honored at startup, during model switching, and by API/chat and specialist agents; preserve conversation state and model-only overrides when switching.
- [ ] Verify complete edit/test/recover workflows across providers, including cancellation and session resume.
- [x] Verify provider/core stream closure and interruption behavior offline, and bounded headless completion/error handling with correlated tool results.
- [x] Verify interactive multi-round save/resume, cancellation, and preservation of full evidence across context compaction using offline runtime tests.
- [x] Preserve runtime failures through completion reporting, specialist handoffs, ledgers, and terminal rendering; isolate agent evidence and reject missing or unknown delegation outcomes. Final-message report fields and explicit no-blocker values preserve actual action evidence. Task correctness remains separate from execution status.
- [ ] Verify installation and coding tools on Linux, macOS, and Windows in CI.
- [x] Add an installed-wheel OS matrix and regressions for Unix-only startup imports, native locks, process checks, Windows upgrade paths, and Python output encoding; hosted OS results remain unverified.
- [x] Run the five-adapter real-tool coding workflow from fresh installed wheels outside the checkout on Linux, macOS and Windows, each on Python 3.11–3.14; model responses are scripted. Foundation candidate `55fd66b` passed all cohorts; live-model and final-artifact qualification remain separate gates.
- [x] Stream serial team events without accumulating whole tool batches, preserving consumer backpressure, interruption cleanup, and per-agent evidence. Full application memory and event-array output remain separate concerns.
- [ ] Establish reproducible coding-task evaluations with success, regression, latency, and cost measurements before claiming industry-leading performance.

### Python development and team leadership

- [x] Default to a primary coding agent with the full live tool suite; preserve explicit user scopes and named-role compatibility. Add custom background conversations, asynchronous messaging, lifecycle status, reactive parent notifications, and cancellation/join on CLI exit and history/session changes. See [dynamic subagents](docs/agents.md#dynamic-background-subagents).
- [ ] Measure live-model dynamic delegation effectiveness, provider concurrency behavior, and whole-process memory under representative workloads; offline lifecycle checks do not establish these results.

- [x] Construct one cached leader through the shared provider/model/prompt configuration path, accept partial builtin-role overrides, and preserve identity, history and scope through normal/direct execution and model/context changes. SDK-scripted request coverage does not establish live model competence.
- [x] Share one default workspace-policy fragment across roles and make supporting artifacts proportional to requested or durable work, preserving explicit project rules and artifact placement. One bounded live Explorer handoff completed without artifact writes; full-team outcomes and latency remain separate evidence.
- [x] Share default planning and handoff fragments, align base/Planner rules with proportional reports and durable tracking, and preserve evidence and review requirements. Full task outcomes and efficiency require live measurement.
- [x] Align shared default guidance around coherent edits, final-state checks, sufficient returned evidence and timely handoffs, preserving explicit requirements and independent review. This is prompt guidance, not runtime enforcement or demonstrated model compliance; paired live evaluation remains outstanding. See [team execution guidance](docs/agents.md#headless-team-execution).
- [x] Disclose current specialist call and round limits at execution and share verification guidance that respects explicit tools, including structured test/lint tools. Limit disclosure and prompt guidance do not prove task completion or improved efficiency.
- [x] Preserve the complete original mission in specialist context, including requirements beyond 500 characters, while bounding the status-board preview and retaining request-capacity checks. Explicit subtask criteria remain scoped; live coordination quality is still under evaluation.
- [x] Isolate cached-agent diagnostic errors per execution while preserving current continuation failures and immutable prior handoffs. Broader live recovery and review coordination remain under evaluation.
- [x] Expose explicit team tool lookup through existing discovery, preserving live role scopes, provider laziness and independent schema priorities. Five-adapter scripted checks route named verification to a specialist and retain observed failures; live team effectiveness remains under evaluation.

- [x] Honor leader and specialist tool allowlists through live scoped lookup, including allowed late MCP registration, removals/replacements, discovery isolation and fallback execution. Five-adapter scripted denial/delegation/verification coverage is available; live team effectiveness remains open.

- [x] Fit tool schemas through bounded discovery when a full catalog exceeds context; preserve full inventory, per-agent scope, explicit output caps and requested schemas. Offline five-adapter edit/test recovery is covered at 8K; live model effectiveness remains open.

- [x] Carry raw context capacity into per-request estimates for messages, tools and output reservations; preserve current-turn evidence, prune older complete turns and reject oversized required input locally. Provider tokenizers and server templates still require live validation.

- [x] Allow a positive session context length on model switches, apply the configured compaction threshold to live/cached/future agents, preserve history and model overrides, and display configured/effective limits.

The agent targets Python developers: organized, idiomatic code; removal of code
smells; reuse of existing functionality; strong DevOps workflows; and coordination
of a whole development team. Existing tools, specialist presets, and prompt rules
are starting points. Their presence alone does not prove these outcomes.

- [ ] Verify a repository-first workflow that finds existing implementations and tests before adding functionality, with evidence carried into implementation and review.
- [x] Add a live Python reuse evaluation with unchanged-fixture checks, observed inspection/edit/test actions, and an independent behavioral check that rejects copied helper implementations. Model success remains an evaluation requirement.
- [x] Harden existing counter, class-extension, rename and multi-file eval criteria with independent behavioral checks and offline false-pass regressions; require successful runtime completion for every decorated scenario. These small scenarios do not establish full task or team effectiveness.
- [x] Add an opt-in engineer evaluation profile that reuses production prompt/preset/tool filtering and exposes profile metadata; preserve the basic baseline and independent oracles. Model verification choices and full-team effectiveness still require live evidence.
- [x] Support shell redirects, default background shell/Python execution with multiple tracked tasks, responsive interactive input, and persistent `/goal` continuation with explicit completion/pause controls. See [execution and goals](docs/tools.md#background-execution).
- [x] Repair default shell validation of quoted Python verification snippets without changing execution approval or whole-command restrictions; retain real subprocess regressions. Rejected literal/escaped newlines include scope-aware recovery guidance, with execution restrictions unchanged.
- [x] Tighten file-edit targeting and recovery: reject partial/mixed line modes, guide unique-context retries, and expose optional absolute numbered reads. Line-range edits still require review and behavioral verification.
- [x] Provide runtime-discoverable Python structure plus bounded syntax-clone, long-method, and deep-nesting candidates through `python_ast`, with file/qualified-symbol locations and explicit coverage/limitations. Semantic duplication and broader code-quality outcomes remain open.
- [ ] Verify that implementation and refactoring preserve behavior and pass the project's formatting, lint, type, and test gates; report unavailable or failed checks truthfully.
- [x] Automatically apply Black after authorized Python edits and observed command mutations, before tool results/verification; preserve untouched files, project configuration, explicit failures and execution policy. Manual formatting shares the backend. End-to-end live task quality remains separate.
- [x] Isolate `python_exec` formatting to its in-memory snippet with a short deadline and warning-only fallback; execute in large workspaces without source tracking in either mode. Generated files require explicit formatting. See [snippet execution](docs/tools.md#python_exec).
- [x] Classify lint-fix invocations as writes for authorization, Plan Mode and automatic Black formatting, including explicit file/directory targets outside the working directory; keep check-only lint read-only.
- [ ] Verify Python DevOps workflows from environment/package management through CI, build artifacts, and release preparation, with safe execution and explicit deployment boundaries.
- [x] Add an offline package artifact evaluation with protected src-layout fixtures, pinned local dependency, independent rebuild/submitted-wheel installation, installed reuse/resource/CLI checks and ordered returned review evidence. Scripted providers validate the evaluator; agent-performed installation/testing, live DevOps competence and hosted CI remain unverified. See [package evaluation](evals/README.md#offline-package-lifecycle-evaluation).
- [ ] Verify team leadership across discovery, planning, ownership, dependent/parallel implementation, review, integration, and recovery from failed or blocked specialists.
- [x] Wire headless JSON to the existing team orchestrator with direct-role routing, agent-attributed events, bounded rounds, current tool policies, and authoritative outer completion. Scripted provider tests exercise research, implementation, test recovery, reuse, review, and acceptance checks; live-model team effectiveness remains open.
- [x] Connect actual user-input handlers in the REPL/TUI and verify question/answer, cancellation, timeout, and headless-unavailable behavior with local runtime tests; native Windows/macOS UI verification remains open.
- [x] Distinguish response delivery from action evidence with `responded`, explicit response/actions requirements, and unverified-task metadata. Normal conversations no longer receive no-action errors; delegated work still defaults to actions.
- [x] Add immutable typed acceptance checks to `verify_plan_execution`, with bounded file/argv/pytest execution, captured change baselines, and persisted historical observations separate from reported step progress. These assertions do not certify whole-task correctness or user-approved criteria.
- [ ] Evaluate task correctness and requirements coverage independently of response delivery, successful tool counts, specialist claims, and the adequacy of model-selected acceptance checks.
- [ ] Evaluate complete Python tasks for correctness, regressions, maintainability, reuse, coordination quality, latency, and cost across providers, with OpenRouter as a primary integration.
- [x] Add an explicit production-team evaluation path with attributed tool ordering, bounded role execution, copied settings and durable reports; independently check a small Python reuse/CLI task with fixed lint, format and type gates. Scripted contracts validate the evaluator; cross-provider live outcomes and comparative performance remain open.
- [x] Align default team-evaluation workspace context with CLI startup and capture authoritative final tool outcomes across basic, engineer and team profiles, including formatting failures, policy denials and unexecuted calls. Model coordination and comparative effectiveness remain separate evidence.

### Included local default model

Target baseline: a 16 GB RAM laptop with CPU operation and optional GPU
acceleration. The included model must provide useful offline Python assistance
alongside the existing OpenRouter and independent provider integrations.

- [x] Apply configured conversation limits and compaction thresholds to the leader and specialists, preserving explicit budgets across provider switches. This does not establish model-window fit or whole-application memory bounds.
- [ ] Evaluate small quantized models on real Python tasks, including structured tool calls, reuse discovery, edits, and recovery from failed tests.
- [ ] Measure total memory use, prompt and generation latency, and useful context size while leaving room for the OS, editor, and development tools.
- [ ] Select redistributable model weights and a portable runtime with pinned artifacts and verified integrity; make acquisition, startup, readiness, shutdown, and failures part of the supported product flow.
- [ ] Verify the included experience on Linux, macOS, and Windows without requiring a GPU or a paid provider; validate optional GPU acceleration separately and keep model limitations and optional remote routing explicit.

---

## Tier 1: Core Developer Experience

Completed: `init`, `config`, `help`, `version`, `doctor`, and `upgrade`; canonical `.henchman/` settings with local import/export, output style/theme/keybinding wiring, and Tier 1 tool discovery for `tool_search`, `skill`, `sleep`, and `web_search`.

### CLI Commands
- [x] `init` — interactive project setup wizard
- [x] `config` — view/edit configuration from CLI
- [x] `help` — enhanced help system with search
- [x] `version` — version info with update check
- [x] `doctor` — diagnostic tool that checks environment, deps, config
- [x] `upgrade` — self-update mechanism

### Settings & Configuration
- [x] `.henchman` directory for project-local settings (like `.claude/`)
- [x] Local settings import/export across machines
- [x] Output style system (compact, verbose, json, etc.)
- [x] Keybindings configuration
- [x] Theme system

### Tools
- [x] `ToolSearchTool` — search available tools by name/description
- [x] `SkillTool` — local skill discovery and metadata inspection surface
- [x] `WebSearchTool` — web search capability when registered in the live runtime
- [x] `SleepTool` — pause execution for N seconds

---

## Tier 2: Session & Context Management

### CLI Commands
- [x] `session` — list, switch, delete sessions
- [x] `resume` — resume a previous session by ID
- [x] `compact` — compact session context to save tokens
- [x] `rewind` — undo last N turns in a session
- [x] `context` — view and manage current context
- [x] `memory` — view and manage memories
- [x] `teleport` — jump to a specific point in conversation history

### Services
- [x] Session Memory service — per-session memory store
- [x] Session Transcript service — persistent transcript storage
- [x] Context Collapse service — automatic context summarization
- [x] Extract Memories service — auto-extract memories from conversations
- [x] Token Estimation service — estimate token usage before API calls
- [x] Tool Use Summary service — summarize tool usage across session
- [x] VCR/playback service — record and replay sessions

### Tools
- [x] `EnterPlanModeTool` / `ExitPlanModeTool` — structured planning mode
- [x] `EnterWorktreeTool` / `ExitWorktreeTool` — git worktree isolation

---

## Tier 3: Agents, Skills & Plugins

Status in this variant: local discovery and management are real; remote marketplaces are not. Compatibility note: Tier 3 skills and plugin surfaces should stay interoperable with Claude (`.claude/`), Gemini (`.gemini/`), and GitHub Copilot (`.github/`) workflow conventions wherever practical.

### Agents Platform
- [x] `agents-platform` CLI command — manage local agent definitions
- [x] Agent definition files (YAML/JSON agent specs)
- [ ] Agent marketplace / registry installs — unavailable in this variant
- [x] Local agent versioning and publishing

### Skills System
- [x] Bundled skills directory (`skills/`)
- [x] Skill discovery and loading
- [x] Skill definition format (YAML + handler)
- [x] Skill discovery and inspection from CLI and conversation tooling (local-only metadata surfaces)
- [x] Custom skill support (user-defined skills)

### Plugin System
- [x] `plugin` CLI command — list and remove local plugins with guarded install UX
- [ ] Plugin marketplace install flow — unavailable unless a real registry backend is configured
- [x] Plugin lifecycle management (load, unload, reload)
- [x] Plugin API / SDK
- [x] Plugin sandboxing

---

## Tier 4: Git & PR Integration

Completed: `commit`, `branch`, `review`, `pr_comments`, `commit-push-pr`, `autofix-pr`, `security-review`, and `install-github-app`; plus local GitHub App setup and PR diff caching. GitHub webhook-helper guidance remains docs-only in this variant.

### CLI Commands
- [x] `commit` — AI-assisted commit message generation
- [x] `branch` — branch management (create, list, switch)
- [x] `review` — AI code review of current branch/PR
- [x] `pr_comments` — generate/respond to PR comments
- [x] `commit-push-pr` — single command: commit + push + create PR
- [x] `autofix-pr` — auto-fix issues found in PR review
- [x] `security-review` — security-focused code review
- [x] `install-github-app` — one-time GitHub app installation

### Services
- [x] GitHub App integration service
- [x] PR diff fetching and caching
- [x] GitHub webhook helper guidance (docs-only, non-runtime in this variant)

---

## Tier 5: Team & Collaboration

Completed local surfaces: project-local team workspaces, messaging and file sharing,
workflow definitions/previews, team memory sync and notification records. Trigger
and bridge records are local metadata; workflow command execution is unavailable.

### Tools
- [x] `TeamCreateTool` — create a team workspace
- [x] `TeamDeleteTool` — delete a team workspace
- [x] `SendMessageTool` — send message to team channel
- [x] `SendUserFileTool` — share file with team member
- [x] `WorkflowTool` — define workflows and prepare step previews; run/trigger report execution unavailable
- [ ] Execute team workflow commands with bounded, portable execution and verified outcomes.

### Services
- [x] Team Memory Sync service
- [x] Local push-notification records
- [x] Local trigger records and workflow previews; command execution remains unavailable
- [x] Bridge records for remote session metadata

---

## Tier 6: Advanced Tooling

Completed: background task management tools, generic stdio `lsp`, project-local MCP auth and server management, experimentation `repl`, `schedule_cron` metadata management (no background runner), step-by-step `verify_plan_execution`, Tungsten immutable workspace snapshots/diffs, and auxiliary AutoDream/MagicDocs/Tips/Prompt Suggestion services.

### Tools
- [x] `TaskCreateTool` / `TaskGetTool` / `TaskListTool` / `TaskOutputTool` / `TaskStopTool` / `TaskUpdateTool` — enhanced task management
- [x] `LSPTool` — Language Server Protocol integration
- [x] `McpAuthTool` — MCP authentication flow
- [x] `MCPTool` — advanced MCP server management
- [x] `REPLTool` — interactive REPL for experimentation
- [x] `ScheduleCronTool` — manage recurring schedule metadata
- [x] `VerifyPlanExecutionTool` — verify plan execution step by step
- [x] `TungstenTool` — immutable workspace snapshots and deterministic diffs

### Services
- [x] LSP service — generic stdio Language Server Protocol support
- [x] MCP service — project-local configuration, auth/status reporting, and registered-tool discovery
- [x] AutoDream service — automatic dreaming/ideation
- [x] MagicDocs service — auto-documentation generation
- [x] Tips service — contextual tips and suggestions
- [x] Prompt Suggestion service — suggest next prompts

---

## Tier 7: Integrations

Completed: `ide`, `desktop`, `mobile`, `chrome`, and `voice`; bundled export-only blueprints for VS Code, JetBrains, Electron, React Native, Chrome, and Slack; plus enhanced Discord channel/mention controls and configurable voice I/O commands.

### IDE
- [x] `ide` CLI command — list/export IDE integration scaffolds
- [x] VS Code export blueprint
- [x] IntelliJ/JetBrains export blueprint

### Desktop & Mobile
- [x] `desktop` CLI command — list/export desktop integration scaffolds
- [x] Electron desktop export blueprint
- [x] `mobile` CLI command — list/export mobile integration scaffolds
- [x] Mobile app export blueprint (React Native or native)

### Browser
- [x] `chrome` CLI command — list/export Chrome integration scaffolds
- [x] Chrome extension export blueprint for web context capture

### Communication
- [x] Slack export blueprint (local scaffold only; no shipped runtime backend)
- [x] Enhanced Discord bot features
- [x] Voice input/output (`voice` command)

---

## Tier 8: Infrastructure & Operations

Status in this variant: do not treat Tier 8 as a shipped remote platform. Foundations may exist in code, but the full backend and operations surfaces below are not claimed as production-ready here.

### API & Remote
- [ ] Full-featured API service (beyond current basic FastAPI)
- [ ] WebSocket session support
- [ ] Remote session management
- [ ] Upstream proxy support
- [ ] OAuth service

### State & Storage
- [ ] AppState store with selectors (like claude-code's store)
- [ ] Schema/model migration system
- [ ] Settings sync backend

### Observability
- [ ] Analytics service
- [ ] Telemetry collection
- [ ] Cost tracking / billing integration
- [ ] Rate limiting / policy limits
- [ ] Diagnostic tracking

### Build & Packaging
- [ ] Auto-updater mechanism
- [ ] Native module bindings (color-diff, file-index, etc.)
- [ ] Feature-flagged builds

### Quality
- [ ] VCR testing infrastructure
- [ ] VCR cassette support
- [x] Contract testing
- [ ] Enhanced integration test suites

---

## Tier 9: Documentation

Completed: `HENCHMAN.md`, expanded `AGENTS.md`, `TODOS.md`, and an expanded docs directory with API reference, tutorials, and guides.

- [x] `CLAUDE.md` equivalent — architecture overview
- [x] `AGENTS.md` equivalent — agent development guide
- [x] `TODOS.md` — living TODO list
- [x] Expanded docs directory (API reference, tutorials, guides)

---

## Tier 10: UI (Textual Enhancements)

Status in this variant: Tier 10 Textual workspace enhancements are implemented for the TUI, while generic discovery/help wording still treats the dialogs as runtime-undiscoverable unless a first-class surface exposes them.

Completed: workspace tab with agent/memory/task/skill/team/settings/context surfaces, status/progress affordances, permission prompts, and dialogs for search, history, theme, model, auto-mode, export, feedback, MCP, bridge, and onboarding. The prompt-toolkit REPL keeps chat metadata in its bottom toolbar and uses a transient thinking indicator for active turns.

- [x] Agent summary panel
- [x] Auto-mode opt-in dialog
- [x] Bridge dialog
- [x] Context visualization
- [x] Dev bar
- [x] Export dialog
- [x] Feedback survey
- [x] Global search dialog
- [x] History search dialog
- [x] MCP server dialogs
- [x] Memory indicators
- [x] Model picker
- [x] Onboarding flow
- [x] Permissions dialogs
- [x] Settings panels
- [x] Skill components
- [x] Task list widget
- [x] Team components
- [x] Theme picker

### UI quality research and follow-through

The [terminal UI research](docs/terminal-ui-research.md) compares firsthand
coding-agent feedback and Python terminal applications. Existing components
remain implemented; all five interaction-quality phases below are native subtasks
of the v0.4.2 epic. The first [UI-0.1 contract](docs/ui-interaction-contract.md)
now records rendered baselines and a deterministic harness. Textual follow/hold,
new-activity navigation and composer submission/cancellation have rendered
regressions; native/assistive-technology/performance evidence and the remaining
controls stay open. Release issue #30 is blocked by the full phase criteria.

- [x] Research coding-agent UI preferences/friction and Python application exemplars, with source dates, surface distinctions and historical-fix caveats.
- [ ] [UI-0 / #32](https://github.com/mlg151/henchman-ai/issues/32): Establish reproducible interaction baselines, keyboard/state contracts and native terminal evidence.
- [ ] [UI-1 / #33](https://github.com/mlg151/henchman-ai/issues/33): Preserve reading position, copy/export, drafts, configurable mouse capture/scrolling and predictable input/cancellation; validate quiet accessible output.
  `ui.mouse_capture` now controls Textual driver startup with keyboard history/live
  fallback and preserved drafts. `ui.reduced_motion` now suppresses transitions,
  loading animation and focused editor cursor blinking while retaining essential
  activity. `ui.detail_density` now controls transcript spacing and initial
  tool-row expansion while retaining manual choices. REPL and Textual `ui.output_mode`
  support plain/quiet transcripts with visible decisions, answers and failures;
  quiet Textual keeps tool cards inspectable. Other optional consumers
  and native qualification remain open; see
  [UI settings](docs/configuration.md#settings-file).
- [ ] [UI-2 / #34](https://github.com/mlg151/henchman-ai/issues/34): Improve existing tool summaries, blocked/error visibility, queued-input controls and changes/diff/verification navigation.
  Compact correlated tool rows and bounded keyboard evidence inspection are
  implemented, alongside owned lifecycle status and F4 navigation to pending
  questions/approvals. F9 now inspects, edits, removes, reorders and explicitly
  sends saved input through revision-bound shared workflow controls. Native
  qualification and other controls remain open. See the
  [queue contract](docs/ui-interaction-contract.md#saved-input-queue).
- [ ] [UI-3 / #35](https://github.com/mlg151/henchman-ai/issues/35): Validate session/task/context navigation, runtime-aware discovery and optional layouts across terminal widths.
  The Context tab now provides bounded read-only context, retention and usage
  inspection with explicit Refresh, current credential projection and preserved
  drafts/focus. Session/task navigation and native qualification remain open;
  see the [inspection contract](docs/ui-interaction-contract.md#context-and-usage-inspection).
- [ ] [UI-4 / #36](https://github.com/mlg151/henchman-ai/issues/36): Qualify visual consistency, onboarding, long-session performance and native accessibility/platform behavior with representative users.

See the [phase exit criteria](docs/terminal-ui-research.md#phased-implementation-roadmap)
and [verification plan](docs/terminal-ui-research.md#verification-and-user-research-plan).
Foundations-first sequencing and current authorization boundaries still apply.

---

## Standards adoption research and roadmap

The [standards adoption RFC](docs/standards.md) is the canonical research for
[issue #3](https://github.com/mlg151/henchman-ai/issues/3). Research completion
does not mean these protocols or schema guarantees have been adopted.

- [x] Record sourced protocol/version research, baseline interface gaps, and phased acceptance criteria for MCP, A2A, OpenTelemetry/evaluation, and tool schemas.
- [ ] P0: Establish tested protocol/SDK compatibility and dependency bounds.
- [ ] P1: Validate canonical schemas and preserve MCP client data fidelity.
- [ ] P2: Migrate modern MCP transport, authentication, resources, and prompts.
- [ ] P3: Add opt-in telemetry and versioned local evaluation artifacts.
- [ ] P4: Pilot outbound A2A with independently verified interoperability.
- [ ] P5: Add controlled inbound serving after the client boundaries are verified.

See the [RFC implementation roadmap](docs/standards.md#phased-implementation-roadmap)
for each phase's scope and exit criteria. Foundations-first ordering and existing
runtime authorization remain prerequisites.

## Implementation Notes

1. **Dependencies between tiers:** Tier 1 should be done first as it improves the dev experience for implementing later tiers. Tier 2 (session/context) is foundational for Tier 3 (agents/skills).

2. **Python vs rewrite:** Some features (LSP, native modules, desktop/mobile apps) may warrant different technology choices. Consider Rust bindings for performance-critical paths.

3. **Existing equivalents:** Some features may partially exist already — audit before implementing:
   - API server mode exists but may need expansion
   - Discord bot exists but may need enhancement
   - Basic MCP support exists
   - Memory system partially exists

4. **Priority re-ordering:** This list should be revisited based on user feedback and usage patterns.
