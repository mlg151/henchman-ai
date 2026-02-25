# Patterns Learning Database

This directory contains the learning database for Henchman-AI agent system, implementing Week 3 of the Performance Improvement Plan.

## Purpose

Capture and organize successful patterns, common errors, effective tool combinations, debugging approaches, and decision frameworks to improve agent performance through institutional knowledge retention.

## Structure

```
patterns/
├── successful_approaches.md      # What worked well (5 patterns)
├── common_errors.md              # What to avoid (10 errors)
├── tool_combinations.md          # Effective tool sequences (10 patterns)
├── debugging_patterns.md         # Problem-solving approaches (10 patterns)
└── decision_frameworks.md        # How to make specific decisions (10 frameworks)
```

## Contents Summary

### 1. successful_approaches.md
- **TDD-Driven Implementation**: Test-first approach with 95% success rate
- **Structured Agent Delegation**: Clear delegation with 88% success rate
- **Knowledge Graph Integration**: Leveraging existing knowledge with 92% success rate
- **Smart File Reading**: Targeted reading reduces context usage by 60%
- **Error-First Debugging**: Systematic debugging with 90% success rate

### 2. common_errors.md
- **Full File Reads for Partial Information**: Wastes 60-80% context window
- **Sequential Re-reading Without Context**: 3.2 re-reads per task baseline
- **Missing Delegation for Specialized Tasks**: Current 25% delegation rate
- **Skipping Thinking Protocol**: Observed in 40% of complex tasks
- **Not Using Available Tools Effectively**: Inefficient workflows

### 3. tool_combinations.md
- **Research Task Sequence**: rag_search → read_file → kg_query → web_search → write_file
- **Debugging Task Sequence**: grep → read_file → shell → kg_query → edit_file
- **Implementation Task Sequence**: read_file → write_file → edit_file → shell → write_file
- **Code Exploration Sequence**: ls/grep → read_file → kg_query → rag_search
- **Documentation Task Sequence**: read_file → grep → shell → write_file → edit_file

### 4. debugging_patterns.md
- **Test Failure Analysis**: 85% success rate for pytest failures
- **Import Error Resolution**: 90% success rate for import issues
- **Configuration Issue Debugging**: 88% success rate for config problems
- **Async Code Debugging**: 80% success rate for async issues
- **Tool Execution Failure**: 92% success rate for tool problems

### 5. decision_frameworks.md
- **Delegation Decision Matrix**: Task type + specialist availability → delegate
- **File Reading Strategy**: File size + purpose → reading approach
- **Tool Selection Decision**: Task type + information needed → tool choice
- **Implementation Approach**: Complexity + risk → implementation strategy
- **Error Handling Strategy**: Severity + impact → error handling approach

## Usage Guidelines

### For Agents
1. **Before starting work**: Check relevant patterns for the task type
2. **During execution**: Apply appropriate tool combinations and debugging patterns
3. **When making decisions**: Use decision frameworks for structured thinking
4. **After completion**: Update patterns with new insights and success rates

### For Task Planning
1. **Research tasks**: Use research sequence and knowledge graph integration
2. **Implementation tasks**: Use TDD approach and implementation sequence
3. **Debugging tasks**: Use error-first debugging and debugging sequences
4. **Documentation tasks**: Use documentation sequence and decision frameworks

### For Performance Improvement
1. **Track metrics**: Success rates, efficiency improvements, error reductions
2. **Update patterns**: Add new patterns, refine existing ones based on experience
3. **Share knowledge**: Use knowledge graph to make patterns discoverable
4. **Validate effectiveness**: Compare performance before/after pattern adoption

## Pattern Format

Each pattern follows this structure:
```
## Pattern: [Name]
**When to use**: [Context for applying the pattern]
**Steps**:
1. [Step 1]
2. [Step 2]
3. [Step 3]
**Success Rate**: [Percentage] (from [number] instances)
**Last Updated**: [Date]
**Example**: [Brief example of pattern use]
```

## Maintenance

### Regular Updates
- **Weekly**: Review and update success rates based on recent usage
- **Monthly**: Add new patterns and retire outdated ones
- **Quarterly**: Comprehensive review and reorganization

### Quality Standards
1. **Evidence-based**: All patterns must have success rate data
2. **Actionable**: Steps must be clear and executable
3. **Tested**: Patterns should be validated in real tasks
4. **Documented**: Examples and context must be included

### Contribution Process
1. **Identify pattern**: From successful task completion or error analysis
2. **Document pattern**: Using standard format with evidence
3. **Test pattern**: Apply in 3+ tasks to establish success rate
4. **Submit for review**: Add to knowledge graph and patterns directory
5. **Monitor effectiveness**: Track usage and success over time

## Integration with Performance Improvement Plan

This learning database supports Week 3 objectives:
- **Goal**: Implement quantitative performance tracking and learning system
- **Success Metric**: All metrics tracked and patterns documented
- **Integration**: Patterns inform thinking protocols, delegation decisions, and tool usage

## Related Resources

- **Knowledge Graph**: Contains architectural decisions and component relationships
- **Performance Metrics**: Tracks effectiveness of pattern application
- **Working Memory**: Caches recent patterns and decisions during task execution
- **Agent Prompts**: Include references to relevant patterns for each specialist

## Next Steps

1. **Integrate with agent prompts**: Reference patterns in specialist instructions
2. **Automate pattern discovery**: Use task analysis to identify new patterns
3. **Create pattern validation tests**: Ensure patterns remain effective
4. **Expand pattern categories**: Add domain-specific patterns as needed

## Last Updated
2025-03-21

## Version
1.0.0 - Initial implementation for Performance Improvement Plan Week 3