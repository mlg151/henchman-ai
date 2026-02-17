# Specific Prompt Engineering Improvements

## Current Prompt Analysis

### Tech Lead Prompt Issues:
1. **Missing explicit thinking requirement**: No mandate to show reasoning
2. **Weak delegation promotion**: Mentions delegation but doesn't require it
3. **No structured thinking frameworks**: Ad-hoc reasoning
4. **Lack of reflection requirements**: No systematic learning from outcomes

## Recommended Prompt Updates

### 1. Enhanced Tech Lead Prompt

**File**: `src/henchman/agents/prompts.py`
**Section**: `LEADER_INSTRUCTIONS`

**Add these sections at the beginning of the prompt**:

```python
THINKING_AND_REASONING_PROTOCOL = """
**THINKING & REASONING PROTOCOL (MANDATORY)**:

A. **ALWAYS THINK BEFORE ACTING**:
   - For EVERY task, you MUST explicitly think through your approach
   - Your thinking MUST be visible in your responses
   - Use structured thinking for complex tasks

B. **THINKING FORMAT (REQUIRED)**:
   Start EVERY response with:
   ```
   THINKING:
   1. Problem Analysis: <What needs to be solved?>
   2. Context Review: <What do we already know?>
   3. Approach Options: <What are possible ways to solve this?>
   4. Decision & Rationale: <Which approach and why?>
   5. Next Steps: <What will I do first?>
   ```

C. **DELEGATION-FIRST MINDSET**:
   Before doing work yourself, ALWAYS ask:
   1. "Is there a specialist who could do this better?"
   2. "Would delegation make this more efficient?"
   3. "Am I the right person for this task?"

   If answer is YES to any, USE `delegate_task`.

D. **REFLECTION AFTER ACTION**:
   After completing work or receiving delegation results:
   1. Record what worked in knowledge graph
   2. Note what could be improved
   3. Update `.agent_tasks/` documentation
"""

DELEGATION_DECISION_MATRIX = """
**DELEGATION DECISION MATRIX (USE FOR EVERY TASK)**:

| Task Type          | Primary Specialist | When to Delegate                  |
|--------------------|-------------------|-----------------------------------|
| Architecture       | Planner           | Always delegate design work       |
| Research           | Explorer          | Always delegate research          |
| Implementation     | Engineer          | Delegate unless trivial           |
| Testing            | Engineer          | Always delegate testing           |
| Documentation      | Explorer          | Delegate documentation writing    |
| Debugging          | Engineer          | Delegate complex debugging        |

**RULE**: If a task fits any category above, DELEGATE IT.
"""
```

**Update the `LEADER_INSTRUCTIONS` to include these at the top**:

```python
LEADER_INSTRUCTIONS = """
Your Role: The Leader — Architect, Implementer, and Quality Gate

""" + THINKING_AND_REASONING_PROTOCOL + DELEGATION_DECISION_MATRIX + """

Core Responsibilities:

1. **Think First, Act Second**: Always use the Thinking Protocol. Make your reasoning visible.
2. **Delegate Systematically**: Use the Delegation Matrix. Specialists exist for a reason.
3. **Implement When Appropriate**: Only do work yourself when it's trivial or requires your specific expertise.
4. **Quality Assurance**: Verify all work meets standards.
5. **Knowledge Management**: Capture learnings in knowledge graph and documentation.

... [rest of existing prompt] ...
```

### 2. Enhanced Specialist Prompts

**Add thinking requirement to all specialists**:

```python
SPECIALIST_THINKING_PROTOCOL = """
**SPECIALIST THINKING PROTOCOL (MANDATORY)**:

Before starting work, you MUST think through:
1. **Task Understanding**: Do I fully understand what's needed?
2. **Approach Planning**: What's the best way to accomplish this?
3. **Risk Assessment**: What could go wrong? How to mitigate?
4. **Success Criteria**: How will I know I'm done correctly?

Format your thinking at the start of EVERY response:
```
THINKING (Specialist):
1. Understanding: <my interpretation of the task>
2. Approach: <how I plan to approach it>
3. Risks: <potential issues and mitigations>
4. Verification: <how I'll verify success>
```

Only after this thinking should you begin execution.
"""
```

**Update each specialist prompt**:
- Add `SPECIALIST_THINKING_PROTOCOL` at the beginning of each specialist's instructions
- Ensure it's included before the "Core Capabilities" section

### 3. Enhanced Delegation Tool Schema

**File**: `src/henchman/tools/builtins/delegate.py`
**Update the `description` property**:

```python
    @property
    def description(self) -> str:
        """Tool description."""
        return (
            "Delegate a task to a specialist agent. Each specialist starts with a "
            "CLEAN context, so you MUST provide all relevant information. "
            
            "\n\n**DELEGATION PRIORITY RULES**:"
            "\n1. ALWAYS consider delegation before doing work yourself"
            "\n2. Use specialists for their designated expertise"
            "\n3. Provide COMPLETE context - specialists have no memory"
            "\n4. Include explicit 'done_when' criteria"
            
            "\n\n**WHEN TO DELEGATE**:"
            "\n- Architecture/design → Planner"
            "\n- Research/exploration → Explorer"
            "\n- Implementation/testing → Engineer"
            "\n- Documentation → Explorer"
            "\n- Complex debugging → Engineer"
        )
```

### 4. Orchestrator Enhancements for Thinking Tracking

**File**: `src/henchman/agents/orchestrator.py`
**Add thinking pattern validation**:

```python
# Add after line 345 (role anchoring check)
THINKING_PATTERN_CHECK = """
# Check for thinking pattern in Tech Lead responses
if agent is self.tech_lead:
    last_message = agent.messages[-1] if agent.messages else None
    if last_message and last_message.role == "assistant":
        content = last_message.content or ""
        if not content.strip().startswith("THINKING:"):
            # Inject thinking reminder
            thinking_reminder = (
                "\n[Thinking Required] Your response must start with THINKING: "
                "followed by your reasoning process. Please revise."
            )
            agent.messages.append(Message(role="user", content=thinking_reminder))
            # Yield event for UI
            yield AgentEvent(
                type=EventType.THINKING_REQUIRED,
                data="Thinking pattern missing in response",
                source_agent="orchestrator",
            )
"""
```

### 5. New Event Types for Thinking Tracking

**File**: `src/henchman/core/events.py`
**Add new event types**:

```python
class EventType(Enum):
    # ... existing events ...
    THINKING_STARTED = "thinking_started"
    THINKING_COMPLETED = "thinking_completed"
    THINKING_REQUIRED = "thinking_required"
    DELEGATION_DECISION = "delegation_decision"
    REFLECTION = "reflection"
```

### 6. Example Response Patterns

**Create example patterns for documentation**:

```python
EXAMPLE_TECH_LEAD_RESPONSE = """
THINKING:
1. Problem Analysis: User wants to add user authentication to the API
2. Context Review: Current codebase uses FastAPI, has User model in models.py, no auth middleware
3. Approach Options:
   - Option A: Implement JWT authentication myself
   - Option B: Delegate to Engineer for implementation
   - Option C: Ask Explorer to research best practices first
4. Decision & Rationale: Choose Option C then B. Need research first, then implementation.
5. Next Steps: Delegate research to Explorer, then implementation to Engineer.

ACTION:
I'll delegate research to Explorer first, then implementation to Engineer.

Using delegate_task:
1. Explorer: Research FastAPI authentication best practices
2. Engineer: Implement based on research findings
"""

EXAMPLE_SPECIALIST_RESPONSE = """
THINKING (Engineer):
1. Understanding: Need to implement JWT authentication middleware for FastAPI
2. Approach: 
   - Read current auth patterns in codebase
   - Implement JWT middleware
   - Add authentication endpoints
   - Write tests
3. Risks: Security implementation must be correct, need to handle token refresh
4. Verification: Tests pass, manual API testing, security review

ACTION:
Starting implementation...
1. Reading current code structure...
"""

EXAMPLE_DELEGATION_FORMAT = """
DELEGATING to Explorer:

Task: Research FastAPI authentication best practices for production use
Done When: Report created in .agent_tasks/auth-research/ with:
  - 3 recommended approaches
  - Security considerations
  - Implementation examples
  - Library recommendations
Context: We're using FastAPI 0.104+, Python 3.12, need JWT-based auth
Files: ["src/main.py", "src/models.py", "requirements.txt"]
Background: No existing auth, simple User model exists
Requirements: Must work with existing User model, support role-based access
"""
```

### 7. Implementation Checklist

#### Phase 1: Prompt Updates (Day 1-2)
- [ ] Add thinking protocols to prompts.py
- [ ] Update Tech Lead prompt with thinking requirement
- [ ] Add thinking requirement to specialist prompts
- [ ] Update delegation tool description

#### Phase 2: Orchestrator Updates (Day 3)
- [ ] Add thinking pattern validation
- [ ] Add new event types
- [ ] Update event handling for thinking events

#### Phase 3: Testing (Day 4)
- [ ] Create tests for thinking patterns
- [ ] Test delegation decision-making
- [ ] Validate example responses

#### Phase 4: Documentation (Day 5)
- [ ] Update documentation with new patterns
- [ ] Create examples for users
- [ ] Update help text

### 8. Success Criteria

#### Immediate (Week 1)
- [ ] 100% of Tech Lead responses include "THINKING:" prefix
- [ ] Delegation rate increases by 20%
- [ ] All tests pass with new patterns

#### Short-term (Week 2)
- [ ] Thinking quality improves (measured by decision outcomes)
- [ ] Delegation becomes systematic (using matrix)
- [ ] Knowledge graph usage increases

#### Long-term (Month 1)
- [ ] Reduced rework due to better thinking
- [ ] More efficient task distribution
- [ ] Better user understanding of agent reasoning

### 9. Risk Mitigation

1. **Prompt Overload**: Start with simple thinking format, iterate
2. **Performance Impact**: Thinking is text-only, minimal overhead
3. **User Confusion**: Provide clear examples and documentation
4. **Agent Resistance**: Gradual implementation with feedback loops

### 10. Monitoring Metrics

Add to orchestrator:
```python
self.metrics = {
    "thinking_pattern_usage": 0,
    "delegation_count": 0,
    "delegation_by_type": {"planner": 0, "explorer": 0, "engineer": 0},
    "thinking_quality_score": 0,  # Simple heuristic based on structure
}
```

This implementation provides a structured approach to improving thinking visibility and delegation while maintaining backward compatibility and minimizing disruption.