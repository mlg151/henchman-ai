# Feature TODO — Henchman Roadmap

Organized by priority tiers. Each item is a discrete feature to implement.

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
- [x] Run the five-adapter real-tool coding workflow on Linux and verify a fresh wheel install outside the source checkout; model responses are scripted and native macOS/Windows runs remain required.
- [x] Stream serial team events without accumulating whole tool batches, preserving consumer backpressure, interruption cleanup, and per-agent evidence. Full application memory and event-array output remain separate concerns.
- [ ] Establish reproducible coding-task evaluations with success, regression, latency, and cost measurements before claiming industry-leading performance.

### Python development and team leadership

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

---

## Implementation Notes

1. **Dependencies between tiers:** Tier 1 should be done first as it improves the dev experience for implementing later tiers. Tier 2 (session/context) is foundational for Tier 3 (agents/skills).

2. **Python vs rewrite:** Some features (LSP, native modules, desktop/mobile apps) may warrant different technology choices. Consider Rust bindings for performance-critical paths.

3. **Existing equivalents:** Some features may partially exist already — audit before implementing:
   - API server mode exists but may need expansion
   - Discord bot exists but may need enhancement
   - Basic MCP support exists
   - Memory system partially exists

4. **Priority re-ordering:** This list should be revisited based on user feedback and usage patterns.
