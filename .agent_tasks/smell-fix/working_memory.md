# Working Memory - High Severity Code Smell Fix

## Current Task: Fix high severity code smells in Henchman-AI CLI

### Task Objectives:
1. Fix 33 high severity code smells identified in smell report
2. Ensure all fixes maintain functionality
3. Run tests to verify no regressions
4. Create smell-free scripts if needed

### Recent Files:
- `src/henchman/cli/app.py` - Primitive Obsession smell at line 645 (already uses RunConfig dataclass) - DECISION: Likely false positive, already uses dataclass
- `src/henchman/cli/commands/agent.py` - Feature Envy smell at line 33 - FIXED: Extracted helper methods
- `src/henchman/cli/commands/builtins.py` - Feature Envy smell at line 52 - FIXED: Extracted helper methods
- `src/henchman/cli/commands/chat.py` - Feature Envy smell at line 120 - FIXED: Extracted helper methods
- `src/henchman/cli/commands/context.py` - Primitive Obsession smell at line 273 - FIXED: Created RangeParameterConfig dataclass
- `src/henchman/cli/commands/context.py` - Duplicate Code smell at line 304 - FIXED: Created _handle_zero_to_one_parameter helper

### Active Context:
- Project: Henchman-AI CLI
- Total high severity smells: 33
- Fixed so far: 5 high severity smells
- Priority: Continue fixing remaining high severity smells
- Approach: Refactor methods to reduce external dependencies, extract parameter objects, eliminate duplicate code

### Decisions Made:
1. Start with Feature Envy smells as they're more actionable than the Primitive Obsession in app.py (which already uses a dataclass)
2. Create helper methods to reduce ctx access in command classes
3. Extract duplicate code into shared functions
4. Create parameter objects for functions with many primitive parameters
5. Keep backward compatibility where possible

### Completed Steps:
1. Created working memory document
2. Analyzed top 3 high severity smells
3. Fixed Feature Envy in commands/agent.py:33
4. Fixed Feature Envy in commands/builtins.py:52  
5. Fixed Feature Envy in commands/chat.py:120
6. Fixed Primitive Obsession in commands/context.py:273
7. Fixed Duplicate Code in commands/context.py:304

### Next Actions:
1. Run tests to verify fixes don't break functionality
2. Continue fixing remaining high severity smells
3. Check commands/mcp.py:121 - Feature Envy
4. Check commands/model.py:61 - Feature Envy
5. Check commands/model.py:125 - Feature Envy

### Insights Gained:
- Some smells might be false positives (app.py already uses RunConfig dataclass)
- Feature Envy is common in command pattern where commands need context access
- Need to balance refactoring with maintaining readability
- Dataclasses are effective for parameter objects

### Problems Encountered:
None yet