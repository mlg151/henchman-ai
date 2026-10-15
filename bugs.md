# Bug Tracker

## Legend
- **Severity:** critical | high | medium | low
- **Status:** open | in-progress | resolved

---

## Resolved Bugs

### BUG-006: Background delegation Task not tracked -- cannot be cancelled or awaited on shutdown
- **Severity:** medium
- **Status:** resolved
- **Resolved:** 2026-05-31
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
- **Status:** resolved
- **Found:** 2026-05-31
- **Resolved:** 2026-05-31
- **File:** `src/henchman/agents/delegation_manager.py:160-161, 263-283`
- **Replication:**
  1. Start a delegation via `start_delegation`.
  2. Call `cancel_delegation()` while `_run_delegation` is running.
  3. `cancel_delegation` moves the task from `ongoing_tasks` to `completed_tasks`.
  4. `_run_delegation` finishes and does unconditional `del self.ongoing_tasks[delegation_task.id]`.
  5. `KeyError` is raised because `cancel_delegation` already removed the entry.
- **Root Cause:**
  Unconditional `del self.ongoing_tasks[delegation_task.id]` at line 161 with no synchronization.
- **Fix:**
  Replaced `del self.ongoing_tasks[delegation_task.id]` with `self.ongoing_tasks.pop(delegation_task.id, None)` so the removal gracefully handles the key already being gone.

### BUG-008: Fire-and-forget `create_task` for MCP connection cannot be awaited on shutdown
- **Severity:** low
- **Status:** resolved
- **Found:** 2026-05-31
- **Resolved:** 2026-05-31
- **File:** `src/henchman/cli/core_init.py:172`
- **Replication:**
  Run the application and then trigger a shutdown while MCP servers are still connecting. The connection task is silently cancelled by the event loop.
- **Root Cause:**
  `asyncio.create_task(connect_mcp())` discards the task reference. No mechanism to await MCP connection during shutdown.
- **Fix:**
  1. Added `background_tasks: set[asyncio.Task]` field to `CoreContext` dataclass.
  2. `initialize_mcp` stores the MCP connection task in `context.background_tasks`.
  3. Done callback auto-removes completed tasks from the set.
  4. Shutdown code can iterate `background_tasks` to cancel/await pending connection tasks.

### BUG-009: RAG indexing task stored but never cancelled or awaited on shutdown
- **Severity:** low
- **Status:** resolved
- **Found:** 2026-05-31
- **Resolved:** 2026-05-31
- **File:** `src/henchman/cli/app.py:569-570`, `src/henchman/cli/repl.py:367`
- **Replication:**
  Run the JSON output mode (which creates a Repl with RAG indexing). Shut down the app. The RAG indexing task runs in the background until the event loop cancels it.
- **Root Cause:**
  `_start_rag_indexing` stores the task on `repl._rag_index_task` via `object.__setattr__`, but this attribute is never read, cancelled, or awaited anywhere.
- **Fix:**
  1. Added `_cancel_rag_task()` helper in `app.py` to cancel any pending indexing task.
  2. `_start_rag_indexing` now calls `_cancel_rag_task(repl)` before creating a new task.
  3. Added `_cancel_rag_task(repl)` calls at the end of each headless processing function (`_run_headless_text`, `_run_headless_json_format`, `_run_headless_json_complete`).
  4. Added RAG indexing task cancellation and await in `Repl.run()`'s finally block.

### BUG-010: `_safe_create_task` accumulates unreferenceable background tasks
- **Severity:** low
- **Status:** resolved
- **Found:** 2026-05-31
- **Resolved:** 2026-05-31
- **File:** `src/henchman/cli/output_handler.py:267-290`
- **Replication:**
  Run the REPL for an extended session with RAG enabled. Each turn that shows status triggers `_start_rag_indexing`, which spawns a new unreferenceable task. Over time, these accumulate.
- **Root Cause:**
  `_safe_create_task` (line 319-334) creates an `asyncio.Task` each call without storing a reference. No mechanism to cancel, await, or enumerate these tasks.
- **Fix:**
  1. Replaced `_safe_create_task` call in `_start_rag_indexing` with direct `asyncio.create_task`.
  2. Added `_cancel_existing_rag_task()` method that cancels any previous indexing task before creating a new one, preventing accumulation.
  3. Stored the task as `self._rag_index_task` so it can be cancelled/awaited on shutdown.
  4. Added `_on_rag_index_done` static method for error logging on task completion.

### BUG-011: Zip/Tar Slip in Plugin Archive Extraction
- **Severity:** high
- **Status:** resolved
- **Resolved:** 2026-05-31
- **Found:** 2026-05-31
- **File:** `src/henchman/extensions/plugin_installer.py:238-267`
- **Replication:**
  1. Configure a plugin with `source=URL` pointing to a crafted archive.
  2. Run plugin installation.
  3. If the archive contains entries with `../` path components, they are written outside the target directory.
- **Description:**
  `_extract_archive_file` calls `zipfile.extractall(target_dir)` and `tarfile.extractall(target_dir)` with no path traversal check. A malicious plugin archive with entries like `../../.ssh/authorized_keys` can overwrite arbitrary files. This is classic Zip Slip / Tar Slip. Archive extraction should validate each member's resolved path stays within the target directory.

### BUG-012: Missing SSRF Protection in Plugin Archive Download
- **Severity:** medium
- **Status:** resolved
- **Resolved:** 2026-05-31
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
- **Status:** resolved
- **Resolved:** 2026-05-31
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
- **Status:** resolved
- **Resolved:** 2026-05-31
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
- **Status:** resolved
- **Resolved:** 2026-05-31
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
- **Status:** resolved
- **Resolved:** 2026-05-31
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
- **Status:** resolved
- **Resolved:** 2026-05-31
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
- **Status:** resolved
- **Found:** 2026-05-31
- **File:** `src/henchman/rag/repo_id.py:179, 190`
- **Replication:**
  1. Have an old-format RAG index that needs migration.
  2. Trigger migration with insufficient disk space or permissions.
  3. `shutil.copytree()` / `shutil.copy2()` fails silently.
  4. Function returns False with no log entry — caller cannot distinguish "no migration needed" from "migration failed."
- **Description:**
  `migrate_old_index()` catches all exceptions from `shutil.copytree()` and `shutil.copy2()` with `except Exception: pass`. If migration fails due to disk-full or permissions, the failure is invisible. Old data may remain in a stale format with no diagnostic.
- **Resolution:**
  Added `import logging` / `logger` to `repo_id.py`. Replaced bare `pass` in both except blocks with `logger.warning(...)` calls including the source and destination paths. Moved `import shutil` to module level. Tests: `tests/rag/test_repo_id_silent_failures.py` (4 tests).

### BUG-019: Message Summarization Failures Are Completely Silent
- **Severity:** medium
- **Status:** resolved
- **Found:** 2026-05-31
- **File:** `src/henchman/utils/compaction.py:852, 1091`
- **Replication:**
  1. Have the LLM provider down or rate-limited during summarization.
  2. Summarization fails silently with `except Exception: pass`.
  3. System degrades to simple message dropping with zero observability.
- **Description:**
  Both `summarize()` (line 852) and `_try_summarize()` (line 1091) catch all exceptions with `except Exception: pass`. No logger call, no warning. If the LLM provider is unavailable, context quality silently degrades over time.
- **Resolution:**
  Added `import logging` / `logger` to `compaction.py`. Replaced bare `pass` in `_generate_summary_with_provider` and `_attempt_summarization` with `logger.warning(...)` calls. Tests: `tests/utils/test_compaction_silent_failures.py` (3 tests).

### BUG-020: Extension Loading Failures Lose Traceback
- **Severity:** medium
- **Status:** resolved
- **Found:** 2026-05-31
- **File:** `src/henchman/extensions/manager.py:63, 82, 93, 114`
- **Replication:**
  1. Install a third-party extension with a bug in its import path.
  2. The extension fails to load.
  3. Only `str(exc)` is logged — no traceback.
  4. The extension author cannot diagnose the failure.
- **Description:**
  Four handlers in `_load_entry_point_extension`, `_try_load_extension_dir`, `_try_instantiate_ext_class`, and `_load_extension_from_file_impl` use `logger.warning("...: %s", exc)` without `exc_info=True`. Only the exception message is logged; the full traceback is lost, making third-party extension debugging nearly impossible.
- **Resolution:**
  Changed all four `logger.warning(...)` calls to pass `exc_info=True` and removed the redundant `%s` for the exception argument. Logs now include full tracebacks. Tests: `tests/extensions/test_manager_tracebacks.py` (4 tests).

### BUG-021: REPL Main Loop Does Not Log Exception Tracebacks
- **Severity:** medium
- **Status:** resolved
- **Found:** 2026-05-31
- **File:** `src/henchman/cli/repl.py:705`
- **Replication:**
  1. Trigger an exception during REPL operation.
  2. Only `str(e)` is displayed to the console.
  3. No traceback is logged anywhere.
- **Description:**
  `repl.py` has no `logging.getLogger()` at all. `_run_turn_no_input()` catches `Exception` but only prints the error message to the renderer. `traceback.format_exc()` is not called, `logger.exception()` is not called. Developers have zero visibility into unexpected REPL failures.
- **Resolution:**
  Added `import logging` / `logger` to `repl.py`. Added `logger.exception(...)` calls in both exception handlers (MCP connection error and general REPL turn error). Tests: `tests/cli/test_repl_exception_logging.py` (2 tests).

### BUG-022: LspService Subprocesses Orphaned on Garbage Collection
- **Severity:** high
- **Status:** resolved
- **Resolved:** 2026-05-31
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
- **Status:** resolved
- **Resolved:** 2026-05-31
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
- **Status:** resolved
- **Resolved:** 2026-05-31
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
- **Status:** resolved
- **Resolved:** 2026-05-31
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
- **Status:** resolved
- **Resolved:** 2026-05-31
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
- **Status:** resolved
- **Resolved:** 2026-05-31
- **Found:** 2026-05-31
- **File:** `src/henchman/cli/textual_widgets.py:476-478`
- **Replication:**
  1. Pass a truthy non-string value (e.g., `[1,2]` or `42`) as the `thought` argument to `ToolMessage.__init__`.
  2. The condition `tool_call is None and thought and not isinstance(thought, str)` evaluates True.
  3. `typing.cast("ToolCallProtocol", thought)` returns the value unchanged (no-op at runtime).
  4. Value stored as `self._tool_call` with zero structural validation.
- **Description:**
  `typing.cast()` performs no runtime conversion — it's a type-checker hint. Any truthy non-string value passes through and is stored as `self._tool_call`. Downstream code guards with `hasattr`/`getattr`, so it doesn't crash, but silently accepts mis-typed data producing garbled display. A runtime `isinstance` check or structural validation should replace the cast.

### BUG-028: Agent errors leave stale entries in ChatPane._active, corrupting subsequent streams
- **Severity:** high
- **Status:** resolved
- **Fix:** Added `for name in list(chat._active): chat.finish_agent_stream(name)` in the `except asyncio.CancelledError`, `except Exception`, and `finally` blocks of `process_user_input` (`textual_mixins.py`). This ensures all active agent streams are finalized regardless of how processing exits.
- **Found:** 2026-05-31
- **Resolved:** 2026-05-31
- **File:** `src/henchman/cli/textual_mixins.py`

### BUG-029: No finish_thinking_stream method -- _active_thinking entries accumulate across turns
- **Severity:** high
- **Status:** resolved
- **Fix:** Added `finish_thinking_stream(agent_name)` method to `ChatPane` (`textual_widgets.py`) that pops the agent from `_active_thinking`. This parallels the existing `finish_agent_stream` and prevents thinking chunks from accumulating across turns.
- **Found:** 2026-05-31
- **Resolved:** 2026-05-31
- **File:** `src/henchman/cli/textual_widgets.py`

### BUG-030: StatusBar and Footer both dock to bottom with reversed stacking
- **Severity:** medium
- **Status:** resolved
- **Fix:** Swapped the compose order in `HenchmanTextualApp.compose()` (`textual_app.py`) so `Footer()` is yielded before `StatusBar()`. With both widgets docking to bottom, the first child (Footer now) occupies the bottommost position, placing keybinding hints at the very bottom and status text above.
- **Found:** 2026-05-31
- **Resolved:** 2026-05-31
- **File:** `src/henchman/cli/textual_app.py`

### BUG-031: HenchmanTextArea on_key handler is dead code that duplicates BINDINGS
- **Severity:** medium
- **Status:** resolved
- **Fix:** Removed the `on_key`, `_handle_enter_key`, and `_handle_shift_enter_key` methods from `HenchmanTextArea` (`textual_widgets.py`). The `BINDINGS` class variable already handles `enter` (submit) and `shift+enter` (newline) correctly.
- **Found:** 2026-05-31
- **Resolved:** 2026-05-31
- **File:** `src/henchman/cli/textual_widgets.py`

### BUG-032: History navigation discards unsaved input buffer when cycling past the newest entry
- **Severity:** medium
- **Status:** resolved
- **Fix:** Added `_saved_input_buffer` attribute to `_navigate_history` (`textual_mixins.py`). When navigating from beyond-history into history, the current unsent input text is saved. When navigating past the newest entry back to the end, the saved buffer is restored instead of clearing to empty.
- **Found:** 2026-05-31
- **Resolved:** 2026-05-31
- **File:** `src/henchman/cli/textual_mixins.py`

### BUG-033: First chunk of agent stream content not scrolled into view
- **Severity:** low
- **Status:** resolved
- **Fix:** Removed the `if not newly_created` guard from `append_agent_chunk` (`textual_widgets.py`). `self._scroll_to_bottom()` is now called unconditionally after every chunk append, ensuring the first chunk content is visible immediately.
- **Found:** 2026-05-31
- **Resolved:** 2026-05-31
- **File:** `src/henchman/cli/textual_widgets.py`

### BUG-034: _streaming_messages dict is never populated -- dead state
- **Severity:** low
- **Status:** resolved
- **Fix:** Removed `self._streaming_messages` from `_init_state()` and the `self._streaming_messages.pop(name, None)` call from `on_agent_finished_message` (`textual_mixins.py`). The dict was never written to by any code path and served no purpose.
- **Found:** 2026-05-31
- **Resolved:** 2026-05-31
- **File:** `src/henchman/cli/textual_mixins.py`

### BUG-035: ChatPane.on_mount reinitializes tracking maps, erasing any pre-mount state
- **Severity:** low
- **Status:** resolved
- **Fix:** Removed the `on_mount` method from `ChatPane` (`textual_widgets.py`). The `__init__` already initializes `_active` and `_active_thinking` to empty dicts, making the `on_mount` reinitialization redundant and fragile.
- **Found:** 2026-05-31
- **Resolved:** 2026-05-31
- **File:** `src/henchman/cli/textual_widgets.py`

### BUG-036: Chat endpoints double-verify API key causing authentication to always fail when auth is enabled
- **Severity:** critical
- **Status:** resolved
- **Resolved:** 2026-05-31
- **Found:** 2026-05-31
- **File:** `src/henchman/api/endpoints/chat.py:300-303, 315, 383-398, 470-488, 509-523`
- **Replication:**
  1. Set `require_auth: true` and `api_keys: ["valid-key-123"]` in settings.yaml `api` section.
  2. Start the API server.
  3. Send `POST /v1/chat/completions` with `X-API-Key: valid-key-123` and valid messages body.
  4. Response is `401 Unauthorized` with `{"error": "Invalid API key"}`.
  5. The same key works fine on `POST /v1/remote/sessions`.
- **Description:**
  All four chat endpoints (`chat_completion`, `chat_completion_stream`, `get_chat_history`, `clear_chat_history`) use `verify_api_key` incorrectly in two ways.
  
  First, the dependency injection `api_key: Annotated[str | None, Depends(verify_api_key)]` makes `api_key` hold the **boolean return value** of `verify_api_key` (True/False), not the API key string -- despite the `str | None` type annotation.
  
  Second, the endpoint body then calls `if not await verify_api_key(api_key):` passing this bool as the `x_api_key` argument. Inside the second call, when `require_auth=True`, the bool is tested against `state.api_keys` (a `set[str]`). Since `True` / `False` is never equal to any string API key, the check always returns `False`, and the endpoint raises 401.
  
  The `remote.py` endpoints (`create_remote_session`, `list_remote_sessions`, etc.) have the **correct** pattern: they name the parameter `api_key_valid: Annotated[bool, Depends(verify_api_key)]` and use `if not api_key_valid:` directly without calling `verify_api_key` again.
  
  Affected chat endpoint lines:
  - `chat_completion`: lines 302-303 (Depends), line 315 (double call)
  - `chat_completion_stream`: lines 385-386 (Depends), line 398 (double call)
  - `get_chat_history`: lines 472-473 (Depends), line 488 (double call)
  - `clear_chat_history`: lines 511-512 (Depends), line 523 (double call)

### BUG-037: RemoteSessionResponse model_validate crashes on missing required fields
- **Severity:** high
- **Status:** resolved
- **Resolved:** 2026-05-31
- **Found:** 2026-05-31
- **File:** `src/henchman/api/endpoints/remote.py:25-35, 108`
- **Replication:**
  1. Start the API server.
  2. Send `POST /v1/remote/sessions` with `{"client_id": "myclient", "title": "My Session"}` and a valid API key.
  3. The server crashes with a 500 Internal Server Error.
  4. The server log shows a Pydantic `ValidationError` about missing `created_at` and `updated_at` fields.
- **Description:**
  `RemoteSessionResponse` (line 25-35) defines `created_at: str` and `updated_at: str` as **required** attributes (no default value, not `Optional`). However, `RemoteSessionManager.create_session()` in `remote_sessions.py:45-53` stores a dict with only `session_id`, `client_id`, `title`, `status`, and `last_event` -- no `created_at` or `updated_at` keys:
  
  ```python
  self._store.upsert_remote_session(session_id, {
      "session_id": session_id,
      "client_id": client_id,
      "title": title,
      "status": "active",
      "last_event": None,
  })
  ```
  
  When the endpoint calls `RemoteSessionResponse.model_validate(session)` (line 108), Pydantic v2 raises a `ValidationError` because the required fields are missing, which FastAPI converts to a 500 response. This affects all three endpoints that use `model_validate`: `create_remote_session` (line 108), `list_remote_sessions` (line 119), and `get_remote_session` (line 135).

### BUG-038: SSE endpoint missing X-Accel-Buffering header -- incompatible with nginx reverse proxy
- **Severity:** medium
- **Status:** resolved
- **Resolved:** 2026-05-31
- **Found:** 2026-05-31
- **File:** `src/henchman/api/endpoints/chat.py:460-467`
- **Replication:**
  1. Deploy the API server behind nginx reverse proxy (common production setup).
  2. Send `POST /v1/chat/completions/stream` with `stream: true` in the messages.
  3. The SSE stream is buffered by nginx -- the client receives nothing until the entire response is complete, defeating the purpose of streaming.
- **Description:**
  The streaming chat endpoint returns a `StreamingResponse` with `media_type="text/event-stream"` and headers `Cache-Control: no-cache` and `Connection: keep-alive`. However, it does **not** include the `X-Accel-Buffering: no` header. Nginx (and other proxies that respect nginx's buffering directives) will buffer SSE responses by default, delaying delivery to the client until the buffer fills or the response completes. This breaks real-time streaming behavior.
  
  The fix is to add `"X-Accel-Buffering": "no"` to the headers dict on line 463 so that nginx passes SSE chunks through immediately.

### BUG-039: ChatRequest.messages has no min_length constraint -- empty messages list accepted
- **Severity:** medium
- **Status:** resolved
- **Resolved:** 2026-05-31
- **Found:** 2026-05-31
- **File:** `src/henchman/api/endpoints/chat.py:35`
- **Replication:**
  1. Send `POST /v1/chat/completions` with body `{"messages": []}` (empty array) and a valid API key.
  2. The endpoint proceeds past validation, never finds a user message, and calls `agent.run(user_input="")`.
  3. The agent processes an empty prompt, producing either an error or an unexpected response.
- **Description:**
  The `messages` field on `ChatRequest` (line 35) is defined as `list[ChatMessage] = Field(description="Conversation history")` with no `min_length` constraint. An empty messages list passes Pydantic validation, but the endpoint logic at lines 326-334 searches for the last user message via `for i in range(len(request.messages) - 1, -1, -1)` and finds nothing, leaving `user_input=""` and `last_user_index=-1`. The agent is then invoked with an empty user prompt. This should return a `422 Unprocessable Entity` with a clear error rather than silently passing garbage to the agent.
  
  The same issue exists on the streaming endpoint at line 412.

### BUG-040: Rate limiter uses request.client.host -- ineffective behind reverse proxy
- **Severity:** medium
- **Status:** resolved
- **Resolved:** 2026-05-31
- **Found:** 2026-05-31
- **File:** `src/henchman/api/server.py:229`
- **Replication:**
  1. Deploy the API server behind a reverse proxy (e.g., nginx, AWS ALB, or any load balancer).
  2. Configure rate limits in settings.yaml.
  3. All traffic appears to come from the proxy's IP address, so rate limiting hits a single bucket for all users.
  4. A single abusive client can exhaust the rate limit for all other users, or alternatively no single client can ever hit the limit because all share one bucket.
- **Description:**
  The rate limit middleware identifies clients using `request.client.host` (line 229): `client_host = request.client.host if request.client is not None else "anonymous"`. In ASGI, `request.client` reflects the TCP connection peer, which behind any reverse proxy is the proxy server itself, not the original client. The code does not consult `X-Forwarded-For` or `X-Real-IP` headers.
  
  This means:
  - All traffic from behind a proxy is bucketed into a single rate-limit bucket using the proxy's IP.
  - An abusive client cannot be throttled individually -- their traffic is indistinguishable from legitimate traffic at the rate limiter level.
  - The rate limiter is effectively broken in any deployment that routes through a load balancer or reverse proxy.
  
  The fix is to check `request.headers.get("x-forwarded-for", "").split(",")[0].strip()` or `request.headers.get("x-real-ip")` and fall back to `request.client.host`.

### BUG-041: Redundant fetch_user calls on every send_message waste API quota and risk rate limiting
- **Severity:** medium
- **Status:** resolved
- **Resolved:** 2026-05-31
- **File:** `src/henchman/chat/discord_bot.py`
- **Root Cause:**
  `send_message` called `await self._client.fetch_user(int(user_id))` on every invocation, even for repeated calls to the same user within a single interaction.
- **Fix:**
  1. Added `self._user_cache: dict[str, Any] = {}` to `DiscordBot.__init__`.
  2. Added `_get_user()` method that checks the cache before calling `fetch_user`.
  3. Updated `send_message` and `send_typing` to use `_get_user` instead of direct `fetch_user`.
  4. Cleared the cache in `on_ready` to handle reconnection scenarios.
- **Verification:** 4 dedicated tests verify: caching for same user, separate calls for different users, cache invalidation on on_ready, and shared cache between send_message and send_typing. All 66 chat tests pass.

### BUG-042: Silent message send failures produce incomplete responses without user notification
- **Severity:** high
- **Status:** resolved
- **Resolved:** 2026-05-31
- **File:** `src/henchman/chat/discord_bot.py`, `src/henchman/chat/manager.py`
- **Root Cause:**
  `send_message` wrapped the send in `except Exception: pass` that only logged. Callers assumed success and appended all content to `response_parts` regardless of delivery.
- **Fix:**
  1. Changed `send_message` return type from `None` to `bool` (True on success, False on failure).
  2. Updated `_process_stream` to check the return value before appending to `response_parts`.
  3. Updated `_handle_message` final flush to conditionally append on success.
- **Verification:** Tests verify False return on failure, True on success, and that failed flushes are not appended to response_parts/history. All 66 chat tests pass.

### BUG-043: Thread channel messages incorrectly blocked by channel ID allowlist
- **Severity:** high
- **Status:** resolved
- **Resolved:** 2026-05-31
- **File:** `src/henchman/chat/discord_bot.py`
- **Root Cause:**
  The `on_message` handler only checked `message.channel.id` against `_allowed_channel_ids`, but thread channels have their own ID, not the parent channel ID.
- **Fix:**
  This bug is no longer applicable: the HEAD version of `discord_bot.py` was refactored to remove the channel allowlist feature entirely. Messages are now accepted from any channel as long as the bot is mentioned. The thread channel issue cannot occur because there is no allowlist to block thread messages.
- **Verification:** N/A -- feature was removed by prior refactoring. No tests affected.

### BUG-044: Typing indicator never refreshed during long-running agent processing
- **Severity:** low
- **Status:** resolved
- **Resolved:** 2026-05-31
- **File:** `src/henchman/chat/manager.py`
- **Root Cause:**
  The typing indicator (Discord's "Bot is typing...") was only sent once at the start of `_handle_message`. It expires after ~10 seconds with no refresh mechanism.
- **Fix:**
  1. Created a background `asyncio.Task` that calls `bot.send_typing()` every 8 seconds during processing.
  2. Wrapped the task lifecycle with try/finally to ensure cleanup via `task.cancel()`.
- **Verification:** A dedicated test simulates a 2-second processing delay and verifies send_typing is called multiple times (initial + refreshes). All 66 chat tests pass.

### BUG-045: Code block closing fence at chunk boundary produces malformed Markdown
- **Severity:** low
- **Status:** resolved
- **Resolved:** 2026-05-31
- **File:** `src/henchman/chat/discord_bot.py`
- **Root Cause:**
  When a code block's closing fence (` ``` `) triggered a chunk split, `code_block_lang` was still set (e.g., "python") because the update to `next_lang` (which is None) happened after, not before, the split logic. The new chunk incorrectly opened with `` ```python\n ``` ``.
- **Fix:**
  Changed the split logic to use `next_lang` (which reflects the state AFTER the current line) instead of `code_block_lang` (which reflects the state BEFORE):
  1. When opening a new chunk, check `code_block_lang is not None and next_lang is not None` to only re-open the code block if the current line is not the closing fence.
  2. Updated the hard-split while loop to also use `next_lang`.
- **Verification:** 4 dedicated tests cover: closing fence at boundary, language tracking, multiple consecutive code blocks, and exact boundary. All 66 chat tests pass.

### BUG-046: Empty message content after mention stripping passed to agent without validation
- **Severity:** low
- **Status:** resolved
- **Resolved:** 2026-05-31
- **File:** `src/henchman/chat/manager.py`
- **Root Cause:**
  Mention-only messages (e.g., `@BotName` with no additional text) produced `content = ""` after stripping, which was passed to `agent.run(user_input="")`, wasting tokens and producing undefined behavior.
- **Fix:**
  Added validation in `_handle_message`: if `message.content.strip()` is empty, the bot responds with "How can I help you?" and returns early without invoking the agent.
- **Verification:** 3 dedicated tests verify: empty content is not passed to agent.run, whitespace-only content is also rejected, and normal content still works. All 66 chat tests pass.

### BUG-047: Group DM messages misclassified as guild messages and rejected
- **Severity:** low
- **Status:** resolved
- **Resolved:** 2026-05-31
- **File:** `src/henchman/chat/discord_bot.py:107`
- **Root Cause:**
  `on_message` checked `isinstance(message.channel, discord.DMChannel)` to detect DMs, but `discord.GroupChannel` messages also need DM-like handling. Group DMs were treated as guild messages.
- **Fix:**
  Changed the DM check from `isinstance(message.channel, discord.DMChannel)` to `message.guild is None`, which correctly identifies both `DMChannel` and `GroupChannel` messages, since both have `guild = None` in discord.py.
- **Verification:** 3 dedicated tests verify: group DM messages are accepted, regular DMs still work, and guild messages without mentions are still rejected. All 66 chat tests pass.

### BUG-048: auto_approve flag in ChatManager is never connected to ToolRegistry confirmation handler
- **Severity:** medium
- **Status:** resolved
- **Resolved:** 2026-05-31
- **File:** `src/henchman/chat/manager.py`
- **Root Cause:**
  `_get_or_create_agent` called `tool_manager.set_auto_approve(auto_approve=True)` but never called `tool_manager.set_confirmation_handler()`, so the `ToolManager.handle_confirmation` method (which checks the `auto_approve` flag) was never registered with the registry. The `auto_approve=True` setting was dead code.
- **Fix:**
  Added `tool_manager.set_confirmation_handler()` after `set_auto_approve(True)` to wire up the confirmation handler, making the `auto_approve` flag take effect as intended.
- **Verification:** A dedicated test verifies that `set_confirmation_handler()` is called after `set_auto_approve()`. All 66 chat tests pass.


---

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

### BUG-005: `asyncio.gather()` without `return_exceptions=True` causes silent cancellation of parallel tool calls
- **Severity:** high
- **Status:** resolved
- **Resolved:** 2026-05-31
- **File:** `src/henchman/cli/tool_executor.py`
- **Root Cause:**
  `execute_tool_calls` called `asyncio.gather(...)` with the default `return_exceptions=False`. When one parallel tool call raised an exception that propagated through `registry.execute` (e.g., `GeneratorExit` or any `BaseException` not caught by `except Exception`), `asyncio.gather` immediately cancelled all other pending futures, then re-raised the exception. All tool calls got generic cancellation messages from the `finally` handler.
- **Fix:**
  1. Added `return_exceptions=True` to the gather call.
  2. Iterated over each result with `zip(to_parallel, results)`.
  3. Logged per-tool-call failures via `logger.error()` instead of letting a single exception cancel unrelated work.
  4. Added `import logging` and `logger = logging.getLogger(__name__)` to the module.
- **Verification:** 3 new tests confirm: (a) a passing parallel tool's result is preserved when another tool raises, (b) all-parallel-success still works, (c) a single parallel tool call still works. All 22 delegation manager tests and 3 tool_executor tests pass.
