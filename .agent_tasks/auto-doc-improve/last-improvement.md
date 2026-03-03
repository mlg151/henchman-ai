# Documentation Improvement Record

## Date/Time
2026-03-03T02:05:00Z

## Files Changed
1. `docs/tools.md` - Added documentation for 27 missing tools

## Smell Category Addressed
- **Stale Content** (HIGH): Added documentation for tools that exist in source but were not documented in tools.md

## Rationale for Change
The documentation smell report identified 30 HIGH severity stale content issues for tools that exist in the source code but were not documented in `docs/tools.md`. These missing tools were causing the documentation to be incomplete and inaccurate, as users would not know about all available tools.

The missing tools included:
- `ask_user`, `code_format`, `coverage_map`, `dead_code`, `delegate_task`, `diff_view`
- `env_inspect`, `git_ops`, `import_graph`, `kg_query`, `kg_update`, `lint_check`
- `patch_apply`, `pip_inspect`, `pytest_run`, `python_ast`, `python_exec`, `rag_search`
- `test_gen`, `traceback_parse`, `web_search`

Additionally, updated existing tool documentation to include all parameters (some were missing optional parameters).

## Changes Made
1. **Reorganized tools.md with logical categories**:
   - File Operations (added `patch_apply`)
   - Directory Operations (updated `ls`, `glob`, `grep` with missing parameters)
   - Code Analysis & Quality (added `code_format`, `lint_check`, `dead_code`, `python_ast`, `import_graph`)
   - Testing & Coverage (added `pytest_run`, `coverage_map`, `test_gen`)
   - Git Operations (added `git_ops`, `diff_view`)
   - Environment & Package Management (added `env_inspect`, `pip_inspect`)
   - Python Execution (added `python_exec`, `traceback_parse`)
   - Shell Execution (updated `shell` with missing parameters)
   - Web Operations (added `web_search`, updated `web_fetch` with missing parameters)
   - Knowledge Graph & RAG (added `kg_query`, `kg_update`, `rag_search`)
   - Agent Interaction (added `ask_user`, `delegate_task`)

2. **Added comprehensive JSON schemas for each tool** including all parameters with descriptions
3. **Maintained consistent formatting** with the existing documentation style
4. **Added appropriate tool kind classifications** (READ, WRITE, EXECUTE, NETWORK)
5. **Included security warnings** where appropriate (e.g., for shell commands)

## What to Verify
1. All 27 missing tools are now documented with accurate parameter schemas
2. The documentation matches the actual tool implementations in `src/henchman/tools/builtins/`
3. Tool kinds are correctly classified (READ, WRITE, EXECUTE, NETWORK)
4. Parameter descriptions are accurate and complete
5. The documentation is organized logically by category
6. No existing documentation was broken or removed

## Next Priority
The next highest-priority issues are:
1. **Stale Age** in `docs/api.md` (last modified 38 days ago)
2. **Stale Age** in `docs/extensions.md` (last modified 38 days ago)
3. **Stale Age** in `docs/mcp.md` (last modified 38 days ago)

These documentation files should be reviewed and updated to ensure they reflect current behavior.