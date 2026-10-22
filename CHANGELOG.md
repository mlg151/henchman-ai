# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

**Note on historical measurements and claims**: Versioned entries describe the state reported at the time of each release. Line counts, test totals, and coverage statements are preserved as historical records, not guarantees about the current tree. Line counts explicitly marked with "(historical snapshot)" likewise record the scale of earlier refactoring rather than current file sizes.

## [Unreleased]

### Added

- **Terminal UI research** — Added a [sourced comparison](docs/terminal-ui-research.md) of coding-agent interfaces and Python terminal applications, with Henchman-specific interaction recommendations and phased acceptance criteria. UI implementation and native usability qualification remain planned.
- **v0.4.2 UI planning** — Included all five UI phases as [epic #11](https://github.com/mlg151/henchman-ai/issues/11) subtasks #32–#36, with shared-service ownership, native prerequisite links and a UI qualification release gate. The epic now contains 24 planned subtasks; no runtime UI completion is implied.

### Removed

- **`.agent_tasks/` workspace convention** — The non-source artifact directory convention (task folders, analysis/docs/scripts subdirectories, working-memory archives, pattern-learning database) is removed from all agent instructions, docs, prompts and tests. All supporting artifacts now live in normal project paths or durable notes. `.agent_tasks/` is deleted from the repository and from exclusions/config. The shared copilot instructions are condensed to under 8,000 characters; `CLAUDE.md` remains a symlink to `.github/copilot-instructions.md`.

## [0.4.1] - 2026-10-15

### Added

- **Milestone releases** — Successful CI for release PRs merged into `main` builds and publishes the matching version using the repository `PYPI` secret, then tags the tested commit and attaches distributions to its GitHub release.

- **Dynamic background subagents** — The default primary coding agent uses the full live workspace tool suite and can launch custom, scoped conversations with `invoke_subagent`, exchange messages, and inspect or cancel work with `manage_subagents`. Results and assistance requests resume the parent through event queues. CLI exit and conversation resets cancel and join owned workers; named-role delegation remains available. See [agent lifecycle](https://github.com/mlg151/henchman-ai/blob/main/docs/agents.md#dynamic-background-subagents).
- **Standards adoption research** — Added the [issue #3 RFC](https://github.com/mlg151/henchman-ai/blob/main/docs/standards.md) with sourced MCP/A2A/OpenTelemetry/schema research, baseline interface gaps, and a phased implementation roadmap. Protocol adoption and interoperability guarantees remain proposed work.

### Fixed

- Clarify configured named-role lifecycle companions and exact dynamic-child tool scopes; refresh integration checks for the full default primary catalog and restricted live registration.
- Background-subagent launch, messaging and cancellation remain responsive while a child holds the source-formatting mutation lock. Reactive result notifications preserve cumulative tool-round and tool-call limits.
- `python_exec` formats only its in-memory snippet, avoiding workspace traversal and failures above 5,000 sources. Formatting errors and short-deadline timeouts log warnings and preserve original execution in foreground and background modes. Generated Python files require explicit `code_format`.
- Keep oversized Black snippet expansion from causing Python execution failures by
  falling back to the original source when formatted output exceeds 12 KiB.
- Run the normal CI checks for pushes and pull requests targeting the `0.4.1` staging branch before release integration.

## [0.4.0] - 2026-10-14

### Added

- `/goal` starts persistent session objectives with automatic interactive continuation, status, pause, resume, completion and clear controls. Structured completion checks the current goal revision and requires a verification summary.

### Changed

- Shell and `python_exec` calls launch independently tracked background jobs by default, with output/status/stop tools and explicit `background=false` foreground execution. Interactive frontends retain messages submitted during work and serialize agent turns.
- Shell validation and secure-shell presets allow redirects, including `/dev/null` and descriptor duplication; unrelated command checks and execution approvals remain enforced.
- **Coherent workflow guidance** — Shared default prompts ask agents to keep related edits and required checks under one owner, verify the final relevant state, reuse sufficiently evidenced checks and return timely handoffs. Explicit user/project requirements and independent review remain in effect. Supplied-context advice does not require ceremonial checks. These are instructions, not runtime enforcement; paired live outcomes have not been measured. See [team execution guidance](docs/agents.md#headless-team-execution).
- **Automatic Black formatting** — The shared harness formats observed Python changes after authorized edits and foreground commands, before verification can consume their results. Black ships at runtime, honors project configuration and reports failures explicitly. Manual `code_format` uses the same bounded backend. The team evaluation's version 3 retains behavior/workflow requirements and checks Black formatting independently.
- **Complete delegation mission context** — Specialists receive the full original request, preserving requirements beyond the former 500-character cutoff. Only the status board's goal preview is shortened; explicit subtask criteria and request-capacity checks remain in effect.
- **Retry diagnostic isolation** — Reused specialists clear prior execution errors when a new run starts. Current tool continuations retain their diagnostics, and previously returned handoffs remain unchanged.
- **Lint-fix execution policy** — `lint_check(fix=True)` uses write authorization, respects Plan Mode and formats observed fixes with Black before returning, including explicit targets outside the working directory. Extension tools can classify invocation modes through `execution_kind(params)`.
- **Evaluation runtime parity** — Team evaluations receive the CLI's actual workspace environment snapshot. All evaluation profiles now observe final harness results, preserving formatter failures, policy denials and unexecuted calls instead of recording raw implementation success too early.

- **Offline package evaluation** — The explicit team runner supports a package artifact task with protected packaging/data/tests, a pinned local dependency, independent offline rebuild, submitted-wheel installation in a fresh environment, installed CLI/reuse checks and returned specialist-review evidence. Shared artifact observation preserves the existing workflow oracle. Evaluator checks do not attest agent-side installation or hosted CI; live DevOps outcomes remain unverified.

- **Proportionate planning and handoffs** — Default roles share planning and handoff fragments, use concise decisions and findings, and reserve saved tracking for requested or durable coordination. Related changes retain their required checks under coherent ownership; final evidence fields, full review coverage and explicit documentation requirements remain required. Mandatory public thinking transcripts were removed.

- **Team tool discovery** — `tool_search(scope="team", query="<exact tool name>")` reports enabled role capabilities from live registration and scoped tools without creating agents/providers or expanding execution permissions. Default searches explain their local boundary; delegation guidance preserves explicit verification tool requirements.

- **Specialist execution guidance** — Delegations disclose current call and tool-round limits before work starts, recomputing them for cached agents without changing enforcement. Default verification guidance accepts structured test/lint tools and project commands, honors explicit tool requirements and requires observed passing checks on the final changes.

- **Delegation handoff accuracy** — `BLOCKERS: none` and blank blocker fields no longer turn successful specialist actions into false failures. Completion fields come from the final assistant message without consuming following lines; later quoted field names do not replace earlier report fields. Runtime failures and genuine blockers remain unsuccessful, with neutral completion-evidence warnings.

- **Proportionate task artifacts** — Default agent prompts return short discovery findings directly and reserve task folders, scratch probes and README updates for requested or useful durable work. Explicit user/project documentation rules still apply; created supporting artifacts remain under `.agent_tasks/`. All five roles share one workspace-policy fragment.

- **OpenRouter text reasoning continuity** — Compatible streams now accept `reasoning` alongside `reasoning_content`, retaining text through tool turns and subsequent requests without duplicating aliases. Structured or encrypted reasoning blocks remain unsupported.

- **Production team evaluation** — An explicit team profile runs the real orchestrator with copied settings, attributed tool evidence and authoritative root completion. A Python reuse/CLI scenario independently checks behavior, helper reuse, fixed Ruff/mypy gates and workflow ordering against observed artifact changes; a report runner preserves results and closes owned clients. Offline contracts do not establish model competence.

- **Live role tool scopes** — The leader now honors its configured tool and approval lists. Allowed tools registered later, including MCP tools, reach cached agent scopes; removals and replacements affect subsequent calls. Default leader tools include plan verification, and scoped discovery stays independent.

- **Context-sized tool discovery** — Requests that cannot fit a full catalog can expose discovery and core coding schemas, then prioritize up to five tools from the latest search. Default specialists include scope-bound search; paginated discovery retains full inventory access and execution policies remain in effect. Required prompts, requested schemas and output still receive explicit overflow errors.

- **Request context accounting** — Team settings and model switches now retain raw request capacity separately from the conversation target. Per-call estimates include serialized messages, tool schemas and reserved output; complete older turns can be omitted without changing history. Oversized required inputs fail locally. Configured output caps are retained, while compatible providers receive a bounded default when unset. Estimates are not exact server counts.

- **Context length during model switches** — `/model set <provider> [model] --context-length <tokens>` updates the session capacity and effective conversation budgets for the leader and cached/future specialists while preserving history and model overrides. `/model` displays the selected capacity and effective budget; omitting the option retains the current policy.

- **Engineer evaluation profile** — Behavioral evals can opt into the production engineer prompt, preset and available tool scope with `EVAL_PROFILE=engineer`. The minimal baseline remains the default; profile metadata records actual tools, prompt digest and context budget alongside independent correctness checks.

- **Team event streaming** — Serial specialist events now flow through the orchestrator immediately with consumer backpressure, avoiding whole-batch event retention. Closing a nested stream stops remaining work, preserves completed-call evidence, and records interrupted delegations as failed.

- **Local model target** — Raised the planned laptop baseline to 16 GB RAM, with CPU operation and optional GPU acceleration. Selection and hardware validation remain open.

- **Headless team execution** — JSON CLI formats now use the configured orchestrator and honor `--agent`, with source-agent attribution and one authoritative final result. Shared loops bound tool rounds and record per-agent execution evidence. Delegation follows registry authorization; cached specialist scopes inherit current plan mode and confirmation handling.

- **Plan acceptance observations** — `verify_plan_execution` can record immutable file, command, and pytest checks at plan creation and run them with `verify`. Bounded sequential execution records timestamps, specification digests, and historical results; reported step completion and passing selected checks do not establish whole-task correctness. The tool now uses normal `EXECUTE` policy.

- **Response completion** — Normal answers now report `responded` without requiring tools. Delegations still require successful actions by default, with an explicit response-only option for advice. Runtime events and JSON output distinguish execution from unestablished task verification; terminal completion labels say “finished execution.”
- **Python quality analysis** — `python_ast(action="quality")` now reports bounded syntax-clone, long-method and deep-nesting candidates with qualified symbols, source locations, errors, and scan coverage. Reused repository detectors now ship in the installed package; script imports remain compatible. Duplicate comparison preserves meaningful names/literals, and nesting distinguishes flat `elif` alternatives.
- **Python reuse workflow** — Default specialist toolsets now include the existing file overview, symbol tracing, and pattern search tools. Shared role guidance asks agents to inspect reusable implementations and tests, carry evidence into handoffs, and review integrated verification results. Custom allowlists remain unchanged.
- **Native-platform verification** — Added an independent Linux/macOS/Windows installed-wheel CI matrix covering CLI aliases, local RAG operations and locking, Python execution, REPL/Textual question channels and interruption, and offline five-provider coding workflows outside the source checkout. Hosted results are required before platform verification is claimed.
- **Supported Python range** — Runtime metadata and CI now target Python 3.11 through 3.14. The built wheel is smoke-installed at both ends of that range after the normal test/build jobs.
- **RAG and knowledge-graph dependency floors** — Raised ChromaDB to `chromadb>=1.5.9` for current packaging compatibility and declared `scipy>=1.11.2` directly because NetworkX PageRank queries require SciPy at runtime.
- **Post-build install smoke coverage** — Package smoke jobs verify wheels on Python 3.11 and 3.14 and the source distribution on Python 3.11. Each checks both entry-point versions, CLI help and unknown-command behavior, API readiness, and an explicit-embedding Chroma add/query round trip without external credentials or model downloads.
- **Operational runtime recovery** — Restored console routing, dependency-bound builtin tools, live-registry tool search, real Textual task/skill/team/session services, and truthful API version, liveness, and readiness responses.
- **Capability documentation truth** — Public docs now follow the shared discovery capability matrix and distinguish runtime-wired, local-only, export-only, metadata-only, unavailable, docs-only, and intentionally undiscoverable surfaces. Fixed tool counts and blanket completion/production-readiness claims were removed.
- **Enforceable coverage policy** — CI now enforces a truthful 90% whole-project branch-coverage floor for the expanded recovery tree while retaining the expectation that changed behavior is fully tested.

### Fixed

- **Subprocess coverage configuration** — Pin the project coverage configuration for child interpreters, preventing line/branch data mismatches from contaminating exact shell and Python output checks.

- **Plugin archive extraction** — Reject tar links, devices, and named pipes before extracting any members, preventing archive-created links from escaping the installation directory on older supported Python versions.

- **Python execution recovery** — Missing Python source now explains the required `code` and optional `cwd` fields, preserving failure status and keeping mistaken shell command arguments unexecuted and unreflected.

- **Shell newline recovery** — Rejected literal or escaped newlines now explain the single-line command requirement and point to `python_exec` only when allowed. Validation, execution permissions and other error categories remain unchanged.

- **Workflow execution truth** — Workflow run/trigger helpers no longer report rendered strings as completed commands. New records retain previews with zero executed steps and explicit execution-unavailable status; tools return unsuccessful execution results. Historical records remain intact, and shared discovery classifies the surface as metadata-only.

- **Chat session continuation** — `/chat resume` retains saved text reasoning alongside assistant/tool history in the command fallback path, preserving the next compatible-provider request without displaying that reasoning.

- **Configured team leader** — The actual leader now shares the pool's cached instance and honors its saved provider, model, identity and prompt, retaining history through direct execution, resets and model/context switching. Partial builtin-role settings inherit preset metadata; explicit lists retain replacement semantics.
- **Active model displays and commands** — REPL and Textual provider/model labels and slash commands follow the acting leader or direct specialist. The toolbar honors an explicit context capacity, and provider selection switches the direct agent while preserving other pinned roles.
- **Active agent reuse** — Delegation rejects a running or reserved agent before clearing its history, preventing self/ancestor delegation from corrupting the shared leader's transcript. Reservations cover suspended startup and release on success, failure and cancellation.

- **Acting-agent tool dispatch** — Fallback terminal and standalone JSON execution now use the acting agent's registry for execution and approval classification. Explicitly supplied empty runtime registries are retained for later tool registration.

- **Ollama request defaults** — Saved compatible options, including output token caps, now reach the shared provider request path. Unsupported SDK keywords still fail before a runtime switch changes active references.

- **Context switch setter integration** — The agent accepts the raw `context_window` passed by the runtime switcher, fixing the unexpected-keyword failure when selecting a context length.

- **Quoted Python verification commands** — The default shell tool no longer recursively splits quoted snippets at semicolons, ampersands or pipes. Balanced `python -c` verification commands reach the shell unchanged while existing whole-command restrictions and execution approval remain in effect.

- **Edit targeting and recovery** — Reject incomplete line ranges even when `old_str` is supplied. Ambiguous-match errors guide a fresh read and unique contextual replacement. Optional `read_file(line_numbers=true)` exposes current absolute line numbers; line edits use the same newline boundaries, including files containing form feeds or Unicode separators. Edit guidance explains full-range replacement and previews.

- **Keyless compatible endpoints** — Supply an explicit placeholder only to the SDK when no API key is configured, retaining empty saved settings and avoiding SDK credential inheritance. This supports SDK versions that reject empty credentials for local servers.

- **Python evaluation false passes** — Live evaluation wrappers reject missing, failed or interrupted turns even when their results are ignored. Counter, class-extension, rename and multi-file scenarios now check independent behavior instead of accepting shared state, unchanged code or comments. Portable child checks bound diagnostics and distinguish completed assertions from premature exit zero.

- **Team context limits** — The leader and specialists now receive the configured conversation limit and compaction threshold. Cached agents preserve explicit budgets across provider switches; standalone pools retain model-derived limits when no budget is supplied.

- **Turn evidence isolation** — Completion checks use the final committed answer rather than discarded retry text. New turns and cleared history reset stall failures while preserving detector settings; tool continuations retain the current turn's evidence. Unbound delegation now reports unavailable instead of claiming execution.
- **Completion integrity** — Provider failures and abnormal finishes now report `failed` even after successful tools. Specialist prose cannot override runtime status; unsuccessful or missing delegation outcomes fail the tool result and ledger entry. Nested tool calls no longer inflate parent success, and terminal UIs no longer render failed or unknown outcomes as completed.
- **Python symbol signatures** — AST symbol output now preserves positional-only and keyword-only parameters, defaults, variadic arguments, and annotations.
- **Terminal interruption** — Bare Escape now interrupts after a bounded input-idle timeout; fragmented arrow and function-key sequences do not accidentally cancel the turn. Question prompts release the key monitor after answers, timeout, or cancellation.
- **Conversational history** — Replies no longer gain a fabricated user message demanding a `THINKING:` prefix. Planning guidance is task-appropriate; concrete tool and completion evidence checks remain separate.
- **User-input evidence** — Unbound `ask_user` no longer fabricates a successful answer. A supplied async handler must return an actual answer; timeout and missing responses fail explicitly. Classic REPL and Textual now bind actual input channels with serialized prompts and cancellation cleanup; headless remains unavailable and discovery distinguishes that dependency.
- **Behavioral evaluation integrity** — Evaluations use the shared provider factory and bounded headless loop. Explicit provider selection cannot silently fall back, whole-turn timeouts are enforced, and incomplete/error terminals fail. A Python reuse scenario checks real inspection, edits, test execution, and use of the existing helper. The installed coding-workflow fixture prevents stale bytecode after instantaneous same-size edits.
- **Python verification and discovery** — Inheritance searches preserve Python identifier case. Pytest and lint tools validate runtime selections. Pytest requires completed-session evidence and a passed test call for execution success; inherited collection and entirely skipped runs cannot establish verification. Its independent report preserves project JUnit artifacts. Interrupted subprocess cleanup uses bounded terminate/kill/reap attempts. Git file-specific commit inspection passes the revision and path as separate arguments, including paths containing spaces.
- **Platform portability** — Shell and RAG startup no longer require Unix-only imports on Windows. RAG uses native POSIX/Windows locks without truncating existing lockfiles. Shell process checks use procfs only on Linux, correctly parse names containing spaces, and preserve native Windows commands without Unix sudo rewrites. Upgrade detection recognizes Windows uv/pipx paths while preserving safe argv and ambiguity handling. Owned Python snippets emit UTF-8 output to match the capture decoder.
- **Interactive session continuity** — REPL and Textual save settled turns after completion or cancellation, including full tool results, reasoning, and partial replies. An independent turn transcript preserves evidence across context compaction. Resume restores the selected agent without leaking summaries from the previous session or duplicating the configured system prompt. Interrupted execution preserves completed tool results and cancels unanswered calls without duplicate responses.
- **Coding-loop interruption and completion** — Provider streams close deterministically and preserve original errors when cleanup also fails. Cancelled partial replies retain an interruption marker. Tool batches with missing or duplicate identities are rejected before dispatch. Headless JSON execution uses bounded iteration, correlated tool results, one terminal completion, and nonzero failure exits. Interactive stream errors stop queued work and preserve cancelled requests and multi-round tool declarations.
- **Configured provider selection and switching** — Shared provider construction honors explicit selection instead of inferring DeepSeek from unrelated credentials. Compatible model names, provider-specific environment keys, key references, keyless Ollama/local endpoints, and saved OpenRouter request options are applied consistently. Runtime model switches update effective model state while retaining session history and tool bindings; configuration success is no longer presented as a network connection test.
- **Provider stream reliability** — OpenRouter and other compatible adapters reject malformed/non-object tool arguments, retain usage-only chunks, and propagate transport failures instead of returning successful assistant text. Anthropic shares argument validation. The agent retains text on finish chunks, reports interrupted streams, and stops stall retries after provider errors. Partial tool calls from truncated responses are not saved as completed requests.
- **REPL chat turn presentation** — Replaced the permanent per-turn `CHAT`/token line (which exposed literal Rich markup) with a transient thinking indicator. Mode and token usage now remain in the bottom toolbar, and direct-agent turns show a plain role detail.
- **Deterministic operational probes** — `/v1/health` and `/v1/ready` bypass request rate limiting, preventing monitoring traffic from consuming the application request bucket or receiving HTTP 429.
- **Non-Git project context boundary** — Context discovery outside a Git repository now stops at the current working directory. It does not inherit instruction files from parent directories or scan subdirectories without a repository root, while global `~/.henchman/HENCHMAN.md` context remains available.

## [0.3.15] - 2026-03-18

### Fixed
- **Discord bot: `max_iterations` was counting every content chunk, not tool calls** (`chat/manager.py`)
  - The 50-iteration limit applied to every streamed content event, so a normal greeting response (100+ content chunks) would immediately hit the cap and emit "Maximum tool iterations reached". Fixed by only counting `TOOL_CALL_REQUEST` events toward the iteration limit.
- **Discord bot: stall detection caused duplicate responses and hallucinated tool calls** (`chat/manager.py`)
  - The stall detector is designed for task-oriented CLI sessions. On Discord it would see casual greetings containing phrases like "Let me know..." and inject a nudge message ("Do not narrate, use tools NOW"). The LLM would then hallucinate a user task and call tools unprompted. Fixed by disabling stall detection on Discord agent instances.
- **Discord bot: improved system prompt prevents unprompted tool usage** (`chat/manager.py`)
  - Tightened the system prompt with explicit rules: only respond to the user's message, don't use tools for greetings/casual conversation, never invent tasks the user didn't ask for.
- **`_get_provider_settings` silent false-positive warning for empty dict config** (`chat/manager.py`)
  - `if provider_settings:` treated an explicit `providers.deepseek: {}` (empty dict = use defaults) as falsy, falling through to the "missing settings" warning branch. Fixed by using `if provider_settings is not None:`.



### Fixed
- **Discord bot infinite loop and duplicate responses** (`chat/manager.py`)
  - The `while True` outer loop in `_handle_message` called `agent.continue_with_tool_results()` unconditionally after every stream. Since that method returns an async generator (never raises), the `except Exception: break` never triggered, causing infinite iterations. Each iteration generated a duplicate LLM response and hit the inner 50-event safety limit, producing repeated "Maximum tool iterations reached" warnings. Fixed by tracking `had_tool_calls` in `_process_stream` and only continuing when tool calls were actually made. Added a 20-round outer safety limit.
- **`/clear` command wiped system prompt** (`chat/manager.py`)
  - `messages.clear()` removed the system prompt along with conversation history, causing "Messages list cannot be empty" provider errors on subsequent messages. Fixed by using `agent.clear_history()` which preserves the system prompt.
- **BUG-7 🟡 MEDIUM — CLI tool calls were echoed multiple times** (`stream_event_handlers.py`, `tool_executor.py`)
  - The REPL rendered a tool call immediately on `TOOL_CALL_REQUEST`, then echoed the same `[tool] ...` line again when executing the pending tool. Fixed by tracking tool-call IDs already announced during stream handling and suppressing the duplicate execution-time echo for those IDs, while preserving the legacy direct-execution path that still needs its own announcement.
- **BUG-8 🟡 MEDIUM — Tool triplication in CLI output** (`henchman/cli/stream_event_handlers.py`)
  - Fixed a regression where tool calls were echoed multiple times due to redundant event emission in the stream handler loop.
- **Maintenance — Cleaned up textual mixins test suite** (`tests/cli/test_textual_mixins.py`)
  - Consolidated scattered test files into a single suite `tests/cli/test_textual_mixins.py`.
  - Fixed dead code issues in `_NullProvider`.
- **BUG-1 🔴 CRITICAL — Deadlock in `run_parallel_delegations`** (`delegation.py`)
  - `max_buffer_size=256` on the anyio `MemoryObjectSendStream` caused a classic producer/consumer deadlock: producer tasks would block on `send()` once the buffer was full, the task group could never exit, and the consumer loop never started. Fixed by setting `max_buffer_size=float("inf")` so producers never block.
- **BUG-2 🔴 HIGH — Race condition in `record_delegation_errors`** (`agent.py`)
  - TOCTOU race: two concurrent threads could both observe `not hasattr(self, "_delegation_tool_errors_lock")` → `True`, each create a new `threading.Lock()`, and the second assignment would silently overwrite the first, losing all errors recorded by the first thread. Fixed by eagerly initializing `_delegation_tool_errors` and `_delegation_tool_errors_lock` in `Agent.__init__()`.
- **BUG-3 🟡 MEDIUM — Double `FINISHED` event emitted per `Agent.run()` call** (`agent.py`, `agent_streaming.py`)
  - `generate_stream_events()` always emits `EventType.FINISHED` in its `finally` block, which flowed through `_stream_with_stall_loop` to callers. `run()` also emits its own richer FINISHED event. Every consumer received two FINISHED events, causing double-finalization and discarding the outer event's usage payload. Fixed by filtering `EventType.FINISHED` in `_stream_with_stall_loop` so only the canonical outer FINISHED propagates.
- **BUG-4 🟡 MEDIUM — Silent exception swallowing in `_fetch_agent_errors`** (`delegation.py`)
  - Bare `except Exception: pass` silently discarded all protocol-level failures from specialist agents. Fixed by logging at `WARNING` level with `exc_info=True` before returning `[]`, preserving graceful degradation while making failures visible in logs.
- **BUG-5 🟡 MEDIUM — Read-only tool duplicate counter never increments** (`turn.py`)
  - `_track_duplicates` only incremented `_consecutive_duplicates` for read-only tools when the counter was already ≥ threshold — a self-defeating condition that kept the counter at 0 permanently. Spinning agents that looped on `read_file`, `ls`, `glob`, or `grep` were never detected. Fixed by always incrementing the counter and using a new `_last_call_is_read_only` field in `is_spinning()` to apply the correct threshold per tool type.
- **BUG-6 🟢 LOW — `execute_batch` result key collision** (`registry.py`)
  - Batch result keys used `f"{tool_name}_{i}"`, which collided when a tool was literally named `my_tool_0` and called at any index. Fixed by using `f"{i}:{tool_name}"` (colon is not a valid Python identifier character, eliminating all ambiguity).

### Added
- **5 new research and exploration tools** in `src/henchman/tools/builtins/`:
  - **`file_overview`** (`FileOverviewTool`) — Hierarchical structural summary of any file without reading full content. For Python: imports, class tree, function signatures, docstrings (first line). Adapts detail level to file size (small files: full read; medium files: structure+docs; large files: structure only). Handles Markdown headings, JSON keys, YAML keys for non-Python files. `ToolKind.READ`.
  - **`deep_research`** (`DeepResearchTool`) — End-to-end web research in a single call. Decomposes a question into sub-queries, searches DuckDuckGo for each, fetches top results, and synthesizes findings into a Markdown report with citations. Replaces 6–15 sequential `web_search` + `web_fetch` calls. `ToolKind.NETWORK`.
  - **`symbol_trace`** (`SymbolTraceTool`) — Full symbol provenance across a codebase. Given a symbol name, finds all definition sites (via AST), import sites, call/reference sites, and type annotations in one call. Replaces manual combination of `python_ast` + `grep` + `import_graph`. `ToolKind.READ`.
  - **`research_notes`** (`ResearchNotesTool`) — Persistent in-session note-taking scratchpad stored in `~/.henchman/notes/`. Actions: `write`, `append`, `read`, `list`, `search`. Write/append require confirmation; read/list/search are auto-approved. Fills the gap between ephemeral tool results and long-term research findings. `ToolKind.WRITE`.
  - **`pattern_search`** (`PatternSearchTool`) — Natural language code search. Extracts structural patterns (inheritance, decorators, async, exceptions, etc.) and keywords from a description, then combines both into ranked results. Goes beyond exact regex (`grep`) without requiring a pre-built vector store. `ToolKind.READ`.
- 162 tests added across 5 new test files in `tests/tools/`.

## [0.3.13] - 2026-02-25

### Changed
- **`cli/commands/session.py` refactored to A quality** — F-grade file that was historically a large file (historical snapshot) (30.0/100, 77 smells) refactored to A (100.0/100, 0 smells).
  - Converted `SessionDisplayFormatter` class (10 `@staticmethod` methods) to module-level functions — eliminates feature envy detection entirely.
  - Removed `SessionCommandHelper` class; its private methods became module-level `_get_manager()` and `_execute_with_executor()` — fixes SLF001 violations.
  - Added `self: ClassName` explicit annotations to all 37 affected instance methods (fixes type-hint detector bug).
  - Added private helper methods to `SessionCommand` (`_validate_min_args`, `_get_manager`, `_get_template_action`, `_render_sessions`) to balance feature-envy ratio in `_template` and `_list`.
  - Extracted `_ARG_IDX_3 = 3` and `_ARG_IDX_4 = 4` module-level constants (fixes 7 magic number smells).
  - Fixed lint: PIE790 (`pass` → `...`), 12× COM812 (trailing commas), A001/FURB110 (`format` → `fmt`, ternary → `or`), ASYNC240 (`# noqa`), RET505, RUF012 (`ClassVar`), E501 (wrapped long line).
  - All 6 session tests pass unchanged.
- **`tool_executor.py` refactored to A quality** — Split monolithic F-grade file (30.0/100, 111 smells) that was historically a very large file (historical snapshot) into 2 focused modules, both grade A (100.0/100, 0 smells).
  - New module: `stream_event_handlers.py` (StreamState dataclass + module-level event handler functions, A 100.0).
  - `tool_executor.py` reduced from historically a very large file (historical snapshot) to a significantly more compact size (historical snapshot), F (30.0) → A (100.0). Method count from 30 to 9.
  - Fixed: Large Class (historically very large with 30 methods) (historical snapshot), Feature Envy (×4 HIGH/MEDIUM), Deep Nesting (depth 6–7), Primitive Obsession, Duplicate Code (×2), Long Methods, PLR0913, COM812, FBT001, E501, ARG002, N806, PIE790, PLC0415, SLF001, TC001/TC003/TC004, TRY300, UP035, Missing Type Hints (×27).
  - Key techniques: `StreamState` parameter object for primitive obsession/PLR0913, module-level functions for feature envy, `match/case` dispatch for deep nesting, merged duplicate event handlers.
  - All 126 tests pass unchanged.
- **`agent.py` refactored to A quality** — Split monolithic large F-grade file (30.0/100) into 4 focused modules, all grade A.
  - New modules: `agent_config.py` (AgentConfig dataclass, A 95.8), `agent_stall.py` (StallDetector, A 97.2), `agent_streaming.py` (StreamState/StreamContext/generate_stream_events, A 91.6).
  - `agent.py` reduced from a large file to a much more compact size (historical snapshot), F (30.0) → A (93.0). Method count from 30+ to 16.
  - Fixed: Large Class, 64 Duplicate Code smells (property getter/setter pairs), Feature Envy, Primitive Obsession, Long Methods, Missing Type Hints, PLR0913, BLE001.
  - Key techniques: `__getattr__`/`__setattr__` delegation for backward-compat property access (eliminates duplicate code), module-level functions for feature envy, `AgentConfig` parameter object for primitive obsession, `StreamContext` for PLR0913.
  - All 2586 tests pass unchanged.
- **`turn.py` refactored to A quality** — Extracted 15+ magic numbers to named module-level constants (F 30.0 → A 97.2).
  - Constants: `HASH_PREFIX_LENGTH`, `READ_ONLY_DUPLICATE_THRESHOLD`, `MAX_RECENT_HASHES`, `READ_ONLY_TOOLS`, `WRITE_TOOLS`, etc.
  - Added `self: TurnState` type annotations to all methods.
- **`session.py` refactored to A quality** — Split monolithic very large F-grade file (11.0/100, 120 smells) into 10 focused modules, all grade A (90.7/100, 0 smells).
  - New modules: `session_models`, `session_data`, `session_helpers`, `session_manager_base`, `session_manager`, `session_merge`, `session_export`, `session_templates`, `session_branch`.
  - `session.py` is now a thin facade (nearly 27 LOC, MI=100) with full backward-compatible re-exports.
  - Fixed: Large Class (historically very large) (historical snapshot), Long Method (historically long) (historical snapshot), Feature Envy (×6 HIGH), Deep Nesting, Complex Functions (CC=16), Missing Type Hints (×34), Duplicate Code, Primitive Obsession.
  - Key techniques: `_AsDictMixin` for duplicate code, parameter objects (`_BranchMeta`, `_TemplateInfo`, `_TemplateIO`), `TypeAlias` for primitive obsession, module-level functions for feature envy, inheritance split for Large Class.
  - All 125 session tests pass unchanged.
- **`orchestrator.py` refactored to A quality** — Split monolithic extremely large F-grade file (3.6/100, 137 smells) into 16 focused modules, all grade A (92.7/100, 0 smells).
  - New modules: `orchestrator_types`, `orchestrator_prompts`, `orchestrator_timeout`, `orchestrator_turns`, `orchestrator_metrics_ctrl`, `orchestrator_validation`, `orchestrator_tools`, `orchestrator_components`, `orchestrator_events`, `orchestrator_loop`, `orchestrator_anchoring`, `orchestrator_execution`, `orchestrator_delegation_ctrl`, `orchestrator_init`, `orchestrator_run`, `orchestrator_tech_lead`.
  - `orchestrator.py` is now a thin facade (~124 LOC, MI=100) with full backward-compatible re-exports.
  - Fixed: Long Methods, Large Class, Feature Envy, Primitive Obsession, FBT001/FBT002, TC001/TC003, SLF001, PERF401, RUF022, and all other detected smells.
  - All 221 agent tests pass with no changes (3 test lines updated for keyword-only `success=` arg).
- **`textual_app.py` code smell refactoring** — Raised grade from F (30/100) to A (94.4/100).
  - Extracted 12 mixin classes into new `src/henchman/cli/textual_mixins.py` (also grade A, 98.6/100).
  - Resolved Large Class HIGH smell (historically extremely large → much more compact) (historical snapshot), Long Method HIGH, and Duplicate Code HIGH.
  - Added type hints, fixed BLE001/PLC0415 lint violations, unified toggle actions via `_toggle_tab()`.
  - `textual_app.py` retains full public API via `__all__ re-exports for backward compatibility.
- **`orchestrator.py`** — Added `from __future__ import annotations` to fix forward-reference `NameError` for `CompletionStatus` used before its definition.
- **`command_processor.py`** — Restored special-case handling for `/quit` (returns `False` directly) ensuring correct REPL exit semantics.

### Added
- **Git operations tool** (`git_ops`) — Dedicated READ tool for git queries (status, log, blame, show, branch_list, stash_list, diff_branches). Auto-approved, eliminating ~30% of shell calls for agent git operations.
- **Dead code detector** (`dead_code`) — AST-based detection of unused imports, functions, and classes. Supports directory scanning, whitelisting, and respects `__all__` exports.
- **Environment inspector** (`env_inspect`) — Python version, virtualenv, installed packages, project detection, and filtered env vars in a single tool call. Replaces 3-5 shell commands.
- **Test generator** (`test_gen`) — Generates pytest test stubs from Python function/class signatures. Supports class-based and function-based styles, async functions, and output to file.
- **Patch apply tool** (`patch_apply`) — Apply multi-hunk unified diff patches with dry-run preview and fuzzy context matching. Supports standard `---`/`+++`/`@@` syntax.
- **Grep enhancements** — Added `context_before`, `context_after`, `invert_match`, `whole_word`, and `count_only` parameters.
- **File edit line-range mode** — Added `start_line`/`end_line` as alternative to `old_str`, plus `dry_run` preview mode.
- **Lint check auto-fix** — Added `fix` parameter that runs `ruff check --fix` with confirmation.
- **Pytest coverage & parallel** — Added `coverage`, `parallel`, `collect_only`, and `markers` parameters.
- **Python AST enhancements** — Added docstring extraction, method classification (staticmethod/classmethod/property/abstractmethod), and `include_docstrings` parameter.
- **Diff view enhancements** — Added `compare` (branch comparison), `stat`, `name_only`, and `context_lines` parameters.
- **Import graph cycle detection** — Added `detect_cycles` (DFS-based circular import detection) and `classify` (stdlib/local/third-party) parameters.
- **Coverage map enhancements** — Added JSON format support, `show_branches`, and `per_function` parameters.

### Fixed
- **Tool registration gap** — `CoverageMapTool` and `ImportGraphTool` were exported but never registered; now registered in `tool_manager.py`. Added regression test to prevent future gaps.
- **Pre-existing test failure** — Fixed `test_async_ask_user_method` that referenced removed `_ask_user_async` method.

## [0.3.11] - 2026-02-24

### Fixed
- **Thinking tokens on separate lines** — `on_agent_thought_message` now uses `append_thinking_chunk()` (streaming API) instead of `add_thinking_message()`, so consecutive thinking tokens accumulate into a single collapsible widget rather than creating one widget per token.
- **Tool result emoji spacing** — Added double space after 🛠️ emoji in ToolMessage headers to prevent terminal variation-selector rendering from eating the gap between emoji and text.

## [0.3.10] - 2026-02-20

### Fixed
- **MarkupError crash** — Tool output containing ANSI escape codes (e.g., colored CI pipeline output) no longer crashes the TUI. Added `_safe_markup()` helper that strips ANSI codes and escapes Rich markup tags before any content reaches widget `.update()` or `.write()` calls.
- **Unescaped paths in textual_app.py** — `on_agent_thought_message`, `on_tool_call_request_message`, and `on_tool_call_result_message` now escape all user-controlled content before embedding in Rich markup strings.
- **Unescaped paths in textual_widgets.py** — `ChatMessage._update_display()`, `ThinkingMessage._update_renderable()`, and `ToolMessage._update_renderable()` now use `_safe_markup()` instead of bare `markup_escape()`.

### Added
- **147 markup safety tests** — Comprehensive TDD test suite (`tests/cli/test_markup_safety.py`) covering ANSI payloads, Rich markup payloads, mixed payloads, and Textual `visualize()` integration. Includes reproduction of exact crash payload from bug report.

## [0.3.9] - 2026-02-20

### Added
- **Collapsible ThinkingMessage** — Thinking messages now render as collapsible widgets with a `🤔 thinking: (click to expand)` header. Click or call `toggle_expansion()` to reveal/hide full thought content. CSS class `expanded` controls visibility.
- **Collapsible ToolMessage** — Tool call messages render as collapsible widgets with `🔧 tool_name(args)` header. Expanded view shows full JSON arguments and accumulated result text.
- **ProgressIndicator widget** — New `ProgressIndicator` widget with `show(message, kind)` / `hide()` API for displaying agent/tool work status. Uses CSS class toggling for visibility.
- **SessionScreen modal** — New `SessionScreen` in `textual_screens.py` for listing, resuming, and deleting saved sessions with tag, timestamp, and message count display.
- **ChatPane streaming API** — `begin_thinking_stream()`, `append_thinking_chunk()`, `_active_thinking` tracking for streaming thought content into collapsible widgets.
- **ChatPane unmounted support** — All ChatPane methods (`add_user_message`, `add_tool_message`, etc.) gracefully handle the case where the pane is not yet mounted in an app.

### Fixed
- **ComponentInitializer test** — Fixed test that patched non-existent module-level `CommandProcessor`; now uses `class_overrides` dict as intended.
- **Anthropic validation tests** — Fixed tests that assumed API calls would always raise; now handle both success and auth-error cases.
- **ThinkingMessage render/header split** — Header sub-widget never shows content text (for CSS-based collapse), while `render()` includes summary for programmatic introspection.
- **Various pre-existing test failures** — Fixed `test_status_bar_update`, `test_thinking_message_accumulates_content`, `test_chat_pane_displays_*`, and `test_no_separate_*_pane_in_layout` tests.

## [0.3.8] - 2026-02-20

### Added
- **TCSS Theming** — Extracted inline CSS into `henchman.tcss` external stylesheet with dark/light theme variants. Press **F4** to toggle themes.
- **Token/Cost Tracker** — StatusBar now displays cumulative session token count and estimated cost (`X,XXX tokens | $X.XXXX`).
- **Async File Preview** — Context tree file preview shows a loading indicator, file size header, increased preview limit (5 000 chars), and graceful encoding-error handling.
- **Search Highlighting** — Search now highlights matches with `[reverse]` markup across ChatMessage, ThinkingMessage, and ToolMessage widgets. Highlights clear on search exit.
- **Markdown Chat Rendering** — Agent messages are rendered as Rich Markdown after streaming completes. A `_looks_like_markdown` heuristic detects headings, code blocks, bold, lists, and links; plain text stays unchanged.

## [0.3.7] - 2026-02-20

### Refactored
- **Textual TUI modularization** — Split the monolithic `textual_app.py` (which was previously very large) into six focused modules while preserving all public imports via re-exports:
  - `textual_config.py` — `TextualConfig`, `ComponentConfig`, `ComponentInitializer`
  - `textual_messages.py` — All Textual `Message` subclasses
  - `textual_widgets.py` — `ChatPane`, `StatusBar`, `ThinkingPane`, `ToolPane`, etc.
  - `textual_bridge.py` — `TuiConsoleAdapter`, `EventBridge`
  - `textual_screens.py` — `ConfirmToolScreen`, `HelpScreen`, `ProviderScreen`
- Applied refactoring rules: guard clauses, extracted helpers, constants, Google-style docstrings, full type hints, ≤88-char lines, ≤50-line functions, ≤3 nesting depth.
- `ComponentInitializer` accepts `class_overrides` dict for dependency injection, preserving test patchability.

### Fixed
- **Textual TUI improvements** — Added thinking messages in chat pane with stub implementations for ThinkingMessage and ToolMessage widgets
- **Textual TUI issues** — Resolved 10 Textual TUI issues from code audit:
  - Fixed RichConsole config in TuiConsoleAdapter (force_terminal, highlight)
  - Updated deprecated asyncio.get_event_loop() to get_running_loop()
  - Corrected version display "v—" → v{__version__} format
  - Removed perf-killing asyncio.sleep(0) yields in event handler
  - Fixed search scroll calc (line_height * index)
  - Added warning for mock provider fallback
  - Cached file read in context tree (avoid double read)
  - Improved provider switch (preserve state, better UX)
  - Robust RichLog search across Textual versions
  - TextArea: .text= → load_text() for proper events
- **Textual TUI test suite** — Fixed all failing tests for the TUI implementation: `test_screen_composition`, `test_command_palette_functionality`, `test_pane_widgets_initialization`, `test_slash_command_filter`, `test_search_navigation` (missing import), and the entire `test_textual_integration.py` suite (47 tests).
- **Textual TUI integration tests** — Fixed `_fake_init` to set `_ui_renderer` (read-only property), added `_chatpane_has_content()` / `_get_chatpane_text()` helpers for `ChatPane` (VerticalScroll, not RichLog), fixed `_show/_hide_command_palette` method names, fixed `ChatPane._active` dict for streaming state, and added mock `command_processor` where required for palette display.
- **Mypy type error** — Fixed `Select` widget construction in `ProviderScreen.compose()` by replacing `**dict` expansion with an explicit `value=` keyword argument, resolving mypy arg-type error.
- **Ruff import sorting** — Fixed unsorted import block in `tests/providers/test_openai_compat.py`.
- **Missing docstring** — Added docstring to inner `callback` function in `HenchmanTextualApp.confirm_tool_execution()`.

### Improved
- **Test coverage** — Increased coverage from 88.19% to 89%+ by adding targeted tests for previously uncovered code paths:
  - `agents/pool.py`: `extra_tools` registry deduplication, confirmation handler copying, `get_identity`, `list_active_agents`, `reset_all`, `shutdown`
  - `cli/session_manager.py`: `_sync_session_to_agent` with `tool_calls` dict-to-object conversion, `create_session`, `load`, `load_by_tag`, `save` (explicit and implicit), `list_sessions`, `delete`
  - `cli/ui_renderer.py`: All delegation methods (`warning`, `heading`, `markdown`, `code`, `rule`, `clear`, `tool_call`, `tool_result`, `tool_summary`, `agent_content`, `show_thinking`, `confirm_tool_execution`, progress task methods, `create_status`), exception path in token counting, RAG indexing status display
- **CI pipeline** — Fixed CI to pass all tests, mypy, ruff, and reach 89% coverage

## [0.3.3] - 2026-02-19

### Added
- **Data Engineer agent** — New specialist role for data pipeline development, AWS infrastructure, PySpark/Pandas transformations, and Airflow DAG design.
- **Enhanced delegation protocols** — Improved delegation briefs with mission context, dependency tracking, and prior failure awareness.
- **Blocker protocol** — Early blocker detection with structured failure analysis for specialists.
- **Convention awareness** — Agents now check project conventions before modifying files.

### Improved
- **Agent prompts** — Enhanced thinking protocols, delegation checklists, and handoff documentation.
- **Status bar** — Better provider/model information display and token usage tracking.
- **Theme system** — 8 built-in themes with `/theme` command for interactive management.

### Fixed
- **Thinking display visibility** — Fixed issue where thinking content was being cleared by the status spinner animation. Now stops the spinner when thinking starts and restarts it when thinking ends, making thinking content fully visible in the terminal.
- **Status spinner restoration** — Improved handling of status spinner state when transitioning in and out of thinking mode to prevent errors when restoring spinner state.

## [0.3.2] - 2026-02-19

### Fixed
- **Thinking display visibility** — Fixed issue where thinking content was being cleared by the status spinner animation. Now stops the spinner when thinking starts and restarts it when thinking ends, making thinking content fully visible in the terminal.
- **Status spinner restoration** — Improved handling of status spinner state when transitioning in and out of thinking mode to prevent errors when restoring spinner state.

## [0.3.1] - 2026-02-19

### Fixed
- **Thinking pattern check breaking tool sequences** — The orchestrator's thinking pattern validation was injecting a user message between assistant tool_calls and their tool responses, breaking the OpenAI API message sequence contract. This caused repeated `repair_message_sequence` cycles that stripped tool calls and dropped tool results, making the agent unable to use tools effectively. Fixed by only running the thinking check when the agent has no pending tool calls.

## [0.2.22] - 2026-02-18

### Fixed
- **MCP test compatibility** — Fixed `create_mock_client` signatures to match keyword arguments in test suite.
- **Plan mode test compatibility** — Updated plan mode test to use Repl's actual tool registry and session manager.
- **Version test compatibility** — Updated version test to match current 0.3.0 version.

## [0.2.21] - 2026-02-16

### Added
- **Thinking protocol enforcement** — Orchestrator now validates Tech Lead responses start with `THINKING:` pattern and injects reminders when missing. Metrics track thinking pattern usage and quality.
- **New thinking event types** — Added `THINKING_STARTED`, `THINKING_COMPLETED`, `THINKING_REQUIRED`, `DELEGATION_DECISION`, and `REFLECTION` event types to core event system.
- **MCP client filtered stream** — Suppresses INFO/DEBUG logs from MCP servers while preserving errors and warnings, improving terminal output clarity.
- **Performance improvement framework** — Comprehensive performance improvement plan with working memory system, smart file reading patterns, structured thinking protocols, and delegation optimization added to copilot instructions.
- **Enhanced thinking protocols** — All agent prompts updated with mandatory thinking frameworks: Tech Lead uses 5-phase thinking protocol, specialists use 4-phase specialist thinking.
- **Delegation decision matrix** — Clear delegation guidelines added to Tech Lead prompt with task type to specialist mapping.

### Changed
- **MCP initialization in headless mode** — Fixed MCP server initialization in headless and interactive modes to ensure tools are available.
- **Orchestrator metrics** — Added thinking and delegation metrics tracking to orchestrator for performance monitoring.
- **Copilot instructions overhaul** — Updated `.github/copilot-instructions.md` with performance improvement strategies, thinking frameworks, and agent effectiveness guidelines.

### Fixed
- **MCP logging verbosity** — Reduced noise from MCP server logs in console output.
- **Test updates** — Updated tests for thinking protocol validation and MCP integration.

## [0.2.20] - 2026-02-16

### Added
- **Agent environment context injection** — All agents (Tech Lead, Planner, Explorer,
  Engineer) now receive a structured `<environment_context>` block in their system
  prompt containing: working directory, git root/branch/status, OS, shell, Python
  version, detected project type, top-level directory snapshot, and available CLI tools.
  This eliminates wasteful ad-hoc tool calls for environment discovery.
- New module `henchman.config.environment` with `EnvironmentContext` dataclass,
  `gather_environment()`, and `format_environment_block()`.
- `get_agent_prompt()` now accepts an optional `environment_context` parameter.
- 49 new tests for environment detection with 100% coverage on the new module.

## [0.2.19] - 2026-02-14

### Fixed
- **Headless and interactive modes crash** — After the REPL refactoring that
  extracted `ReplSessionManager`, both `_run_headless` and `_run_interactive`
  in `app.py` were overwriting `repl.session_manager` with a raw `SessionManager`,
  causing `AttributeError: 'SessionManager' object has no attribute 'record_user_message'`.
  Now properly uses the REPL's `set_session()` method.
- **Plan mode in headless/interactive** — Fixed `repl.session` references to use
  `repl.session_manager.current` throughout `app.py`.
- **Shell tool test stdin error** — Fixed `test_shell_tool_execution` to pass
  `auto_approve_tools=True` via `ReplConfig` constructor so the tool manager
  receives it during initialization.
- **All UI integration tests** — Updated 15 tests across `ui_integration/` and
  `smoke/` directories to work with the refactored REPL architecture
  (`UIRenderer`, `ReplSessionManager`, `ToolManager`).
- **Max delegation turns test** — Updated test to match the new default of 150.

### Added
- **`henchman` CLI alias** — Added `henchman` as a second entry point in `pyproject.toml`
  alongside `henchman`, so both commands work.

### Removed
- Stale `repl.py.backup` and `repl.py.backup2` files.

## [0.2.17] - 2026-02-14

### Added
- **4-agent team** — Expanded multi-agent system from 2 agents (Leader + Explorer)
  to 4 agents (Leader + Planner + Explorer + Engineer).
  - **Planner**: Architecture design, task decomposition, and structured planning.
    Has read/search/write/knowledge-graph tools but no `shell` — plans, doesn't execute.
  - **Engineer**: Code implementation, testing, and debugging. Has file manipulation
    and `shell` tools but no web tools — builds and verifies.
  - **Leader** prompt updated to reference and delegate to all three specialists.
  - Each agent has role-specific system prompts with appropriate cross-cutting rules.

## [0.2.16] - 2026-02-14

### Fixed
- **Knowledge graph validation hardened** — `kg_update` now rejects invalid
  `entity_type` and `relation_type` values via enum validation (both in JSON
  schema and at runtime). `add_relation` requires both source and target entities
  to exist before creating an edge — previously NetworkX silently created phantom
  nodes with no attributes, which crashed `kg_query` when iterating. Entity IDs
  are sanitized (stripped, reject empty/whitespace/None). All node iteration in
  `KnowledgeStore` now uses a safe deserializer that skips malformed nodes
  instead of crashing.

## [0.2.15] - 2026-02-14

### Fixed
- **`kg_query` and `kg_update` tools not available** — Both knowledge graph tools
  were exported from the builtins package and added to the explorer preset, but
  were never instantiated in `Repl._register_builtin_tools()`. The Tech Lead
  (and any agent using the parent registry) could not see them. Added both tools
  to the REPL registration list and added a regression test that verifies all
  expected built-in tools are present.

## [0.2.14] - 2026-02-14

### Fixed
- **Context length bug** — Agents were stuck at 8,000 tokens instead of using
  the model's full context window. The `Agent` now auto-detects `default_model`
  from the provider and sizes context to 85% of the model limit (e.g. 108,800
  tokens for DeepSeek's 128k window). Previously, both the Tech Lead and
  delegated agents received `model=None`, falling through to the 8,000-token
  safe default.

## [0.2.13] - 2026-02-13

### Added
- **Project knowledge graph** — Persistent, structured understanding of codebases
  that survives between agent sessions. Uses NetworkX for graph structure (entities,
  relations, graph algorithms) with JSON persistence.
  - Auto-populated from lightweight code analysis (imports, directory structure,
    top-level definitions) via `scanner.py`
  - Agent-curated additions via `kg_update` tool (observations, relations, decisions)
  - Query via `kg_query` tool: semantic search, neighbors, PageRank importance, stats
  - Storage: `~/.henchman/knowledge/<repo-hash>/graph.json`
  - Only activates for directories inside git repositories
- **`kg_query` tool** (READ) — 6 actions: search, get, neighbors, relations,
  important, stats. Auto-scans repository on first query if graph is empty.
- **`kg_update` tool** (WRITE) — 4 actions: add_entity, add_observation,
  add_relation, remove_entity. Auto-saves after every write.
- **`networkx>=3.0`** added as a dependency for graph algorithms
- **Multi-file context discovery** — `ContextLoader` now searches for
  `HENCHMAN.md`, `.github/copilot-instructions.md`, and `.gemini/GEMINI.md`
  (in that priority order) at every directory in the hierarchy. All matches
  are included, so projects with existing Copilot or Gemini instruction files
  get picked up automatically.
- New `DEFAULT_FILENAMES` constant and `filenames` constructor parameter for
  full control over which instruction files are discovered.

### Removed
- **Skills system** — The entire `src/henchman/skills/` module and `/skill`
  command have been removed. The skills system never worked reliably and has
  been replaced by the knowledge graph.

## [0.2.11] - 2026-02-13

### Changed
- **Consolidated agent team from 7 specialists to 2** — The previous 7-agent
  team (architect, coder, reviewer, tester, devops, researcher, technical_writer)
  has been replaced with a 2-agent model:
  - **Leader** — Combined tech lead + coder + architect. Does all planning,
    implementation, testing, and review directly. Can delegate research tasks
    to the Explorer.
  - **Explorer** — Research & documentation specialist. Investigates codebases,
    reads documentation, and writes findings to `.agent_tasks/<task-slug>/`.
- **Leader implements directly** — No more delegating implementation to a
  separate coder. The Leader reads, writes, edits, and tests code itself.
- **Old role templates preserved** — Custom agent configs using legacy role
  names (coder, architect, etc.) in `settings.yaml` still work via backward-
  compatible ROLE_TEMPLATES.

## [0.2.10] - 2026-02-13

### Removed
- **`send_message` tool** — Removed entirely. The tool did not work effectively
  for inter-agent communication and confused agents into using it instead of
  proper delegation. Removed from orchestrator, agent pool, prompts, and source.

### Changed
- **`max_delegation_turns` raised to 80** — Specialists now get 80 tool-call
  turns per delegation (up from 40) for complex tasks.
- **`.agent_tasks/` workspace convention** — All agent-generated artifacts
  (analysis scripts, design docs, research notes, validation reports) must now
  be placed in `.agent_tasks/<task-slug>/` instead of the repo root. Each task
  gets its own folder with a README, analysis/, docs/, and scripts/ subdirs.
  This convention is enforced via all role prompts.

## [0.2.9] - 2026-02-12

### Changed
- **Shell tool default timeout raised to 1 hour** — Default timeout changed from
  60 seconds to 3600 seconds (1 hour). Long-running data transformation jobs,
  builds, and test suites now complete without being killed.
- **`timeout=0` means no timeout** — Pass `timeout=0` to the shell tool for
  commands that may run indefinitely. The tool will wait until the command finishes.
- **Configurable shell timeout via settings** — `tools.shell_timeout` in
  `settings.yaml` is now wired into the ShellTool. Previously the config value
  was defined but never used.
- **Updated tool description** — Shell tool description now explicitly states
  that long-running commands are supported, helping the LLM choose appropriate
  timeout values.

## [0.2.7] - 2026-02-12

### Added
- **Acceptance Criteria (`done_when`)** — New field in `delegate_task` tool schema.
  The Tech Lead specifies an explicit, verifiable exit condition for each delegation
  (e.g., "pytest passes with 0 failures"). Specialists receive it as a `## Done When`
  section and stop working once the condition is met.
- **Per-Delegation Turn Limit** — New `max_delegation_turns` setting (default 25) in
  `AgentSettings`. Specialists are hard-stopped after this many tool-call turns.
  A wrap-up warning is injected 3 turns before the limit so the specialist can
  produce a final summary gracefully.
- **Cross-Delegation Handoff Notes** — When delegating to a specialist, the
  orchestrator auto-injects summaries from the last 5 completed delegations into
  the brief's background section. Specialists now know what prior agents accomplished
  without the Tech Lead having to manually relay everything.
- **Tool Error Aggregation** — Tool failures during a delegation are tracked and
  appended as a `⚠️ TOOL ERRORS` digest to the summary returned to the Tech Lead,
  making it immediately clear what went wrong.
- **Completion Report Parsing** — New `_parse_completion_report()` extracts
  `STATUS`, `FILES_MODIFIED`, `TESTS_RUN`, and `VERIFICATION` fields from the
  specialist's structured output. These are included in the `AGENT_COMPLETED` event
  data for richer downstream consumption.
- **Exit Condition Awareness in Specialist Prompts** — Updated
  `DELEGATION_SUMMARY_SCHEMA` to instruct specialists to respect the `## Done When`
  section and stop working once the exit condition is satisfied.

### Changed
- **Tech Lead Prompt — Delegation Results** — Updated to mention `⚠️ TOOL ERRORS`,
  structured `STATUS`/`FILES_MODIFIED`/`VERIFICATION` fields, and the mandatory
  `done_when` field in delegation calls.

## [0.2.6] - 2026-02-12

### Changed
- **Stall Detection Moved to Agent Class** — Stall detection (colon-ending
  and intent-phrase patterns) is now handled inside `Agent._check_for_stalling()`
  rather than the orchestrator.  The agent internally nudges itself and sets
  `_stall_failure` after `_max_stall_nudges` unsuccessful attempts.
- **Tech Lead Exempt from Stall Detection** — The Tech Lead has
  `stall_detection_enabled = False` so it can narrate plans and outline
  strategies before delegating without being killed by stall detection.
  Previously, the TL's planning narration triggered false positives.
- **Agent `stall_detection_enabled` Flag** — New boolean attribute on `Agent`
  (default `True`) that completely bypasses `_check_for_stalling` when `False`.
- **Stall Failure Reporting** — After max nudges, the orchestrator emits an
  `ERROR` event with a `STALL FAILURE` message and appends it to the Tech Lead's
  conversation so it can reassign or retry the task.

## [0.2.4] - 2026-02-12

### Changed
- **Clean-Start Delegations** — Specialist agents now have their conversation
  history cleared (`clear_history()`) before every delegation.  This eliminates
  context pollution between tasks and ensures each specialist operates from a
  self-contained brief provided by the Tech Lead.
- **Structured Delegation Brief** — `_run_delegation()` assembles a formatted
  brief with `## Task`, `## Requirements`, `## Relevant Files`, `## Background`,
  and `## Additional Context` sections instead of a flat string.
- **Enriched `delegate_task` Tool Schema** — Added `files` (array), `background`,
  and `requirements` fields alongside the existing `context`.  The Tech Lead
  prompt now instructs explicit population of these fields since specialists
  start with no prior memory.
- **Tech Lead Prompt — Clean Delegation Protocol** — Updated delegation
  instructions to emphasize that specialists have NO memory of prior delegations
  and all relevant information must be provided via the structured fields.

## [0.2.3] - 2026-02-12

### Added
- **Checklist-First Initiation** (Task 1) — `TaskLedger` now supports a structured
  checklist via `add_checklist_item()` and `check_item()`. Tech Lead prompt mandates
  generating a checklist before any delegation.
- **Mandatory Reconnaissance Phase** (Task 2) — All specialist prompts now include
  `RECON_FIRST_RULE` requiring read/search tools before any write/execute tools.
- **Verification Tool-Lock** (Task 3) — `TaskLedger` now has a `verified` flag and
  `mark_verified()` method. Coder, Tester, and DevOps prompts require running a
  verification shell command before declaring a task complete.
- **Periodic Role Anchoring** (Task 5) — Orchestrator injects a role-anchor
  reminder message every 8 tool calls to prevent prompt drift.
- **Scope Sentinel** (Task 6) — All agent prompts now include `SCOPE_SENTINEL`
  with explicit negative constraints forbidding out-of-scope work.
- **Structured Delegation Summaries** (Task 7) — All specialist prompts include
  `DELEGATION_SUMMARY_SCHEMA` requiring STATUS/FILES_MODIFIED/TESTS_RUN/VERIFICATION/SUMMARY
  output format.
- **Lint-on-Write** (Task 8) — Coder and DevOps prompts include `LINT_ON_WRITE_RULE`
  requiring automatic linting after every file edit.
- **Mission Recapitulation** (Task 9) — `TaskLedger.mission_recap()` provides a
  one-sentence status summary. Included in every ledger render. Tech Lead prompt
  requires reciting mission status before major actions.
- **Clean-Up Habit** (Task 10) — Coder, Tester, DevOps, and Tech Writer prompts
  include `CLEANUP_HABIT` requiring verification of no leftover debug/temp files.
- New `ChecklistItem` dataclass exported from `henchman.agents`

### Changed
- **Strict Specialists' Context** (Task 4) — `_run_delegation()` no longer injects
  broad `shared_context` into specialist prompts. Only explicit `context` from the
  delegating agent is passed, keeping specialists focused on their specific task.
- Role anchoring reminder in `get_agent_prompt()` enhanced with drift-detection
  instruction ("If you notice yourself drifting from your role, STOP and re-read
  this prompt").
- `TaskLedger.render()` now always includes mission recap line and optional
  checklist section.

## [0.2.2] - 2026-02-12

### Added
- **Task Ledger** for multi-agent orchestration
  - New `TaskLedger` class tracks delegations with goal, status, and summaries
  - Orchestrator auto-injects ledger snapshot into every delegation tool result
  - Tech Lead always has a structured "status board" even after context compaction
  - Ledger tracks completed, failed, and in-progress delegations with icons
  - Older entries auto-collapse when ledger grows large

### Fixed
- **Delegation summaries no longer doubled** — summary now extracted from agent
  message history instead of streamed content events that could duplicate
- **Delegation tool results now include actual summary** — previously returned
  hardcoded "Delegation completed." instead of the agent's real output
- TOOL_CALL_RESULT events for delegations now include `tool_name`, `success`,
  and truncated result (matching format of regular tool results)

### Changed
- Tech Lead system prompt updated with "Task Tracking" section instructing it
  to consult the 📋 TASK LEDGER as its single source of truth

## [0.2.1] - 2026-02-12

## [0.2.0] - 2026-02-11

### Added
- **Multi-Agent Dev Team Orchestration**
  - New `Orchestrator` system for coordinating multiple specialist agents
  - Event-driven `EventBus` for inter-agent communication
  - Specialist roles: Architect, Coder, Reviewer, Tester, DevOps, Researcher, and Technical Writer
  - `delegate_task` tool for Tech Lead to assign work to specialists
  - `send_message` tool for peer-to-peer agent collaboration
  - Configurable team presets and per-agent overrides in `settings.yaml`
  - Agent attribution in REPL and saved sessions
  - New `/agent` and `/team` slash commands for managing the team
  - `--agent` flag for direct agent targeting from CLI
  - `--team` flag to display team roster

### Changed
- **Core Architecture**
  - Refactored `Agent` class to support identities and source attribution in events
  - Extended session schema to track active agents and delegation logs
  - Composable system prompts for different roles
  - Scoped tool registries per agent for security and focus

## [0.1.14] - 2025-02-12

### Added
- **Enhanced PyPI Documentation**
  - Improved README.md with badges, better structure, and detailed examples
  - Added comprehensive CONTRIBUTING.md guide for contributors
  - Updated project metadata with better classifiers and documentation URLs
  - Added local documentation build script for offline viewing

### Changed
- **Project Metadata**
  - Updated pyproject.toml with additional Python version classifiers
  - Added more specific topic classifiers (AI, Scientific/Engineering)
  - Enhanced project URLs with better documentation links

### Fixed
- **Documentation**
  - Fixed documentation URLs to point to GitHub docs directory
  - Improved installation and usage instructions in README

## [0.1.11] - 2026-01-30

### Fixed

- **Rich Markup Escaping**
  - Fixed crash when error messages contain Rich-like markup tags (e.g., `[/dim]`)
  - Added `escape()` to `success()`, `info()`, `warning()`, `error()`, and `heading()` methods in OutputRenderer
  - Prevents `MarkupError` when displaying exception messages that contain bracket sequences

- **RAG Concurrency**
  - Fixed HNSW segment writer errors when multiple henchman instances start simultaneously
  - Lock is now acquired during `RagSystem.__init__` before ChromaDB initialization
  - Added retry logic (3 attempts with backoff) for transient ChromaDB errors
  - Instances that cannot acquire the lock switch to read-only mode gracefully

- **RAG Lock Function**
  - Fixed `acquire_rag_lock()` to return the `RagLock` object instead of the raw file handle
  - Prevents premature file closure when the lock object goes out of scope

- **Test Fixes**
  - Fixed RAG concurrency integration tests to properly mock all dependencies
  - Updated tests to use correct patch paths for module-level vs inline imports

## [0.1.10] - 2026-01-28

### Added

- **RAG Home Directory Storage**
  - RAG indices now stored in `~/.henchman/rag_indices/` instead of project directories
  - Automatic migration of existing project-based indices to home directory
  - Repository identification using git remote URLs and paths for consistent caching
  - New `/rag clear-all` command to clear ALL RAG indices
  - New `/rag cleanup` command to remove old project-based indices

### Changed

- **RAG Configuration**
  - Removed `index_path` setting from RagSettings
  - Added `cache_dir` setting for custom cache location (defaults to `~/.henchman/rag_indices/`)
  - Updated RAG system to use centralized cache instead of project-based storage

### Fixed

- **Code Quality**
  - Updated all RAG tests to work with new home directory storage
  - Fixed test assertions for manifest file locations
  - Enhanced test coverage for repository identification

## [0.1.9] - 2026-01-28

### Added

- **Error Handling & Recovery**
  - Added retry utilities with exponential backoff (`henchman.utils.retry`)
  - NETWORK tools now automatically retry on transient failures (ConnectionError, TimeoutError, OSError)
  - Configurable retry settings: `network_retries`, `retry_base_delay`, `retry_max_delay` in ToolSettings
  - `RetryConfig` dataclass for fine-grained retry configuration
  - `with_retry` decorator and `retry_async` function for custom retry logic

- **Batch Operations**
  - Added `execute_batch()` method to ToolRegistry for parallel tool execution
  - Independent tool calls now execute concurrently using `asyncio.gather()`
  - `BatchResult` dataclass with success/failure counts and individual results
  - Batch execution continues even when some tools fail

## [0.1.8] - 2024-01-XX

### Fixed

- **Safety & Stability**
  - Added safety limits to tools and compactor to prevent excessive resource usage
  - Switched safety limits from character-based to token-based for better model compatibility
  - Fixed indentation and syntax issues in tool implementations
  - Enhanced Python 3.10 compatibility (asyncio.TimeoutError handling)

- **User Interface**
  - Ctrl+C now exits cleanly when waiting for user input at the prompt (prompt_toolkit key binding)
  - Escape key now exits gracefully (no crash) when pressed on empty buffer
  - Added newline after Henchman finishes talking or after tool execution for improved readability

### Added

- **Testing & Quality**
  - Comprehensive integration tests for token management, tool calls, and validation
  - Enhanced test coverage for keyboard interrupt handling
  - Added tests for Ctrl+C and Escape key behavior in input bindings
  - GitHub Actions workflows for CI/CD pipeline

- **Documentation**
  - MkDocs documentation site with Material theme
  - Updated implementation plans and progress reports

## [0.1.7] - 2024-01-XX

### Fixed
- Switched safety limits from character-based to token-based
- Fixed indentation and syntax issues

## [0.1.6] - 2024-01-XX

### Fixed
- Added safety limits to tools and compactor

## [0.1.5] - 2024-01-XX

### Added
- Integration tests for token management

## [0.1.4] - 2024-01-XX

### Added
- Enhanced test coverage

## [0.1.3] - 2024-01-XX

### Added
- Keyboard interrupt handling improvements

## [0.1.2] - 2024-01-XX

### Added
- Python 3.10 compatibility fixes

## [0.1.1] - 2024-01-XX

### Added
- GitHub Actions workflows
- CHANGELOG file

## [0.1.0] - 2024-01-XX

### Added

- **Core Agent System**
  - Agent class with streaming event architecture
  - Event-driven processing (CONTENT, THOUGHT, TOOL_CALL_REQUEST, etc.)
  - Tool execution with confirmation workflow
  - Session management with auto-save

- **Provider System**
  - DeepSeek provider (default)
  - OpenAI-compatible base provider
  - Anthropic provider with native API
  - Ollama provider for local models
  - Provider registry for dynamic provider creation

- **Built-in Tools**
  - `read_file` - Read file contents
  - `write_file` - Write to files
  - `edit_file` - Surgical file edits
  - `ls` - List directory contents
  - `glob` - Find files by pattern
  - `grep` - Search file contents
  - `shell` - Execute shell commands
  - `web_fetch` - Fetch web pages

- **Interactive REPL**
  - Rich terminal UI with theming
  - Slash commands (/help, /quit, /clear, /tools, /chat)
  - File references with @filename syntax
  - Shell command execution with !command syntax
  - Session save/resume functionality

- **MCP Integration**
  - McpClient for single server connections
  - McpManager for multiple servers
  - Trusted/untrusted server modes
  - /mcp list and /mcp status commands

- **Extension System**
  - Extension base class
  - Entry point discovery
  - Local extension loading from ~/.henchman/extensions/
  - /extensions list command

- **Configuration**
  - Hierarchical YAML settings
  - Environment variable overrides
  - HENCHMAN.md context file discovery
  - Workspace and user-level settings

- **Documentation**
  - MkDocs site with Material theme
  - Getting started guide
  - Provider documentation
  - Tool reference
  - MCP integration guide
  - Extension development guide
  - API reference

- **Quality**
  - 100% test coverage (567+ tests)
  - Type hints throughout
  - Google-style docstrings
  - Ruff linting and formatting
  - Mypy type checking

### Changed

- Rebranded from henchman-cli to henchman-ai

[Unreleased]: https://github.com/mlg151/henchman-ai/compare/v0.4.1...HEAD
[0.4.1]: https://github.com/mlg151/henchman-ai/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/mlg151/henchman-ai/compare/v0.3.17...v0.4.0
[0.3.13]: https://github.com/mlg151/henchman-ai/compare/v0.3.11...v0.3.13
[0.3.11]: https://github.com/mlg151/henchman-ai/compare/v0.3.10...v0.3.11
[0.3.10]: https://github.com/mlg151/henchman-ai/compare/v0.3.9...v0.3.10
[0.3.9]: https://github.com/mlg151/henchman-ai/compare/v0.3.8...v0.3.9
[0.3.8]: https://github.com/mlg151/henchman-ai/compare/v0.3.7...v0.3.8
[0.3.7]: https://github.com/mlg151/henchman-ai/compare/v0.3.3...v0.3.7
[0.3.3]: https://github.com/mlg151/henchman-ai/compare/v0.3.2...v0.3.3
[0.3.2]: https://github.com/mlg151/henchman-ai/compare/v0.3.1...v0.3.2
[0.3.1]: https://github.com/mlg151/henchman-ai/compare/v0.2.22...v0.3.1
[0.2.22]: https://github.com/mlg151/henchman-ai/compare/v0.2.21...v0.2.22
[0.2.21]: https://github.com/mlg151/henchman-ai/compare/v0.2.20...v0.2.21
[0.2.20]: https://github.com/mlg151/henchman-ai/compare/v0.2.19...v0.2.20
[0.1.8]: https://github.com/mlg151/henchman-ai/compare/v0.1.7...v0.1.8
[0.1.7]: https://github.com/mlg151/henchman-ai/compare/v0.1.6...v0.1.7
[0.1.6]: https://github.com/mlg151/henchman-ai/compare/v0.1.5...v0.1.6
[0.1.5]: https://github.com/mlg151/henchman-ai/compare/v0.1.4...v0.1.5
[0.1.4]: https://github.com/mlg151/henchman-ai/compare/v0.1.3...v0.1.4
[0.1.3]: https://github.com/mlg151/henchman-ai/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/mlg151/henchman-ai/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/mlg151/henchman-ai/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/mlg151/henchman-ai/releases/tag/v0.1.0
