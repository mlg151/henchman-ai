#!/usr/bin/env python3
"""Test the code examples in the intelligent context documentation."""

import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from henchman.providers.base import Message
from henchman.utils.intelligent_context import (
    IntelligentCompactionResult,
    IntelligentContextManager,
)


def test_basic_import():
    """Test basic import and initialization."""
    print("Testing basic import...")
    manager = IntelligentContextManager()
    assert manager is not None
    print("✓ Basic import test passed")


def test_message_creation():
    """Test message creation for examples."""
    print("\nTesting message creation...")

    # Create sample messages as shown in documentation
    messages = [
        Message(role="system", content="You are a helpful assistant"),
        Message(role="user", content="Write a Python function to calculate factorial"),
        Message(role="assistant", content="Here's a factorial function..."),
        Message(role="user", content="Now write a Fibonacci function"),
        Message(role="assistant", content="Here's a Fibonacci function..."),
    ]

    assert len(messages) == 5
    assert messages[0].role == "system"
    assert messages[1].role == "user"
    print("✓ Message creation test passed")


def test_compaction_methods():
    """Test compaction methods exist and work."""
    print("\nTesting compaction methods...")

    manager = IntelligentContextManager()
    messages = [
        Message(role="system", content="You are a helpful assistant"),
        Message(role="user", content="Test message"),
    ]

    # Test compact method
    compacted = manager.compact(messages)
    assert isinstance(compacted, list)

    # Test compact_with_result method
    result = manager.compact_with_result(messages)
    assert isinstance(result, IntelligentCompactionResult)
    assert hasattr(result, 'messages')
    assert hasattr(result, 'was_compacted')
    assert hasattr(result, 'dropped_count')

    print("✓ Compaction methods test passed")


def test_importance_scoring():
    """Test importance scoring method."""
    print("\nTesting importance scoring...")

    manager = IntelligentContextManager()
    messages = [
        Message(role="system", content="You are a helpful assistant"),
        Message(role="user", content="Test message"),
    ]

    scores = manager._calculate_importance_scores(messages)
    assert isinstance(scores, dict)
    assert len(scores) == len(messages)

    # Scores should be between 0 and 1
    for score in scores.values():
        assert 0.0 <= score <= 1.0

    print("✓ Importance scoring test passed")


def test_clustering_methods():
    """Test clustering methods exist."""
    print("\nTesting clustering methods...")

    manager = IntelligentContextManager()
    messages = [
        Message(role="user", content="Hello"),
        Message(role="assistant", content="Hi there"),
    ]

    # Test that clustering methods exist
    clusters = manager._cluster_messages(messages)
    assert isinstance(clusters, list)

    # Test individual clustering methods
    initial_clusters = [[0], [1]]
    clustered = manager._cluster_temporal_proximity(messages, initial_clusters)
    assert isinstance(clustered, list)

    print("✓ Clustering methods test passed")


def test_adaptive_compression():
    """Test adaptive compression methods."""
    print("\nTesting adaptive compression...")

    manager = IntelligentContextManager()
    messages = [
        Message(role="system", content="You are a helpful assistant"),
        Message(role="user", content="Write some code"),
    ]

    importance_scores = {0: 0.7, 1: 0.6}
    clusters = [[0], [1]]
    cluster_importance = {0: 0.7, 1: 0.6}

    # Test conversation type detection
    conv_type = manager._detect_conversation_type(messages)
    assert conv_type in ["coding", "research", "debugging", "general"]

    # Test cluster importance calculation
    calc_importance = manager._calculate_cluster_importance(clusters, importance_scores)
    assert isinstance(calc_importance, dict)

    print("✓ Adaptive compression test passed")


def test_custom_manager_example():
    """Test that custom manager example would work."""
    print("\nTesting custom manager example...")

    # This just tests that the example code would compile/import correctly
    # We don't actually run it since it's an example

    class CustomContextManager(IntelligentContextManager):
        def _apply_coding_compression_strategy(self, messages, clusters, cluster_importance):
            # Custom implementation
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

    # Create instance to verify it works
    custom_manager = CustomContextManager()
    assert isinstance(custom_manager, IntelligentContextManager)

    print("✓ Custom manager example test passed")


def test_cli_commands_exist():
    """Test that CLI command module exists."""
    print("\nTesting CLI command module...")

    try:
        from henchman.cli.commands.context import ContextCommand
        command = ContextCommand()
        assert command.name == "context"
        assert hasattr(command, 'execute')
        print("✓ CLI command module test passed")
    except ImportError as e:
        print(f"✗ CLI command module import failed: {e}")
        raise


def main():
    """Run all tests."""
    print("Testing code examples from intelligent context documentation...")
    print("=" * 60)

    tests = [
        test_basic_import,
        test_message_creation,
        test_compaction_methods,
        test_importance_scoring,
        test_clustering_methods,
        test_adaptive_compression,
        test_custom_manager_example,
        test_cli_commands_exist,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"✗ {test.__name__} failed: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"Test Results: {passed} passed, {failed} failed")

    if failed > 0:
        print("\nSome tests failed. Please check the implementation.")
        sys.exit(1)
    else:
        print("\nAll tests passed! Documentation examples are valid.")
        sys.exit(0)


if __name__ == "__main__":
    main()
