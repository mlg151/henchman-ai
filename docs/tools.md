# Tools

User-driven [checkpoint review commands](checkpoints.md#user-commands) inspect
captured file/hunk changes and apply previewed conflict-checked decisions. They
share a service across CLI, REPL and Textual command input; automatic agent capture
and dedicated review navigation remain pending.

Henchman-AI registers built-in tools according to the active runtime and agent preset. The table below documents the core tool set; use `/tools`, help search, doctor, or `tool_search` for the live inventory instead of relying on a hard-coded count.

When context cannot hold every tool schema, the request exposes `tool_search` and
a selection of core coding tools. Search an exact tool name to prioritize its
schema for the next request. Results show five entries by default, with a total
and next offset; pass `offset` to continue or `limit` from 1 to 100 to change the
page size. Up to five executable tools on the returned page receive schema
priority. Searches use the current agent's registered scope;
prioritization grants no new permissions. A new user turn resets priorities, and
an explicitly requested schema that cannot fit produces a context error. See
[request accounting](configuration.md#context-management-settings).

For a required tool outside the acting agent's scope, an agent with
`delegate_task` can query `tool_search(scope="team", query="pytest_run")`.
Team lookup requires an exact tool name and returns paginated enabled role
identifiers with that tool registered in their scope. It uses cached scopes when
available and current registration plus configuration otherwise, without starting
specialists or creating provider clients. It excludes the caller and aliases of
that same agent. A runtime without team lookup reports it unavailable.

Team results are capability metadata: they do not promise model readiness,
approval, or current execution availability. They grant no tool access and do not
prioritize foreign schemas. Keep explicit tool/environment/check requirements in
the delegation brief and inspect the specialist's observed results. A default
local search miss says nothing about another role's tools.


Discovery surfaces share one capability matrix and distinguish these important boundaries:

| Capability | Classification |
|------------|----------------|
| `goal` | Runtime-dependent interactive continuation with the registered `goal_status` tool |
| `background shell` / `background python_exec` | Each requires its executor plus registered task get/list/output/stop tools |
| `web_search` | Runtime-wired only when the tool is registered |
| `mcp` and `mcp_auth` | Runtime-wired only when both tools are registered |
| `skill` | Local-only discovery and inspection |
| `schedule_cron` | Metadata-only; it does not start a background runner |
| `workflow` | Metadata-only definitions/previews; run and trigger actions do not execute commands |
| Integration blueprints, including Slack | Export-only |
| Plugin marketplace install | Unavailable; local plugin lifecycle remains available |
| Agent registry install | Unavailable; local agent workflows remain available |

## Quick Reference

| Tool | Category | Kind | Description |
|------|----------|------|-------------|
| `read_file` | File Operations | READ | Read file contents |
| `write_file` | File Operations | WRITE | Write content to a file |
| `edit_file` | File Operations | WRITE | Make surgical edits to a file |
| `patch_apply` | File Operations | WRITE | Apply unified diff patches |
| `file_overview` | File Operations | READ | Get structural summary without reading full content |
| `ls` | Directory Operations | READ | List directory contents |
| `glob` | Directory Operations | READ | Find files matching patterns |
| `grep` | Directory Operations | READ | Search file contents with regex |
| `code_format` | Code Analysis | WRITE | Run Black on Python files |
| `lint_check` | Code Analysis | READ | Run ruff/mypy linting |
| `dead_code` | Code Analysis | READ | Detect unused code |
| `python_ast` | Code Analysis | READ | Symbol tables and bounded Python quality scans |
| `import_graph` | Code Analysis | READ | Analyze import dependencies |
| `pattern_search` | Code Analysis | READ | Search code using natural language descriptions |
| `symbol_trace` | Code Analysis | READ | Trace symbol provenance across codebase |
| `pytest_run` | Testing | EXECUTE | Run pytest tests |
| `coverage_map` | Testing | READ | Parse coverage reports |
| `test_gen` | Testing | WRITE | Generate pytest test stubs |
| `verify_plan_execution` | Testing | EXECUTE | Track steps and run recorded acceptance checks |
| `git_ops` | Git Operations | READ | Run git operations (status, log, blame, etc.) |
| `diff_view` | Git Operations | READ | Show git diffs |
| `env_inspect` | Environment | READ | Inspect Python environment |
| `pip_inspect` | Environment | READ | Query installed packages |
| `python_exec` | Python Execution | EXECUTE | Start tracked background Python processes |
| `traceback_parse` | Python Execution | READ | Parse Python tracebacks |
| `shell` | Shell Execution | EXECUTE | Start tracked background shell commands |
| `web_fetch` | Web Operations | NETWORK | Fetch content from URLs |
| `web_search` | Web Operations | NETWORK | Search the web |
| `deep_research` | Web Operations | NETWORK | End-to-end web research with synthesis |
| `kg_query` | Knowledge Graph | READ | Query project knowledge graph |
| `kg_update` | Knowledge Graph | WRITE | Update knowledge graph |
| `rag_search` | RAG | READ | Semantic code search |
| `research_notes` | Knowledge Graph | WRITE | Persistent note-taking scratchpad |
| `ask_user` | Agent Interaction | READ | REPL/Textual input; headless calls report unavailable |
| `delegate_task` | Agent Interaction | EXECUTE | Delegate tasks to specialist agents |

## Built-in Tools

### Workflow preparation

The `workflow` tool stores local definitions, renders step previews and manages
local trigger/bridge records. `run` and `trigger` report execution unavailable:
their records contain `rendered_steps`, zero `executed_steps` and status
`execution_unavailable`. No command, test, build or CI job runs through this path.
Historical records retain their original fields and are not proof of execution.
Use actual command/test tools or bounded argv checks in
[`verify_plan_execution`](#verify_plan_execution) for execution and inspect their
observed results. Local checks do not establish a hosted CI run.

### File Operations

#### read_file

Read UTF-8 text, with CRLF and CR line endings normalized to LF.

```json
{
  "name": "read_file",
  "kind": "READ",
  "parameters": {
    "path": "string (required) - Path to the file",
    "start_line": "integer (optional) - First line to read, 1-based",
    "end_line": "integer (optional) - Last line to read, inclusive; -1 for EOF",
    "max_chars": "integer (optional) - Output character limit, default 50000",
    "line_numbers": "boolean (optional) - Absolute line-number prefixes, default false"
  }
}
```

**Example:**

```
Read the file src/main.py
```

#### write_file

Write the supplied content as UTF-8, preserving its newline characters on every
platform (creates or overwrites).

```json
{
  "name": "write_file",
  "kind": "WRITE",
  "parameters": {
    "path": "string (required) - Path to the file",
    "content": "string (required) - Content to write"
  }
}
```

#### edit_file

Make surgical edits to a file using search and replace. String matching and line
coordinates use the LF-normalized text returned by `read_file`.

```json
{
  "name": "edit_file",
  "kind": "WRITE",
  "parameters": {
    "path": "string (required) - Path to the file",
    "old_str": "string (optional) - Exact text that occurs once; omit for line mode",
    "new_str": "string (required) - Full replacement text",
    "start_line": "integer (optional) - First line to replace, 1-based",
    "end_line": "integer (optional) - Last line to replace, inclusive",
    "dry_run": "boolean (optional) - Preview the diff without writing"
  }
}
```

Supply either `old_str` or both line bounds. Mixed modes and incomplete line
ranges are rejected. If a string has multiple matches, read the current file and
include enough surrounding text to identify exactly one occurrence. Preserve
that surrounding text in `new_str` except for the intended changes.

For line edits, first use `read_file` with `line_numbers: true`. It returns absolute
1-based prefixes such as `12: text`, including when reading a partial range.
Prefixes are display annotations: omit them from replacement text. Plain reads
remain the default; numbered prefixes count toward `max_chars` (the truncation
notice is additional). A line edit replaces the **entire inclusive range** with
`new_str`; include every line that should remain in that range. An end bound past
EOF is clamped to EOF. Preview with `dry_run`, and reread after edits before
using line numbers again. These tools do not establish semantic correctness;
inspect the diff and run relevant tests.

#### patch_apply

Apply a unified diff patch to one or more files.

```json
{
  "name": "patch_apply",
  "kind": "WRITE",
  "parameters": {
    "patch": "string (required) - Unified diff patch content",
    "path": "string (optional) - Target file path",
    "dry_run": "boolean (optional) - Preview changes without applying",
    "fuzz": "integer (optional) - Lines of fuzz for context matching"
  }
}
```

#### file_overview

Get a hierarchical structural summary of a file without reading full content. For Python files: shows imports, class tree, function signatures, and docstrings. Adapts detail level to file size. Much faster than read_file for understanding structure.

```json
{
  "name": "file_overview",
  "kind": "READ",
  "parameters": {
    "path": "string (required) - Path to the file to summarize",
    "depth": "integer (optional) - Nesting depth: 1 = top-level only, 2 = include class methods (default: 2)"
  }
}
```

### Directory Operations

#### ls

List directory contents.

```json
{
  "name": "ls",
  "kind": "READ",
  "parameters": {
    "path": "string (optional) - Directory path, defaults to current",
    "show_hidden": "boolean (optional) - Whether to show hidden files"
  }
}
```

#### glob

Find files matching a pattern.

```json
{
  "name": "glob",
  "kind": "READ",
  "parameters": {
    "pattern": "string (required) - Glob pattern (e.g., **/*.py)",
    "path": "string (optional) - Base path to search in"
  }
}
```

#### grep

Search file contents with regular expressions.

```json
{
  "name": "grep",
  "kind": "READ",
  "parameters": {
    "pattern": "string (required) - Text or regex pattern to search for",
    "path": "string (optional) - File or directory to search in",
    "ignore_case": "boolean (optional) - Case insensitive search",
    "line_numbers": "boolean (optional) - Include line numbers in output",
    "glob": "string (optional) - File glob pattern to filter files",
    "context_before": "integer (optional) - Lines before each match",
    "context_after": "integer (optional) - Lines after each match",
    "invert_match": "boolean (optional) - Select non-matching lines",
    "whole_word": "boolean (optional) - Match whole words only",
    "count_only": "boolean (optional) - Only show match counts per file"
  }
}
```

### Code Analysis & Quality

#### Automatic Python formatting

The harness runs Black after authorized file edits and foreground workspace commands, before returning
their tool results. Verification therefore sees the formatted files without a
separate model formatting call. Black uses the project's `pyproject.toml` settings;
the normal Black defaults apply when none are configured. It is included as a
runtime dependency.

`python_exec` formats only its supplied snippet, before foreground execution or
background launch. It never scans or formats workspace files, including files
created by the snippet. Its formatting is best effort; see [python_exec](#python_exec).
Background `shell` launches also skip workspace formatting and report that in
the receipt. Run `code_format` on generated Python files before dependent checks.
See [background execution](#background-execution).

For a command that both edits source and runs checks or builds artifacts, Black
runs after that command completes. Run verification or the build in a subsequent
call so it uses the formatted sources.

Direct `write_file` and `edit_file` calls track their Python target. Other write
and execute tools, except `python_exec`, track changed `.py` and `.pyi` files in their working directory.
Unchanged files retain their existing formatting. Command tracking prunes child
symlinks, virtual environments, dependency/cache directories and build outputs.
Background writes or command writes outside that working directory are not
attested by these snapshots. Explicit file edits can target other directories.

Workspace tracking is bounded to 5,000 source files and 20,000 directory entries. Black runs
with one worker and a combined 30-second deadline; each changed source is limited
to 2 MiB. Tracking, parsing, configuration and formatter failures are reported as
unsuccessful tool results. A failed command remains failed even if its partial
Python writes were formatted. Cancellation propagates after subprocess cleanup.
Formatting establishes style, so lint, types, tests and review remain required.

#### code_format

Run Black on an explicitly selected Python file or directory. Ordinary agent
edits are already formatted automatically; this tool supports explicit formatting
requests. It uses the same bounded Black backend and project configuration.

```json
{
  "name": "code_format",
  "kind": "WRITE",
  "parameters": {
    "path": "string (required) - Path to Python file or directory to format"
  }
}
```

#### lint_check

Run ruff and/or mypy on Python code.

Check-only calls are read-only. With `fix: true`, the invocation is a write:
normal confirmation policies apply, Plan Mode blocks it even when the tool is
auto-approved, and the harness runs Black on observed Python changes in the
explicit file or directory before returning the result. This also applies to
targets outside the current working directory. Failed checks remain failed even
when their partial fixes were formatted.

Unsupported checker names and option-like paths fail validation. Targets are
passed after the option separator. Missing checkers and nonzero exits remain
failures; timeout and cancellation trigger bounded subprocess cleanup.

```json
{
  "name": "lint_check",
  "kind": "READ",
  "parameters": {
    "path": "string (required) - Path to Python file or directory to lint",
    "linter": "string (optional) - Which linter to run: 'ruff', 'mypy', or 'both'",
    "fix": "boolean (optional) - Auto-fix safe ruff issues"
  }
}
```

#### dead_code

Detect unused imports, functions, and classes.

```json
{
  "name": "dead_code",
  "kind": "READ",
  "parameters": {
    "path": "string (required) - Path to Python file or directory to analyze",
    "check_imports": "boolean (optional) - Check for unused imports",
    "check_functions": "boolean (optional) - Check for unused functions/classes",
    "whitelist": "array (optional) - Names to exclude from detection"
  }
}
```

#### python_ast

With the default `action="symbols"`, parse one Python file and return its symbol
table. Use `action="quality"` for a file or directory to find duplicate syntax,
long methods, and deep nesting without importing or executing project code.

```json
{
  "name": "python_ast",
  "kind": "READ",
  "parameters": {
    "path": "string (required) - Python file, or directory for quality scans",
    "action": "symbols (default) | quality",
    "include_docstrings": "boolean (optional) - Include docstrings in symbol output",
    "max_files": "integer (optional) - Quality scan budget; default 500, maximum 5000",
    "max_findings": "integer (optional) - Quality output budget; default 100, maximum 500"
  }
}
```


Quality output is JSON containing `findings`, `errors`, `complete`, `truncated`,
coverage counts, and applied limits. Each finding identifies a file, line range,
qualified function or method, and a suggested review action. Findings themselves
do not make tool execution fail; read/parse errors or an incomplete scan do.

- Duplicate candidates require matching AST syntax with at least 20 nodes after
  removing docstrings and normalizing the outer function name. Identifiers,
  literals, call targets, signatures, and decorators remain significant. A later
  occurrence points to the first location. These are candidates for review, not
  proof of interchangeable behavior: globals, decorators and surrounding scopes
  still need inspection. Renamed and partial clones can be missed.
- Long methods start at 30 physical body lines excluding the leading docstring;
  comments, blank lines, and nested definitions count toward that span.
- Deep nesting starts at four statement-level control-flow levels. Comprehensions
  and conditional expressions do not count. `elif` alternatives do not
  add artificial depth; nested functions have their own depth. The report gives
  the deepest location for each affected function.

Scanning prunes dependency/cache/build directories and `.agent_tasks`, skips child
symlinks, and does not interpret `.gitignore`. Explicit files can be selected
inside an excluded directory. Hard limits are 1 MiB per file, 10 MiB total source,
20,000 directory entries, and 20 reported errors. A one-byte overflow read can be
used to establish that a byte limit was exceeded. Cancellation stops further
traversal after the current bounded file. Narrow the path when a report is partial.
An empty findings list is not proof that code is smell-free. Continue with caller
inspection, tests, Ruff, and mypy through the existing tools.

#### import_graph

Analyze import dependencies of a Python file.

```json
{
  "name": "import_graph",
  "kind": "READ",
  "parameters": {
    "path": "string (required) - Path to Python file to analyze",
    "scan_dir": "string (optional) - Directory to scan for reverse imports",
    "detect_cycles": "boolean (optional) - Scan for circular import chains",
    "classify": "boolean (optional) - Classify imports as stdlib/local/third-party"
  }
}
```

#### pattern_search

Search code using natural language descriptions. Extracts keywords and structural patterns (inheritance, decorators, async, etc.) from the description, then searches and ranks results. Use instead of crafting complex grep regexes.

```json
{
  "name": "pattern_search",
  "kind": "READ",
  "parameters": {
    "description": "string (required) - Natural language description of what to find, e.g. 'functions that handle HTTP errors', 'classes that inherit from Tool'",
    "path": "string (optional) - Root directory or file to search (defaults to current directory)",
    "top_k": "integer (optional) - Maximum number of results to return",
    "strategy": "string (optional) - Search strategy: 'semantic' (keyword-based), 'structural' (structural pattern extraction), or 'combined' (both)"
  }
}
```

#### symbol_trace

Trace a symbol's full provenance across a codebase: definition site(s), all import statements, all call/reference sites, and type annotations. Replaces the manual combination of python_ast + grep + import_graph.

```json
{
  "name": "symbol_trace",
  "kind": "READ",
  "parameters": {
    "symbol": "string (required) - Symbol name to trace (function, class, variable, or alias)",
    "path": "string (optional) - Root directory or file to search (defaults to current directory)",
    "include_tests": "boolean (optional) - Whether to include test files in the trace"
  }
}
```

### Testing & Coverage

#### pytest_run

Run pytest on test files.

Targets are test paths or node IDs, not command-line options. Tool options are
passed separately from the target. Results distinguish test execution, collection
without execution, and no tests collected; successful collection does not establish
that tests passed. Invalid arguments and failed or missing checkers are failures.

Execution success requires completed-session evidence and at least one passed
test call. Inherited collection-only settings, entirely skipped runs, and missing
evidence cannot establish passing execution. The explicit Henchman pytest plugin
records this evidence independently, preserving project-configured JUnit report
destinations. Timeout and cancellation trigger bounded subprocess cleanup.

```json
{
  "name": "pytest_run",
  "kind": "EXECUTE",
  "parameters": {
    "path": "string (required) - Test path: file, directory, or file::test_name",
    "keyword": "string (optional) - Filter tests by keyword expression",
    "markers": "string (optional) - Filter tests by marker expression",
    "verbose": "boolean (optional) - Enable verbose output",
    "timeout": "integer (optional) - Timeout in seconds",
    "coverage": "boolean (optional) - Collect coverage",
    "coverage_source": "string (optional) - Source directory for coverage",
    "parallel": "integer (optional) - Number of parallel workers",
    "collect_only": "boolean (optional) - List tests without running"
  }
}
```

#### coverage_map

Parse coverage report and show uncovered lines.

```json
{
  "name": "coverage_map",
  "kind": "READ",
  "parameters": {
    "path": "string (required) - Path to coverage.xml or coverage.json file",
    "file_filter": "string (optional) - Filter to show only matching files",
    "show_branches": "boolean (optional) - Include branch coverage information",
    "per_function": "boolean (optional) - Show per-function coverage breakdown"
  }
}
```

#### test_gen

Generate pytest test stubs from Python signatures.

Both styles produce Python scaffolds that can be compiled, formatted and collected.
Generated tests carry explicit `pytest.mark.skip` TODO markers. Implement meaningful
inputs and assertions, then remove those markers. Creating or collecting these
stubs does not verify the source behavior; unfinished stubs never count as passing
checks and do not call application code with invented inputs.

```json
{
  "name": "test_gen",
  "kind": "WRITE",
  "parameters": {
    "path": "string (required) - Path to Python source file",
    "output_path": "string (optional) - Path to write generated test file",
    "style": "string (optional) - Test style: 'class' or 'function'"
  }
}
```

### Git Operations

#### git_ops

Run git operations: status, log, blame, show, etc.

For `show`, `ref` selects the commit (default `HEAD`) and `path` restricts its diff
to that file. Paths containing spaces remain a single argument after Git's `--`
separator.

```json
{
  "name": "git_ops",
  "kind": "READ",
  "parameters": {
    "action": "string (required) - Git action: 'status', 'log', 'blame', 'show', 'branch_list', 'stash_list', 'diff_branches'",
    "path": "string (optional) - File path for blame/log",
    "ref": "string (optional) - Git ref/commit for show/log",
    "ref2": "string (optional) - Second ref for diff_branches",
    "max_count": "integer (optional) - Max entries for log",
    "start_line": "integer (optional) - Start line for blame range",
    "end_line": "integer (optional) - End line for blame range",
    "stat": "boolean (optional) - Show diffstat summary",
    "cwd": "string (optional) - Working directory"
  }
}
```

#### diff_view

Show git diff of current changes or compare branches.

```json
{
  "name": "diff_view",
  "kind": "READ",
  "parameters": {
    "path": "string (optional) - File path to limit diff to",
    "staged": "boolean (optional) - Show staged changes",
    "compare": "string (optional) - Compare two refs, e.g., 'main..feature'",
    "stat": "boolean (optional) - Show file summary",
    "name_only": "boolean (optional) - Show only names of changed files",
    "context_lines": "integer (optional) - Number of context lines around changes",
    "cwd": "string (optional) - Working directory"
  }
}
```

### Environment & Package Management

#### env_inspect

Inspect Python environment: version, packages, project type.

```json
{
  "name": "env_inspect",
  "kind": "READ",
  "parameters": {
    "cwd": "string (optional) - Working directory to inspect",
    "packages": "array (optional) - Specific packages to check versions for",
    "show_env_vars": "boolean (optional) - Include environment variables",
    "show_path": "boolean (optional) - Include sys.path entries"
  }
}
```

#### pip_inspect

Query installed Python packages.

```json
{
  "name": "pip_inspect",
  "kind": "READ",
  "parameters": {
    "package": "string (optional) - Specific package name to inspect"
  }
}
```

### Python Execution

#### python_exec

Start Python code in a background subprocess by default. Each invocation returns
a unique task ID; see [background execution](#background-execution). Set
`background: false` to wait for stdout/stderr in the tool result.

Supply Python source in `code`, and use `cwd` to select its working directory.
The `command` argument and shell syntax are not translated into Python. Missing
or blank code returns guidance and performs no execution; use `shell` only when
it is allowed in the current tool scope.

Invocation classification is per snippet: code that only evaluates
side-effect-free expressions is classified `READ` (available in Plan Mode);
anything else stays `EXECUTE`. See [Tool Kinds](#tool-kinds).
Pure expressions run with Python's isolated and no-site flags, so working-directory
and `PYTHONPATH` startup hooks cannot add effects to a read-only invocation.

Before either execution mode, an isolated worker applies Black's in-memory
string API with default settings to the snippet. It does not inspect the working
directory or load project Black configuration. Formatting has a 300 ms deadline,
with time reserved for worker cleanup within a half-second overhead budget;
snippets larger than 12 KiB skip formatting. Formatted output has the same 12 KiB
limit so expansion cannot exceed process argument limits on Windows. Formatting errors, unavailable Black,
incomplete output, and timeouts log a warning and execute the original source.
Python syntax/runtime errors and execution timeouts still report execution failures.
Cancellation stops formatting and prevents execution.

Workspace files are never tracked or automatically formatted by `python_exec`,
even for foreground calls or repositories with more than 5,000 sources. Use
`code_format` explicitly for generated Python files before dependent verification.

```json
{
  "name": "python_exec",
  "kind": "EXECUTE",
  "parameters": {
    "code": "string (required) - Python code to execute",
    "timeout": "integer (optional) - Execution timeout in seconds",
    "cwd": "string (optional) - Working directory for execution",
    "background": "boolean (optional, default true) - Return a tracked task ID immediately"
  }
}
```

#### traceback_parse

Parse Python traceback into structured data.

```json
{
  "name": "traceback_parse",
  "kind": "READ",
  "parameters": {
    "traceback": "string (required) - The traceback text to parse"
  }
}
```

### Shell Execution

#### shell

Start shell commands in the background by default. Each call returns a unique
task ID. Set `background: false` when the caller needs the command's final output
in the same result. Interactive terminal input requires foreground execution.

Input, output, append and descriptor redirects are supported, including
`> file`, `>> file`, `< file`, `2>&1` and `> /dev/null`. Redirect destinations
are not banned by the default validator or secure-shell presets. An explicit
custom `allow_redirects=False` policy can still prohibit them.

Quoted Python snippets such as `python -c "value = 4; print(value + 1)"` are
validated as a whole command and passed through unchanged apart from outer
whitespace. Semicolons, ampersands and pipes inside quoted arguments are not
split by the default shell tool's validation pass. Existing pattern restrictions,
quote validation and EXECUTE approval still apply. This is not a shell sandbox.
The lower-level helper's optional command-prefix policy retains its existing
conservative subcommand checks and quoting limitations.

Commands must stay on one line. Literal control characters and escaped `\n`
sequences are rejected, including inside quoted arguments. These rejections give
recovery guidance while retaining the validation failure. For multiline Python,
use `python_exec` when it is allowed in the current agent's tool scope; otherwise
submit supported single-line commands.

Invocation classification is per command: side-effect-free single commands
(read-only allowlist programs, read-only `git` subcommands, `find` without
mutating flags, no chaining/redirects/substitution) are classified `READ`
(available in Plan Mode); everything else stays `EXECUTE`. See
[Tool Kinds](#tool-kinds).

Commands use the host's native default shell: `/bin/sh` on Linux/macOS and
`cmd.exe` on Windows. Use syntax and quoting for that shell; POSIX commands are
not translated into Windows commands. Output capture, working-directory selection,
and timeouts use the subprocess transport on all platforms. Linux additionally
checks procfs for exited processes when available.

Interactive PTY forwarding and the noninteractive `sudo -A` rewrite are Unix-only.
Windows runs commands through its native shell without importing Unix terminal
modules or applying the sudo rewrite. `python_exec` is useful for portable Python
snippets: it uses the current interpreter directly and captures UTF-8 stdout/stderr
independently of the inherited console encoding.

```json
{
  "name": "shell",
  "kind": "EXECUTE",
  "parameters": {
    "command": "string (required) - Command to execute",
    "timeout": "integer (optional) - Command timeout in seconds",
    "cwd": "string (optional) - Working directory",
    "interactive": "boolean (optional) - Enable interactive mode with background=false",
    "background": "boolean (optional, default true) - Return a tracked task ID immediately"
  }
}
```

!!! warning "Security Note"
    Shell commands require user confirmation by default. The `HENCHMAN_CLI=1` environment variable is set during execution.

### Background execution

`shell` and `python_exec` share the existing project task service. Multiple shell
and Python jobs can run simultaneously; starting another job does not replace
an earlier one. A launch receipt means the process started, not that it passed.

| Tool | Use |
|------|-----|
| `task_list` | List job IDs and states for the current project |
| `task_get(task_id=...)` | Inspect one job's state and exit code |
| `task_output(task_id=..., lines=25)` | Read captured output while running or after exit |
| `task_stop(task_id=...)` | Stop a selected job without stopping other jobs |

Use the ID from each launch when checking results. Python output is unbuffered
and UTF-8. Both tools retain `cwd` and timeout behavior (`0` means unlimited).
Workspace formatting is skipped at background launch because the process may
still be writing files. After completion, run `code_format` on changed Python
files before dependent verification. Foreground `shell` calls use the automatic
workspace-formatting transaction; `python_exec` only formats its input snippet
in either mode. Launch receipts explain when generated files need explicit formatting.
Keep commands in the foreground of their own subprocess (omit trailing `&`) so
the task ID represents their lifetime. On POSIX, child processes in the owned
process group are terminated when the parent exits or the task is stopped.
Windows currently terminates the direct subprocess.
Jobs and captured logs live under `.henchman/tasks/`. Running processes belong
to the current application runtime; saved records/logs survive exit, but jobs
are not a detached service and are not restarted on session resume.
Before dispatch, the service persists `queued` intent, then `started` before
process creation and `running` after receiving its process handle. `queued`
means not dispatched and requires explicit disposition; it never starts on reload.
When a fresh runtime loads a record last saved as `started` or `running`, it reports
`outcome_unknown` and preserves the observed timestamps and exit-code evidence.
It does not invent a stop time or infer ownership from the saved PID. `task_get`
and `task_list(status="outcome_unknown")` expose these records; `task_output`
continues to expose eligible retained evidence. `task_stop` and waiting refuse
unowned processes. Inspect external process state before explicitly starting new
work; no command is replayed from the saved argv.

The versioned `.henchman/tasks/index.json` stores index and per-task revisions,
a store identity and a damage-detection checksum. A stable `index.lock` protects
conditional updates across processes; keep that lock with the index. Independent
task updates merge, while stale updates to the same task fail explicitly. Missing,
corrupt, replaced or downgraded known authority blocks dispatch. The checksum
does not authenticate against malicious replacement. Legacy list indexes remain
readable. Resolving a correlated operation does not resolve its child task, and
there is no trusted task-disposition command yet.

New task output is decoded and redacted before persistence, with a 1 MiB capture
limit and a visible truncation marker. Task metadata and private atomic index
writes share the known-credential policy; raw command arguments and environment
values still reach the child unchanged. Capture failures stop/reap the owned
process and settle its waiter with an explicit failure. Output readers and
timeout diagnostics reject linked or substituted files.

Indexed terminal logs are migrated on load/read using private atomic replacement:
up to 16 MiB of valid UTF-8 input is examined and at most 1 MiB is retained.
Malformed, oversized, linked or changed originals remain untouched with an
`evidence_migration_error` diagnostic. Unresolved logs are projected on read without
replacement, so observing another runtime cannot detach its active output writer. Corrupt
indexes are preserved for explicit repair instead of overwritten with empty
history. Migration only covers indexed logs and registered credentials. POSIX
uses directory descriptors; Windows checks file identities and reparse points
without the same directory-descriptor guarantee. Persistent records never confer
ownership of another process or authorize replay after interruption.

Interactive chat accepts messages while work is underway and processes them in
order at agent-turn boundaries. `/goal pause` is available during processing;
it stops future goal turns, while the current turn can finish. Esc interrupts
the active turn and pauses its goal. Background jobs remain independently
controllable with `task_stop`.

### Goal completion

`/goal <objective>` starts a session goal and keeps the interactive agent working
across turns. `/goal status`, `/goal pause`, `/goal resume`, `/goal complete` and
`/goal clear` manage its lifecycle. Use `/goal set <objective>` for objectives
that would otherwise look like a control word. Goals persist with sessions.

The registered `goal_status` tool reads the current goal or completes it using
its current `goal_id` and a verification summary. Replacing a goal invalidates
old completion IDs. Agent completion is rejected while project jobs are queued,
started, running, outcome-unknown, or have failed status persistence. The user can
explicitly override completion with `/goal complete`; that is not verification proof.
Runtime errors and interrupted turns pause continuation. This is interactive
session execution, separate from cron scheduling.

### Web Operations

#### web_fetch

Fetch content from a URL.

HTTP(S) fetches reject private, loopback and special IP targets, including numeric
aliases. DNS answer sets and the connected peer are checked before HTTP headers
are sent; every redirect is checked again with fresh connection/DNS resolution.
TLS retains the original hostname and certificate verification. Redirects share
one total timeout and stop after ten hops. Environment proxies, netrc credentials
and cookies are disabled. Explicit initial URL authentication remains only on
the same origin and is permanently removed after an origin change; redirects
cannot introduce credentials.

This implementation supports exact `tools.network_allowed_hosts` restrictions
with live registry authorization checks on supported transports. Restricted
fetches require aiohttp's public socket hook; unsupported versions refuse before
DNS. See [host policy and revocation limits](configuration.md#exact-network-host-restrictions).
This boundary does not filter model traffic or provide OS isolation.

```json
{
  "name": "web_fetch",
  "kind": "NETWORK",
  "parameters": {
    "url": "string (required) - URL to fetch",
    "max_length": "integer (optional) - Maximum content length",
    "timeout": "integer (optional) - Request timeout in seconds"
  }
}
```

#### web_search

Search the web for information.

```json
{
  "name": "web_search",
  "kind": "NETWORK",
  "parameters": {
    "query": "string (required) - The search query",
    "max_results": "integer (optional) - Maximum number of results"
  }
}
```

#### deep_research

Perform end-to-end web research on a question: generates sub-queries, searches the web for each, fetches top results, and synthesizes findings into a structured Markdown report with citations. Use instead of multiple web_search + web_fetch calls.

```json
{
  "name": "deep_research",
  "kind": "NETWORK",
  "parameters": {
    "question": "string (required) - Research question or topic to investigate",
    "max_sources": "integer (optional) - Maximum number of sources to gather (default: 5)",
    "focus": "string (optional) - Optional focus keyword to narrow sub-queries (e.g. 'Python', 'security', 'performance')"
  }
}
```

### Knowledge Graph & RAG

#### kg_query

Query the project knowledge graph.

```json
{
  "name": "kg_query",
  "kind": "READ",
  "parameters": {
    "action": "string (required) - Query action: 'search', 'get', 'neighbors', 'relations', 'important', 'stats'",
    "query": "string (required) - Search term or entity id",
    "entity_type": "string (optional) - Filter by entity type",
    "depth": "integer (optional) - Hop depth for neighbors",
    "top_k": "integer (optional) - Number of results for important"
  }
}
```

#### kg_update

Update the project knowledge graph.

```json
{
  "name": "kg_update",
  "kind": "WRITE",
  "parameters": {
    "action": "string (required) - Update action: 'add_entity', 'add_observation', 'add_relation', 'remove_entity'",
    "entity_id": "string (required) - Entity id for all actions",
    "entity_type": "string (optional) - Type for add_entity",
    "name": "string (optional) - Human-readable name for add_entity",
    "description": "string (optional) - Description for add_entity or observation",
    "file_path": "string (optional) - Source file path for add_entity",
    "tags": "array (optional) - Tags for add_entity",
    "observation": "string (optional) - Observation text for add_observation",
    "source": "string (optional) - Source citation for add_observation",
    "target_id": "string (optional) - Target entity id for add_relation",
    "relation_type": "string (optional) - Relation type for add_relation"
  }
}
```

#### rag_search

Search the codebase using semantic similarity.

```json
{
  "name": "rag_search",
  "kind": "READ",
  "parameters": {
    "query": "string (required) - Natural language query to search for",
    "top_k": "integer (optional) - Number of results to return"
  }
}
```

#### research_notes

Persistent in-session note-taking scratchpad. Write, append, read, list, or search named notes stored in ~/.henchman/notes/. Use to accumulate research findings and decisions across multiple agent turns.

```json
{
  "name": "research_notes",
  "kind": "WRITE",
  "parameters": {
    "action": "string (required) - Action: 'write', 'append', 'read', 'list', or 'search'",
    "tag": "string (optional) - Note identifier/name (required for write/append/read)",
    "content": "string (optional) - Note content (required for write/append)",
    "query": "string (optional) - Search query (required for search)"
  }
}
```

### Agent Interaction

#### ask_user

Ask a question through a runtime-supplied asynchronous input handler. Success means
an actual nonempty answer was received. Unbound calls, missing answers, and timeout
are failures; cancellation propagates to the handler.

The classic REPL collects a literal answer with a dedicated terminal prompt. It
serializes questions and suspends the interrupt-key reader while input is active.
EOF means unanswered; Ctrl+C cancels the active question. Answers bypass command
expansion and command history and are retained as tool results in session history.

Textual collects answers in a modal dialog. Escape cancels without an answer;
blank submissions leave the dialog open. Questions and tool approvals are
serialized. Timeout or task cancellation retires the dialog. If an unrelated
modal obscures it, that modal stays open and the expired question closes when
it becomes visible again; queued tool prompts wait for its removal.

Headless execution has no input channel and reports the unanswered question
explicitly. Embedders can pass `question_handler` when constructing `AskUserTool`
or `ToolManager`. Help, doctor, and tool-search status report this runtime
dependency through the shared discovery capability matrix.

**When to use `ask_user`:**
- **Clarification needed**: When requirements are ambiguous or incomplete
- **Decision confirmation**: Before making significant changes or taking risky actions
- **Preference gathering**: When multiple valid approaches exist and user preference matters
- **Missing information**: When the agent lacks necessary context or credentials
- **Complex trade-offs**: When decisions involve subjective judgment or business priorities

**Best practices:**
1. **Be specific**: Ask clear, focused questions that users can answer easily
2. **Provide context**: Explain why you're asking and what depends on the answer
3. **Offer options**: When appropriate, present choices with pros/cons
4. **Set reasonable timeouts**: Use `timeout` parameter for time-sensitive decisions
5. **Follow up**: Use the answer to continue the task or ask clarifying follow-ups

**Example scenarios:**
- "Which database should I use for this feature: PostgreSQL or SQLite?"
- "The file `config.yaml` already exists. Should I overwrite it or create a backup first?"
- "I found 3 possible solutions. Which approach aligns best with your priorities?"
- "Which configured environment should I use for verification?"

```json
{
  "name": "ask_user",
  "kind": "READ",
  "parameters": {
    "question": "string (required) - The question to ask the user",
    "timeout": "integer (optional) - Timeout in seconds (0 for no timeout)"
  }
}
```

### Background Subagent Tools

These tools use the active orchestrator's process-owned background runtime.
They are available to the default primary agent; restricted agents must have the
tool explicitly in scope. Normal plan-mode and execution-approval policies apply.

| Tool | Parameters | Result and policy |
| --- | --- | --- |
| `invoke_subagent` | Required `task`, `role`, `system_prompt`, and `tools` array | Returns a new `conversation_id` immediately; EXECUTE policy |
| `send_message` | `conversation_id`, `message` | Queues a follow-up or parent reply; WRITE policy |
| `manage_subagents` | `action: list` (default), or `get`/`cancel` with `conversation_id` | Returns live records/bounded output; list/get READ, cancel WRITE |

Example tool arguments for an independent inspection task:

```json
{
  "task": "Inspect the parser and report concrete validation gaps.",
  "role": "parser reviewer",
  "system_prompt": "Inspect the assigned parser and return findings with file references.",
  "tools": ["read_file", "glob", "grep"]
}
```

Every delegated tool must be available to the caller; an empty list grants no
tools. Role names do not select a preset. Each child owns a separate conversation,
and `send_message` follow-ups retain its history. A child can use the destination
`parent` to send assistance requests or progress to its owner. Dynamic messaging
uses `conversation_id`; legacy workspace-channel messaging still uses its
`workspace`/`sender` parameters, and those addressing modes cannot be mixed.

Records report `running`, `idle`, `waiting_for_input`, `errored`, or `done`, plus
`cancelled`, `error`, `output`, and `output_truncated`. Completion and assistance
notifications arrive at safe parent turn boundaries; do not repeatedly poll status
to wait for results. Cancellation joins owned child work; application exit and
conversation reset also stop unfinished subagents. These conversations are not
detached jobs or persistent session checkpoints. See
[agent lifecycle and scope](agents.md#dynamic-background-subagents).

### Named-Role Delegation

#### delegate_task

Delegate a task to a specialist agent. This is a **critical tool** for the multi-agent system that enables the Tech Lead to leverage specialized expertise for complex tasks. Each specialist agent starts with a CLEAN context, so you MUST provide all relevant information in the structured parameters.

**When to use `delegate_task`:**
- **Specialized expertise needed**: When a task requires specific skills (architecture, research, implementation, data engineering)
- **Complex task decomposition**: When a large task needs to be broken down and handled by specialists
- **Parallel work**: When multiple tasks can be worked on simultaneously by different specialists
- **Quality assurance**: When specialized review or testing is needed
- **Knowledge transfer**: When you want to document how a specialist would approach a problem

**Specialist Agents Available:**
- **`planner`**: Architecture design, task decomposition, structured planning, system design
- **`explorer`**: Research, documentation, code exploration, knowledge gathering
- **`engineer`**: Implementation, testing, debugging, code refactoring
- **`data_engineer`**: Data pipelines, AWS infrastructure, PySpark/Pandas transformations, Airflow DAG design

**Best practices for effective delegation:**
1. **Be specific with `task`**: Provide precise, actionable descriptions with clear objectives
2. **Define verifiable `done_when`**: Specify explicit, testable completion criteria
3. **Provide complete `context`**: Include relevant decisions, constraints, and code snippets
4. **List required `files`**: Always specify files the specialist should read or modify
5. **Include `background`**: Summarize what other agents have already done
6. **Set clear `requirements`**: Specify acceptance criteria and constraints
7. **Acknowledge `depends_on`**: Document dependencies on prior work

**Example scenarios:**
- "Delegate API implementation to the engineer with specific endpoint requirements"
- "Ask the explorer to research best practices for authentication middleware"
- "Have the planner design the database schema for a new feature"
- "Request the data engineer to create an ETL pipeline for customer data"

**Critical reminder**: Specialist agents start with CLEAN context. Never assume they remember anything from prior conversations or delegations. Always provide complete information in the delegation parameters.

```json
{
  "name": "delegate_task",
  "kind": "EXECUTE",
  "parameters": {
    "agent": "string (required) - Specialist agent role: 'planner', 'explorer', 'engineer', 'data_engineer'",
    "task": "string (required) - Precise description of the task",
    "done_when": "string (optional) - Declared exit condition for the specialist",
    "completion_requirement": "actions (default) | response - Required execution evidence",
    "context": "string (optional) - Free-form context",
    "files": "array (optional) - List of file paths to read/modify",
    "background": "string (optional) - Summary of prior work",
    "requirements": "string (optional) - Explicit acceptance criteria",
    "depends_on": "string (optional) - Description of dependencies"
  }
}
```

Delegation requires an active orchestrator. Interactive and headless CLI runs
(including JSON formats) share that orchestrator and execute the selected
specialist. Standalone registry execution remains unavailable. Delegation is an
`EXECUTE` tool: the caller must have it registered, and normal plan-mode and
confirmation policies apply before starting a specialist. Cached specialists
inherit current parent plan mode and confirmation handling; explicit per-agent
auto-approval settings still apply.

The default `actions` requirement rejects a tool-free promise. Explicit `response`
allows advice based on supplied context to finish as `responded`. Neither mode
verifies that implementation requirements were met: `done_when` and `requirements`
are declared criteria, not automatically executed checks. Completion/tool-result
metadata includes `task_verified: false`; the lead must review actual artifacts
and verification evidence. See [completion semantics](architecture.md#overview).

### Plan Acceptance Checks

#### verify_plan_execution

Create an ordered checklist with optional acceptance checks, then run those checks
against the project. Actions are `create`, `list`, `next`, `complete`, `status`,
and `verify`. `complete` records reported step progress and optional evidence text;
it does not run checks or establish correctness. `verify` requires a `plan_id`
with recorded checks and executes their assertions independently of that text.

Create the checks before implementation when using `file_changed`, so its baseline
captures the original file. Checks cannot be changed through this tool after
creation; create a new plan to revise the assertions.

```json
{
  "action": "create",
  "title": "Repair invoice totals",
  "steps": ["Inspect existing calculation helpers", "Reuse the helper and test"],
  "checks": [
    {"kind": "file_exists", "path": "src/invoices.py"},
    {"kind": "file_contains", "path": "src/invoices.py", "text": "calculate_total"},
    {"kind": "file_changed", "path": "src/invoices.py"},
    {"kind": "pytest", "path": "tests/test_invoices.py", "timeout": 60,
     "inputs": ["src/invoices.py", "tests/test_invoices.py", "pyproject.toml"], "requirement_ids": ["REQ-total"]},
    {"kind": "command", "argv": ["ruff", "check", "src/invoices.py"], "expected_exit": 0, "timeout": 60,
     "inputs": ["src/invoices.py", "pyproject.toml"]}
  ]
}
```

Use the returned identifier with `{"action": "verify", "plan_id": "plan-..."}`.

| Check kind | Assertion |
|------------|-----------|
| `file_exists` | The project-relative path resolves to a regular file. |
| `file_contains` | A UTF-8 file contains the supplied literal `text`. |
| `file_changed` | The file's SHA-256 differs from its creation-time baseline; creating a previously absent file also qualifies. Baseline read errors fail the check. |
| `command` | An argv command exits with `expected_exit` (default `0`). |
| `pytest` | Pytest exits successfully and its independent session evidence confirms completed test execution with at least one passed test call. Collection-only and entirely skipped runs cannot pass. |

Paths use project-relative forward slashes. Absolute paths, parent traversal, and
symlinks resolving outside the project are rejected for file and pytest targets.
Pytest paths can include node selectors such as `tests/test_invoices.py::test_total`.
Command argv runs in the project directory without shell interpolation. It is
ordinary process execution, not a sandbox; command arguments and test code can
access whatever the process permits. The tool has kind `EXECUTE` and follows the
runtime's normal execution approval policy. The confirmation request includes the
recorded checks and commands; `status` also displays their specifications.

A plan can record 1–20 checks, which run sequentially. File-content reads are
limited to 1 MiB; the `file_exists` assertion reads metadata, while its separate
freshness observation reads eligible content. Captured stdout and stderr each
retain at most 64 KiB and report truncation. Command and pytest timeouts default
to 60 seconds and accept integers from 1 to 300. Each command accepts up to 64
arguments and 16 KiB of UTF-8 argument text. Paths and literal text are bounded to
4,096 characters. The full check specification, including captured baselines,
is limited to 512 KiB of canonical JSON. These limits bound observations; they do not establish a total
application memory budget or verify operation on the target 16 GB laptop with CPU operation and optional GPU acceleration.

Reports include `checks_passed`, per-check observations, timestamps, and a
`spec_digest` binding a finished report to its recorded specifications.
`task_verified` remains `false`: a literal match does not prove reuse, a changed
file does not prove a correct fix, and passing selected tests does not prove
complete requirements coverage. The tool does not establish that criteria were
approved by a user. Select checks that reflect the task and review their scope.

Records live in `.henchman/plans/verification.json`. `status` shows reported step
progress, historical observations and current declared-input status. Legacy plans
without checks remain readable and require a new plan with checks before `verify`.
If saving completed observations fails, verification reports the storage error
and attempts to retain a small terminal failure record without rerunning checks.

Verification evidence shares the runtime's configured-credential policy, including
registered MCP credentials and earlier values after rotation. Titles, step evidence,
captured output and errors are projected before persistence and display. New
executable checks containing known credentials in arguments, paths, literal text,
input declarations or requirement tags are rejected before baseline reads; use
environment references in the invoked program instead of literal credentials.

If rotation makes a saved specification sensitive, inspection returns empty
executable checks and `checks_unavailable` with its original specification digest.
The current status becomes `unavailable`; redacted display values are never executed.
Read-only inspection does not rewrite old bytes. Runtime tool binding, verification
and subsequent writes sanitize retained evidence under the writer lock; embedders
can explicitly call `sanitize_persisted_evidence()`. A sanitation failure blocks
this verification tool with a diagnostic and preserves the prior storage.
Credential redaction is limited to known or marked values and does not detect
arbitrary secrets. Redacting output alone does not discard independently observed
exit evidence; changes to proof-bearing content revoke current verification.

#### Declared-input freshness

Checks may include `inputs`, a list of 1–256 distinct project-relative files, and
up to 32 `requirement_ids` of 1–128 ASCII letters, digits or `_.:/-`. These IDs tag
assertions; they do not establish user approval or requirements coverage. File
assertions always include their target. Commands and pytest need explicit `inputs`
to establish current content evidence; include relevant source, tests and config.
Directories, globs and transitive dependencies are not inferred. An incomplete
scope cannot establish that all inputs affecting a command were unchanged.

The service fingerprints declared supported contents and modes around each check
and the full sequence, and binds file assertions to the bytes read. If they differ, `checks_passed` is false and `freshness`
is `stale`, while individual historical results remain available. Otherwise
`current_checks_passed` is true only when every check passed and every check has
available declared-input evidence. Unscoped or unsupported inputs produce
`unverified`; a passing command exit may still be retained as a historical result.
Missing executables and timeouts have explicit per-check `not_run` and `timeout`
states and current status `incomplete`.

`PlanExecutionService.verification_status(plan_id)` reads the current files and
returns `pass`, `fail`, `stale`, `unverified`, `not_run`, `incomplete`, `running`,
`cancelled`, `error` or credential-sensitive `unavailable`. It does not rewrite saved observations. Manual edits,
formatting and subagent changes to declared files are detected without relying on
modification times. Restores also retain their existing explicit invalidation.
Legacy reports without input evidence remain unverified until checks run again.

Input observation uses the checkpoint reader's supported file subset: regular
UTF-8 text or explicit absence, with no symlink traversal or ignored/private
content capture. It stores hashes and metadata, never input bytes. A run permits
at most 256 input files, 1 MiB per file and 16 MiB in total; each snapshot stops
between files after five seconds, with a Git ignore query bounded to two seconds.
Cancellation joins input and file-assertion readers. These are before/after observations, not a
filesystem lock: a later write can invalidate them, and transient changes restored
between observations are not detected. This reports configured check evidence;
it does not certify task correctness, environment identity or unlisted dependencies.

## Tool Kinds

Tools are classified by kind, which determines confirmation behavior:

| Kind | Description | Auto-Approve |
|------|-------------|--------------|
| `READ` | Read-only operations | Yes (by default) |
| `WRITE` | File modifications | No |
| `EXECUTE` | Shell commands | No |
| `NETWORK` | Network requests | No |

The static `kind` stays the tool's catalog classification. Tools with read-only
and mutating modes override `execution_kind()` per invocation; authorization
(including Plan Mode blocking), confirmation requests, and network retries use
that effective classification. The classifiers are conservative — anything that
cannot be proven read-only retains the static kind:

- `shell` downgrades side-effect-free single commands to `READ`: an allowlist of
  read-only programs, read-only `git` subcommands (`status`, `log`, `diff`,
  `show`), and `find` without mutating flags, with no chaining, redirection,
  or substitution. `sort` remains `EXECUTE` because it can write output and
  temporary files.
- `python_exec` downgrades snippets that only evaluate side-effect-free
  expressions to `READ`: no imports, assignments, subscripts, attribute
  access, definitions, or control flow, and calls limited to a small allowlist
  of pure builtins. Unsafe builtins cannot be loaded as values or aliased through
  comprehension variables.
- The `mcp` management tool downgrades its `status` and `discover` actions to
  `READ`; `mcp_auth` downgrades its `status` action to `READ`.
- MCP server tools always carry the conservative `NETWORK` execution
  classification: server trust controls local confirmation, not effect, so
  Plan Mode blocks MCP tool calls even from trusted servers.

These verdicts resolve from one centralized policy layer:
`ToolRegistry.evaluate_policy(name, params)` returns a `PolicyDecision`
computed by a single shared evaluator (`evaluate_effective_policy`) that
combines the effective Plan Mode boundary (including inherited scoped-registry
ancestry), the tool's per-invocation operation effect, and the registry's
approval grants. `authorize()` — and therefore `execute()`, batch execution,
and the orchestrated delegation path — consumes that same verdict, so
late-registered tools and scoped subagent registries cannot bypass the
boundary. Auto-approval suppresses the confirmation requirement in the
verdict but never overrides the Plan Mode denial.

Configured [restricted tool access](configuration.md#restricted-tool-access)
also applies through this evaluator and the actual file operation. Only qualified
implementations execute when restrictions are active; a tool's name or declared
kind cannot grant access. A `shell_secure` invocation's requested security level
must also satisfy the configured command, option and directory restrictions.

### Approval-reuse scoping

When a user confirms a confirmation request, the approval is recorded as a
session-scoped grant keyed to the exact approved scope: the registered tool
implementation, project identity, resolved physical targets, tool name, the
effective operation effect, a canonical digest of the parameters, and the
risk level. Repeated invocations with the identical scope are authorized
without re-prompting. Any change — different tool, different arguments,
escalated operation effect, or changed risk — invalidates the match and
re-prompts; denials record no grant, and auto-approved tools (whose
confirmation is suppressed by policy) record none either.

Grants are shared across a registry ancestry (a scoped subagent registry and
its parent see the same session grants) but are never shared across separate
registries or persisted to disk. Activating a different session (for example
`/chat resume`) clears the session's grants through
`ToolRegistry.clear_grants()`, so an approval from one session never carries
over. Policy, registration, parameters and target identity are rechecked after
approval, formatter waits and before retries. A changed invocation is denied and
must be retried for fresh approval; replacing a target inode also requires a new
grant. These checks do not confine filesystem/network access or prevent races
inside a tool's own I/O. Custom dispatchers using `authorize()` must recheck any
authority affected by their own later asynchronous work.

## Configuration

### Auto-Approve Read Tools

```yaml
tools:
  auto_approve_read: true  # Default
```

### Auto-Approve Specific Tools

```yaml
tools:
  auto_approve:
    - read_file
    - ls
    - glob
    - grep
```

### Shell Timeout

```yaml
tools:
  shell_timeout: 60  # seconds
```

## Creating Custom Tools

Extend the `Tool` class to create custom tools:

```python
from henchman.tools import Tool, ToolKind, ToolResult

class MyTool(Tool):
    @property
    def name(self) -> str:
        return "my_tool"
    
    @property
    def description(self) -> str:
        return "Does something useful"
    
    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "input": {"type": "string"}
            },
            "required": ["input"]
        }
    
    @property
    def kind(self) -> ToolKind:
        return ToolKind.READ
    
    async def execute(self, **params) -> ToolResult:
        result = process(params["input"])
        return ToolResult(content=result)
```

### Registering Custom Tools

```python
from henchman.tools import ToolRegistry

registry = ToolRegistry()
registry.register(MyTool())
```

## Tool Registry

The `ToolRegistry` manages tool registration and execution:

```python
from henchman.tools import ToolRegistry

registry = ToolRegistry()

# Get tool declarations for LLM
declarations = registry.get_declarations()

# Execute a tool
result = await registry.execute("read_file", {"path": "README.md"})
```
