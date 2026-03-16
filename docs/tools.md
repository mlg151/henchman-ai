# Tools

Henchman-AI includes a comprehensive set of 34 built-in tools that the AI agent can use to interact with your system.

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
| `code_format` | Code Analysis | WRITE | Run ruff format on Python files |
| `lint_check` | Code Analysis | READ | Run ruff/mypy linting |
| `dead_code` | Code Analysis | READ | Detect unused code |
| `python_ast` | Code Analysis | READ | Parse Python AST and symbol table |
| `import_graph` | Code Analysis | READ | Analyze import dependencies |
| `pattern_search` | Code Analysis | READ | Search code using natural language descriptions |
| `symbol_trace` | Code Analysis | READ | Trace symbol provenance across codebase |
| `pytest_run` | Testing | EXECUTE | Run pytest tests |
| `coverage_map` | Testing | READ | Parse coverage reports |
| `test_gen` | Testing | WRITE | Generate pytest test stubs |
| `git_ops` | Git Operations | READ | Run git operations (status, log, blame, etc.) |
| `diff_view` | Git Operations | READ | Show git diffs |
| `env_inspect` | Environment | READ | Inspect Python environment |
| `pip_inspect` | Environment | READ | Query installed packages |
| `python_exec` | Python Execution | EXECUTE | Execute Python code in subprocess |
| `traceback_parse` | Python Execution | READ | Parse Python tracebacks |
| `shell` | Shell Execution | EXECUTE | Execute shell commands |
| `web_fetch` | Web Operations | NETWORK | Fetch content from URLs |
| `web_search` | Web Operations | NETWORK | Search the web |
| `deep_research` | Web Operations | NETWORK | End-to-end web research with synthesis |
| `kg_query` | Knowledge Graph | READ | Query project knowledge graph |
| `kg_update` | Knowledge Graph | WRITE | Update knowledge graph |
| `rag_search` | RAG | READ | Semantic code search |
| `research_notes` | Knowledge Graph | WRITE | Persistent note-taking scratchpad |
| `ask_user` | Agent Interaction | READ | Ask user questions |
| `delegate_task` | Agent Interaction | READ | Delegate tasks to specialist agents |

## Built-in Tools

### File Operations

#### read_file

Read the contents of a file.

```json
{
  "name": "read_file",
  "kind": "READ",
  "parameters": {
    "path": "string (required) - Path to the file"
  }
}
```

**Example:**

```
Read the file src/main.py
```

#### write_file

Write content to a file (creates or overwrites).

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

Make surgical edits to a file using search and replace.

```json
{
  "name": "edit_file",
  "kind": "WRITE",
  "parameters": {
    "path": "string (required) - Path to the file",
    "old_str": "string (required) - Text to replace",
    "new_str": "string (required) - Replacement text"
  }
}
```

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

#### code_format

Run ruff format on Python files.

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

Parse Python file and return symbol table.

```json
{
  "name": "python_ast",
  "kind": "READ",
  "parameters": {
    "path": "string (required) - Path to Python file to analyze",
    "include_docstrings": "boolean (optional) - Include docstrings in output"
  }
}
```

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

Execute Python code in a subprocess.

```json
{
  "name": "python_exec",
  "kind": "EXECUTE",
  "parameters": {
    "code": "string (required) - Python code to execute",
    "timeout": "integer (optional) - Execution timeout in seconds",
    "cwd": "string (optional) - Working directory for execution"
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

Execute shell commands.

```json
{
  "name": "shell",
  "kind": "EXECUTE",
  "parameters": {
    "command": "string (required) - Command to execute",
    "timeout": "integer (optional) - Command timeout in seconds",
    "cwd": "string (optional) - Working directory",
    "interactive": "boolean (optional) - Enable interactive mode"
  }
}
```

!!! warning "Security Note"
    Shell commands require user confirmation by default. The `HENCHMAN_CLI=1` environment variable is set during execution.

### Web Operations

#### web_fetch

Fetch content from a URL.

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

Ask the user a question and wait for response. This is a **critical tool** for agent interaction that enables collaborative problem-solving by allowing the agent to seek clarification, gather requirements, or confirm decisions.

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
- "I need API credentials to proceed. Please provide your access token."

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

#### delegate_task

Delegate a task to a specialist agent.

```json
{
  "name": "delegate_task",
  "kind": "READ",
  "parameters": {
    "agent": "string (required) - Specialist agent role: 'planner', 'explorer', 'engineer', 'data_engineer'",
    "task": "string (required) - Precise description of the task",
    "done_when": "string (required) - Explicit exit condition",
    "context": "string (optional) - Free-form context",
    "files": "array (optional) - List of file paths to read/modify",
    "background": "string (optional) - Summary of prior work",
    "requirements": "string (optional) - Explicit acceptance criteria",
    "depends_on": "string (optional) - Description of dependencies"
  }
}
```

## Tool Kinds

Tools are classified by kind, which determines confirmation behavior:

| Kind | Description | Auto-Approve |
|------|-------------|--------------|
| `READ` | Read-only operations | Yes (by default) |
| `WRITE` | File modifications | No |
| `EXECUTE` | Shell commands | No |
| `NETWORK` | Network requests | No |

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
