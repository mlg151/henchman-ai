# Henchman Operational Recovery Design

## Objective

Restore Henchman-AI's documented, supported local-first product surface to an operational state on Python 3.11 through 3.14. The completed work must be proven through real console entry points, runtime integration tests, API probes, static analysis, the full test suite, and clean installed-wheel smoke tests.

The repository's current product truth remains authoritative: remote marketplaces, a Slack runtime, cron execution, and the broader Tier 8 remote operations platform are future surfaces and are not part of this recovery. Existing commands and documentation must describe those boundaries truthfully.

## Constraints

- Support CPython 3.11, 3.12, 3.13, and 3.14.
- Preserve the canonical project-local `.henchman` directory and use legacy casing only as a read fallback.
- Derive discovery, help, and doctor classifications from `src/henchman/cli/commands/discovery_capabilities.py` plus the live runtime registry.
- Preserve argv-only command execution and manual upgrade guidance for unknown installation methods.
- Keep local settings synchronization file-based through `config import` and `config export`.
- Do not expose placeholder-only builtin exports as operational tools.
- Preserve unrelated user changes in the existing dirty worktree.

## Architecture

The recovery keeps the existing Click CLI, core context, Textual application, FastAPI service, tool registry, and service modules. It repairs the boundaries between those components instead of adding parallel implementations.

Runtime construction becomes dependency-first: load settings, construct the configured MCP manager and session manager, bind the project/session/MCP references to `ToolManager`, register builtins, and only then construct the orchestrator. Dynamic tools such as `rag_search` continue to register after their backing service is initialized, while `tool_search` reads the live registry so its results reflect those additions.

The Textual workspace imports the real project-local services already used by builtin tools. The API uses the package version constant everywhere and distinguishes process liveness from agent readiness. CLI entry-point compatibility is handled by a narrow argv normalization step before Click parses commands.

## CLI Entry-Point Contract

`henchman` and `mlg` use the same `main()` entry point.

- No arguments start the interactive `chat` command.
- Root `--help` and `--version` remain root options.
- Legacy chat options such as `-p`, `--prompt`, `--tui`, and `--plan` are normalized by prepending `chat`, then Click performs normal validation.
- Explicit subcommands are passed to Click unchanged.
- Unknown command names are not reinterpreted as chat input; Click returns a nonzero error.
- `main()` always invokes Click after normalization. It must not return immediately after editing `sys.argv`.
- The committed `xyztest` diagnostic command is removed from the public command set.
- Documentation uses the canonical `henchman chat -p ...` form. Provider and model selection examples use supported configuration surfaces rather than nonexistent root flags.

The console-entry regression suite must invoke the actual `main()` boundary with controlled `sys.argv`, not only invoke the underlying Click group with `CliRunner`.

## Runtime Dependency Binding

`create_core_context()` constructs runtime dependencies in this order:

1. Construct the configured `McpManager`, or `None` when no MCP servers are configured.
2. Construct `ReplSessionManager`.
3. Construct `ToolManager`, bind `Path.cwd()`, the session manager, and the MCP manager, then register builtins.
4. Construct plugins, event bus, and orchestrator from the fully initialized tool registry.
5. Return the same bound objects in `CoreContext`.

This ordering ensures every builtin with `bind_runtime()` receives the real dependency before it is registered. A core-context integration test must execute the registered `mcp` status tool against a fake configured manager and prove that the result does not report `MCP manager unavailable`. Tests must also prove that project-scoped and session-scoped tools receive their runtime references.

## Live Tool Discovery

`ToolSearchTool` keeps its metadata-only builtin resolver for standalone use, but gains runtime binding to a `ToolRegistry`. When bound, it resolves tool instances from the registry at execution time. This resolver is live rather than snapshotted, so tools registered later by RAG or plugins appear without rebuilding the search tool.

Capability classification receives the exact live tool names. A regression test registers a synthetic dynamic tool after `tool_search`, searches for it, and verifies that it appears. Another test verifies that an absent dynamic tool is not advertised.

## Textual Workspace Services

`src/henchman/cli/textual_mixins.py` stops defining local placeholder versions of:

- `TaskService`
- `SkillCatalog`
- `TeamWorkspaceService`
- `BridgeSessionService`
- `export_as_markdown`

It imports the existing implementations from `henchman.advanced`, `henchman.skills`, `henchman.team`, and `henchman.core.session_export`. Workspace refreshes use the current project root through those services. Bridge listing uses the real keyword-only `workspace_id` interface. Session export uses the real Markdown serializer and continues writing the selected session export to the current project directory.

Integration tests populate real temporary `.henchman` task/team state and local skill definitions, run the workspace refresh helpers, and assert the user-visible widget entries. An export test asserts actual session content and metadata rather than the former `# Export` placeholder.

## API Health and Version Semantics

All API version fields import `henchman.version.VERSION`; no endpoint or model hardcodes an older release.

- `GET /v1/health` is a liveness endpoint. It always returns HTTP 200 while the process is serving, reports `agent_ready`, and reports `status="ok"` only when the agent exists; otherwise it reports `status="degraded"`.
- `GET /v1/ready` is a readiness endpoint. It returns the same structured health payload with HTTP 200 when the agent exists and HTTP 503 when provider/agent startup failed.
- Provider construction failure remains visible through readiness without exposing secrets or exception internals in the response.
- The root response, FastAPI metadata, response-model defaults, health response, and readiness response all report the package version.

The basic API remains a local beta surface. This recovery does not claim that Tier 8 authentication, OAuth, billing, telemetry, proxying, or distributed state are production-ready.

## Error Handling

- CLI parse failures remain Click errors with nonzero exit codes and actionable option/command text.
- Missing provider configuration remains an explicit user-facing error in chat and a degraded/not-ready API state.
- Configured MCP startup may degrade individual servers, but the registered MCP management tool always has the manager reference needed to report status and remediation.
- TUI data-service failures are surfaced through the existing UI error path; empty state is reserved for genuinely empty persisted data.
- RAG remains optional at runtime, but when initialization succeeds its search tool must be discoverable through the live registry.

## Documentation and Release Gates

Documentation and checklists must agree on Python 3.11 through 3.14, canonical CLI syntax, the 90% branch-coverage floor, and the local-first capability boundary. References to a nonexistent `scripts/ci.sh` are replaced with the actual `uv run` commands unless that script is added as an independently tested artifact.

CI must continue to run Ruff, mypy, and pytest across supported Python versions, build distributions, and smoke-install the wheel on Python 3.11 and 3.14. The recovery extends artifact verification to the source distribution or documents why the wheel is the only published artifact. The final local proof includes:

- focused red/green tests for every repaired boundary;
- `uv lock --check`;
- Ruff checks for touched and full source/test trees;
- mypy over `src/`;
- the full pytest suite with the configured 90% branch-coverage gate;
- MkDocs strict build;
- wheel metadata/content inspection;
- clean wheel installs on Python 3.11 and 3.14;
- real `henchman` and `mlg` command probes;
- API liveness/readiness probes;
- ephemeral Chroma indexing and query smoke coverage.

Formatting is enforced on files changed by this recovery. Repository-wide formatting drift outside the repair is reported separately rather than mechanically rewriting hundreds of unrelated user-owned files.

## Completion Criteria

The recovery is complete only when all of the following are true:

1. Supported Python versions, dependency metadata, lockfile, and CI agree.
2. Both installed console entry points route no-argument, legacy prompt, explicit subcommand, help/version, and unknown-command cases correctly.
3. A configured MCP manager is reachable from the registered MCP tools in a real core context.
4. Runtime tool search reflects tools registered after initial builtin construction, including a successfully initialized RAG tool.
5. Textual task, skill, team, bridge, and export surfaces use real persisted services and return real data.
6. Every API version source agrees with the package version, liveness reports degradation accurately, and readiness fails when no agent is available.
7. Current documentation and release instructions contain no contradictory supported-version or CLI claims.
8. Focused, static, full-suite, documentation, coverage, and clean-artifact gates pass with no project-owned warnings.
9. The completion audit maps each supported capability claim to direct runtime or artifact evidence; weak or skipped external-service evidence is disclosed rather than treated as proof.
