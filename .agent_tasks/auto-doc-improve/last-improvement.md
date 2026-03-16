# Last Documentation Improvement

## Date/Time
2026-03-16T06:05:00Z (approximate)

## Files Changed
1. `docs/tools.md` - Enhanced `ask_user` tool documentation with comprehensive guidance

## Smell Category Addressed
COMPLETENESS (incomplete tool usage guidance)

## Rationale for Change
The `ask_user` tool is one of the most critical tools for agent interaction, enabling collaborative problem-solving by allowing agents to seek clarification, gather requirements, and confirm decisions. However, the original documentation only provided a basic parameter description without guidance on when and how to use this tool effectively.

**Changes made**:
1. **Added importance context**: Emphasized that `ask_user` is a critical tool for collaborative problem-solving
2. **Added "When to use" section**: Provided clear scenarios where the tool should be used:
   - Clarification needed for ambiguous requirements
   - Decision confirmation before significant changes
   - Preference gathering for multiple valid approaches
   - Missing information or credentials
   - Complex trade-offs requiring subjective judgment
3. **Added "Best practices" section**: Provided actionable guidance:
   - Be specific with clear, focused questions
   - Provide context for why the question is being asked
   - Offer options with pros/cons when appropriate
   - Set reasonable timeouts for time-sensitive decisions
   - Follow up on answers to continue tasks
4. **Added "Example scenarios"**: Provided concrete examples of effective questions:
   - Database selection choices
   - File overwrite confirmation
   - Solution approach selection
   - Credential requests

**Why this improvement matters**:
1. **User empowerment**: Helps users understand when and how agents should interact with them
2. **Agent effectiveness**: Guides agents to use the tool appropriately for better collaboration
3. **Clarity**: Provides concrete examples that illustrate proper usage
4. **Professionalism**: Comprehensive documentation reflects mature tool design
5. **Learning resource**: Serves as a reference for both users and agent developers

## Verification Performed
1. ✅ **Accuracy check**: Verified tool parameters match actual implementation
2. ✅ **Completeness assessment**: Confirmed all critical aspects of tool usage are covered
3. ✅ **Formatting check**: Ensured Markdown formatting renders correctly
4. ✅ **Consistency check**: Verified terminology matches rest of documentation
5. ✅ **Practical value**: Assessed that guidance is actionable and useful

## What to Verify
1. ✅ **Tool accuracy**: Documentation matches actual `ask_user` tool implementation
2. ✅ **Usage guidance**: Provides clear, actionable advice for when and how to use the tool
3. ✅ **Example relevance**: Scenarios are realistic and helpful
4. ✅ **Formatting**: Markdown renders correctly in documentation site
5. ✅ **Integration**: Documentation flows naturally with surrounding content

## Impact
- **Low risk**: Documentation-only changes, no code modifications
- **High value**: Users and agents can collaborate more effectively
- **Improved usability**: Clear guidance reduces confusion about tool usage
- **Better outcomes**: Agents will ask better questions, leading to better results
- **Educational value**: Serves as a learning resource for agent interaction patterns

## Next Priority
With comprehensive `ask_user` documentation now in place, future documentation efforts could focus on:
1. **More tool deep-dives**: Similar enhancements for other critical tools like `delegate_task`
2. **Tool combination patterns**: Document effective sequences of tool usage
3. **Troubleshooting guides**: Common issues and solutions for tool usage
4. **Performance optimization**: Best practices for efficient tool usage
5. **Case studies**: Real-world examples of effective agent-user collaboration

The `ask_user` tool documentation now provides comprehensive guidance that will help users and agents collaborate more effectively, leading to better outcomes and more productive interactions.