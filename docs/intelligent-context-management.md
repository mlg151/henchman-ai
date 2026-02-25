# Intelligent Context Management

Intelligent Context Management is an advanced feature in Henchman-AI that reduces token usage while preserving important context through sophisticated techniques like importance scoring, semantic clustering, and adaptive compression.

## Overview

As conversations grow longer, they consume more tokens, increasing costs and potentially exceeding model context limits. The Intelligent Context Management system addresses this by:

1. **Scoring message importance** based on content, role, and position
2. **Clustering related messages** to preserve conversational context
3. **Applying adaptive compression** based on conversation type
4. **Preserving critical information** like tool calls, errors, and decisions

### Key Benefits

- **Token Reduction**: Typically reduces token usage by 30-60% in long conversations
- **Context Preservation**: Maintains important information while removing redundancy
- **Adaptive Strategies**: Different compression techniques for coding, debugging, research, and general conversations
- **Transparent Operation**: CLI commands to monitor and configure the system

## Configuration

Intelligent Context Management is configured through settings with sensible defaults.

### Default Settings

```yaml
context:
  intelligent_context: false  # Enable/disable intelligent context
  max_tokens: 128000          # Maximum tokens before compaction
  compaction_threshold: 0.75  # Start compaction at 75% of max_tokens
  importance_threshold: 0.5   # Minimum importance score to preserve
  cluster_similarity_threshold: 0.7  # Similarity for clustering
  adaptive_compression: true  # Use adaptive compression techniques
```

### Configuration Files

Settings can be configured in multiple locations (in order of precedence):

1. **Environment Variable**: `HENCHMAN_SETTINGS_PATH` (overrides all others)
2. **User Settings**: `~/.henchman/settings.yaml`
3. **Workspace Settings**: `.henchman/settings.yaml` in current directory

### Example Configuration

```yaml
# ~/.henchman/settings.yaml
context:
  intelligent_context: true
  max_tokens: 32000           # Lower for cost-sensitive usage
  importance_threshold: 0.4   # Preserve more messages
  adaptive_compression: true
```

## CLI Usage

The Intelligent Context Management system includes a dedicated CLI command for monitoring and configuration.

### Command Structure

```
/context [subcommand] [options]
```

### Subcommands

#### Show Status
```bash
/context
```
Displays current intelligent context settings and status.

#### Enable/Disable
```bash
/context enable
/context disable
```
Enable or disable intelligent context management.

#### Strategy Management
```bash
/context strategy                    # Show current strategy settings
/context strategy set <param> <value>  # Change a parameter
```

Available parameters:
- `max_tokens <int>` - Maximum tokens before compaction (min: 1000)
- `threshold <float>` - Compaction threshold (0.1-1.0)
- `importance <float>` - Importance threshold (0.0-1.0)
- `similarity <float>` - Cluster similarity threshold (0.0-1.0)
- `adaptive <on|off>` - Enable/disable adaptive compression

#### Statistics
```bash
/context stats
```
Show context usage statistics including compression ratios and token savings.

## Examples

### Basic Usage

1. **Enable intelligent context**:
   ```bash
   /context enable
   ```

2. **Configure for coding conversations**:
   ```bash
   /context strategy set importance 0.7
   /context strategy set similarity 0.8
   ```

3. **Monitor performance**:
   ```bash
   /context stats
   ```

### Python API Usage

```python
from henchman.utils.intelligent_context import IntelligentContextManager
from henchman.providers.base import Message

# Create manager with custom settings
manager = IntelligentContextManager(
    max_tokens=16000,
    importance_threshold=0.6,
    cluster_similarity_threshold=0.75,
    adaptive_compression=True
)

# Sample messages
messages = [
    Message(role="system", content="You are a helpful assistant"),
    Message(role="user", content="Write a Python function to calculate factorial"),
    Message(role="assistant", content="Here's a factorial function..."),
    Message(role="user", content="Now write a Fibonacci function"),
    Message(role="assistant", content="Here's a Fibonacci function..."),
]

# Compact messages
compacted = manager.compact(messages)

# Get detailed results
result = manager.compact_with_result(messages)
print(f"Compression ratio: {result.compression_ratio}")
print(f"Messages dropped: {result.dropped_count}")
```

### Integration with Agent

```python
from henchman.core.agent import Agent
from henchman.providers.deepseek import DeepSeekProvider

# Create agent with intelligent context
provider = DeepSeekProvider(api_key="your-api-key")
agent = Agent(
    provider=provider,
    intelligent_context=True,
    importance_threshold=0.5,
    cluster_similarity_threshold=0.7,
    adaptive_compression=True
)

# The agent will automatically use intelligent context management
# during long conversations
```

## How It Works

### 1. Importance Scoring

Each message receives an importance score (0.0-1.0) based on:

- **Role Priority**: system > user > assistant > tool
- **Content Indicators**: Error messages, tool calls, code blocks
- **Position**: Recent messages get higher scores
- **Length**: Longer messages may indicate more important content

### 2. Semantic Clustering

Messages are grouped into clusters based on:

- **Tool Call Sequences**: Assistant tool calls with corresponding tool responses
- **Temporal Proximity**: Adjacent messages in conversation
- **Topic Similarity**: Keywords and semantic content
- **Role Patterns**: User-assistant conversation pairs

### 3. Adaptive Compression

Different strategies for different conversation types:

#### Coding Conversations
- Preserves: Tool calls, code snippets, error messages
- Strategy: High importance threshold (0.7), preserve code blocks

#### Debugging Conversations  
- Preserves: Error messages, stack traces, debugging steps
- Strategy: Very high importance threshold (0.8), focus on critical info

#### Research Conversations
- Preserves: Key findings, data points, source references
- Strategy: Lower threshold (0.6), preserve more context

#### General Conversations
- Preserves: Recent queries, important decisions
- Strategy: Balanced approach with medium threshold (0.6)

### 4. Compression Techniques

Based on cluster importance:
- **High Importance (≥ 0.7)**: Preserve fully
- **Medium Importance (0.4-0.7)**: Summarize key points
- **Low Importance (< 0.4)**: Drop or heavily compress

## Performance Characteristics

### Token Reduction Expectations

| Conversation Type | Typical Reduction | Notes |
|------------------|-------------------|-------|
| Coding | 40-60% | High redundancy in code explanations |
| Debugging | 30-50% | Preserves critical error info |
| Research | 35-55% | Summarizes findings, preserves data |
| General | 25-45% | Balanced preservation |

### Computational Overhead

The intelligent context system adds minimal overhead:
- **Importance Scoring**: O(n) where n = number of messages
- **Clustering**: O(n²) worst case, optimized with heuristics
- **Compression**: O(k) where k = number of clusters

Typical performance: < 100ms for conversations with 100+ messages.

### Memory Usage

The system maintains:
- Message importance scores
- Cluster assignments  
- Compression metadata

Memory overhead: ~100 bytes per message.

## Troubleshooting

### Common Issues

#### 1. Too Much Context Loss
**Symptoms**: Important information is being dropped from conversations.

**Solutions**:
- Lower the importance threshold:
  ```bash
  /context strategy set importance 0.3
  ```
- Disable adaptive compression for more predictable behavior:
  ```bash
  /context strategy set adaptive off
  ```

#### 2. Insufficient Compression
**Symptoms**: Token usage remains high despite intelligent context.

**Solutions**:
- Increase the importance threshold:
  ```bash
  /context strategy set importance 0.7
  ```
- Lower the cluster similarity threshold for more aggressive clustering:
  ```bash
  /context strategy set similarity 0.5
  ```

#### 3. Performance Issues
**Symptoms**: Noticeable delay in conversation processing.

**Solutions**:
- Increase max_tokens to reduce compaction frequency:
  ```bash
  /context strategy set max_tokens 64000
  ```
- Disable adaptive compression:
  ```bash
  /context strategy set adaptive off
  ```

### Debug Mode

For detailed debugging, enable verbose logging:

```python
import logging
logging.getLogger("henchman.utils.intelligent_context").setLevel(logging.DEBUG)
```

This will log:
- Importance scores for each message
- Cluster assignments
- Compression decisions
- Performance metrics

## Best Practices

### 1. Start Conservative
Begin with default settings and adjust based on your use case:
```bash
/context enable
/context strategy set importance 0.5
/context strategy set similarity 0.7
```

### 2. Monitor Performance
Regularly check statistics:
```bash
/context stats
```

Look for:
- Compression ratio > 0.3 (30% reduction)
- Reasonable token savings
- No loss of critical information

### 3. Adjust for Conversation Type

**Coding Sessions**:
```bash
/context strategy set importance 0.7
/context strategy set similarity 0.8
```

**Research/Documentation**:
```bash
/context strategy set importance 0.4
/context strategy set similarity 0.6
```

**General Assistance**:
```bash
/context strategy set importance 0.5
/context strategy set similarity 0.7
```

### 4. Test with Your Workload

Create test conversations that match your typical usage and verify:
1. Critical information is preserved
2. Token reduction meets expectations
3. Conversation flow remains coherent

## Advanced Topics

### Custom Compression Strategies

Extend the system with custom strategies:

```python
from henchman.utils.intelligent_context import IntelligentContextManager

class CustomContextManager(IntelligentContextManager):
    def _apply_coding_compression_strategy(self, messages, clusters, cluster_importance):
        # Custom implementation for coding conversations
        # Preserve all function definitions and imports
        preserved = []
        for cluster_idx, cluster in enumerate(clusters):
            importance = cluster_importance.get(cluster_idx, 0.0)
            if importance >= 0.6 or self._contains_code_definitions(messages, cluster):
                for msg_idx in cluster:
                    preserved.append(messages[msg_idx])
        return preserved
    
    def _contains_code_definitions(self, messages, cluster):
        for idx in cluster:
            if idx < len(messages):
                content = messages[idx].content or ""
                if "def " in content or "class " in content or "import " in content:
                    return True
        return False
```

### Integration with External Systems

The intelligent context system can be integrated with:

1. **Monitoring Systems**: Export metrics to Prometheus/Grafana
2. **Cost Tracking**: Correlate token reduction with API cost savings
3. **Quality Assurance**: Validate compression doesn't affect task completion

### Performance Tuning

For high-volume applications:

1. **Batch Processing**: Process multiple conversations in parallel
2. **Caching**: Cache importance scores for repeated messages
3. **Incremental Updates**: Update clusters incrementally as conversations grow

## API Reference

### `IntelligentContextManager` Class

#### Constructor
```python
IntelligentContextManager(
    max_tokens: int = 8000,
    max_protected_ratio: float = 0.3,
    importance_threshold: float = 0.5,
    cluster_similarity_threshold: float = 0.7,
    adaptive_compression: bool = True
)
```

#### Methods

**`compact(messages: list[Message], protect_from_index: int = -1) -> list[Message]`**
Compact messages to fit within max_tokens using intelligent techniques.

**`compact_with_result(messages: list[Message], protect_from_index: int = -1) -> IntelligentCompactionResult`**
Compact messages and return detailed result with intelligence metrics.

**`enforce_safety_limits(messages: list[Message]) -> list[Message]`**
Enforce limits on individual message size using tokens.

**`validate_compacted_sequence(messages: list[Message]) -> bool`**
Validate that a message sequence follows OpenAI API rules.

### `IntelligentCompactionResult` Dataclass

```python
@dataclass
class IntelligentCompactionResult:
    messages: list[Message]           # Compacted messages
    was_compacted: bool = False       # Whether compaction occurred
    dropped_count: int = 0            # Number of messages dropped
    summary: str | None = None        # Summary of dropped content
    importance_scores: dict[int, float] | None = None  # Message importance scores
    clusters: list[list[int]] | None = None  # Detected conversation clusters
    compression_ratio: float | None = None  # Achieved compression ratio
```

## Frequently Asked Questions

### Q: Does intelligent context work with all LLM providers?
**A**: Yes, it's provider-agnostic and works with any OpenAI-compatible provider.

### Q: Can I use it with streaming responses?
**A**: Yes, intelligent context operates on the message history, not the streaming response itself.

### Q: How does it handle multilingual conversations?
**A**: The system uses language-agnostic techniques (position, role, structure) that work across languages.

### Q: Is there a way to manually mark messages as important?
**A**: Not directly, but you can influence importance by including keywords like "important", "critical", or "remember this".

### Q: Can I disable it for specific conversations?
**A**: Yes, use `/context disable` before starting the conversation, then `/context enable` afterward.

## Support

For issues with Intelligent Context Management:

1. **Check the logs**: Enable debug logging as shown above
2. **Review settings**: Verify your configuration with `/context`
3. **Test with defaults**: Reset to default settings to isolate issues
4. **File an issue**: Include logs, configuration, and example conversation

## Related Documentation

- [Configuration Guide](configuration.md) - General configuration settings
- [CLI Reference](api.md) - Complete CLI command reference
- [Agent API](api.md#agent) - Programmatic agent usage
- [Performance Tuning](configuration.md#performance-tuning) - General performance optimization