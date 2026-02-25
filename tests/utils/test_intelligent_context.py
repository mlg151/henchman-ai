"""Tests for intelligent context management."""

from henchman.providers.base import Message, ToolCall
from henchman.utils.intelligent_context import IntelligentContextManager


def test_calculate_importance_scores_empty():
    """Test importance scoring with empty message list."""
    manager = IntelligentContextManager()
    scores = manager._calculate_importance_scores([])
    assert scores == {}


def test_calculate_importance_scores_tool_calls_high():
    """Test that messages with tool calls get high importance scores."""
    manager = IntelligentContextManager()

    # Create a message with tool calls
    tool_call = ToolCall(id="test_tool_1", name="test_function", arguments={})

    messages = [Message(role="assistant", content="I'll use a tool", tool_calls=[tool_call])]

    scores = manager._calculate_importance_scores(messages)
    assert len(scores) == 1
    assert scores[0] >= 0.9  # Should be high importance


def test_calculate_importance_scores_errors_high():
    """Test that messages containing error keywords get high importance scores."""
    manager = IntelligentContextManager()

    messages = [
        Message(role="user", content="There was an error in the process"),
        Message(role="assistant", content="An exception occurred while processing"),
        Message(role="tool", content="Failed to execute command"),
        Message(role="user", content="This is a normal message"),
    ]

    scores = manager._calculate_importance_scores(messages)
    assert len(scores) == 4

    # First three should have high scores due to error keywords
    # (accounting for position-based adjustments)
    assert scores[0] >= 0.8  # "error" - high importance
    assert scores[1] >= 0.8  # "exception" - high importance
    assert scores[2] >= 0.8  # "failed" - high importance
    # Normal message should have user message importance (0.6 base)
    assert 0.6 <= scores[3] <= 1.0  # User message with position boost


def test_calculate_importance_scores_role_based():
    """Test that different roles get appropriate importance scores."""
    manager = IntelligentContextManager()

    messages = [
        Message(role="system", content="You are a helpful assistant"),
        Message(role="user", content="What is the weather?"),
        Message(role="assistant", content="The weather is sunny"),
        Message(role="tool", content="Weather data: sunny, 25°C"),
    ]

    scores = manager._calculate_importance_scores(messages)
    assert len(scores) == 4

    # System messages should be medium importance
    assert scores[0] >= 0.7

    # User queries should be medium importance
    assert scores[1] >= 0.6

    # Assistant response without tool calls should be lower
    assert 0.3 <= scores[2] <= 0.6

    # Tool response with content should be medium importance
    assert scores[3] >= 0.7


def test_calculate_importance_scores_position_based():
    """Test that recent messages get higher importance scores."""
    manager = IntelligentContextManager()

    messages = [
        Message(role="user", content="Message 1"),
        Message(role="assistant", content="Response 1"),
        Message(role="user", content="Message 2"),
        Message(role="assistant", content="Response 2"),
    ]

    scores = manager._calculate_importance_scores(messages)
    assert len(scores) == 4

    # Position boost should increase scores for later messages
    # Check that within same role types, later messages have higher scores
    assert scores[2] > scores[0]  # Later user message > earlier user message
    assert scores[3] > scores[1]  # Later assistant message > earlier assistant message


def test_calculate_importance_scores_content_length():
    """Test that longer messages get higher importance scores."""
    manager = IntelligentContextManager()

    short_content = "Short message"
    long_content = "A" * 500  # 500 characters
    very_long_content = "B" * 1000  # 1000 characters

    messages = [
        Message(role="user", content=short_content),
        Message(role="user", content=long_content),
        Message(role="user", content=very_long_content),
    ]

    scores = manager._calculate_importance_scores(messages)
    assert len(scores) == 3

    # Longer messages should have higher scores
    assert scores[2] > scores[1] > scores[0]


def test_calculate_importance_scores_deterministic():
    """Test that scores are deterministic for the same input."""
    manager = IntelligentContextManager()

    messages = [
        Message(role="system", content="System prompt"),
        Message(role="user", content="User query with error"),
        Message(role="assistant", content="Assistant response"),
    ]

    scores1 = manager._calculate_importance_scores(messages)
    scores2 = manager._calculate_importance_scores(messages)

    assert scores1 == scores2  # Should be identical


def test_calculate_importance_scores_range():
    """Test that all scores are in the range 0.0 to 1.0."""
    manager = IntelligentContextManager()

    # Test with various message types
    messages = [
        Message(role="system", content="System"),
        Message(role="user", content="User"),
        Message(role="assistant", content="Assistant"),
        Message(role="tool", content="Tool result"),
        Message(
            role="assistant",
            content="",
            tool_calls=[ToolCall(id="tool1", name="test", arguments={})],
        ),
    ]

    scores = manager._calculate_importance_scores(messages)

    for idx, score in scores.items():
        assert 0.0 <= score <= 1.0, f"Score {score} at index {idx} is out of range"


def test_calculate_importance_scores_mixed_scenarios():
    """Test importance scoring with mixed scenarios."""
    manager = IntelligentContextManager()

    tool_call = ToolCall(id="test_tool", name="execute", arguments={"cmd": "ls"})

    messages = [
        Message(role="system", content="You are an AI assistant"),
        Message(role="user", content="Please run a command for me"),
        Message(role="assistant", content="I'll execute the command", tool_calls=[tool_call]),
        Message(role="tool", content="Command executed successfully"),
        Message(role="user", content="Great! Now there's an error in the next step"),
        Message(role="assistant", content="Let me check what went wrong"),
    ]

    scores = manager._calculate_importance_scores(messages)
    assert len(scores) == 6

    # Check specific expectations
    assert scores[0] >= 0.7  # System message
    assert scores[1] >= 0.6  # User query
    assert scores[2] >= 0.9  # Assistant with tool call
    assert scores[3] >= 0.7  # Tool response with content
    assert scores[4] >= 0.8  # User message with "error"
    assert 0.3 <= scores[5] <= 0.6  # Assistant response without special features


def test_cluster_messages_empty():
    """Test clustering with empty message list."""
    manager = IntelligentContextManager()
    clusters = manager._cluster_messages([])
    assert clusters == []


def test_cluster_messages_single():
    """Test clustering with single message."""
    manager = IntelligentContextManager()
    messages = [Message(role="user", content="Hello")]
    clusters = manager._cluster_messages(messages)
    assert clusters == [[0]]


def test_cluster_tool_call_sequences():
    """Test that tool call sequences are clustered together."""
    manager = IntelligentContextManager()

    tool_call = ToolCall(id="tool_123", name="execute", arguments={"cmd": "ls"})

    messages = [
        Message(role="user", content="Run a command"),
        Message(role="assistant", content="I'll run it", tool_calls=[tool_call]),
        Message(role="tool", content="Command output", tool_call_id="tool_123"),
        Message(role="user", content="Thanks"),
    ]

    clusters = manager._cluster_messages(messages)

    # Tool call sequence (indices 1 and 2) should be in same cluster
    tool_sequence_clustered = False
    for cluster in clusters:
        if 1 in cluster and 2 in cluster:
            tool_sequence_clustered = True
            break

    assert tool_sequence_clustered, "Tool call sequence should be clustered together"


def test_cluster_temporal_proximity():
    """Test that adjacent messages with same role are clustered."""
    manager = IntelligentContextManager()

    messages = [
        Message(role="user", content="Question 1"),
        Message(role="user", content="Question 2"),
        Message(role="assistant", content="Answer 1"),
        Message(role="assistant", content="Answer 2"),
    ]

    clusters = manager._cluster_messages(messages)

    # Check that adjacent same-role messages are clustered
    # User messages (0, 1) should be together
    user_clustered = False
    assistant_clustered = False

    for cluster in clusters:
        if 0 in cluster and 1 in cluster:
            user_clustered = True
        if 2 in cluster and 3 in cluster:
            assistant_clustered = True

    assert user_clustered, "Adjacent user messages should be clustered"
    assert assistant_clustered, "Adjacent assistant messages should be clustered"


def test_cluster_user_assistant_pairs():
    """Test that user-assistant pairs are clustered."""
    manager = IntelligentContextManager()

    messages = [
        Message(role="user", content="What is the weather?"),
        Message(role="assistant", content="The weather is sunny today."),
        Message(role="user", content="What about tomorrow?"),
        Message(role="assistant", content="Tomorrow will be cloudy."),
    ]

    clusters = manager._cluster_messages(messages)

    # Each user-assistant pair should be clustered together
    # Pair 1: indices 0 and 1
    # Pair 2: indices 2 and 3
    pair1_clustered = False
    pair2_clustered = False

    for cluster in clusters:
        if 0 in cluster and 1 in cluster:
            pair1_clustered = True
        if 2 in cluster and 3 in cluster:
            pair2_clustered = True

    assert pair1_clustered, "First user-assistant pair should be clustered"
    assert pair2_clustered, "Second user-assistant pair should be clustered"


def test_cluster_topic_similarity():
    """Test that messages with similar topics are clustered."""
    manager = IntelligentContextManager(cluster_similarity_threshold=0.3)

    messages = [
        Message(role="user", content="I need help with Python programming"),
        Message(role="assistant", content="I can help with Python code"),
        Message(role="user", content="How do I write a function in Python?"),
        Message(role="assistant", content="Here's how to write a Python function"),
        Message(role="user", content="What about JavaScript?"),
        Message(role="assistant", content="JavaScript is different from Python"),
    ]

    clusters = manager._cluster_messages(messages)

    # Messages about Python (indices 0-3) should be more clustered than with JavaScript
    # At minimum, the Python-related messages should have some clustering
    python_indices = {0, 1, 2, 3}
    python_clusters = []

    for cluster in clusters:
        python_in_cluster = python_indices.intersection(set(cluster))
        if python_in_cluster:
            python_clusters.append(cluster)

    # Python messages should be in fewer clusters than total messages
    assert len(python_clusters) < 4, "Python-related messages should be clustered together"


def test_cluster_role_patterns():
    """Test clustering based on role patterns."""
    manager = IntelligentContextManager()

    messages = [
        Message(role="user", content="Tell me about machine learning"),
        Message(role="assistant", content="Machine learning is a field of AI"),
        Message(role="user", content="What are neural networks?"),
        Message(role="assistant", content="Neural networks are a type of ML model"),
    ]

    clusters = manager._cluster_messages(messages)

    # Should have 2 clusters (user-assistant pairs)
    assert len(clusters) <= 2, "Should cluster user-assistant pairs together"

    # Each cluster should contain a user-assistant pair
    for cluster in clusters:
        roles = {messages[idx].role for idx in cluster}
        assert "user" in roles and "assistant" in roles, (
            "Clusters should contain both user and assistant roles"
        )


def test_cluster_complex_conversation():
    """Test clustering with a complex conversation."""
    manager = IntelligentContextManager(cluster_similarity_threshold=0.5)

    tool_call1 = ToolCall(id="tool_1", name="search", arguments={"query": "weather"})
    tool_call2 = ToolCall(id="tool_2", name="calculate", arguments={"x": 5, "y": 3})

    messages = [
        Message(role="system", content="You are a helpful assistant"),
        Message(role="user", content="What's the weather like?"),
        Message(role="assistant", content="Let me check", tool_calls=[tool_call1]),
        Message(role="tool", content="Weather: sunny, 25°C", tool_call_id="tool_1"),
        Message(role="assistant", content="It's sunny and 25°C"),
        Message(role="user", content="Thanks! Now calculate 5 + 3"),
        Message(role="assistant", content="I'll calculate that", tool_calls=[tool_call2]),
        Message(role="tool", content="Result: 8", tool_call_id="tool_2"),
        Message(role="assistant", content="The result is 8"),
    ]

    clusters = manager._cluster_messages(messages)

    # System message might be alone or with first user message
    # Tool call sequences should be clustered (indices 2-3 and 6-7)
    # User-assistant pairs should be clustered

    # Verify tool sequences are clustered
    tool_seq1_clustered = False
    tool_seq2_clustered = False

    for cluster in clusters:
        if 2 in cluster and 3 in cluster:
            tool_seq1_clustered = True
        if 6 in cluster and 7 in cluster:
            tool_seq2_clustered = True

    assert tool_seq1_clustered, "First tool sequence should be clustered"
    assert tool_seq2_clustered, "Second tool sequence should be clustered"

    # Verify we have reasonable number of clusters (not too many, not too few)
    assert 3 <= len(clusters) <= 6, (
        f"Expected 3-6 clusters for complex conversation, got {len(clusters)}"
    )


def test_apply_adaptive_compression_empty():
    """Test adaptive compression with empty inputs."""
    manager = IntelligentContextManager()
    messages = []
    importance_scores = {}
    clusters = []
    
    result = manager._apply_adaptive_compression(messages, importance_scores, clusters)
    assert result == []


def test_apply_adaptive_compression_preserves_high_importance():
    """Test that high-importance clusters are preserved."""
    manager = IntelligentContextManager()
    
    # Create messages with varying importance
    messages = [
        Message(role="user", content="Important question about Python"),
        Message(role="assistant", content="Detailed answer about Python"),
        Message(role="user", content="Less important follow-up"),
        Message(role="assistant", content="Brief response"),
    ]
    
    # Assign high importance to first two messages, low to last two
    importance_scores = {0: 0.9, 1: 0.8, 2: 0.3, 3: 0.2}
    
    # Cluster messages in pairs
    clusters = [[0, 1], [2, 3]]
    
    result = manager._apply_adaptive_compression(messages, importance_scores, clusters)
    
    # High-importance cluster should be preserved
    assert len(result) >= 2
    # First two messages should be in result
    assert any(msg.content == "Important question about Python" for msg in result)
    assert any(msg.content == "Detailed answer about Python" for msg in result)


def test_apply_adaptive_compression_tool_sequences():
    """Test that tool call sequences are preserved."""
    manager = IntelligentContextManager()
    
    tool_call = ToolCall(id="tool_123", name="execute", arguments={"cmd": "ls"})
    
    messages = [
        Message(role="user", content="Run a command"),
        Message(role="assistant", content="I'll run it", tool_calls=[tool_call]),
        Message(role="tool", content="Command output", tool_call_id="tool_123"),
        Message(role="user", content="Thanks"),
    ]
    
    # Tool sequences should have high importance
    importance_scores = {0: 0.6, 1: 0.9, 2: 0.8, 3: 0.4}
    
    # Cluster tool sequence together
    clusters = [[0], [1, 2], [3]]
    
    result = manager._apply_adaptive_compression(messages, importance_scores, clusters)
    
    # Tool sequence should be preserved
    tool_sequence_preserved = False
    for i in range(len(result) - 1):
        if (result[i].role == "assistant" and result[i].tool_calls and
            i + 1 < len(result) and result[i + 1].role == "tool"):
            tool_sequence_preserved = True
            break
    
    assert tool_sequence_preserved, "Tool call sequence should be preserved"


def test_detect_conversation_type_coding():
    """Test conversation type detection for coding conversations."""
    manager = IntelligentContextManager()
    
    messages = [
        Message(role="user", content="How do I write a Python function?"),
        Message(role="assistant", content="Here's how: def my_function(): pass"),
        Message(role="user", content="What about JavaScript?"),
        Message(role="assistant", content="function myFunction() {}"),
    ]
    
    conv_type = manager._detect_conversation_type(messages)
    assert conv_type == "coding"


def test_detect_conversation_type_research():
    """Test conversation type detection for research conversations."""
    manager = IntelligentContextManager()
    
    messages = [
        Message(role="user", content="I need to research machine learning algorithms"),
        Message(role="assistant", content="According to recent studies, deep learning..."),
        Message(role="user", content="What are the findings?"),
        Message(role="assistant", content="The analysis shows that..."),
    ]
    
    conv_type = manager._detect_conversation_type(messages)
    assert conv_type == "research"


def test_detect_conversation_type_debugging():
    """Test conversation type detection for debugging conversations."""
    manager = IntelligentContextManager()
    
    messages = [
        Message(role="user", content="I'm getting an error in my code, need to debug"),
        Message(role="assistant", content="What's the error message and stack trace?"),
        Message(role="user", content="Traceback: NameError: name 'x' is not defined, fix this bug"),
        Message(role="assistant", content="You need to define x before using it to fix the issue"),
    ]
    
    conv_type = manager._detect_conversation_type(messages)
    assert conv_type == "debugging"


def test_detect_conversation_type_general():
    """Test conversation type detection for general conversations."""
    manager = IntelligentContextManager()
    
    messages = [
        Message(role="user", content="Hello, how are you?"),
        Message(role="assistant", content="I'm good, thanks for asking!"),
        Message(role="user", content="What's the weather like?"),
        Message(role="assistant", content="I don't have access to weather data"),
    ]
    
    conv_type = manager._detect_conversation_type(messages)
    assert conv_type == "general"


def test_calculate_cluster_importance():
    """Test cluster importance calculation."""
    manager = IntelligentContextManager()
    
    clusters = [[0, 1], [2], [3, 4, 5]]
    importance_scores = {0: 0.8, 1: 0.6, 2: 0.3, 3: 0.4, 4: 0.5, 5: 0.6}
    
    cluster_importance = manager._calculate_cluster_importance(clusters, importance_scores)
    
    assert len(cluster_importance) == 3
    assert 0 in cluster_importance  # First cluster
    assert 1 in cluster_importance  # Second cluster
    assert 2 in cluster_importance  # Third cluster
    
    # First cluster average: (0.8 + 0.6) / 2 = 0.7, plus size boost
    assert cluster_importance[0] >= 0.7
    # Second cluster: 0.3, no size boost
    assert cluster_importance[1] >= 0.3
    # Third cluster average: (0.4 + 0.5 + 0.6) / 3 = 0.5, plus size boost
    assert cluster_importance[2] >= 0.5


def test_apply_adaptive_compression_edge_cases():
    """Test adaptive compression with edge cases."""
    manager = IntelligentContextManager()
    
    # Test with all high-importance messages
    messages = [
        Message(role="user", content="Critical question 1"),
        Message(role="assistant", content="Critical answer 1"),
        Message(role="user", content="Critical question 2"),
        Message(role="assistant", content="Critical answer 2"),
    ]
    
    importance_scores = {0: 0.9, 1: 0.9, 2: 0.9, 3: 0.9}
    clusters = [[0, 1], [2, 3]]
    
    result = manager._apply_adaptive_compression(messages, importance_scores, clusters)
    
    # All messages should be preserved
    assert len(result) == 4
    assert all(msg in result for msg in messages)
    
    # Test with single message - medium importance gets summarized
    messages_single = [Message(role="user", content="Single message")]
    importance_scores_single = {0: 0.5}
    clusters_single = [[0]]
    
    result_single = manager._apply_adaptive_compression(
        messages_single, importance_scores_single, clusters_single
    )
    # Medium importance message should be summarized
    assert len(result_single) == 1
    assert result_single[0].role == "system"
    assert "[Summarized cluster 0]" in result_single[0].content
    
    # Test with high-importance single message - should be preserved
    messages_high = [Message(role="user", content="Important single message")]
    importance_scores_high = {0: 0.8}
    clusters_high = [[0]]
    
    result_high = manager._apply_adaptive_compression(
        messages_high, importance_scores_high, clusters_high
    )
    assert len(result_high) == 1
    assert result_high[0].content == "Important single message"
