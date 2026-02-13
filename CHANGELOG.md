# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.12] - 2026-02-13

### Added
- **Multi-file context discovery** — `ContextLoader` now searches for
  `HENCHMAN.md`, `.github/copilot-instructions.md`, and `.gemini/GEMINI.md`
  (in that priority order) at every directory in the hierarchy. All matches
  are included, so projects with existing Copilot or Gemini instruction files
  get picked up automatically.
- New `DEFAULT_FILENAMES` constant and `filenames` constructor parameter for
  full control over which instruction files are discovered.

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

- Rebranded from mlg-cli to henchman-ai

[Unreleased]: https://github.com/mlg151/henchman-ai/compare/v0.1.8...HEAD
[0.1.8]: https://github.com/mlg151/henchman-ai/compare/v0.1.7...v0.1.8
[0.1.7]: https://github.com/mlg151/henchman-ai/compare/v0.1.6...v0.1.7
[0.1.6]: https://github.com/mlg151/henchman-ai/compare/v0.1.5...v0.1.6
[0.1.5]: https://github.com/mlg151/henchman-ai/compare/v0.1.4...v0.1.5
[0.1.4]: https://github.com/mlg151/henchman-ai/compare/v0.1.3...v0.1.4
[0.1.3]: https://github.com/mlg151/henchman-ai/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/mlg151/henchman-ai/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/mlg151/henchman-ai/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/mlg151/henchman-ai/releases/tag/v0.1.0
