# Common Errors

Common mistakes and anti-patterns to avoid in Henchman-AI development.

## Error 1: Full File Reads for Partial Information
**Description**: Reading entire large files when only specific sections are needed
**Impact**: Wastes 60-80% of context window, slows down task completion
**Example**: Reading 1000+ line files to find specific functions instead of using grep
**Frequency**: High (observed in 6/10 recent tasks)
**Solution**: Use targeted line ranges, grep for patterns first, read only needed sections
**Prevention**: Always check file size, use `start_line`/`end_line` parameters

## Error 2: Sequential Re-reading Without Context Retention
**Description**: Reading the same file multiple times during a single task
**Impact**: 2-3x more file reads than necessary, increases token usage
**Example**: Reading `textual_app.py` multiple times for different bug categories
**Frequency**: High (3.2 re-reads per task baseline)
**Solution**: Implement working memory system, cache recently read files
**Prevention**: Check working memory before reading, track `recent_files`

## Error 3: Missing Delegation for Specialized Tasks
**Description**: Attempting complex specialized work without delegating to appropriate specialist
**Impact**: Lower quality results, longer completion time, higher error rate
**Example**: Engineer trying to design architecture instead of delegating to Planner
**Frequency**: Medium (delegation rate currently 25%)
**Solution**: Use delegation decision matrix, delegate when ANY checklist item is YES
**Prevention**: Always consult delegation matrix before starting work

## Error 4: Skipping Thinking Protocol for Complex Tasks
**Description**: Jumping directly to implementation without structured thinking
**Impact**: Poor solution design, missed requirements, higher rework rate
**Example**: Implementing features without analyzing constraints or success criteria
**Frequency**: Medium (observed in 4/10 complex tasks)
**Solution**: Mandatory thinking protocol for all complex tasks
**Prevention**: Include thinking protocol in all specialist prompts

## Error 5: Not Using Available Tools Effectively
**Description**: Over-reliance on basic tools (read_file) instead of specialized tools
**Impact**: Inefficient workflows, missed optimization opportunities
**Example**: Using manual grep instead of `rag_search` for semantic code understanding
**Frequency**: Medium (observed in 5/10 tasks)
**Solution**: Learn tool combination patterns, use appropriate tools for each task type
**Prevention**: Review tool capabilities regularly, use tool combination patterns

## Error 6: Test-Driven Over-Reading
**Description**: Excessive file reading during test development and verification
**Impact**: 2-3x file reads during TDD cycles, slows down development
**Example**: Reading source files for each test case instead of targeted reading
**Frequency**: Medium (observed in test-heavy tasks)
**Solution**: Use test-specific reading patterns, cache test context
**Prevention**: Apply size-aware reading strategies to test files

## Error 7: Missing File Size Awareness
**Description**: Not adapting reading strategy based on file size
**Impact**: Performance degradation with large files, potential UI blocking
**Example**: Synchronous reading of large files blocks UI in Textual app
**Frequency**: Low (but high impact when occurs)
**Solution**: Implement chunking strategies, use async reading for large files
**Prevention**: Always check file size, apply size-based reading guidelines

## Error 8: Redundant Cross-Referencing
**Description**: Reading multiple files to understand relationships without caching
**Impact**: Exponential increase in file reads for complex tasks
**Example**: Reading all theme files to understand UI system instead of targeted reading
**Frequency**: Medium (observed in architecture exploration tasks)
**Solution**: Cache relationships in working memory, use knowledge graph
**Prevention**: Track cross-references, use semantic search tools

## Error 9: Lack of Strategic Reading Order
**Description**: Reading files in suboptimal order, requiring re-reading
**Impact**: 30-40% efficiency loss in comprehension
**Example**: Reading implementation files before understanding architecture
**Frequency**: Medium (observed in 4/10 exploration tasks)
**Solution**: Follow strategic reading order: structure → imports → specific functions
**Prevention**: Plan reading order before starting file exploration

## Error 10: Not Updating Knowledge Graph
**Description**: Discovering patterns but not recording them for future use
**Impact**: Lost institutional knowledge, repeated research
**Example**: Finding efficient tool combinations but not documenting them
**Frequency**: High (observed in 7/10 research tasks)
**Solution**: Mandatory knowledge graph updates after discoveries
**Prevention**: Include kg_update in all research workflows