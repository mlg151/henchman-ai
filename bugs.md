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

### BUG-028: Agent errors leave stale entries in ChatPane._active, corrupting subsequent streams
- **Severity:** high
- **Status:** open
- **Found:** 2026-05-31
- **File:** `src/henchman/cli/textual_mixins.py:1166-1183` and `src/henchman/cli/textual_widgets.py:640-655`
- **Replication:**
  1. Send a message to the agent (e.g., "hello").
  2. While the agent streams a response, trigger an error (e.g., provider disconnects).
  3. Note that `process_user_input` catches the exception but never calls `chat.finish_agent_stream()`.
  4. Send a second message ("are you there?").
  5. The new agent response is APPENDED to the old errored widget instead of creating a new one, because `append_agent_chunk` finds the old `_active["Assistant"]` entry and skips `begin_agent_stream()`.
- **Description:**
  When `process_user_input` (textual_mixins.py:1150) raises an exception in the `try` block, both the `except asyncio.CancelledError` and `except Exception` paths in the `try`/`finally` block (lines 1166-1183) never call `finish_agent_stream()` on the `ChatPane`. This means the agent name (e.g., `"Assistant"`) remains in `ChatPane._active`.

  On the next user submission, `append_agent_chunk` (textual_widgets.py:640) checks `newly_created = agent_name not in self._active`. Since the stale entry exists, `newly_created` is `False`, and `begin_agent_stream` is never called. The new chunks are appended to the old errored `ChatMessage` widget via `self._active[agent_name].append(chunk)` at line 645. The user sees new response text grafted onto the previous turn's error message, with no visual break.

  The fix is to add `chat.finish_agent_stream(name)` (for each active agent) in the `finally` block or `except` blocks of `process_user_input`.

### BUG-029: No finish_thinking_stream method -- _active_thinking entries accumulate across turns
- **Severity:** high
- **Status:** open
- **Found:** 2026-05-31
- **File:** `src/henchman/cli/textual_widgets.py:694-698`
- **Replication:**
  1. Open the app and send a message to the agent.
  2. The agent thinks -- a `ThinkingMessage` widget is created and stored in `_active_thinking["Assistant"]`.
  3. Send another message.
  4. The new thinking chunks are APPENDED to the previous turn's expanding `ThinkingMessage` widget instead of creating a fresh one.
  5. Repeat -- the single thinking widget grows unbounded across turns.
- **Description:**
  `append_thinking_chunk` (line 694) checks `if agent_name not in self._active_thinking` and only creates a new widget if no entry exists. There is NO `finish_thinking_stream` method anywhere in the codebase -- `_active_thinking` entries are only removed by `clear_thinking_messages()` (user action) or `clear_messages()` (`/clear` command). They are never cleaned up between conversation turns.

  This means every turn's thinking content for the same agent name is concatenated into the same widget. Over a long session the `ThinkingMessage` widget grows without bound, and the user cannot distinguish "thinking from this turn" from "thinking from previous turns."

  The same pattern applies to `_active` (agent streams), but that is at least cleaned up by `finish_agent_stream` on success. There is no equivalent for thinking streams.

  Fix: Add a `finish_thinking_stream(agent_name)` method analogous to `finish_agent_stream` that pops from `_active_thinking`, and call it from an `on_agent_thought_finished` handler or at the start of each new turn.

### BUG-030: StatusBar and Footer both dock to bottom with reversed stacking
- **Severity:** medium
- **Status:** open
- **Found:** 2026-05-31
- **File:** `src/henchman/cli/henchman.tcss:52-55` and `src/henchman/cli/textual_app.py:310-311`
- **Replication:**
  1. Run the Textual TUI.
  2. Observe the bottom of the screen.
  3. The StatusBar (status text, token count) appears below the Footer (keybinding hints), which is the reverse of the expected visual order.
- **Description:**
  The `compose()` method yields `StatusBar(id="status-bar")` at line 310, then `Footer()` at line 311. In the TCSS file, `#status-bar` has `dock: bottom; height: 1;`. `Footer` also has `dock: bottom; height: 1;` from its Textual default CSS.

  In Textual's docking system, when multiple widgets dock to the same edge, they stack in children/DOM order. Since StatusBar is a child before Footer, it occupies the bottommost position, and Footer sits above it. The visual result is:
  ```
  [HenchmanTextArea]
  [Footer]         <-- keybinding hints (expected at very bottom)
  [StatusBar]      <-- status info (unexpectedly below Footer)
  ```

  This is reversed from the normal convention where keybinding hints (Footer) are at the very bottom and status text sits above them. This can cause the status text to be partially hidden or visually confused with the footer.

  Fix: Either swap the compose order (yield Footer before StatusBar) so Footer occupies the bottommost dock position, or remove `dock: bottom` from `#status-bar` CSS and let it use normal flow above the docked Footer.

### BUG-031: HenchmanTextArea on_key handler is dead code that duplicates BINDINGS
- **Severity:** medium
- **Status:** open
- **Found:** 2026-05-31
- **File:** `src/henchman/cli/textual_widgets.py:254-281`
- **Replication:**
  1. Review `HenchmanTextArea.BINDINGS` (line 254): defines `enter` -> `app.action_submit_message` and `shift+enter` -> `newline`.
  2. Review `HenchmanTextArea.on_key` (line 263): separately handles `event.key == "enter"` -> `app.action_submit_message()` and `event.key == "shift+enter"` -> `self.insert("\n")`.
  3. In Textual, when a widget's binding matches a key, the key event is consumed and `on_key` is NOT called. This means the `on_key` handler for these two keys never executes.
- **Description:**
  `HenchmanTextArea` defines both widget-level `BINDINGS` and an `on_key` message handler for the same two keys (`enter` and `shift+enter`). In Textual, key bindings on a widget take precedence over `on_key` -- when a binding matches, the binding action is invoked and the key event is stopped before reaching `on_key`.

  This makes the `on_key` handler dead code for `enter` and `shift+enter`. However, there are two risks:

  1. **Double-fire risk**: If a future Textual version changes the event processing order (or if `show=False` on bindings affects propagation), both the binding action AND the `on_key` handler could fire for the same keypress, causing double message submission (`action_submit_message` called twice) or double newline insertion (`action_newline` + `insert("\n")`).

  2. **Maintenance hazard**: The `on_key` handler is misleading. A developer reading the code would reasonably believe `on_key` has effect. If they modify `on_key` without checking BINDINGS (or vice versa), the two mechanisms would diverge, leading to inconsistent behavior that only manifests under specific conditions.

  Fix: Remove the `on_key` handler and its helper methods (`_handle_enter_key`, `_handle_shift_enter_key`) since the BINDINGS already handle these keys correctly. The `action_newline` binding already handles Shift+Enter.

### BUG-032: History navigation discards unsaved input buffer when cycling past the newest entry
- **Severity:** medium
- **Status:** open
- **Found:** 2026-05-31
- **File:** `src/henchman/cli/textual_mixins.py:915-933`
- **Replication:**
  1. Type some text in the input that you have NOT submitted yet (e.g., "work in progress").
  2. Press Up to navigate to a previous history entry.
  3. Press Down repeatedly until you cycle past the newest entry.
  4. The input is now EMPTY -- your unsaved "work in progress" text is lost.
- **Description:**
  `_navigate_history` (line 915) handles cycling through `self.command_history`. When the user navigates past the newest entry (`new_idx >= len(history)`), the code sets `widget.load_text("")` -- clearing the input to an empty string. Standard shell history navigation (e.g., bash, readline) saves the current unsent input into a temporary buffer before cycling into history, and restores that buffer when the user navigates back past the newest entry.

  This implementation lacks that buffer. Any text the user typed but didn't submit is silently discarded when they cycle history then go past the end.

  Fix: Save the current input text to a `_saved_input_buffer` attribute before overwriting it in `_navigate_history`, and restore it when navigating past the newest entry.

### BUG-033: First chunk of agent stream content not scrolled into view
- **Severity:** low
- **Status:** open
- **Found:** 2026-05-31
- **File:** `src/henchman/cli/textual_widgets.py:640-647`
- **Replication:**
  1. Send a message that triggers a streaming response.
  2. The first chunk of the response triggers `append_agent_chunk` with `newly_created=True`.
  3. `begin_agent_stream` creates the widget and calls `_add_message_widget`, which calls `_try_scroll()` -- scrolling to bottom while the widget is still EMPTY.
  4. Then `self._active[agent_name].append(chunk)` fills the first chunk of content into the now-visible (but scrolled-to-bottom) widget.
  5. If the first chunk causes the widget to grow below the viewport, the content is not visible until the second chunk triggers a proper `_scroll_to_bottom`.
- **Description:**
  In `append_agent_chunk`, when `newly_created=True`, the scroll is triggered by `_add_message_widget` (inside `begin_agent_stream`) BEFORE the first chunk content is appended. The sequence is:

  1. `begin_agent_stream(agent_name)` -> `_add_message_widget(...)` -> `_try_scroll()` -> scroll happens with empty widget
  2. `self._active[agent_name].append(chunk)` -> content is added, but NO scroll follows

  The condition `if not newly_created: self._scroll_to_bottom()` (line 646-647) means the second-and-later chunks trigger a proper post-append scroll. But the first chunk is appended after the scroll, so if it makes the widget taller than the viewport, the first few words/lines are not visible until the next chunk triggers the scroll.

  Fix: Always call `self._scroll_to_bottom()` after appending, removing the `if not newly_created` guard. The double-scroll on creation is harmless (the second scroll is idempotent after the first).

### BUG-034: _streaming_messages dict is never populated -- dead state
- **Severity:** low
- **Status:** open
- **Found:** 2026-05-31
- **File:** `src/henchman/cli/textual_mixins.py:410, 1804`
- **Replication:**
  1. Search for all references to `_streaming_messages` in the codebase.
  2. It is initialized in `_init_state()` (line 410).
  3. It is `.pop()`'ed in `on_agent_finished_message` (line 1804).
  4. It is NEVER written to by any code path.
- **Description:**
  `self._streaming_messages: dict[str, ChatMessage] = {}` is created in `_init_state()` at line 410. The only other reference is `self._streaming_messages.pop(name, None)` in `on_agent_finished_message` at line 1804. Since the dict is always empty, every `.pop()` call is a no-op. The dict exists solely as unreachable dead state -- it consumes a trivial amount of memory but never serves any purpose.

  The attribute name suggests it was originally intended to track active streams separately from `ChatPane._active`, but was never wired up. It can mislead future developers into thinking streams are tracked at the app level.

  Fix: Remove `self._streaming_messages` from `_init_state()` and the `.pop()` call from `on_agent_finished_message`.

### BUG-035: ChatPane.on_mount reinitializes tracking maps, erasing any pre-mount state
- **Severity:** low
- **Status:** open
- **Found:** 2026-05-31
- **File:** `src/henchman/cli/textual_widgets.py:587-590`
- **Replication:**
  1. `ChatPane.__init__` initializes `self._active = {}` and `self._active_thinking = {}` (lines 584-585).
  2. `ChatPane.on_mount` sets `self._active = {}` and `self._active_thinking = {}` again (lines 589-590).
  3. If `on_mount` fires MORE THAN ONCE (possible in some Textual lifecycle scenarios, e.g., TabbedContent re-evaluating children, CSS hot-reload, or screen transitions), the tracking maps are wiped, losing all active stream references.
- **Description:**
  While this is currently safe because no widgets are added between `__init__` and the first `on_mount`, the redundant reinitialization in `on_mount` is fragile. If Textual ever re-mounts the `ChatPane` (e.g., due to an upstream widget being detached and reattached, or if `ChatPane` is later subclassed to pre-populate messages in `compose`), the `on_mount` handler would silently destroy all stream tracking.

  The `on_mount` handler should be removed since `__init__` already initializes these fields. Alternatively, make it idempotent:
  ```python
  def on_mount(self):
      if not hasattr(self, "_active"):
          self._active = {}
          self._active_thinking = {}
  ```

### BUG-036: Chat endpoints double-verify API key causing authentication to always fail when auth is enabled
- **Severity:** critical
- **Status:** open
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
- **Status:** open
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
- **Status:** open
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
- **Status:** open
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
- **Status:** open
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
- **Status:** open
- **Found:** 2026-05-31
- **File:** `src/henchman/chat/discord_bot.py:231`
- **Replication:**
  1. Enable the Discord bot for chat.
  2. Send a message that triggers multiple streaming flushes (content chunks) and tool calls.
  3. Examine the API calls made to Discord: a `GET /users/{user_id}` fetch_user call is made for EACH `send_message` invocation.
  4. With many streaming flushes and tool call notifications, a single user interaction can generate 5-10+ fetch_user calls for the same user.
- **Description:**
  `send_message` at line 231 calls `await self._client.fetch_user(int(user_id))` on every invocation, even when called repeatedly for the same user within a single interaction. During a typical agent response, `send_message` is called for:
    - Each content chunk flush (potentially multiple times per response)
    - Each tool call notification ("Running: tool_name")
    - Each tool result display
    - The final content flush after the stream ends.
  
  All these calls fetch the same user object via the Discord REST API, wasting API quota and contributing to rate limit accumulation. The `User` object returned by `fetch_user` could be cached in the `DiscordBot` instance keyed by `user_id`, with the cache invalidated periodically or on `on_ready`. Each `user.send()` call on a cached `User` object works identically to a freshly fetched one.

### BUG-042: Silent message send failures produce incomplete responses without user notification
- **Severity:** high
- **Status:** open
- **Found:** 2026-05-31
- **File:** `src/henchman/chat/discord_bot.py:245-246`
- **Replication:**
  1. Use the Discord bot in a scenario where a message fails to send (e.g., Discord API returns a transient error, user blocks DMs mid-conversation, or the bot hits a rate limit).
  2. The `send_message` method catches the exception at line 245 and logs it via `logger.exception`.
  3. The caller in `_process_stream` or `_handle_message` receives no signal that the message failed -- the chunk is still appended to `response_parts` as if it succeeded.
  4. The user misses part (or all) of the response with no error indication.
- **Description:**
  `send_message` wraps the entire send operation in a bare `except Exception` block that does nothing but log. Every caller -- `_process_stream` (content flushes at lines 345/354/365/383/395), `_handle_message` (final flush at line 493), and `_handle_command` (lines 543/551/566/585/589) -- assumes that if `send_message` returns without raising, the message was delivered. This is a false assumption: the exception is swallowed, the method returns `None`, and callers proceed as if delivery succeeded.
  
  The impact is especially severe during streaming: a failed chunk in the middle of the response is silently dropped, the remaining chunks continue to be sent, and the response is permanently incomplete. The user has no way to know part of the response was lost, because `response_parts` accumulates the failed chunk's text in the bot's history as if it was delivered.

### BUG-043: Thread channel messages incorrectly blocked by channel ID allowlist
- **Severity:** high
- **Status:** open
- **Found:** 2026-05-31
- **File:** `src/henchman/chat/discord_bot.py:120-121`
- **Replication:**
  1. Configure the Discord bot with `allowed_channel_ids` containing a guild text channel ID, e.g., `["123456789012345678"]`.
  2. In that guild, create a thread or reply to a message in that channel (creating a thread).
  3. Send a message mentioning the bot inside the thread.
  4. The bot's `on_message` handler receives the message, reads `message.channel.id` as the thread's own ID (not the parent channel's ID), and checks it against the allowlist.
  5. The thread ID is not in the allowlist, so the message is silently dropped -- the bot never responds.
- **Description:**
  Line 120-121 reads `channel_id = str(getattr(message.channel, "id", ""))` and checks it against `self._allowed_channel_ids`. For thread channels (`discord.Thread`), `message.channel.id` returns the thread's own unique snowflake ID, not the parent channel's ID. The allowlist contains the parent channel ID, so thread-originated messages always fail the lookup when `allowed_channel_ids` is configured.
  
  The fix would be to also check the parent channel ID for thread channels: `parent_id = getattr(message.channel, "parent_id", None)` or `message.channel.parent.id` and match against both the thread ID (explicit allow) and the parent channel ID (implicit allow for all threads in that channel).

### BUG-044: Typing indicator never refreshed during long-running agent processing
- **Severity:** low
- **Status:** open
- **Found:** 2026-05-31
- **File:** `src/henchman/chat/discord_bot.py:248-263` and `src/henchman/chat/manager.py:460`
- **Replication:**
  1. Send the Discord bot a request that requires multiple tool calls or generates a long streaming response that takes more than 10 seconds.
  2. The bot sends a typing indicator once at line 460 of manager.py via `send_typing`.
  3. After approximately 10 seconds, Discord's typing indicator expires and disappears.
  4. The user sees no typing indicator for the remaining duration of the processing, even though the bot is still actively working on the request.
- **Description:**
  Discord's typing indicator (the "Bot is typing..." animation) automatically expires approximately 10 seconds after being triggered. The `send_typing` method (discord_bot.py:248-263) uses `async with user.typing(): pass`, which triggers the indicator but does not keep it active beyond the initial trigger. The typing indicator is only sent once at the start of `_handle_message` (manager.py:460), before the agent stream begins.
  
  During long processing (multiple tool execution rounds or large responses), the 10-second window expires, and the user has no visual feedback that processing is ongoing. This can make the bot appear unresponsive or broken. A typing indicator should be refreshed periodically (e.g., every 8 seconds) during the processing loop.

### BUG-045: Code block closing fence at chunk boundary produces malformed Markdown
- **Severity:** low
- **Status:** open
- **Found:** 2026-05-31
- **File:** `src/henchman/chat/discord_bot.py:315-328, 358`
- **Replication:**
  1. Use the Discord bot and send a message that causes a response where a code block's closing fence (```) falls at a chunk split boundary, e.g., a code block whose content fills the chunk to within 8 characters of the 2000-character limit, followed by the closing ``` fence.
  2. The `_split_message` method's conservative `close_overhead = 4` calculation (line 308) does not account for the current line being the closing fence itself. The check on line 315 adds `close_overhead` to the total, triggering a premature split.
  3. The split logic on lines 325-328 opens a new chunk with `f"```{code_block_lang}\n{line}"` where `line` is the closing fence text itself, since `code_block_lang` has not yet been updated to `None` (the update happens at line 358, after the split).
  4. The closing fence is rendered as literal content inside a new (empty) code block, producing garbled Markdown.
- **Description:**
  The `_split_message` method computes `close_overhead` (line 307-308) solely from the current `code_block_lang` state, without examining whether the line being processed is itself the code block closing fence. When the closing fence is the line that triggers a chunk split:
    - `code_block_lang` is still "python" (or whatever language) because `next_lang` has been set to `None` but `code_block_lang` is not updated until line 358.
    - The split logic at line 326 creates `current_chunk = f"```python\n{line}"` where `line` is the literal text "```", producing the string `` ```python\n``` ``.
    - After the split, `code_block_lang = None` is applied, but the damage is done -- the new chunk contains an empty, incorrectly-opened code block.
  
  The resulting Markdown chunk renders as an empty Python code block followed by what should have been normal text. This occurs in a narrow window where the code block content fills the chunk to within 8 characters of the limit before the closing fence. The same bug could affect the hard-split while loop (lines 332-354) when splitting inside a code block whose content is near the limit.

### BUG-046: Empty message content after mention stripping passed to agent without validation
- **Severity:** low
- **Status:** open
- **Found:** 2026-05-31
- **File:** `src/henchman/chat/discord_bot.py:135-141` and `src/henchman/chat/manager.py:468`
- **Replication:**
  1. In a guild channel with `mention_only = True`, mention the bot without any additional text (e.g., `@BotName`).
  2. The `on_message` handler at lines 136-141 detects the bot mention and strips it from the content, producing `content = ""`.
  3. A `ChatMessage` is created with empty content and dispatched to `_handle_message`.
  4. Since `""` does not start with `/`, the command path is skipped.
  5. `_handle_message` calls `agent.run(user_input="")` (line 468), passing an empty string to the agent.
  6. The agent processes an empty prompt, which may produce an error, a response to empty input, or waste tokens.
- **Description:**
  There is no validation that `message.content` is non-empty after mention stripping. A mention-only message with no additional text produces `content = ""`, which passes through the full message processing pipeline. The agent is invoked with `user_input=""`, which is an undefined behavior -- it could cause the model to produce an irrelevant response, an error, or consume API quota unnecessarily. The bot should either respond with a help prompt ("How can I help you?") or silently ignore empty mentions.
  
  The same issue applies to messages that contain only attachments with no text content, where `message.content` is also empty. While `message.attachments` is captured in the `ChatMessage`, the agent receives no text input to process.

### BUG-047: Group DM messages misclassified as guild messages and rejected
- **Severity:** low
- **Status:** open
- **Found:** 2026-05-31
- **File:** `src/henchman/chat/discord_bot.py:116`
- **Replication:**
  1. Add the bot to a group DM (if the bot is configured for this in the Discord Developer Portal).
  2. The authorized user sends a message to the group DM mentioning the bot.
  3. Line 116 checks `isinstance(message.channel, discord.DMChannel)`, which is `False` for `discord.GroupChannel`.
  4. Because `is_dm` is `False`, the message enters the guild-message path: channel ID allowlist check and mention-only check.
  5. The group DM channel ID is not in `_allowed_channel_ids`, so the message is silently rejected.
- **Description:**
  The `on_message` handler only recognizes `discord.DMChannel` as a DM channel type (line 116). Messages from `discord.GroupChannel` (group DMs) are treated as guild messages and subjected to the channel ID allowlist and mention-only checks. Since group DM channel IDs would not typically be in the allowlist, all group DM messages are silently dropped.
  
  The fix is to extend the DM check to also include `discord.GroupChannel`, or more broadly, check `message.guild is None` to detect all non-guild channel types. In discord.py, both `DMChannel` and `GroupChannel` have `message.guild` set to `None`.

### BUG-048: auto_approve flag in ChatManager is never connected to ToolRegistry confirmation handler
- **Severity:** medium
- **Status:** open
- **Found:** 2026-05-31
- **File:** `src/henchman/chat/manager.py:167-168`
- **Replication:**
  1. Trace the tool execution flow for the Discord chat integration.
  2. `_get_or_create_agent` at line 167 calls `tool_manager.set_auto_approve(auto_approve=True)`.
  3. The ToolManager's `auto_approve` flag (checked in `handle_confirmation` at tool_manager.py:152) is never connected to the registry because `tool_manager.set_confirmation_handler()` is never called.
  4. In `ToolRegistry.execute` (registry.py:237-246), the confirmation check evaluates `self._confirmation_handler is not None`. Since no handler was registered, the check is always `False`, and tool execution proceeds without any approval check.
  5. Changing `set_auto_approve(auto_approve=False)` has zero effect -- tools are still auto-approved because the confirmation handler path is never invoked.
- **Description:**
  The ChatManager at lines 167-168 calls `tool_manager.set_auto_approve(auto_approve=True)`, but the ToolManager's `auto_approve` flag only takes effect inside its `handle_confirmation` method (tool_manager.py:152), which is never registered as the registry's confirmation handler via `set_confirmation_handler`. The `ToolRegistry.execute` method checks `self._confirmation_handler is not None` at registry.py:239 before calling the handler. Since no handler was registered, `_confirmation_handler` is `None`, and all tools proceed to execution without any approval.
  
  While the current behavior (all tools auto-approved) matches the intended behavior for the non-interactive Discord flow, the `auto_approve` setting is effectively dead code. If a developer later adds a confirmation handler to the chat flow (e.g., for security-sensitive tools), they would need to remember to consult the `auto_approve` flag in the handler, because the current `set_auto_approve(True)` call will have silently had no effect. The fix is either to call `set_confirmation_handler` to wire up the handler, or to remove the misleading `set_auto_approve` call and let the registry's default confirmation-bypass behavior be the explicit design.


---

## Resolved Bugs

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

---

## Summary

| Severity | Count |
|----------|-------|
| Critical | 1 |
| High | 10 |
| Medium | 22 |
| Low | 11 |
| **Total Open** | **44** |
| **Total Resolved** | **4** |
