# Enhanced Session Management

## Objective
Design and implement Enhanced Session Management for Henchman-AI with session branching, merging, templates, and export/import capabilities.

## Requirements
1. Maintain backward compatibility - existing sessions must still work
2. Session branching should preserve full history up to branch point
3. Merging should intelligently combine non-conflicting insights
4. Templates should support parameterization (e.g., project name, task type)
5. Export formats: JSON (full fidelity), Markdown (human readable)
6. All operations should be available via CLI commands

## Design Overview

### 1. Session Extensions
- Add `parent_id` field to Session for branching
- Add `branch_point` (message index where branch occurred)
- Add `template_id` for template-based sessions
- Add `parameters` dict for template parameterization

### 2. Branching System
- `branch_session(session_id: str, branch_point: int) -> Session`: Create new session with same history up to branch point
- Preserve all metadata and messages up to branch point
- New session gets new ID, references parent

### 3. Merging System
- `merge_sessions(session_ids: list[str], strategy: str = "union") -> Session`
- Strategies: "union" (combine all messages), "intersection" (common messages), "smart" (intelligent merge)
- Detect conflicts (same message index with different content)
- Create merged session with combined insights

### 4. Template System
- `save_template(session_id: str, name: str, parameters: dict) -> Template`
- `create_from_template(template_id: str, parameters: dict) -> Session`
- Templates store message patterns with parameter placeholders
- Parameter substitution in messages

### 5. Export/Import
- `export_session(session_id: str, format: str = "json") -> str`
- `import_session(data: str, format: str = "json") -> Session`
- Formats: JSON (full), Markdown (human readable with metadata)

### 6. CLI Commands
- `/session branch <id> <point>` - Branch from session
- `/session merge <id1> <id2> [strategy]` - Merge sessions
- `/session template save <id> <name>` - Save as template
- `/session template create <name>` - Create from template
- `/session export <id> [format]` - Export session
- `/session import <file>` - Import session

## Implementation Plan
1. Extend Session dataclass with new fields ✓
2. Implement branching in SessionManager ✓
3. Implement merging logic ✓
4. Implement template system ✓
5. Implement export/import formats ✓
6. Add CLI commands ✓
7. Write comprehensive tests ✓
8. Update documentation ✓

## Implementation Status: COMPLETE

### What was implemented:

1. **Enhanced Session Data Model** (`src/henchman/core/session.py`):
   - Added new fields to Session dataclass: `parent_id`, `branch_point`, `template_id`, `template_parameters`, `export_metadata`
   - Made TurnSummaryRecord hashable for deduplication in merge operations
   - Updated serialization/deserialization methods to handle new fields

2. **SessionManager Enhanced Methods**:
   - `branch_session()`: Create new session branched from existing session at specified message point
   - `merge_sessions()`: Merge multiple sessions with strategies: "union", "intersection", "smart"
   - `export_session()`: Export session to JSON (full fidelity) or Markdown (human readable)
   - `import_session()`: Import session from JSON format
   - `save_template()`: Save session as reusable template with parameterization
   - `create_from_template()`: Create new session from template with parameter substitution
   - `list_templates()`: List available templates
   - `delete_template()`: Delete a template

3. **CLI Integration** (`src/henchman/cli/commands/session.py`):
   - New `/session` command with subcommands:
     - `branch <id> <point> [tag]`: Branch from session
     - `merge <id1> <id2> [strategy] [tag]`: Merge sessions
     - `template save <id> <name>`: Save session as template
     - `template create <name>`: Create from template
     - `template list`: List templates
     - `template delete <id>`: Delete template
     - `export <id> [format]`: Export session
     - `import <file> [format]`: Import session
     - `list`: List sessions with enhanced info
   - Added to builtin commands and help menu

4. **Comprehensive Testing**:
   - Updated existing tests for Session and SessionManager
   - Added 14 new tests in `tests/core/test_session_enhanced.py`
   - Achieved 95%+ coverage for session.py module
   - All 78 tests passing

5. **Backward Compatibility**:
   - All existing session operations continue to work
   - New fields are optional and default to None/empty dicts
   - Existing session files can be loaded without modification
   - Updated serialization handles both old and new format

### Key Features:
- **Branching**: Create alternative conversation paths from any point
- **Merging**: Intelligently combine insights from multiple sessions
- **Templates**: Save common patterns with parameterization support
- **Export/Import**: JSON (full fidelity) and Markdown (human readable)
- **CLI Integration**: All operations available via `/session` command
- **Backward Compatible**: Existing sessions continue to work unchanged

### Usage Examples:
```bash
# Branch from session at message 5
/session branch abc123 5 "new-branch"

# Merge two sessions with smart strategy
/session merge session1 session2 smart "merged-session"

# Save session as template
/session template save session123 "Code Review Template"

# Create from template
/session template create template_xyz "new-review"

# Export session to Markdown
/session export session123 markdown

# Import session from JSON file
/session import session_backup.json json "imported-session"
```