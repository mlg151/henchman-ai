# UI Improvements - Delegation Plan

## Overview
This document outlines the delegation of UI improvement tasks to specialist agents based on the technical assessment. Each task includes clear requirements, acceptance criteria, and context needed for successful implementation.

## Task Priority Matrix

| Task | Priority | Estimated Effort | Specialist | Dependencies |
|------|----------|------------------|------------|--------------|
| Add Additional Themes | High | 1 day | Engineer | None |
| Create Theme Command | High | 2 days | Engineer | Additional Themes |
| Apply Theme from Settings | High | 1 day | Engineer | Theme Command |
| Enhance Status Bar | High | 2 days | Engineer | None |
| Refactor REPL Class | Medium | 3 days | Engineer | None |
| Add Tab Completion | Medium | 2 days | Engineer | REPL Refactoring |
| Form-based Tool Input | Medium | 3 days | Planner + Engineer | REPL Refactoring |
| Progress Indicators | Medium | 2 days | Engineer | Status Bar Enhancements |
| Table/Tree View Renderers | Medium | 4 days | Engineer | None |
| Keyboard Shortcuts | Low | 3 days | Explorer + Engineer | REPL Refactoring |
| High-Contrast Themes | Low | 1 day | Engineer | Theme System |
| Diff Visualization | Low | 3 days | Engineer | Output Visualization |
| UI Plugin System | Low | 5 days | Planner + Engineer | All core UI components |

## Task Specifications

### Task 1: Add Additional Themes
**Specialist**: Engineer
**Objective**: Add 6 new built-in themes to ThemeManager
**Requirements**:
- Add solarized-dark, solarized-light, monokai, dracula, high-contrast-dark, high-contrast-light themes
- Themes should follow existing Theme dataclass structure
- All themes must be visually distinct and usable
- Update ThemeManager.__init__ to include new themes

**Acceptance Criteria**:
- `ThemeManager().list_themes()` returns all 8 themes
- Each theme can be retrieved with `get_theme()`
- Theme colors are appropriately set for each theme
- 100% test coverage maintained

**Context Files**:
- `src/henchman/cli/console.py`
- `tests/cli/test_console.py`

**Done When**:
- Tests pass with new themes
- Code review completed
- Documentation updated

### Task 2: Create Theme Command
**Specialist**: Engineer
**Objective**: Implement `/theme` slash command for theme management
**Requirements**:
- Command should support: `/theme list`, `/theme set <name>`, `/theme preview <name>`
- List should show available themes with current theme highlighted
- Set should change the active theme and provide feedback
- Preview should show sample output with the theme
- Command should be registered in builtins.py

**Acceptance Criteria**:
- `/theme list` shows all themes
- `/theme set solarized-dark` changes theme
- `/theme preview dracula` shows sample output
- Command appears in `/help` output
- 100% test coverage for new command

**Context Files**:
- `src/henchman/cli/commands/builtins.py`
- `src/henchman/cli/commands/theme.py` (new file)
- `tests/cli/test_theme_command.py` (new file)

**Done When**:
- Theme command fully functional
- Tests passing
- Integrated with help system

### Task 3: Apply Theme from Settings
**Specialist**: Engineer  
**Objective**: Load and apply theme from settings.yaml
**Requirements**:
- Load theme name from `settings.ui.theme` in app.py
- Create OutputRenderer with specified theme
- Pass themed renderer to REPL
- Fall back to default theme if specified theme not found
- Update settings documentation

**Acceptance Criteria**:
- Theme from settings.yaml is applied at startup
- Invalid theme name falls back to default with warning
- Theme persists across REPL restarts (when saved to settings)
- 100% test coverage maintained

**Context Files**:
- `src/henchman/cli/app.py`
- `src/henchman/cli/repl.py`
- `src/henchman/config/schema.py`
- `tests/cli/test_app.py`

**Done When**:
- Theme loaded from settings on startup
- Fallback mechanism working
- Tests updated

### Task 4: Enhance Status Bar
**Specialist**: Engineer
**Objective**: Add more information to status bar display
**Requirements**:
- Show provider name and model
- Show token usage percentage
- Show active tool count
- Show MCP connection status (if MCP manager exists)
- Format should be compact and informative

**Acceptance Criteria**:
- Status bar shows provider:model (e.g., "DeepSeek:deepseek-chat")
- Token percentage shown (e.g., "Tokens: 45%")
- Tool count shown (e.g., "Tools: 12")
- MCP status shows connected/total (e.g., "MCP: 2/3")
- All information updates in real-time

**Context Files**:
- `src/henchman/cli/ui_renderer.py`
- `src/henchman/cli/repl.py`
- `tests/cli/test_ui_renderer.py`

**Done When**:
- Enhanced status bar displays all information
- Information updates correctly
- Tests cover new functionality

### Task 5: Refactor REPL Class
**Specialist**: Engineer
**Objective**: Split REPL class into smaller, focused components
**Requirements**:
- Extract input handling to separate class
- Extract output handling to separate class  
- Extract command processing to separate class
- Extract tool execution to separate class
- Maintain backward compatibility
- Improve code organization and readability

**Acceptance Criteria**:
- REPL class under 400 lines
- Each extracted class has single responsibility
- All existing functionality preserved
- 100% test coverage maintained
- Code follows SOLID principles

**Context Files**:
- `src/henchman/cli/repl.py` (major changes)
- New files: `input_handler.py`, `output_handler.py`, `command_processor.py`, `tool_executor.py`
- Update all imports and tests

**Done When**:
- REPL refactored into smaller components
- All tests passing
- Code review completed

### Task 6: Add Tab Completion
**Specialist**: Engineer
**Objective**: Implement tab completion for commands and tool names
**Requirements**:
- Tab completes slash commands (/help, /theme, etc.)
- Tab completes tool names (read_file, write_file, etc.)
- Completion should work in middle of typing
- Should integrate with prompt_toolkit
- Should be configurable (enable/disable)

**Acceptance Criteria**:
- Typing `/th` + Tab completes to `/theme`
- Typing `!re` + Tab completes to `!read_file`
- Completion works at any position in input
- Configurable via settings
- 100% test coverage

**Context Files**:
- `src/henchman/cli/input.py`
- `src/henchman/cli/repl.py`
- `tests/cli/test_input.py`

**Done When**:
- Tab completion working for commands and tools
- Configurable via settings
- Tests passing

### Task 7: Form-based Tool Input
**Specialist**: Planner (design) + Engineer (implementation)
**Objective**: Create interactive forms for complex tool parameters
**Requirements**:
- Form system for tools with complex parameters
- Support for different input types (string, integer, boolean, file path)
- Validation of input values
- Integration with tool execution system
- User-friendly interface with clear prompts

**Acceptance Criteria**:
- Complex tools can use form input instead of JSON
- Forms validate input types and constraints
- User can navigate forms with keyboard
- Forms integrate with existing tool system
- 100% test coverage

**Context Files**:
- `src/henchman/cli/forms.py` (new)
- `src/henchman/cli/repl.py`
- `src/henchman/tools/base.py`
- `tests/cli/test_forms.py` (new)

**Done When**:
- Form system implemented and integrated
- At least 3 tools converted to use forms
- Tests covering form functionality

### Task 8: Progress Indicators
**Specialist**: Engineer
**Objective**: Add progress bars for long operations
**Requirements**:
- Progress bars for file operations
- Progress indicators for RAG indexing
- Progress for large file reads/writes
- Integration with Rich library
- Non-blocking progress display

**Acceptance Criteria**:
- File operations show progress
- RAG indexing shows progress
- Progress updates smoothly
- Doesn't block main thread
- 100% test coverage

**Context Files**:
- `src/henchman/cli/ui_renderer.py`
- `src/henchman/tools/builtins/file_read.py`
- `src/henchman/rag/system.py`
- `tests/cli/test_progress.py` (new)

**Done When**:
- Progress indicators working for key operations
- Non-blocking implementation
- Tests passing

## Delegation Protocol

### For Each Task:
1. **Engineer receives**:
   - Clear task specification
   - Acceptance criteria
   - Context files list
   - "Done when" conditions

2. **Engineer provides**:
   - Implementation following project conventions
   - 100% test coverage
   - Documentation updates
   - Code review ready implementation

3. **Tech Lead verifies**:
   - All acceptance criteria met
   - Tests passing
   - Code quality standards met
   - No breaking changes

### Communication Protocol:
- Each task should be delegated individually
- Specialist starts with CLEAN context (no prior task memory)
- All relevant information must be in delegation
- Questions should be directed to Tech Lead
- Completion should be reported with verification

## Timeline

### Week 1: Foundation
- Day 1-2: Task 1 (Additional Themes)
- Day 3-4: Task 2 (Theme Command)
- Day 5: Task 3 (Theme from Settings)

### Week 2: Enhanced UX
- Day 6-7: Task 4 (Status Bar Enhancements)
- Day 8-10: Task 5 (REPL Refactoring)

### Week 3: Interactive Features
- Day 11-12: Task 6 (Tab Completion)
- Day 13-15: Task 7 (Form-based Input)

### Week 4: Polish
- Day 16-17: Task 8 (Progress Indicators)
- Day 18-20: Testing and bug fixes

## Quality Requirements

All implementations must:
- Maintain 100% test coverage
- Follow existing code conventions
- Include comprehensive docstrings
- Pass all CI checks (ruff, mypy, pytest)
- Be backward compatible
- Follow security best practices

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Breaking changes | Thorough testing, backward compatibility focus |
| Performance impact | Profiling, async implementation |
| Complexity creep | Feature flags, optional features |
| Maintenance burden | Clean architecture, documentation |
| Accessibility gaps | Early testing, WCAG guidelines |

## Success Metrics

1. **User Satisfaction**: 40% increase (measured via feedback)
2. **Task Completion Time**: 25% improvement
3. **Help Command Usage**: 30% reduction (less confusion)
4. **Accessibility**: WCAG compliance for core features
5. **Performance**: No noticeable degradation

## Next Immediate Action

Delegate Task 1 (Additional Themes) to Engineer specialist with complete context.