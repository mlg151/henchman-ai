# Bug Tracker

## Legend
- **Severity:** critical | high | medium | low
- **Status:** open | in-progress | resolved

---

## Open Bugs

### BUG-005: `asyncio.gather()` without `return_exceptions=True` causes silent cancellation of parallel tool calls
- **Severity:** high
- **Status:** open
- **Found:** 2026-05-31
- **File:** `src/henchman/cli/tool_executor.py:269`
- **Replication:**
  1. Have two or more auto-approved tool calls in a single turn (e.g., two `read_file` calls), so they land in `to_parallel`.
  2. Have one of them throw an exception (e.g., `shell` with a non-existent command, or `read_file` on a missing path).
  3. Observe that ALL remaining parallel tool calls are silently cancelled -- their results are lost.
- **Description:**
  `execute_tool_calls` at line 269 calls `asyncio.gather(*[...])` with the default `return_exceptions=False`. When one parallel tool call raises, `asyncio.gather` immediately cancels all other pending futures in that gather, then re-raises the exception. The cancelled tool call results are replaced by `_ensure_all_tool_calls_have_response` in the `finally` block with the generic string "Tool execution was interrupted or cancelled." Worse, the exception propagates up through the agent call stack, causing the current turn to end with an error even though the other (cancelled) tool calls might have succeeded.
  
  The fix is to add `return_exceptions=True` to the gather and handle each result individually, logging errors per-tool-call rather than letting a single failure cancel unrelated work.

### BUG-006: Background delegation Task not tracked -- cannot be cancelled or awaited on shutdown
- **Severity:** medium
- **Status:** open
- **Found:** 2026-05-31
- **File:** `src/henchman/agents/delegation_manager.py:102`
- **Replication:**
  1. Call `DelegationManager.start_delegation()` to start a delegation.
  2. The returned `asyncio.Task` reference is discarded immediately.
  3. On application shutdown, there is no way to await or cancel the in-flight delegation.
  4. The `cancel_delegation()` method on line 263 cancels the `task_future` but not the `asyncio.Task` itself, so `_run_delegation` continues executing until its next `await` point, wasting resources.
- **Description:**
  `start_delegation()` at line 102 does `asyncio.create_task(self._run_delegation(...))` but stores nothing. The task object is lost. This means:
  - Shutdown code cannot wait for pending delegations to finish.
  - The task cannot be cancelled if the user wants to abort a delegation.
  - `cancel_delegation()` (line 263-283) only cancels `task.task_future` (the result future), not the actual `asyncio.Task` running `_run_delegation`. The coroutine keeps running in the background until it reaches an await point where it gets CancelledError from loop shutdown.

### BUG-007: Race condition on `ongoing_tasks` dict between `cancel_delegation` and `_run_delegation`
- **Severity:** medium
- **Status:** open
- **Found:** 2026-05-31
- **File:** `src/henchman/agents/delegation_manager.py:160-161, 263-283`
- **Replication:**
  1. Start a delegation via `start_delegation`.
  2. Call `cancel_delegation()` while `_run_delegation` is running (e.g., by having a timer fire or user action).
  3. `cancel_delegation` moves the task from `ongoing_tasks` to `completed_tasks`.
  4. `_run_delegation` finishes its async-for loop and reaches line 160-161 where it does an unconditional `del self.ongoing_tasks[delegation_task.id]`.
  5. A `KeyError` is raised because `cancel_delegation` already removed the entry from `ongoing_tasks`.
- **Description:**
  `cancel_delegation` (line 263-283) and `_run_delegation` (line 109-176) both modify `self.ongoing_tasks` and `self.completed_tasks` without any synchronization. The normal-path code at line 161 does an unconditional `del self.ongoing_tasks[delegation_task.id]`, which will `KeyError` if `cancel_delegation` deleted the same key first. Note: `cancel_delegation` is currently dead code (never called anywhere in the codebase), but the method exists as a public API and would trigger this bug if ever invoked.

### BUG-008: Fire-and-forget `create_task` for MCP connection cannot be awaited on shutdown
- **Severity:** low
- **Status:** open
- **Found:** 2026-05-31
- **File:** `src/henchman/cli/core_init.py:172`
- **Replication:**
  Run the application and then trigger a shutdown while MCP servers are still connecting. The connection task is silently cancelled by the event loop.
- **Description:**
  Line 172 does `asyncio.create_task(connect_mcp())` and discards the task reference. There is no mechanism to await the MCP connection task during shutdown. If the application exits while MCP servers are still connecting, the task is cancelled by the event loop with no chance for cleanup.

### BUG-009: RAG indexing task stored but never cancelled or awaited on shutdown
- **Severity:** low
- **Status:** open
- **Found:** 2026-05-31
- **File:** `src/henchman/cli/app.py:569-570`
- **Replication:**
  Run the JSON output mode (which creates a Repl with RAG indexing). Shut down the app. The RAG indexing task runs in the background until the event loop cancels it.
- **Description:**
  `_start_rag_indexing` stores the task on `repl._rag_index_task` via `object.__setattr__`, but this attribute is never read, cancelled, or awaited anywhere in the codebase. On shutdown, the indexing task runs to completion or is cancelled by the event loop, whichever comes first.

### BUG-010: `_safe_create_task` accumulates unreferenceable background tasks
- **Severity:** low
- **Status:** open
- **Found:** 2026-05-31
- **File:** `src/henchman/cli/output_handler.py:270, 319-334`
- **Replication:**
  Run the REPL for an extended session with RAG enabled. Each turn that shows status triggers `_start_rag_indexing`, which spawns a new unreferenceable task. Over time, these accumulate.
- **Description:**
  `_safe_create_task` (line 319-334) creates an `asyncio.Task` each time it is called and does not store the reference. The `_on_done` callback logs errors, but there is no mechanism to cancel, await, or even enumerate these tasks. The `_start_rag_indexing` method (line 267) calls `_safe_create_task` each time turn status is displayed (line 308), meaning multiple indexing tasks are spawned over a session without any deduplication or cleanup.

### BUG-011: Zip/Tar Slip in Plugin Archive Extraction
- **Severity:** high
- **Status:** open
- **Found:** 2026-05-31
- **File:** `src/henchman/extensions/plugin_installer.py:257, 266`
- **Replication:**
  1. Configure a plugin with `source=URL` pointing to a crafted archive.
  2. Run plugin installation.
  3. If the archive contains entries with `../` path components, they are written outside the target directory.
- **Description:**
  `_extract_archive_file` calls `zipfile.extractall(target_dir)` and `tarfile.extractall(target_dir)` with no path traversal check. A malicious plugin archive with entries like `../../.ssh/authorized_keys` can overwrite arbitrary files. This is classic Zip Slip / Tar Slip. Archive extraction should validate each member's resolved path stays within the target directory.

### BUG-012: Missing SSRF Protection in Plugin Archive Download
- **Severity:** medium
- **Status:** open
- **Found:** 2026-05-31
- **File:** `src/henchman/extensions/plugin_installer.py:201-226`
- **Replication:**
  1. Configure a plugin with `source_url=http://169.254.169.254/latest/meta-data/`
  2. Run plugin installation.
  3. The download makes an HTTP request to the internal endpoint.
- **Description:**
  `_download_archive()` downloads plugin archives using `aiohttp` without calling `validate_url()` from `tools/security.py:123`. That function blocks SSRF by rejecting private IPs, loopback, and link-local addresses. The `web_fetch` tool uses `validate_url()` properly, but this code path bypasses it entirely.

### BUG-013: Shell Metacharacter Injection via Sudo Command Rewrite
- **Severity:** high
- **Status:** open
- **Found:** 2026-05-31
- **File:** `src/henchman/tools/builtins/shell.py:355-365`
- **Replication:**
  1. Call the shell tool with `sudo ; echo PWNED`.
  2. `sanitize_command()` passes it (contains no backticks or `$()`).
  3. `_is_sudo_command()` returns True.
  4. The command is rewritten: `sudo -A ; echo PWNED`.
  5. `echo PWNED` executes as current user outside sudo.
- **Description:**
  `_create_process` rewrites sudo commands via string concatenation: `f"sudo -A {command[_SUDO_PREFIX_LEN:]}"`. `sanitize_command()` blocks backticks and `$()` but does NOT block shell metacharacters like `;`, `&&`, `||`, or `|`. This allows command chaining through the sudo rewrite. A command like `sudo && rm -rf /` would be rewritten to `sudo -A && rm -rf /`, executing `rm` outside sudo.

### BUG-014: Two load_settings Implementations Diverge on Env-Var Handling
- **Severity:** high
- **Status:** open
- **Found:** 2026-05-31
- **File:** `src/henchman/config/__init__.py:44` vs `src/henchman/config/settings.py:137`
- **Replication:**
  1. Set `HENCHMAN_PROVIDER=openai` in the environment.
  2. Run `henchman chat`.
  3. The env var is silently ignored — the provider from settings.yaml is used instead.
- **Description:**
  There are two independent `load_settings` functions. The one in `config/__init__.py` (used by app.py, api/server.py, chat_serve, etc.) does NOT support `HENCHMAN_SETTINGS_PATH`, `HENCHMAN_PROVIDER`, or `HENCHMAN_MODEL` env vars. The version in `config/settings.py` that supports these env vars is dead code — only `save_settings` from that module is imported. Users configuring documented env vars get them silently ignored.

### BUG-015: Missing Bounds Validation on Numeric Config Fields
- **Severity:** medium
- **Status:** open
- **Found:** 2026-05-31
- **File:** `src/henchman/config/schema.py`
- **Replication:**
  1. Set `max_tokens: 0` or `shell_timeout: -1` in settings.yaml.
  2. Schema validation passes.
  3. Downstream code hits division-by-zero or hangs indefinitely.
- **Description:**
  Fields like `max_tokens`, `compaction_threshold`, `importance_threshold`, `shell_timeout`, `max_delegation_depth`, `max_delegation_turns`, `shared_context_max_tokens`, `top_k`, `chunk_size`, and `chunk_overlap` all lack Pydantic `ge=`/`le=` constraints. Negative or zero values pass validation silently, causing crashes or infinite loops downstream.

### BUG-016: RAG chunk_overlap Can Exceed chunk_size
- **Severity:** medium
- **Status:** open
- **Found:** 2026-05-31
- **File:** `src/henchman/config/schema.py` (RagSettings)
- **Replication:**
  1. Set `chunk_size: 100` and `chunk_overlap: 200` in RAG config.
  2. Validation passes.
  3. Downstream chunking produces zero-length or negative-length chunks.
- **Description:**
  No `@model_validator` ensures `chunk_overlap < chunk_size`. With overlap exceeding size, text splitters produce empty or negative-span chunks, silently corrupting the RAG index.

### BUG-017: McpServerConfig.command Lacks Non-Empty Validation
- **Severity:** medium
- **Status:** open
- **Found:** 2026-05-31
- **File:** `src/henchman/config/schema.py` (McpServerConfig)
- **Replication:**
  1. Configure an MCP server with `command: ""`.
  2. Schema validation passes.
  3. Connection attempt fails with an opaque subprocess error.
- **Description:**
  The `command` field has no `min_length` constraint or validator. Empty string `""` or whitespace `"   "` passes validation but cannot be executed, causing confusing errors at connection time.

### BUG-018: RAG Index Migration Silently Swallows Failures
- **Severity:** medium
- **Status:** open
- **Found:** 2026-05-31
- **File:** `src/henchman/rag/repo_id.py:179, 190`
- **Replication:**
  1. Have an old-format RAG index that needs migration.
  2. Trigger migration with insufficient disk space or permissions.
  3. `shutil.copytree()` / `shutil.copy2()` fails silently.
  4. Function returns False with no log entry — caller cannot distinguish "no migration needed" from "migration failed."
- **Description:**
  `migrate_old_index()` catches all exceptions from `shutil.copytree()` and `shutil.copy2()` with `except Exception: pass`. If migration fails due to disk-full or permissions, the failure is invisible. Old data may remain in a stale format with no diagnostic.

### BUG-019: Message Summarization Failures Are Completely Silent
- **Severity:** medium
- **Status:** open
- **Found:** 2026-05-31
- **File:** `src/henchman/utils/compaction.py:852, 1091`
- **Replication:**
  1. Have the LLM provider down or rate-limited during summarization.
  2. Summarization fails silently with `except Exception: pass`.
  3. System degrades to simple message dropping with zero observability.
- **Description:**
  Both `summarize()` (line 852) and `_try_summarize()` (line 1091) catch all exceptions with `except Exception: pass`. No logger call, no warning. If the LLM provider is unavailable, context quality silently degrades over time.

### BUG-020: Extension Loading Failures Lose Traceback
- **Severity:** medium
- **Status:** open
- **Found:** 2026-05-31
- **File:** `src/henchman/extensions/manager.py:63, 82, 93, 114`
- **Replication:**
  1. Install a third-party extension with a bug in its import path.
  2. The extension fails to load.
  3. Only `str(exc)` is logged — no traceback.
  4. The extension author cannot diagnose the failure.
- **Description:**
  Four handlers in `_load_entry_point_extension`, `_try_load_extension_dir`, `_try_instantiate_ext_class`, and `_load_extension_from_file_impl` use `logger.warning("...: %s", exc)` without `exc_info=True`. Only the exception message is logged; the full traceback is lost, making third-party extension debugging nearly impossible.

### BUG-021: REPL Main Loop Does Not Log Exception Tracebacks
- **Severity:** medium
- **Status:** open
- **Found:** 2026-05-31
- **File:** `src/henchman/cli/repl.py:705`
- **Replication:**
  1. Trigger an exception during REPL operation.
  2. Only `str(e)` is displayed to the console.
  3. No traceback is logged anywhere.
- **Description:**
  `repl.py` has no `logging.getLogger()` at all. `_run_turn_no_input()` catches `Exception` but only prints the error message to the renderer. `traceback.format_exc()` is not called, `logger.exception()` is not called. Developers have zero visibility into unexpected REPL failures.

### BUG-022: LspService Subprocesses Orphaned on Garbage Collection
- **Severity:** high
- **Status:** open
- **Found:** 2026-05-31
- **File:** `src/henchman/lsp/service.py:69-84, 146-163`
- **Replication:**
  1. Create an `LspService`, call `start_server("some-server")`.
  2. Let the `LspService` go out of scope without calling `stop_server()`.
  3. The LSP subprocess continues running as an orphan consuming OS resources.
- **Description:**
  `LspService` manages LSP subprocesses via `asyncio.create_subprocess_exec()` stored in `_LspRuntime.sessions`. There's no `__del__` finalizer or `atexit` handler. When the `LspService` is garbage collected, subprocesses become orphaned — consuming process table entries and pipe file descriptors indefinitely.

### BUG-023: EventBus Has No Unsubscribe — Subscribers Accumulate Permanently
- **Severity:** medium
- **Status:** open
- **Found:** 2026-05-31
- **File:** `src/henchman/core/eventbus.py:14-23`
- **Replication:**
  1. Subscribe to events from per-turn or per-session lifecycle code.
  2. The handler is appended to `self._subscribers[event_name]`.
  3. There is no mechanism to remove it.
  4. Over process lifetime, handlers and their captured references accumulate.
- **Description:**
  `EventBus` provides `subscribe()` (appends to `defaultdict(list)`) but has no `unsubscribe()`. Handlers registered per-turn or per-session retain references to agents, sessions, etc., preventing garbage collection. Over many turns, subscriber lists grow without bound.

### BUG-024: ChatManager._user_histories Grows Unbounded
- **Severity:** medium
- **Status:** open
- **Found:** 2026-05-31
- **File:** `src/henchman/chat/manager.py:85, 497-503`
- **Replication:**
  1. Run a Discord bot for days/weeks.
  2. Each user's conversation history grows indefinitely.
  3. Memory usage increases linearly with conversation volume.
- **Description:**
  `_user_histories` stores the entire conversation history for every user as `list[dict[str, Any]]` with no size cap, `maxlen`, eviction policy, or periodic cleanup. Over long-running bot sessions, memory grows without bound.

### BUG-025: ChatManager._user_agents Grows Unbounded with No Idle Eviction
- **Severity:** medium
- **Status:** open
- **Found:** 2026-05-31
- **File:** `src/henchman/chat/manager.py:84, 121-191`
- **Replication:**
  1. Run a Discord bot with many users.
  2. Each new user creates a new Agent instance with full tool registry.
  3. Agents and their conversation histories accumulate forever.
- **Description:**
  `_user_agents` maps `user_id -> Agent` with no eviction strategy. Each agent holds a `messages` list, `ToolRegistry`, and `ModelProvider`. After thousands of unique users, memory grows linearly. No idle-timeout or LRU eviction exists.

### BUG-026: Unhandled KeyError when agent config references unregistered provider
- **Severity:** medium
- **Status:** open
- **Found:** 2026-05-31
- **File:** `src/henchman/agents/pool.py:193`
- **Replication:**
  1. Configure an agent with `provider: "non_existent_provider"` in settings.yaml.
  2. Start the application.
  3. `AgentPool._resolve_provider` calls `self.provider_registry.get(config.provider)`.
  4. `ProviderRegistry.get()` raises `KeyError` for unregistered names.
  5. Crash propagates through orchestration startup.
- **Description:**
  `ProviderRegistry.get()` raises `KeyError` when the provider name is not registered — it does NOT return `None`. The call site at `pool.py:192-193` guards against `None`/empty-string for `config.provider` but does NOT validate that the provider name is actually registered. Any misconfigured provider name triggers an unhandled `KeyError`. Should either use `self.provider_registry._providers.get(config.provider)` (returns None) or wrap in `try/except KeyError` to fall back to default.

### BUG-027: Unsafe type cast in ToolMessage.__init__ accepts arbitrary non-string values
- **Severity:** low
- **Status:** open
- **Found:** 2026-05-31
- **File:** `src/henchman/cli/textual_widgets.py:476-478`
- **Replication:**
  1. Pass a truthy non-string value (e.g., `[1,2]` or `42`) as the `thought` argument to `ToolMessage.__init__`.
  2. The condition `tool_call is None and thought and not isinstance(thought, str)` evaluates True.
  3. `typing.cast("ToolCallProtocol", thought)` returns the value unchanged (no-op at runtime).
  4. Value stored as `self._tool_call` with zero structural validation.
- **Description:**
  `typing.cast()` performs no runtime conversion — it's a type-checker hint. Any truthy non-string value passes through and is stored as `self._tool_call`. Downstream code guards with `hasattr`/`getattr`, so it doesn't crash, but silently accepts mis-typed data producing garbled display. A runtime `isinstance` check or structural validation should replace the cast.

---

## Resolved Bugs

### BUG-004: MCP manager silently swallows server connection failures
- **Severity:** medium
- **Status:** resolved
- **Resolved:** 2026-05-31
- **Found:** 2026-05-31
- **File:** `src/henchman/mcp/manager.py:63`
- **Root Cause:**
  `MCPManager.connect_all()` used bare `except Exception: continue` with no logging. The module had no logger configured. MCP server connection failures were completely invisible.
- **Fix:**
  1. Added `import logging` and module-level `logger = logging.getLogger(__name__)`
  2. Changed `except Exception: continue` to `except Exception: logger.warning("Failed to connect to MCP server %r", server_name, exc_info=True); continue`
- **Verification:** All 10 MCP tests pass, full suite 2773 passed.

### BUG-003: `DelegationManager.wait_for_delegation` raises exception when delegation failed
- **Severity:** medium
- **Status:** resolved
- **Resolved:** 2026-05-31
- **Found:** 2026-05-31
- **File:** `src/henchman/agents/delegation_manager.py:253-254`
- **Root Cause:**
  When `_run_delegation` catches an exception, it calls `task_future.set_exception(e)` and sets `task.completed = True`. The fast path in `wait_for_delegation` (line 253: `task.completed and task.task_future.done()`) then calls `task_future.result()` which re-raises the original exception, violating the method contract to return `tuple[str, bool]`.
- **Fix:**
  Wrapped the completed-task fast path in `try/except (asyncio.CancelledError, Exception)` that converts exceptions to `(f"Delegation failed: {error_msg}", False)` tuples. The `asyncio.wait_for` path is left unwrapped so `TimeoutError` propagates naturally as documented.
- **Verification:** All 17 delegation manager tests pass, full suite 2773 passed.

### BUG-002: `test_skill_tool_rejects_unknown_skill` test assertion too strict
- **Severity:** low
- **Status:** resolved
- **Resolved:** 2026-05-31
- **Found:** 2026-05-31
- **File:** `tests/tools/test_tier1_tools.py:167`
- **Root Cause:**
  The test asserted `"Available skills: planner"` in the error message, but `SkillTool._list_available_skills()` merges both handler-backed skills AND catalog-discovered skills (from `SkillCatalog.list_skills()`). The catalog picks up real project skills like `discord-message`, so the full message read `"Available skills: discord-message, planner."`.
- **Fix:**
  Changed the assertion to `assert "planner" in result.content` -- verifying the registered handler name appears in the available-skills list without assuming it's the only entry.
- **Verification:** All 3 SkillTool tests pass, full suite 2773 passed, 0 failed.

### BUG-001: `SerializableDataclass.from_dict` fails on nested dataclasses with `| None` syntax
- **Severity:** high
- **Status:** resolved
- **Resolved:** 2026-05-31
- **File:** `src/henchman/utils/serialization.py`
- **Root Cause:**
  `_deserialize_val` checked `origin is Union` (imported from `typing`), but Python 3.10+ `X | None` syntax produces `types.UnionType`, not `typing.Union`. Nested dataclass fields declared with `| None` were never deserialized -- the raw dict was returned instead of the dataclass instance.
- **Fix:**
  1. Added `import types` at top of file
  2. Changed `if origin is Union:` to `if origin in (Union, types.UnionType):` on line 62
- **Verification:** All 12 contract tests pass, full test suite (2483+ tests) has no regression from this change.
