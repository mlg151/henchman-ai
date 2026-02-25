# Decision Frameworks

Structured approaches for making specific types of decisions in Henchman-AI development.

## Framework 1: Delegation Decision Matrix
**When to use**: Before starting any work to determine if delegation is appropriate
**Decision Factors**:
1. Task type (architecture, research, implementation, documentation, debugging)
2. Specialist availability and expertise
3. Complexity of the task
4. Clear requirements and success criteria
**Decision Rule**: If ANY delegation checklist item is YES → DELEGATE
**Checklist**:
- ✅ Is this a specialized task type?
- ✅ Would a specialist do this better/faster?
- ✅ Can I provide clear requirements?
- ✅ Is the specialist available/appropriate?
**Example**: Architecture design tasks always delegate to Planner
**Last Updated**: 2025-03-21

## Framework 2: File Reading Strategy Decision
**When to use**: Before reading any file to determine optimal reading approach
**Decision Factors**:
1. File size (<100, 100-500, 500-1000, >1000 lines)
2. Purpose of reading (exploration, error analysis, function analysis, etc.)
3. Recent access (check working memory for recent_files)
4. Information needed (specific vs general)
**Decision Rules**:
- < 100 lines → Read entire file
- 100-500 lines → Use targeted line ranges
- 500-1000 lines → ALWAYS use line ranges, read max 100 lines at once
- > 1000 lines → Use grep/pattern matching first, then targeted reads
**Example**: Reading configuration files uses targeted line ranges
**Last Updated**: 2025-03-21

## Framework 3: Tool Selection Decision
**When to use**: When choosing which tool to use for a specific task
**Decision Factors**:
1. Task type (research, debugging, implementation, etc.)
2. Information needed (semantic, structural, specific)
3. Efficiency considerations (time, context usage)
4. Tool capabilities and limitations
**Decision Rules**:
- Code understanding → `rag_search` for semantic, `grep` for pattern
- File examination → `read_file` with line ranges
- System exploration → `ls`, `glob` for structure
- Knowledge access → `kg_query` for existing patterns
- External research → `web_search` for documentation
**Example**: Research tasks use tool combination pattern #1
**Last Updated**: 2025-03-21

## Framework 4: Implementation Approach Decision
**When to use**: When deciding how to implement a feature or fix
**Decision Factors**:
1. Complexity of the change
2. Existing code patterns and conventions
3. Test coverage requirements
4. Risk of breaking existing functionality
**Decision Rules**:
- Simple changes → Direct edit with tests
- Medium complexity → TDD approach with incremental implementation
- High complexity → Design first, then implementation with validation
- Breaking changes → Compatibility layer or gradual migration
**Example**: MCP integration used design-first approach due to complexity
**Last Updated**: 2025-03-21

## Framework 5: Error Handling Strategy Decision
**When to use**: When deciding how to handle errors or exceptions
**Decision Factors**:
1. Severity of the error (critical, recoverable, warning)
2. User impact (blocking, degraded performance, cosmetic)
3. Frequency of occurrence (common, rare, edge case)
4. Root cause (configuration, code bug, external dependency)
**Decision Rules**:
- Critical errors → Immediate fix with rollback plan
- Recoverable errors → Graceful degradation with logging
- Warnings → Monitor and address in next iteration
- Configuration errors → Clear error messages with guidance
**Example**: File permission errors handled with clear user guidance
**Last Updated**: 2025-03-21

## Framework 6: Testing Strategy Decision
**When to use**: When deciding what and how to test
**Decision Factors**:
1. Criticality of the code (core functionality, edge cases)
2. Complexity of the logic (simple, complex, algorithmic)
3. Integration points (external dependencies, APIs)
4. Performance requirements (speed, memory, scalability)
**Decision Rules**:
- Core functionality → Comprehensive unit tests
- Integration points → Integration tests with mocks
- Performance-critical → Benchmark tests
- User-facing features → End-to-end tests
**Example**: Provider system has comprehensive unit and integration tests
**Last Updated**: 2025-03-21

## Framework 7: Documentation Priority Decision
**When to use**: When deciding what to document and when
**Decision Factors**:
1. User impact (high, medium, low)
2. Complexity of the feature
3. Likelihood of misuse or confusion
4. Maintenance requirements
**Decision Rules**:
- Public APIs → Always document with examples
- Complex features → Detailed documentation with use cases
- Configuration → Clear examples and default values
- Internal code → Minimal documentation for maintainers
**Example**: MCP integration has extensive documentation due to complexity
**Last Updated**: 2025-03-21

## Framework 8: Performance Optimization Decision
**When to use**: When deciding whether and how to optimize performance
**Decision Factors**:
1. Current performance metrics
2. User impact of performance issues
3. Complexity of optimization
4. Risk of introducing bugs
**Decision Rules**:
- Critical path optimization → High priority, careful implementation
- Minor improvements → Lower priority, batch with other changes
- Complex optimizations → Prototype first, then implement
- Risky optimizations → Extensive testing required
**Example**: File reading optimization prioritized due to high impact
**Last Updated**: 2025-03-21

## Framework 9: Dependency Management Decision
**When to use**: When deciding whether to add or update dependencies
**Decision Factors**:
1. Necessity of the dependency
2. Maintenance status and community support
3. License compatibility
4. Impact on build size and performance
**Decision Rules**:
- Core functionality → Prefer standard library or minimal dependencies
- Common patterns → Well-maintained, popular libraries
- Specialized needs → Evaluate alternatives carefully
- Large dependencies → Consider impact on distribution
**Example**: Rich and prompt_toolkit chosen for UI due to quality and maintenance
**Last Updated**: 2025-03-21

## Framework 10: Rollback Decision
**When to use**: When deciding whether to rollback a change
**Decision Factors**:
1. Severity of issues caused
2. Impact on users
3. Complexity of fix
4. Availability of workarounds
**Decision Rules**:
- Critical breaking changes → Immediate rollback
- Significant issues with no quick fix → Rollback
- Minor issues with workaround → Fix forward
- Cosmetic issues only → Schedule fix
**Example**: UI regression in Textual app required rollback and fix
**Last Updated**: 2025-03-21