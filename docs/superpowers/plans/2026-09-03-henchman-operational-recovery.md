# Henchman Operational Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore every documented, supported local-first Henchman runtime boundary and prove the result on Python 3.11 through 3.14.

**Architecture:** Keep the existing Click, ToolManager, Textual, FastAPI, and packaging architecture. Repair entry-point routing, construct and bind runtime dependencies before tool registration, resolve discovery from the live registry, replace TUI-local stubs with existing service modules, and give the API truthful version/liveness/readiness semantics.

**Tech Stack:** Python 3.11–3.14, Click, AnyIO/asyncio, Textual, FastAPI, pytest, Ruff, mypy, uv, MkDocs, ChromaDB.

**Spec:** `docs/superpowers/specs/2026-09-03-operational-recovery-design.md`

## Global Constraints

- Supported CPython versions are exactly 3.11, 3.12, 3.13, and 3.14.
- Project-local state writes only to `.henchman`; legacy casing is read-only fallback.
- Capability truth comes from `src/henchman/cli/commands/discovery_capabilities.py` and the live tool registry.
- Remote marketplaces, Slack runtime, cron execution, and the broader Tier 8 platform remain explicitly unshipped.
- Preserve all unrelated worktree changes; do not reset, clean, or mechanically format unrelated files.
- Do not create commits automatically because target files already contain approved uncommitted recovery work; report the final diff for user-controlled staging.
- For every behavior change: add one regression, run it red, apply the minimal implementation, run it green, then run the focused neighboring suite.

---

### Task 1: Restore Console Entry-Point Routing

**Files:**
- Create: `tests/cli/test_console_entrypoint.py`
- Modify: `src/henchman/cli/app.py`
- Modify: `README.md`
- Modify: `docs/getting-started.md`

**Interfaces:**
- Consumes: `cli: click.Group`, `chat_command(**kwargs)`, and console scripts pointing to `henchman.cli.app:main`.
- Produces: `_normalize_cli_argv(argv: list[str], *, known_commands: Collection[str]) -> list[str]`; `main()` always invokes `cli()` after assigning the normalized argv.

- [ ] **Step 1: Write failing entry-point regressions**

Add behavior tests with literal expectations:

```python
def test_normalize_no_args_to_chat() -> None:
    assert _normalize_cli_argv(["henchman"], known_commands={"chat", "doctor"}) == [
        "henchman",
        "chat",
    ]


@pytest.mark.parametrize("option", ["-p", "--prompt", "--tui", "--plan"])
def test_normalize_legacy_chat_options(option: str) -> None:
    argv = ["henchman", option, "hello"] if option in {"-p", "--prompt"} else ["henchman", option]
    assert _normalize_cli_argv(argv, known_commands={"chat", "doctor"})[1] == "chat"


def test_normalize_preserves_root_and_explicit_commands() -> None:
    assert _normalize_cli_argv(["henchman", "--help"], known_commands={"chat"}) == [
        "henchman",
        "--help",
    ]
    assert _normalize_cli_argv(["henchman", "doctor"], known_commands={"doctor"}) == [
        "henchman",
        "doctor",
    ]
    assert _normalize_cli_argv(["henchman", "not-a-command"], known_commands={"chat"}) == [
        "henchman",
        "not-a-command",
    ]


def test_module_entrypoint_rejects_unknown_command() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "henchman", "not-a-command"],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode != 0
    assert "No such command 'not-a-command'" in result.stderr
```

Also assert `"xyztest" not in cli.commands` and invoke `main()` with a patched `sys.argv` plus Click's real command parsing to prove the no-argument normalization reaches `chat` rather than returning early.

- [ ] **Step 2: Run the regressions and confirm RED**

Run:

```bash
uv run --extra dev python -m pytest --no-cov tests/cli/test_console_entrypoint.py -q
```

Expected: collection/import fails because `_normalize_cli_argv` does not exist, and the subprocess assertion shows the unknown command currently exits zero.

- [ ] **Step 3: Implement narrow argv normalization**

Add a pure helper near `main()`:

```python
_ROOT_OPTIONS = frozenset({"--help", "-h", "--version"})
_LEGACY_CHAT_OPTIONS = frozenset(
    {"-p", "--prompt", "-a", "--agent", "--team", "--output-format", "--plan", "--debug", "-y", "--yes", "--tui"}
)


def _normalize_cli_argv(argv: list[str], *, known_commands: Collection[str]) -> list[str]:
    normalized = list(argv)
    if len(normalized) == 1:
        normalized.append("chat")
    elif normalized[1] in _LEGACY_CHAT_OPTIONS:
        normalized.insert(1, "chat")
    return normalized
```

Remove `xyztest_command`. In `main()`, preserve the Textual inspection branch, replace the broad unknown-command rewrite with `_normalize_cli_argv`, and always call `cli()`. Keep root options and explicit subcommands untouched so Click owns their errors.

Update command examples to canonical `henchman chat -p ...`. Replace nonexistent `--provider` and `--model` examples with supported `henchman config set ...` plus `henchman chat -p ...` sequences verified against the config command.

- [ ] **Step 4: Verify GREEN and neighboring CLI behavior**

Run:

```bash
uv run --extra dev python -m pytest --no-cov tests/cli/test_console_entrypoint.py tests/cli/test_cli_smoke.py tests/cli/test_app_coverage_100.py -q
uv run --extra dev python -m ruff check src/henchman/cli/app.py tests/cli/test_console_entrypoint.py
uv run --extra dev python -m ruff format --check src/henchman/cli/app.py tests/cli/test_console_entrypoint.py
uv run --no-sync henchman --help
uv run --no-sync henchman definitely-nope
```

Expected: tests and Ruff pass; help exits zero; the unknown command exits nonzero with Click's command error.

- [ ] **Step 5: Record the scoped checkpoint**

Run `git diff --check -- src/henchman/cli/app.py tests/cli/test_console_entrypoint.py README.md docs/getting-started.md` and retain the uncommitted diff for the final user-controlled staging step.

---

### Task 2: Bind Runtime Dependencies Before Builtin Registration

**Files:**
- Modify: `tests/cli/test_core_init.py`
- Modify: `src/henchman/cli/core_init.py`

**Interfaces:**
- Consumes: `ToolManager.bind_runtime(project_root: Path, session_manager: object | None, mcp_manager: object | None) -> None` and `ToolManager.register_builtin_tools() -> None`.
- Produces: `create_core_context()` returns a registry whose runtime-bound tools reference the same session and MCP managers stored in `CoreContext`.

- [ ] **Step 1: Write a failing real-registry MCP regression**

Add a test that patches only the external MCP factory and slow plugin loading, creates a real `ToolManager` through `create_core_context()`, and executes the real registered MCP tool:

```python
@pytest.mark.anyio
async def test_create_core_context_binds_configured_mcp_manager_before_registration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    fake_mcp = FakeMcpManager()
    settings = Settings(mcp_servers={"local": McpServerConfig(command="echo")})

    with patch.object(McpManager, "create_from_settings", return_value=fake_mcp):
        context = create_core_context(FakeProvider(), settings=settings)

    result = await context.tool_registry.execute("mcp", {"action": "status"})
    assert result.success is True
    assert "local" in result.content
    assert "MCP manager unavailable" not in result.content
    assert context.mcp_manager is fake_mcp
```

Use a complete fake implementing the `configs`, `clients`, `list_servers()`, and discovery members read by `MCPTool`. Add one project-scoped assertion by executing `schedule_cron` create/list under `tmp_path`, and assert its state is written below `tmp_path/.henchman`.

- [ ] **Step 2: Run the test and confirm RED**

Run:

```bash
uv run --extra dev python -m pytest --no-cov tests/cli/test_core_init.py::test_create_core_context_binds_configured_mcp_manager_before_registration -q
```

Expected: `result.success` is false and content contains `MCP manager unavailable`.

- [ ] **Step 3: Reorder dependency construction**

In `create_core_context()`:

1. Create `mcp_manager` from settings first.
2. Create `session_manager = ReplSessionManager(auto_save=True)`.
3. Create `ToolManager`, set auto-approval, call `bind_runtime(project_root=Path.cwd(), session_manager=session_manager, mcp_manager=mcp_manager)`, then register builtins.
4. Continue constructing plugins, event bus, and orchestrator.
5. Return the already-created `session_manager`.

Do not create a second session manager or mutate tool internals after registration.

- [ ] **Step 4: Verify GREEN and runtime neighbors**

Run:

```bash
uv run --extra dev python -m pytest --no-cov tests/cli/test_core_init.py tests/cli/test_core_init_bug008_mcp_task.py tests/tools/test_tier2_tools.py tests/tools/test_tier5_tools.py tests/tools/test_tier6_mcp_tools.py tests/tools/test_tier6_task_tools.py -q
uv run --extra dev python -m ruff check src/henchman/cli/core_init.py tests/cli/test_core_init.py
uv run --extra dev python -m mypy src/henchman/cli/core_init.py
```

Expected: all focused tests and static checks pass without project-owned warnings.

- [ ] **Step 5: Record the scoped checkpoint**

Run `git diff --check -- src/henchman/cli/core_init.py tests/cli/test_core_init.py` and retain the uncommitted diff.

---

### Task 3: Make Tool Search Reflect the Live Registry

**Files:**
- Modify: `tests/tools/test_tier1_tools.py`
- Modify: `src/henchman/tools/builtins/tier1_tools.py`

**Interfaces:**
- Consumes: `ToolRegistry.list_tools() -> list[str]`, `ToolRegistry.get(name: str) -> Tool | None`, and the existing metadata-only `_ToolClassResolver` fallback.
- Produces: `ToolSearchTool.bind_runtime(*, tool_registry: ToolRegistry | None = None, **_: object) -> None`; bound execution searches current tool instances, including later registrations.

- [ ] **Step 1: Write a failing dynamic-registration regression**

Create a real registry with `ToolSearchTool`, register a synthetic `DynamicKnowledgeTool` afterward, and execute search through the registry:

```python
@pytest.mark.anyio
async def test_tool_search_finds_tools_registered_after_runtime_binding() -> None:
    registry = ToolRegistry()
    search = ToolSearchTool()
    search.bind_runtime(tool_registry=registry)
    registry.register(search)
    registry.register(DynamicKnowledgeTool())

    result = await registry.execute("tool_search", {"query": "dynamic knowledge"})

    assert result.success is True
    assert "dynamic_knowledge" in result.content
```

Add a second assertion that a separate registry without the dynamic tool returns no match, proving there is no static false advertisement.

- [ ] **Step 2: Run the regression and confirm RED**

Run:

```bash
uv run --extra dev python -m pytest --no-cov tests/tools/test_tier1_tools.py::test_tool_search_finds_tools_registered_after_runtime_binding -q
```

Expected: `ToolSearchTool` has no `bind_runtime` method or does not return the dynamically registered tool.

- [ ] **Step 3: Implement live instance resolution**

Store an optional registry reference. At execution time, resolve tools with:

```python
def _resolve_tools(self) -> tuple[Tool, ...]:
    if self._tool_registry is None:
        return tuple(_instantiate_tool(tool_class) for tool_class in self._tool_class_resolver())
    return tuple(
        tool
        for name in self._tool_registry.list_tools()
        if (tool := self._tool_registry.get(name)) is not None
    )
```

Use those instances both for names and rendered metadata. Preserve the standalone class-resolver constructor contract and deterministic sorted rendering. Accept extra runtime binding keywords so `ToolManager` can bind it alongside other builtins.

- [ ] **Step 4: Verify GREEN and discovery neighbors**

Run:

```bash
uv run --extra dev python -m pytest --no-cov tests/tools/test_tier1_tools.py tests/cli/test_tool_manager_tier1.py tests/cli/test_doctor_command.py tests/cli/test_help_command.py tests/rag/test_system.py -q
uv run --extra dev python -m ruff check src/henchman/tools/builtins/tier1_tools.py tests/tools/test_tier1_tools.py
uv run --extra dev python -m mypy src/henchman/tools/builtins/tier1_tools.py
```

Expected: all focused tests pass, static builtin fallback behavior remains intact, and a later registration appears in live search.

- [ ] **Step 5: Record the scoped checkpoint**

Run `git diff --check -- src/henchman/tools/builtins/tier1_tools.py tests/tools/test_tier1_tools.py` and retain the uncommitted diff.

---

### Task 4: Replace Textual Workspace Stubs With Real Services

**Files:**
- Modify: `tests/cli/test_tier10_textual_ui.py`
- Modify: `src/henchman/cli/textual_mixins.py`

**Interfaces:**
- Consumes: `henchman.advanced.TaskService`, `henchman.skills.SkillCatalog`, `henchman.team.TeamWorkspaceService`, `henchman.team.BridgeSessionService`, and `henchman.core.session_export.export_as_markdown`.
- Produces: `_WorkspaceMixin` reads real current-project persisted data and calls `BridgeSessionService.list_bridges(workspace_id=<id>)` with its keyword-only argument.

- [ ] **Step 1: Write failing behavior regressions through the mixin**

Use `tmp_path` and `monkeypatch.chdir(tmp_path)`. Create a real task record (or a persisted task fixture matching `TaskService`'s public schema), a `.henchman/skills/review.yaml` skill, and a real team workspace plus bridge. Instantiate the app/mixin with real widgets or patch only `_query_one_or_none` to return concrete `TaskListWidget`, `SkillPanel`, and `TeamPanel` instances. Call `_refresh_workspace_widgets()` and assert rendered text contains the task title, `review`, and workspace name.

Add a bridge regression:

```python
entries = textual_app._build_bridge_dialog_entries()
assert any("remote-session-1" in entry for entry in entries)
```

Add a real session export regression and assert the output file contains `## Conversation` and the literal user message. These tests must fail against the local classes that always return `[]` and `"# Export"`.

- [ ] **Step 2: Run the regressions and confirm RED**

Run:

```bash
uv run --extra dev python -m pytest --no-cov tests/cli/test_tier10_textual_ui.py -q
```

Expected: persisted task/skill/team/bridge entries are absent and exported Markdown lacks the conversation.

- [ ] **Step 3: Import the real services and fix the bridge call**

At module scope import:

```python
from henchman.advanced import TaskService
from henchman.core.session_export import export_as_markdown
from henchman.skills import SkillCatalog
from henchman.team import BridgeSessionService, TeamWorkspaceService
```

Delete the five local stub definitions. Change bridge listing to `bridge_service.list_bridges(workspace_id=ws.workspace_id)`. Keep the existing UI rendering and file-write error paths.

- [ ] **Step 4: Verify GREEN and Textual neighbors**

Run:

```bash
uv run --extra dev python -m pytest --no-cov tests/cli/test_tier10_textual_ui.py tests/cli/test_textual_mixins.py tests/cli/test_textual_integration.py tests/ui_integration -q
uv run --extra dev python -m ruff check src/henchman/cli/textual_mixins.py tests/cli/test_tier10_textual_ui.py
uv run --extra dev python -m mypy src/henchman/cli/textual_mixins.py
```

Expected: real-data regressions and neighboring Textual suites pass with no project-owned async/resource warnings.

- [ ] **Step 5: Record the scoped checkpoint**

Run `git diff --check -- src/henchman/cli/textual_mixins.py tests/cli/test_tier10_textual_ui.py` and retain the uncommitted diff.

---

### Task 5: Add Truthful API Version, Liveness, and Readiness

**Files:**
- Modify: `tests/api/test_api.py`
- Modify: `tests/contracts/test_api_contracts.py`
- Modify: `src/henchman/api/server.py`
- Modify: `src/henchman/api/endpoints/health.py`
- Modify: `docs/api.md`

**Interfaces:**
- Consumes: `henchman.version.VERSION` and global API `state.agent`/`state.settings`.
- Produces: `GET /v1/health` returns a `HealthResponse` with truthful status; `GET /v1/ready` returns HTTP 200 or 503 using the same response schema.

- [ ] **Step 1: Update tests first with literal runtime expectations**

Replace stale `0.3.11` assertions with `VERSION` imported independently from `henchman.version`. Add:

```python
def test_health_is_degraded_when_agent_is_missing(self, patch_state: Any) -> None:
    patch_state.agent = None
    response = client.get("/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "degraded"
    assert response.json()["agent_ready"] is False


def test_readiness_returns_503_without_agent(self, patch_state: Any) -> None:
    patch_state.agent = None
    response = client.get("/v1/ready")
    assert response.status_code == 503
    assert response.json()["status"] == "degraded"


def test_readiness_returns_200_with_agent(self, patch_state: Any) -> None:
    response = client.get("/v1/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
```

Assert `app.version`, `/`, `/v1/health`, and the response-model default all equal `VERSION`. Extend the API contract test so both health routes validate against `api/health_response`.

- [ ] **Step 2: Run the tests and confirm RED**

Run:

```bash
uv run --extra dev python -m pytest --no-cov tests/api/test_api.py::TestHealthEndpoints tests/contracts/test_api_contracts.py -q
```

Expected: stale version assertions fail, missing-agent health reports `ok`, and `/v1/ready` returns 404.

- [ ] **Step 3: Implement shared health payload semantics**

Import `VERSION` in both API modules. Replace every `0.3.11` version default or response with `VERSION`. Add a private payload builder in `health.py`:

```python
def _build_health_response() -> HealthResponse:
    agent_ready = state.agent is not None
    return HealthResponse(
        status="ok" if agent_ready else "degraded",
        version=VERSION,
        provider=state.settings.providers.default if state.settings else None,
        agent_ready=agent_ready,
    )
```

Return it from `/health`. Add `/ready` with `responses={503: {"model": HealthResponse}}`; return the model when ready and a `JSONResponse(status_code=503, content=payload.model_dump())` otherwise. Do not expose provider exceptions.

Document `/v1/health` as liveness and `/v1/ready` as readiness, including the 503 condition.

- [ ] **Step 4: Verify GREEN and API neighbors**

Run:

```bash
uv run --extra dev python -m pytest --no-cov tests/api tests/contracts/test_api_contracts.py -q
uv run --extra dev python -m ruff check src/henchman/api/server.py src/henchman/api/endpoints/health.py tests/api/test_api.py tests/contracts/test_api_contracts.py
uv run --extra dev python -m mypy src/henchman/api
```

Expected: API and contract tests pass; liveness is 200/degraded without an agent and readiness is 503/degraded.

- [ ] **Step 5: Record the scoped checkpoint**

Run `git diff --check -- src/henchman/api/server.py src/henchman/api/endpoints/health.py tests/api/test_api.py tests/contracts/test_api_contracts.py docs/api.md` and retain the uncommitted diff.

---

### Task 6: Align Release Truth and Prove the Final Artifact

**Files:**
- Modify: `.github/copilot-instructions.md`
- Modify: `.github/workflows/ci.yml`
- Modify: `RELEASE_CHECKLIST.md`
- Modify: `CHANGELOG.md`
- Modify: `README.md`
- Modify: `docs/getting-started.md`
- Test: existing full test tree and built artifacts

**Interfaces:**
- Consumes: project metadata in `pyproject.toml`, `uv.lock`, console entry points, and the completed runtime repairs.
- Produces: truthful contributor/release instructions and CI artifact smoke coverage for both wheel and source distribution.

- [ ] **Step 1: Add or update CI contract assertions before workflow edits**

Extend the existing CI/package contract test to load `.github/workflows/ci.yml` and assert literal supported versions `3.11`, `3.12`, `3.13`, `3.14`, wheel smoke versions `3.11`, `3.14`, both console entry points, and installation of both a wheel and an sdist in clean environments. The mutation caught is removing either artifact path or a supported interpreter from CI.

- [ ] **Step 2: Run the CI contract and confirm RED for sdist coverage**

Run the specific CI/package contract test selected in Step 1 with `--no-cov`.

Expected: it fails because the workflow currently smoke-installs only the wheel.

- [ ] **Step 3: Align workflow and durable documentation**

Extend the packaging job to install the built sdist in an isolated Python 3.11 environment and run version/help/import probes. Preserve wheel smoke on 3.11 and 3.14, including Chroma. Replace references to nonexistent `./scripts/ci.sh` with the actual `uv run --extra dev python -m ...` commands. Change release checklist interpreter wording from 3.10–3.12 to 3.11–3.14 and check the already-proven 90% branch floor only after the final coverage command succeeds.

Update the changelog with the operational boundary repairs. Keep the beta/local-first exclusions explicit.

- [ ] **Step 4: Run focused release gates**

Run:

```bash
uv lock --check
uv run --extra dev python -m ruff check src tests
uv run --extra dev python -m mypy src/
uv run --extra dev mkdocs build --strict
git diff --check
```

Expected: all commands exit zero. Formatting is checked only for files touched by this plan; repository-wide pre-existing format drift is reported separately.

- [ ] **Step 5: Run the full test and coverage gate**

Run:

```bash
uv run --extra dev python -m pytest --cov=henchman --cov-branch --cov-report=term-missing --cov-fail-under=90
```

Expected: the full suite passes, branch coverage is at least 90%, and no project-owned RuntimeWarning, ResourceWarning, or PytestUnraisableExceptionWarning is emitted.

- [ ] **Step 6: Build and inspect final distributions**

Build into a fresh `mktemp -d` directory using `uv build --out-dir <temp>/dist`. Inspect wheel and sdist metadata for `Requires-Python: >=3.11`, expected dependencies, both console scripts, and `henchman/py.typed`. Install the wheel into clean Python 3.11 and 3.14 environments and the sdist into clean Python 3.11. Run:

```bash
henchman --version
mlg --version
henchman --help
henchman doctor
henchman definitely-nope
```

The first four probes must behave according to their contract; the unknown command must exit nonzero. Run an ephemeral Chroma add/count/query probe and an API TestClient liveness/readiness probe from the installed artifact.

- [ ] **Step 7: Perform the requirement-by-requirement completion audit**

Map all nine completion criteria in the approved spec to direct command output, runtime behavior, or artifact inspection. Treat missing external credentials and unavailable Serena/Discord services as disclosed unverified integrations, not as passing evidence. Do not mark the goal complete until every supported local-first criterion has direct proof.
