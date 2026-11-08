# Neovim pilot

The opt-in client supports **Neovim 0.12.6 on Linux**. It launches one Henchman
subprocess for each explicitly requested run and uses the shared
[v1 editor protocol](api.md#editor-stdio-protocol-v1), orchestrator, session store,
approvals and usage accounting. Other Neovim versions, macOS and Windows clients
are unsupported by this pilot. The underlying stdio transport has its own
POSIX boundary described in the protocol reference.

## Install and activate

Install a Henchman build containing the pilot using the
[installation instructions](getting-started.md#installation), and configure its
provider through the normal [project settings](configuration.md). Export the
bundled client to a directory of your choice:

```bash
henchman ide export neovim /absolute/path/to/henchman-neovim
```

This writes `lua/henchman/init.lua`. Export does not launch Neovim, start a model
request or change your editor configuration. Existing files are refused unless
you explicitly pass `--force`; review local client edits before overwriting them.
`--format json` changes only the export receipt.

Add the exported directory to Neovim's runtime path and explicitly configure the
project, executable and saved files in your `init.lua`:

```lua
vim.opt.runtimepath:prepend("/absolute/path/to/henchman-neovim")
require("henchman").setup({
  project = "/absolute/path/to/project",
  command = { "/absolute/path/to/henchman" },
  paths = { "src/calculator.py", "tests/test_calculator.py" },
})
```

`command` is an argument vector, not shell text. For an existing Python
installation it can instead be `{ "/absolute/path/to/python", "-m", "henchman" }`.
The client appends the protocol version, project and repeated `--editor-path`
arguments itself. Setup registers commands but does not create a session or run.
The subprocess uses the configured provider; exporting the client does not
choose a provider or establish that a model is available.

## Start, decide and cancel

| Command | Behavior |
|---------|----------|
| `:HenchmanSelect src/calculator.py tests/test_calculator.py` | Set saved files for the next run. It does not change an active run's selection. |
| `:HenchmanNew Inspect addition, fix it and run the selected test` | Explicitly create a new project-scoped session and start one run. With no text, prompt for the task. |
| `:HenchmanResume EXACT_SESSION_ID Continue inspecting the selected files` | Explicitly load that session in the same project and start one run. There is no automatic latest-session selection. |
| `:HenchmanShow` | Open bounded run evidence in a read-only scratch window; `q` closes it. |
| `:HenchmanDecision` | Present the still-current permission or question again. |
| `:HenchmanCancel` | Retire an unanswered start prompt or request cancellation of the owned run. |
| `:HenchmanReview` | After settlement, inspect recorded file/hunk changes for that actual run. |

To inspect the last session ID, use
`:lua print(require("henchman").status().session_id)` after initialization.
Resume does not replay an interrupted operation or bypass its recovery state.
Only one owned run or review can be active at a time; there is no automatic
reconnect, retry, new session or background continuation.

Permission prompts offer **Deny**, **Inspect evidence** and **Allow once**.
Inspecting opens the evidence without answering; use `HenchmanDecision` when
ready to decide. Dismissing the permission chooser denies the request. Questions
use Neovim's input UI; dismissing returns no answer. Replies are bound to the
current connection, session, run and decision generation. A callback retained
after cancellation cannot authorize a later decision.

The displayed runtime outcome and process/delivery outcome remain separate.
A `completed` run still has `task_verified: false`. A missing, malformed or
mismatched terminal frame, incomplete pipe delivery or inconsistent process exit
is reported as incomplete, even when a runtime result was already received.
The [protocol reference](api.md#editor-stdio-protocol-v1) defines terminal and exit
semantics. Neither a successful tool call nor a completed run proves the task.

## Saved files and buffer protection

Select 1–256 distinct, existing regular files inside the explicit physical
project root. Symlinks, hardlinks, special files, private state such as `.git/`
or `.henchman/`, and outside-project targets are refused. New-file creation,
deletion and rename are outside this pilot's selected-file contract.
If `paths` is omitted from setup, the current buffer path becomes the explicit
selection when a start command is invoked; an unnamed or unsaved file is refused.

Loaded selected buffers must have no unsaved changes, including another buffer
that resolves to the same physical file. During a run the client temporarily
disables `modifiable` and `autoread` for selected buffers, including matching
buffers opened later. It watches for forced changes, renamed/deleted buffers and
newly discovered dirty buffers; detection requests cancellation while preserving
the user's live text. This monitoring is not a hard key-to-cancellation latency
guarantee or filesystem isolation from another editor/process.

Original buffer options are restored after process and pipe settlement. The
client never saves buffers or replaces their text with model output. Tool edits
change saved disk files, so an unchanged editor buffer may still show old text.
Inspect `HenchmanReview`, then use Neovim's `:checktime` for the relevant unmodified
buffers when you choose to reconcile disk changes. Keep unsaved edits intact;
there is no automatic forced reload.

## Tool and review boundaries

Only the exact bundled implementations of `read_file`, `write_file`, `edit_file`,
`patch_apply`, `pytest_run` and `ask_user` may dispatch in the selected-file run.
File tools, including every parsed patch target, must name selected existing
files. Pytest must name a selected test file, optionally followed by `::node`;
its timeout is 1–300 seconds, coverage is disabled and parallel execution is
unsupported. Shell, Python-exec, network, MCP and custom tool implementations are
not admitted through this selection guard.

**Pytest runs trusted project code.** Tests, imports, `conftest.py` and plugins can
perform effects beyond the selected files, including subprocess or network work.
The guard is a dispatch boundary, not an OS sandbox. It rechecks tool identity,
targets, project/parent identity and current inherited policy after awaited
authorization boundaries. It does not confine independent writers during a tool
body, restrict provider traffic or replace existing approval/access policy.

Supported deterministic mutations use the shared
[automatic checkpoint capture](checkpoints.md#automatic-tool-capture). Review
filters canonical stored operation records by the actual run ID before display
redaction; it does not infer ownership from Git status or parse display labels.
`HenchmanReview` invokes `henchman checkpoint review-run RUN_ID` as a separate,
read-only subprocess. It shows file and hunk evidence, unavailable captures and
visible omission notices. It does not accept, reject, restore, stage, commit or
publish changes. For a restore decision, use the shared
[preview/apply and recovery commands](checkpoints.md#user-commands), which retain
their revision and content-conflict checks. Restricted tool policy can make this
unmediated checkpoint review unavailable; selecting a file grants no exception.

## Bounds and failure handling

| Boundary | Limit |
|----------|-------|
| Wire frames | 1 MiB per frame, 16 JSON nesting levels; invalid UTF-8, duplicate keys and non-finite numbers are rejected |
| Outstanding client requests | 32; acknowledged controls retire their entries |
| Task prompt / question answer | 256 KiB / 64 KiB |
| Evidence display | 128 KiB retained prefix, followed by a visible omission notice |
| Raw process stderr | Discarded; only a bounded received-byte indicator is retained |
| Server pipe write | Absolute 30-second deadline per complete frame; see the protocol reference |
| Client cleanup request | `cleanup_ms = 5000` by default; configurable from 1 to 30,000 ms before requesting process stop |
| Review subprocess | `review_ms = 10000` by default, configurable from 1 to 30,000 ms; at most 512 KiB JSON plus its newline |
| Review projection | At most 16 records, 64 hunks and 32,768 text characters per record; 256 KiB intermediate aggregate and explicit omissions |

Set `cleanup_ms` and `review_ms` in `setup` to change those client deadlines.
They do not define a model-request or whole-task timeout. Shutdown cancels owned
work, waits for settlement and has a bounded process-stop fallback; a stop
request alone does not establish successful cleanup. Review timeout, oversized
output or invalid output produces an unavailable/incomplete review. The service
still enumerates its checkpoint catalog before applying output caps, so these
are not hard filesystem traversal bounds. Review scratch text has the same
128 KiB display limit and a separate omission notice.

## Qualification evidence

The accepted pilot was tested on Linux using the official
[Neovim 0.12.6 release](https://github.com/neovim/neovim/releases/tag/v0.12.6)
and an installed Henchman wheel under Python 3.12.13. Its focused suite passed
**132 tests**, including **56 actual Neovim subprocess cases**. The cases cover
shared-runtime inspect/edit/pytest flows, explicit approval and denial,
cancellation, raw pipe framing, session/run correlation, buffer preservation,
correlated checkpoint review and malformed-frame rejection. They use scripted
providers or owned loopback fixtures, with no model inference.

Independent review reran all 132 cases and passed 48 adversarial probes: 13
client correlation/lifetime cases and 35 decoder cases in the actual editor.
The [qualification report and receipt](evaluations/2026-11-08-neovim-pilot.md)
record the exact source, wheel and log identities; repeated runs of the same
suite are not counted as additional distinct tests.
These are automated client/runtime checks, not human accessibility testing,
native interactive responsiveness qualification or evidence of live model coding
quality. Broader platforms and editor versions remain unsupported. Exact release
artifact qualification remains part of the [release process](../CONTRIBUTING.md#-release-process).
