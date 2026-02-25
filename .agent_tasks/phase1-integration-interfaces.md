# Phase 1 Integration Interfaces

## Overview
This document defines the integration points between the three Phase 1 systems:
1. **Intelligent Context Management System**
2. **Enhanced Session Management**  
3. **Performance Dashboard**

## Core Integration Points

### 1. Agent Class (`src/henchman/core/agent.py`)
All three systems interact with the Agent class:

#### Intelligent Context Management
```python
# Integration point: _apply_compaction_if_needed() method
async def _apply_compaction_if_needed(self) -> bool:
    # Current: uses ContextCompactor from utils.compaction
    # New: Should use IntelligentContextManager when enabled
    pass
```

#### Enhanced Session Management
```python
# Integration point: Session recording
# Agent should record to enhanced sessions with branching support
def record_to_session(self, session: Session):
    # Should handle session branching metadata
    pass
```

#### Performance Dashboard
```python
# Integration point: Metrics collection
# Agent should emit metrics for token usage, costs, etc.
def _emit_metrics(self, event_type: str, data: dict):
    # Send to MetricsCollector
    pass
```

### 2. Configuration System (`src/henchman/config/schema.py`)

#### Settings Structure
```yaml
# New settings for Phase 1 features
context:
  intelligent_compaction: true  # Enable intelligent context management
  max_tokens: 8000
  compression_strategy: "semantic"  # semantic, priority, hybrid
  
sessions:
  enable_branching: true
  enable_templates: true
  default_template: "code_review"
  auto_save: true
  
metrics:
  enabled: true
  collection_interval: 60  # seconds
  retention_days: 30
  anonymize: true
  export_formats: ["csv", "json"]
```

### 3. CLI Commands (`src/henchman/cli/commands/`)

#### New Commands
```
# Intelligent Context Management
/context strategy <semantic|priority|hybrid>  # Set compression strategy
/context stats                                 # Show context usage statistics

# Enhanced Session Management  
/session branch <name>                         # Create session branch
/session merge <session1> <session2>           # Merge two sessions
/session template save <name>                  # Save current as template
/session template list                         # List available templates
/session export <id> [format]                  # Export session

# Performance Dashboard
/dashboard                                     # Show interactive dashboard
/stats tokens                                  # Show token usage
/stats costs                                   # Show cost breakdown  
/stats tools                                   # Show tool performance
/stats export <format>                         # Export statistics
```

## Data Flow Between Systems

### Context → Session Flow
```
Intelligent Context Management
        ↓ (compacted messages)
Enhanced Session Management  
        ↓ (session with metadata)
Performance Dashboard
        ↓ (metrics collection)
```

### Session → Context Flow
```
Enhanced Session Management
        ↓ (load session with branching)
Intelligent Context Management
        ↓ (restore with semantic understanding)
Agent Conversation
```

## Shared Data Models

### 1. Message Importance Scores
```python
@dataclass
class MessageImportance:
    message_id: str
    score: float  # 0.0 to 1.0
    categories: list[str]  # ["tool_call", "error", "decision", "query"]
    semantic_hash: str  # For deduplication
```

### 2. Session Branch Metadata
```python
@dataclass  
class BranchMetadata:
    parent_session_id: str
    branch_point: int  # Message index where branch occurred
    branch_reason: str
    merged_into: Optional[str]  # If this branch was merged
```

### 3. Metrics Data
```python
@dataclass
class ConversationMetrics:
    session_id: str
    token_count: int
    estimated_cost: float
    tool_calls: int
    success_rate: float
    duration_seconds: float
```

## Integration Tests Required

### 1. Context + Session Integration
```python
def test_intelligent_context_with_session_branching():
    # Create session with branching
    # Apply intelligent compaction
    # Verify context preserved correctly
    # Verify branch metadata intact
```

### 2. Session + Metrics Integration
```python  
def test_session_metrics_collection():
    # Run conversation with enhanced sessions
    # Verify metrics collected
    # Export session with metrics
    # Verify export includes metrics
```

### 3. Context + Metrics Integration
```python
def test_context_compaction_metrics():
    # Run conversation with intelligent compaction
    # Verify metrics show token reduction
    # Verify cost savings calculated
```

## Configuration Dependencies

### Feature Flags
```python
# All Phase 1 features should be configurable via feature flags
FEATURE_FLAGS = {
    "intelligent_context": True,
    "enhanced_sessions": True,
    "performance_dashboard": True,
    "experimental_features": False,
}
```

### Dependency Order
1. **Base configuration** loaded first
2. **Feature flags** evaluated
3. **System initialization** based on flags
4. **Integration points** activated if features enabled

## Error Handling Coordination

### Shared Error Types
```python
class Phase1IntegrationError(Exception):
    """Base error for Phase 1 integration issues"""
    pass

class ContextCompactionError(Phase1IntegrationError):
    """Intelligent context compaction failed"""
    pass

class SessionBranchError(Phase1IntegrationError):
    """Session branching operation failed"""
    pass

class MetricsCollectionError(Phase1IntegrationError):
    """Metrics collection failed"""
    pass
```

### Error Recovery
- **Context errors**: Fall back to basic compaction
- **Session errors**: Continue without enhanced features  
- **Metrics errors**: Log but don't fail operation
- **Integration errors**: Disable problematic feature, continue with others

## Performance Requirements

### Maximum Overhead
- **Intelligent Context**: <5% time overhead, 40% token reduction
- **Enhanced Sessions**: <2% time overhead, <1% storage overhead
- **Performance Dashboard**: <3% time overhead, <100MB storage

### Memory Limits
- **Context embeddings**: Max 100MB cache
- **Session history**: Configurable, default 1GB
- **Metrics storage**: Configurable, default 500MB

## Security Considerations

### Data Privacy
- **Metrics anonymization**: Optional, default enabled
- **Session encryption**: Optional for sensitive conversations
- **Context embeddings**: Local only, not transmitted

### Access Control
- **Session access**: User-only by default
- **Metrics access**: User-only, configurable sharing
- **Context data**: Process isolation for embeddings

## Testing Strategy

### Unit Tests
- Each system tested independently
- Mock integration points
- 95%+ coverage required

### Integration Tests
- Test combinations of systems
- Verify data flow between systems
- Test error conditions

### Performance Tests
- Benchmark overhead of each system
- Measure token reduction
- Verify memory limits

## Documentation Requirements

### For Each System
1. **Architecture overview**
2. **Configuration options**
3. **API documentation**
4. **Usage examples**
5. **Troubleshooting guide**

### Integration Documentation
1. **Data flow diagrams**
2. **Configuration dependencies**
3. **Error handling procedures**
4. **Performance tuning guide**

## Release Checklist

### Pre-Release
- [ ] All integration tests passing
- [ ] Performance benchmarks met
- [ ] Documentation complete
- [ ] Backward compatibility verified
- [ ] Feature flags working correctly

### Post-Release
- [ ] Monitor integration errors
- [ ] Collect user feedback
- [ ] Measure actual performance
- [ ] Plan Phase 2 based on Phase 1 success

---
*Last Updated: February 2025*  
*Interface Version: 1.0*  
*For Phase 1 Specialists: Please review and ensure your implementations follow these interfaces.*