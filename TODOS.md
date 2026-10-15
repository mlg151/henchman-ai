# TODOS.md

Living roadmap snapshot for Henchman-AI. `FEATURE_TODO.md` remains the tier-by-tier source of truth; this file is the quick view of shipped foundations versus narrowed or still-unshipped surfaces.

## Recovery baseline

- Supported runtime and CI matrix: Python 3.11–3.14.
- Packaging dependency floors: `chromadb>=1.5.9` for RAG and direct `scipy>=1.11.2` for NetworkX PageRank queries.
- Context safety: outside Git, project instruction discovery is bounded to the current working directory.
- Install verification: CI builds a wheel and smoke-installs it on Python 3.11 and 3.14, checking both CLI entry points and an ephemeral Chroma collection.

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

## Current focus

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
- The five-adapter real file edit/test/recover matrix now passes on Linux, both in development and from a fresh installed wheel outside the checkout. Provider responses in this matrix are scripted; live-provider checks and native macOS/Windows runs remain open. Behavioral evals now use explicit provider selection and the bounded runtime loop, and include a Python reuse task with independent verification.
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
