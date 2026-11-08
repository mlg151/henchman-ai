# TODOS.md

Living roadmap snapshot for Henchman-AI. `FEATURE_TODO.md` remains the tier-by-tier source of truth; this file is the quick view of shipped foundations versus narrowed or still-unshipped surfaces.

## Recovery baseline

- Context token estimates and RAG chunking use packaged verified vocabularies;
  fresh offline installs no longer depend on a warm tokenizer download cache.
  Native smoke runs isolate settings, interpreter lookup and cold token caches.

- MCP client/wrapper fidelity now includes bounded paginated catalogs, local
  input/output validation and typed results. Explicit refresh updates owned
  registry entries and invalidates stale handles without widening agent scopes.
  Provider text projections, events, chat and session retention preserve typed
  evidence with explicit binary/omission limits. Modern transport and final
  contract qualification remain #21/#25 work; see
  [compatibility limits](docs/mcp.md#refresh-a-connected-catalog).
  Registry-wide schema compilation and output validation now cover local tools
  and extensions, including approval-time schema changes and completed failures.
  SDK 2.3.0 adds bounded modern/legacy stdio and rejects implicit replay or active
  telemetry. Bounded unauthenticated Streamable HTTP supports JSON/SSE across four
  revisions; OAuth/context retrieval and final native qualification remain open.

- [Operation recovery](docs/operation-recovery.md) now binds durable dispatch
  authority to saved requests/results and exposes `/recovery` user decisions.
  Primary turns resumed by background notifications now retain ordered correlation
  across child questions, parent replies and durable reload.
  Process mode remains the default. Versioned opaque continuation profiles are
  implemented; native/live acceptance, goal/queue persistence and background
  task restart authority remain open under #23.
  Saved running task records are now reported as outcome-unknown without invented
  exit evidence; inspecting history does not establish child-process ownership.

- [Content checkpoints](docs/checkpoints.md) now provide a tested standalone
  POSIX capture/review/restore service with private retention and crash recovery.
  CLI and interactive `/checkpoint` share review/preview/apply/recovery/retention.
  Restore invalidates plan checks and supersedes in-flight observations.
  The Windows NTFS backend exposes a private-ACL content-only policy and awaits
  native qualification. Runtime capture covers declared write/edit/patch/test
  targets; unknown scopes are unavailable. Dedicated review navigation remains
  open under #22; legacy metadata snapshots are explicitly non-restorable.

- Declared runtime support: Python 3.11–3.14. The expanded CI matrix is configured; successful native execution is still required for release readiness. Python 3.12 enforces the 90% whole-project coverage floor.
- Packaging dependency floors: `chromadb>=1.5.9` for RAG and direct `scipy>=1.11.2` for NetworkX PageRank queries.
- Context safety: outside Git, project instruction discovery is bounded to the current working directory.
- Install verification: CI passes its validated wheel to Linux, macOS and Windows smoke jobs on Python 3.11–3.14, checking both CLI entry points, local RAG and scripted coding workflows outside the source checkout. See issue #12 for actual execution evidence.

## Completed tiers

“Completed” in this snapshot refers only to the listed local or runtime surface; it does not broaden the narrowed capabilities below.

- Tier 1 - Core Developer Experience, including `web_search` when it is registered in the live runtime
- Tier 2 - Session & Context Management
- Tier 4 - Git & PR helpers, with GitHub webhook-helper kept docs-only in this variant
- Tier 5 - Local team collaboration helpers; workflow definitions/previews and trigger/bridge records do not execute commands
- Tier 6 - Advanced tooling, including MCP when both runtime tools are registered and metadata-only `schedule_cron`
- Tier 7 - Integration exports and local setup scaffolds (export-only where noted)
- Tier 9 - Documentation
- Tier 10 - Textual workspace UI plus prompt-toolkit REPL chat status, including workspace panels, transient turn feedback, context/status affordances, permission prompts, and search/theme/model/export/onboarding dialogs

## Narrowed runtime scope

- `ask_user` is connected to real REPL/Textual input with serialized prompts, timeout/cancellation cleanup, and actual-answer tool results. Headless remains unbound and fails explicitly. Native Windows/macOS UI behavior still needs verification.
- Tier 3 - Skills are local-only discovery/inspection surfaces; agent and plugin marketplace installs remain unavailable in this variant.
- Tier 7 - Slack remains an export-only scaffold, not a shipped runtime integration.
- Tier 8 - Remote infrastructure and operations backends are not claimed as shipped in this variant.

### Tier 10: UI (Textual Enhancements)

- Textual dialogs are implemented in the TUI, but generic help/discovery surfaces still classify them as undiscoverable in this variant.
- [Terminal UI research](docs/terminal-ui-research.md) records coding-agent likes/dislikes and Python application examples. UI-0–UI-4 in [Tier 10](FEATURE_TODO.md#ui-quality-research-and-follow-through) are planned v0.4.2 subtasks #32–#36: establish the baseline, fix interaction reliability, improve work visibility/navigation, then qualify polish and native usability. They are native children of epic #11 and prerequisites for release #30; existing widgets do not establish usability. The first [UI-0.1 contract](docs/ui-interaction-contract.md) now records rendered baselines, follow/hold navigation and composer-key regressions. Native, assistive-technology and performance qualification remains open.

## Current focus

- #22/#23 now have Textual F8 checkpoint review and versioned background-task
  intent with conditional concurrent updates. Apply waits for idle local work;
  recovered task evidence cannot control a process or trigger replay. Native
  qualification and trusted task disposition remain open. Both interactive
  frontends now use shared goal/queue authority, with revision-checked controls,
  held restores and current evidence for user-bound goal checks.
  See [checkpoints](docs/checkpoints.md#textual-review) and
  [background tasks](docs/tools.md#background-execution).

- #16 plan checks now bind observations to explicit input contents and requirement
  tags. Read-only current status detects manual edits and separates historical
  pass, stale, unverified and incomplete checks. Explicit project checks now bind
  required assertions to new plans and revoke evidence after configuration changes.
  A library repair coordinator now retains bounded observations under explicit
  edit/criterion scope. Explicit `repair_direct` now binds checks and model attempts
  to one public run, budget and operation journal with a foreground file-tool lease.
  Interactive controls and live evaluation remain open. See
  [bounded repair](docs/tools.md#bounded-repair-library).

- #21/#25 transport/schema foundations now include explicit resource/template/
  prompt previews, with bounded retrieval and no history/instruction changes.
  Explicit idle-only attachment now preserves reviewed context as user data with
  process-local single-use handles and retained source evidence. OAuth now has
  typed configuration, guarded discovery, separate generation-bound storage and
  owned callback/token flows and guarded manager APIs with teardown invalidation.
  Explicit Python clients now support authenticated HTTP with pinned pre-header
  guards and unusable-transport handling after uncertain cleanup.
  Discovery and token exchange share the guard after connection setup, with
  conservative claim settlement and no implicit replay after uncertain dispatch.
  An owned browser helper now provides bounded, guarded desktop handoff; synthetic
  launcher tests do not qualify a real browser or authorization service.
  Configured OAuth connections remain refused
  pending interactive login and normal manager activation.
  Remaining qualification gates are
  recorded in the recovery baseline above and the
  [compatibility foundation](docs/standards.md#implemented-compatibility-foundation-v042-work).

- #20 config mutation responses and JSON/YAML sync exports now redact credential
  echoes, including shadowed/configured keys and freeform UI fields. Actual
  persisted/runtime values stay unchanged; sync redaction is explicitly lossy.
  Background task logs now redact before persistence, cap output and migrate
  eligible indexed legacy logs privately; corrupt/unsupported evidence stays
  intact with diagnostics. See [background execution](docs/tools.md#background-execution).
  Verification reports now share that policy; sensitive saved checks cannot be
  replayed and read-only inspection remains separate from locked sanitation.
  See [plan checks](docs/tools.md#plan-acceptance-checks).
  Metric SQLite writes, legacy reads, exports and exporter diagnostics now project
  known credentials and marked metadata while retaining numeric/identity semantics.
  Existing database bytes remain unchanged during inspection; broader #20
  qualification remains open.

- #20 authorization now rechecks policy, registration, project and physical
  targets after approval, formatter waits and retry delays. This closes stale
  grant reuse. Typed restricted roots now mediate builtin file reads/writes on
  supported platforms; any restriction denies all other, unqualified tools.
  Web fetch validates DNS/peers/redirects with verified TLS and origin-scoped
  credentials. Exact host restrictions and live registry checks now mediate the
  qualified builtin on capable aiohttp versions; unsupported transports refuse
  before DNS. Other network tools, native qualification and custom-dispatch checks remain open. See
  [restricted tool access](docs/configuration.md#restricted-tool-access).

- #14 configuration persistence now retains explicit default-valued overrides
  through set/import and subsequent edits; only unset removes them. REPL/Textual
  now retain live values and session origins for `/config view|get`, `/doctor`,
  provider/context switching and resume. Theme/context persistence changes named
  keys only. Read-confirmation controls now reach primary/scoped registries, and
  unsupported Docker sandbox requests fail at setup. Automatic compaction controls
  now reach primary, specialist, dynamic child and API agents while retaining
  explicit hard-capacity checks. Remaining context/UI consumers and
  expanded nonsecret transfer remain open; see
  [effective settings](docs/configuration.md#inspecting-effective-settings).

- #24 provider usage and explicit pricing: compatible and Anthropic adapters
  preserve cumulative request counts, cache subsets and availability provenance.
  Compatible requests ask for usage by default with an explicit opt-out for
  unsupported servers. Cost records distinguish configured estimates from
  reported billing, preserve zero rates and leave unknown costs unset. A standalone
  process-lifetime ledger now supplies atomic reservation/claim/reconciliation with
  exact money arithmetic and conservative uncertain holds. Explicit Python scopes
  account compatible/Anthropic attempts and summaries using typed usage limits and
  provider/model prices. A SQLite adapter now persists claims, cumulative
  reconciliation and authoritative session bindings, with process/crash tests.
  Public orchestrator and CLI turns now bind shared scopes across delegation,
  summaries and continuation, retain interrupted/goal budgets and expose `/usage`
  plus headless aggregates. Model observations now retain partial-count coverage
  and distinct configured price snapshots, including unknown-priced attempts.
  Standalone API requests now use isolated caller-owned
  process runs, preserve tool-follow-up budgets and reject unsupported durable
  mode. Explicit user goal transitions authorize replacement;
  transcript metadata cannot refund consumption. A [local budget probe](docs/evaluations/2026-11-07-local-budget-qualification.md)
  confirms failed-request/unknown-hold retention and pre-HTTP denial after restart.
  A separate [CPU request](docs/evaluations/2026-11-07-cpu-budget-reconciliation.md)
  now qualifies successful final-usage settlement and restart retention for one
  local request at USD 0 spend. Final artifact/native qualification and remaining
  UI presentation stay open; see [task accounting](docs/providers.md#automatic-task-accounting).

- #20 session lookup boundaries: full IDs, prefixes and stale current pointers
  now follow the current project's scope across root commands, REPL/Textual slash
  commands, context/memory access and session-derived exports/branches/templates.
  Existing templates use their embedded session identity. Canary regressions join
  the native installed-wheel cohort. A shared credential policy now sanitizes
  session saves/backups, exports, templates and new playback records; configured
  interactive-provider keys and rotation are registered without mutating live
  execution inputs. Thirty-one redaction regressions join the native wheel cohort,
  including short credentials, marker-containing values and legacy backup-only
  credentials while preserving protocol identities and structured session records.
  Headless JSON output now masks split credentials with separate agent/content
  buffers, sanitizes tool previews and flushes safely on failure/cancellation.
  Execution events and correlation/control fields retain their original meaning.
  REPL/Textual event streams, tool displays and approvals now share the policy;
  Textual command output, direct chat/status/history displays and interactive
  failure diagnostics are also projected before output. Other logs/UI panels,
  metrics/handoffs, config secret references and restricted execution remain
  open. See [session project boundaries](docs/configuration.md#session-project-boundaries)
  and [redaction boundaries](docs/configuration.md#session-evidence-redaction).

- #23 storage foundation: session writes now use atomic replacement, versioned
  integrity checks, a recoverable prior copy and cooperative native locks with
  stale-writer rejection. Legacy sessions migrate on save; recovery warns about
  possibly missing recent changes and never replays actions. Deletion removes both
  copies. Fault, process-termination and concurrent-writer regressions are staged
  in the native installed-wheel cohort; operational goal/queue recovery and
  provider continuation qualification remain open. See [session storage](docs/architecture.md#sessionmanager).

- The reviewed evaluation registry connects twelve independent scenarios to typed metadata and validated dispatch, including syntax repair, semantic bug repair, tool-failure recovery, interruption/recovery, Fibonacci implementation, package lifecycle and test/documentation delivery with wrong-result, early-exit and runtime-failure controls. The interruption/recovery case requires an observed one-round tool limit after completed work and runtime cancellation of pending calls; unrelated first-turn failures remain failed evidence. It then requires a recovery turn in the same workspace, leaves the provided tests untouched, and passes an independent pytest oracle; the rig's `consume_expected_interruption()` records the interrupted turn as evidence without weakening the strict success gate. The test/documentation case executes doctests, preserves the implementation AST and checks candidate tests against five semantic mutants. Independent Python checks isolate bytecode caches so current source determines the result. The bounded repeat-run machinery under [#13](https://github.com/mlg151/henchman-ai/issues/13) is delivered: every run is recorded (success, verification failure, timeout, runtime error), reports publish explicit planned-versus-executed denominators with p50/p95 latency and usage availability, one cooperative deadline covers the complete scenario, expired work cannot become a verified success, iteration caps remain per turn, latency includes setup and cleanup for every outcome, local cohorts carry zero-cost provenance and hosted cohorts never fabricate cost, and reports are redacted and written atomically. Verifier timeouts now carry their budget in the recorded error text, and the success-path regressions name each run's outcome and error, so CI flakes are diagnosable from their failure messages. The [first live local development cohort](docs/evaluations/2026-11-07-local-baseline.md) completed all 22 planned attempts with 22 timeouts and no verified successes; token usage was unavailable and API spend was zero. Its original report is retained, and compatible-provider model identity reporting is corrected for future cohorts. A [CPU follow-up](docs/evaluations/2026-11-07-cpu-readiness.md) records four failed syntax attempts and one independently verified diagnostic; its temporary profile was removed after testing. Broader local qualification and hosted baselines within the zero-spend constraint remain incomplete under #13; the twelve-case corpus is frozen.
- Foundation [#12](https://github.com/mlg151/henchman-ai/issues/12) is complete at `55fd66b`: [all 20 CI jobs passed](https://github.com/mlg151/henchman-ai/actions/runs/41758021286), including all supported Python/native-wheel cohorts. Python 3.12 passed 8,374 tests with 93.12% coverage. Independent evaluation and final-artifact release gates remain open.
- The typed terminal UI controls (`ui.output_mode`, `ui.reduced_motion`, `ui.detail_density`, `ui.keyboard_mode`, `ui.mouse_capture`, `ui.layout.compact_tables`) ship under [#14](https://github.com/mlg151/henchman-ai/issues/14) with field-attributed validation and local import/export sync round-trips, and the shared discovery capability matrix now classifies them as TUI-scoped controls that generic discovery/help surfaces do not advertise as generic commands. Consumer alignment as the UI child features land and final runtime wiring remain open.

- #33 now applies `ui.mouse_capture` at Textual driver startup, retaining keyboard
  history/live navigation and drafts. Setting changes require the next launch;
  native selection, clipboard and remote behavior remain unqualified. Other UI
  settings consumers remain pending or partial as described in
  [configuration](docs/configuration.md).

- #34 now has compact correlated tool rows and bounded keyboard evidence
  inspection, with strict outcomes, visible omissions and credential reprojection.
  Owned lifecycle status now retains cancellation through cleanup and exposes
  F4 navigation to an actual pending question or approval without answering it.
  F9 now provides revision-bound inspect/edit/remove/reorder/Send controls with
  joined cancellation, preserved drafts and no automatic rearming. Native
  qualification remains open; see the [queue contract](docs/ui-interaction-contract.md#saved-input-queue).
- The portable `AGENTS.md` instruction increment is integrated under [#15](https://github.com/mlg151/henchman-ai/issues/15): default discovery keeps `HENCHMAN.md` primary, boundary and alias rejection is enforced before reads, and immutable provenance snapshots feed content-free session records and a bounded delegation appendix (paths/scopes/digests only). Runtime refresh now covers primary/delegated requests, supported input/output paths, parsed patches and formatter descendants. Mutations defer until new guidance reaches the model, with fresh checks after approval and formatter waits. Directory lint fixes require explicit files; shell/Python embedded paths remain cwd-scoped. [Native CI qualification](https://github.com/mlg151/henchman-ai/actions/runs/42386583146) passed all 12 platform/Python wheel combinations; #15 is complete. Final release qualification remains under #30. See [runtime refresh](docs/configuration.md#context-files-henchmanmd-and-agentsmd).
- The plan-mode transition authority increment is delivered under [#18](https://github.com/mlg151/henchman-ai/issues/18): sessions persist `plan_mode_origin` (`user`/`model`, legacy sessions default to `user`), a model-callable `exit_plan_mode` closes only model-proposed planning and cannot lift a user-imposed `/plan` boundary, user/runtime transitions retain the widening right for both states, interactive/headless startup re-applies a resumed session's plan mode to the live registry and agent prompt while preserving its persisted origin, dynamic subagents inherit the active plan-mode boundary in their system prompt, and plan mode now classifies each invocation by effective operation effect (read-only shell/`python_exec` sources are `READ`, trusted MCP server tools stay `NETWORK` so they cannot bypass the boundary, and `mcp`/`mcp_auth` introspection actions are `READ`). The effective policy now resolves through one shared `PolicyDecision` evaluator that `ToolRegistry.evaluate_policy()` exposes and that `authorize()` (and therefore `execute()`, batch execution, and orchestrated delegation) consumes, so late-registered tools and scoped subagent registries cannot bypass the boundary. Approval reuse is now scoped to the granted action/path/session policy: user confirmations are recorded as session-scoped grants keyed to (tool, effective effect, canonical parameter digest, risk), reused for identical still-valid authorizations without re-prompting, invalidated on any changed argument or risk, shared across a registry ancestry but never across separate registries or persisted, and cleared when a different session is activated. Headless confirmation is now explicit: when confirmation is required, no grant is active, and no confirmation handler exists in the registry ancestry, `authorize()` returns an explicit needs-input denial (distinct from a user denial) and records no grant.
- Four #19 increments are delivered under [#19](https://github.com/mlg151/henchman-ai/issues/19): (1) `compact_session` writes a `kind="compaction"` record naming the absolute turn numbers it covers (`source_turns`) and retaining their original messages (`retained_messages`), so compacted turns stay retrievable with valid tool call/result pairs; `SessionContextService.restore_compacted_messages()` reconstructs the full original sequence, legacy records load with documented defaults (`kind="turn"`, empty retention fields), and the session/turn-summary/message contracts cover the retention fields plus the persisted tool-call `id`. (2) Session memory now supports `edit_memory`, `clear_memories` and a persisted extraction opt-out (`set_extraction_opt_out`/`extraction_opt_out` gating `extract_memories`), surfaced as `memory edit`, `memory clear` and `memory extract --opt-out/--no-opt-out`; a `runtime/session_memory_record` contract validates memory payloads and the session contract covers `session_memories` plus the opt-out flag. (3) Workspace memory retention propagation: `TeamMemorySyncService.sync_session` reconciles previously synced records from a session (removing deleted/edited content scoped to the source session) and a new `delete_memory` removes one workspace record; `sync_session` no longer extracts implicitly, so tier-5 tools extract explicitly before syncing and sync respects the persisted opt-out. (4) Export surfaces: `export_as_markdown` renders a `## Session Memories` section and, for compaction records, the covered source turns plus their retained original messages (covering the REPL `/session export` and the Textual UI together). A follow-up hardening pass keeps session memory reads non-mutating, escapes angle brackets in exported memory content and indents multiline memory items, accepts the persisted tool-call `id` on compaction-retained messages in the session contract, and makes verifier timeouts diagnosable in baseline run records. (5) Cross-surface effective-policy parity: `build_snapshot` now carries the persisted memory-extraction opt-out flag and the compacted-turn retention count, the headless `context` command renders both (text and JSON), and the export surfaces report the same shared-service state, so UI and headless surfaces report the same effective policy (a dedicated in-TUI snapshot display stays with the UI workstream). All five #19 scope items are delivered; closure awaits the final CI qualification and the acceptance-criteria evidence pass.
- In-progress `v0.4.2` delivery is tracked by [epic #11](https://github.com/mlg151/henchman-ai/issues/11) and its 24 subtasks in the [v0.4.2 milestone](https://github.com/mlg151/henchman-ai/milestone/2), based on [feature-demand research #10](https://github.com/mlg151/henchman-ai/issues/10) and [terminal UI research #31](https://github.com/mlg151/henchman-ai/issues/31). The dependency-ordered plan covers verified coding, context/control, review/recovery, budgets/privacy, integrations, terminal interaction/navigation/accessibility and release evidence; no completion is implied. Its completed foundation task reconciles Python 3.11–3.14 and native-package support; later features and final artifact qualification remain required.
- Release `0.4.1` integrates snippet formatting, dynamic background subagents, and standards research. Publication after successful main push CI uses the milestone version and repository `PYPI` secret; see [release process](CONTRIBUTING.md#-release-process).
- The default primary now works directly with the full live tool catalog and can create scoped background conversations through `invoke_subagent`, `send_message`, and `manage_subagents`. CLI shutdown and history/session changes join owned work; configured restrictions and approvals remain binding. See [dynamic subagents](docs/agents.md#dynamic-background-subagents). Live-model effectiveness and whole-process memory still require measurement.
- Standards research for [issue #3](https://github.com/mlg151/henchman-ai/issues/3) is documented in the [standards adoption RFC](docs/standards.md), including sourced versions, baseline gaps, and acceptance criteria. The [P0–P5 adoption phases](FEATURE_TODO.md#standards-adoption-research-and-roadmap) remain unchecked implementation work; no new protocol support is claimed.
- An explicit production-team eval now measures attributed inspection, implementation, post-edit tests and specialist review against independent Python reuse/CLI/quality checks. The first bounded MiMo/OpenRouter sample produced passing artifacts but timed out before completing tests and review; investigate coordination and latency before claiming team effectiveness. See [team evaluations](evals/README.md#production-team-evaluation).
- Leader startup now uses the same configured, cached agent as direct execution. Partial builtin-role settings inherit preset metadata; provider/model/prompt overrides and model/context switching have offline coverage. See [team configuration](docs/agents.md#configuration).
- Default workspace policy now returns short discovery findings inline and creates supporting artifacts for explicit requirements or useful durable work. A bounded live Explorer check completed without artifacts; overall team efficiency remains under evaluation. See [workspace conventions](docs/agents.md#agent-workspace-conventions).
- Default planning and handoffs now share canonical fragments, keep related checks with coherent ownership, and scale reports/tracking to requested or durable work. A bounded live run passed the code and required test checks but timed out before review; no latency improvement was established. Required evidence and review coverage remain intact. See [headless teams](docs/agents.md#headless-team-execution).
- Shared defaults now specify final-state verification, conditional reuse of returned check evidence and timely handoffs, preserving explicit requirements and a distinct independent reviewer. Supplied-context advice needs no ceremonial checks unless required. These instructions have no paired live results yet and do not establish runtime enforcement, model compliance or performance gains. See [team execution guidance](docs/agents.md#headless-team-execution).
- Active-agent reservations reject self/ancestor delegation before history changes, and top-level admission protects the current ledger/metrics from concurrent requests. Direct-role UI commands now switch the acting specialist; scripted transport and cancellation checks remain separate from live team competence.
- A live 700K-context team probe exposed false handoff failures for `BLOCKERS: none`; final-message parsing and absence handling now preserve actual action evidence while retaining genuine failures. The sample predates that fix and still timed out during review; a complete live workflow remains unverified.
- Specialists now receive current call/round limits at execution. Default verification guidance accepts available structured tools and honors explicit tool requirements while retaining observed pass/fail evidence; see [headless teams](docs/agents.md#headless-team-execution). Full workflow and efficiency require live evaluation.
- A prior 700K-capacity MiMo team run preserved successful Explorer/Engineer handoffs and passed all independent artifact checks, but substituted shell verification after scope-limited discovery and timed out at 480 seconds. This exposed the team lookup gap below.
- Explicit `tool_search(scope="team", query="<exact tool name>")` now locates enabled roles with a registered scoped tool without starting agents/providers or granting access. Five-adapter scripted checks preserve verification pass/fail evidence. A bounded live MiMo run used lookup, retained the named `pytest_run` requirement and executed all four tests successfully; it still timed out during the reviewer's final response. Full task completion and efficiency remain unverified. See [tool discovery](docs/tools.md#tools).
- Default shell verification accepts balanced quoted Python snippets containing semicolons; a live counter-evaluation failure now has a real subprocess regression. Whole-command restrictions and EXECUTE approval remain in effect.
- Leader and specialist scopes now follow live allowed registrations and replacements. Fallback CLI execution uses the acting scope; scripted cross-provider workflows cover denied leader edits followed by delegated repair.
- Bound tool discovery can reduce schemas to fit context, then expose searched tools on the next request. Five-adapter 8K edit/test recovery and default UI clarification have offline coverage.
- Request budgeting now retains raw capacity, estimates serialized input plus output, and rejects oversized required inputs before a model call. Full history remains available; estimates are not exact server counts.
- `/model set ... --context-length <tokens>` updates session context capacity and live team budgets; omitted limits preserve the current policy. `/model` shows configured and effective limits. See [provider switching](docs/providers.md#provider-selection-and-credentials).
- Behavioral evals can opt into the canonical engineer prompt and available tool scope, with profile metadata and unchanged correctness oracles. See [evaluation profiles](evals/README.md#evaluation-profiles); the default basic harness is not a full production-workflow evaluation.
- File-edit recovery now rejects incomplete targeting, explains unique-context retries and full-range replacement, and supports optional numbered reads. See [file tools](docs/tools.md#edit_file); semantic correctness still requires verification.
- Coding-agent priority: reliable coding loops and provider portability, with OpenRouter emphasis and no provider dependency in the core loop.
- The harness now automatically applies Black to observed Python changes before returning write/execute results. Manual formatting shares the backend; lint, tests, types and review remain required. See [automatic formatting](docs/tools.md#automatic-python-formatting).
- `python_exec` now formats only its input string in an isolated, time-bounded worker. It skips workspace tracking in both execution modes and falls back to original code with warnings; generated files require explicit `code_format`. See [snippet execution](docs/tools.md#python_exec).
- Delegation preserves the full original mission instead of discarding requirements after character 500. Only the ledger preview is shortened; subtask scope and request-capacity checks remain explicit. See [team execution](docs/agents.md#headless-team-execution).
- Cached specialists now isolate diagnostics per execution; lint fixes use write authorization and automatic formatting even for explicit external targets. Check-only lint remains read-only. See [lint checks](docs/tools.md#lint_check) and [team execution](docs/agents.md#headless-team-execution).
- Evaluation profiles now retain final harness tool outcomes, and default team prompts receive the CLI's actual workspace environment snapshot. See [team evaluation](evals/README.md#production-team-evaluation).
- Shell newline rejections now explain the single-line requirement and suggest `python_exec` only when allowed; existing validation and execution restrictions remain unchanged. See [shell execution](docs/tools.md#shell).
- Product focus: Python developers, organized and idiomatic code, code-smell prevention, discovery of reusable implementations, DevOps, and whole-team leadership. Audit existing runtime tools and workflows before adding overlapping capabilities; outcome verification is tracked in `FEATURE_TODO.md`.
- Workflow run/trigger return execution-unavailable results and retain rendered previews with zero executed steps. Shared discovery marks this metadata-only; actual bounded argv checks exist through plan acceptance. An opt-in package artifact evaluator now independently rebuilds and installs submitted wheels, checks installed reuse/CLI behavior and separates runtime/review evidence. Live agent DevOps and hosted CI outcomes remain unverified. See [package evaluation](evals/README.md#offline-package-lifecycle-evaluation) and [workflow preparation](docs/tools.md#workflow-preparation).
- Compatible streams now preserve OpenRouter text reasoning across tool turns, confirmed by a bounded MiMo run. That run passed independent artifact checks but hit delegation limits and its explicit 32K context cap before completing the workflow. Structured/encrypted reasoning and team efficiency remain open; see [streaming reliability](docs/providers.md#streaming-reliability).
- `/chat resume` now retains saved text reasoning in its command fallback path; disk-backed tag/ID tests verify the next SDK request and keep that text out of console/events. Structured/encrypted continuation state remains open. See [session commands](docs/getting-started.md#slash-commands).
- Python evals now reject ignored runtime failures and known false passes in counter, class-extension, rename and multi-file tasks. Independent checks use the current interpreter with bounded output and explicit completion evidence; see [evaluation contracts](evals/README.md#runtime-completion-and-independent-python-checks).
- Included local model target: a 16 GB RAM laptop with CPU operation and optional GPU acceleration. Model/runtime selection, real coding usefulness, total memory, and portable installation remain unverified; reuse existing local provider adapters.
- Team context settings now reach the leader and specialists, including cached agents across provider switches. The conversation budget applies the configured compaction threshold; output and whole-process memory remain separate limits. See [context configuration](docs/configuration.md#context-management-settings).
- Stream-safety regressions now cover compatible providers and native Anthropic; see [provider guarantees](docs/providers.md#streaming-reliability).
- Shared provider construction and runtime switching now honor saved credentials, endpoints, and request settings across CLI/TUI, API/chat, and specialist agents while retaining conversation state; see [provider selection](docs/providers.md#provider-selection-and-credentials).
- Bounded headless completion, provider/core/orchestrator cancellation, and interactive save/resume now have offline regression coverage. Session transcripts preserve full evidence across context compaction; see [session architecture](docs/architecture.md#sessionmanager).
- Serial team streams now forward specialist progress immediately with consumer backpressure and nested cleanup, avoiding an extra batch-sized event list. This does not bound conversation history or `json-complete` output arrays.
- Headless JSON now shares the team orchestrator, honors direct roles, and preserves agent attribution. Round limits and dynamic specialist policies apply; scripted team workflows are runtime evidence, not live-model quality evidence. See [headless teams](docs/agents.md#headless-team-execution).
- Completion reporting preserves provider failures and abnormal finishes, rejects unsupported specialist success claims, and isolates nested execution evidence. See [execution status limitations](docs/architecture.md#overview); successful tool calls still do not prove task correctness.
- Native OS verification is configured through an independent installed-wheel CI matrix. Unix-only shell/RAG imports, Linux process assumptions, Windows upgrade-path detection, and Python output encoding have focused regressions; hosted Windows/macOS results are still required.
- The five-adapter real file edit/test/recover matrix passes from fresh installed wheels outside the checkout on Linux, macOS and Windows across Python 3.11–3.14 at foundation candidate `55fd66b`. Provider responses are scripted; live-provider quality and final-artifact qualification remain open. Behavioral evals now use explicit provider selection and the bounded runtime loop, and include a Python reuse task with independent verification.
- Keep roadmap and README claims aligned to the shared discovery capability matrix.
- Keep the supported Python range and built-wheel smoke checks aligned with packaging and CI.
- Preserve confirmed-real local foundations without turning narrowed surfaces back into implied promises.
- Expand the new contract suites from API/core seams to the remaining runtime protocols and adapters.

- Shell redirects are supported. Shell/Python tools default to independently tracked background jobs; `/goal` continues interactive work until completion or pause, and user input queues during work. See [execution and goals](docs/tools.md#background-execution).

## Maintenance notes

- Keep this file synchronized with the verified runtime state in `FEATURE_TODO.md`.
- Only record a surface as shipped here when the CLI/runtime entrypoint is proven, not when code merely exists in the tree.

- Normal conversation now reports `responded`; explicit action requirements still reject answer-only work. Completion events expose activity evidence and `task_verified: false`. Typed file/command/pytest checks now provide bounded historical observations through `verify_plan_execution`; independent semantic correctness and requirements coverage remain open; see [completion semantics](docs/architecture.md#overview).

- `python_ast(action="quality")` exposes bounded stdlib-only syntax-clone, long-method and deep-nesting review candidates. It reuses the repository smell detectors, reports incomplete coverage explicitly, and does not certify semantic equivalence or smell-free code.
