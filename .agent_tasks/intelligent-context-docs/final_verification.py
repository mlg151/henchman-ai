#!/usr/bin/env python3
"""Final verification of intelligent context documentation."""

import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


def verify_documentation_structure():
    """Verify documentation files exist and are properly structured."""
    print("Verifying documentation structure...")
    
    # Check main documentation file exists
    docs_dir = project_root / "docs"
    main_doc = docs_dir / "intelligent-context-management.md"
    assert main_doc.exists(), f"Main documentation not found: {main_doc}"
    
    # Check it's referenced in index
    index_file = docs_dir / "index.md"
    index_content = index_file.read_text()
    assert "intelligent-context-management.md" in index_content, \
        "Intelligent context documentation not linked in index"
    
    # Check configuration references it
    config_file = docs_dir / "configuration.md"
    config_content = config_file.read_text()
    assert "intelligent-context-management.md" in config_content, \
        "Intelligent context documentation not referenced in configuration"
    
    print("✓ Documentation structure verified")


def verify_code_examples():
    """Verify code examples in documentation work."""
    print("\nVerifying code examples...")
    
    # Test basic imports
    from henchman.utils.intelligent_context import (
        IntelligentContextManager,
        IntelligentCompactionResult
    )
    from henchman.providers.base import Message
    
    # Test example from documentation
    manager = IntelligentContextManager(
        max_tokens=16000,
        importance_threshold=0.6,
        cluster_similarity_threshold=0.75,
        adaptive_compression=True
    )
    
    messages = [
        Message(role="system", content="You are a helpful assistant"),
        Message(role="user", content="Write a Python function to calculate factorial"),
        Message(role="assistant", content="Here's a factorial function..."),
        Message(role="user", content="Now write a Fibonacci function"),
        Message(role="assistant", content="Here's a Fibonacci function..."),
    ]
    
    # Test compaction
    compacted = manager.compact(messages)
    assert isinstance(compacted, list)
    
    # Test detailed result
    result = manager.compact_with_result(messages)
    assert isinstance(result, IntelligentCompactionResult)
    
    print("✓ Code examples verified")


def verify_cli_integration():
    """Verify CLI integration works."""
    print("\nVerifying CLI integration...")
    
    from henchman.cli.commands.context import ContextCommand
    
    command = ContextCommand()
    assert command.name == "context"
    assert "intelligent context" in command.description.lower()
    
    print("✓ CLI integration verified")


def verify_settings_schema():
    """Verify settings schema matches documentation."""
    print("\nVerifying settings schema...")
    
    from henchman.config.schema import Settings
    
    settings = Settings()
    
    # Check default values match documentation
    assert settings.context.intelligent_context == False
    assert settings.context.max_tokens == 128000
    assert settings.context.compaction_threshold == 0.75
    assert settings.context.importance_threshold == 0.5
    assert settings.context.cluster_similarity_threshold == 0.7
    assert settings.context.adaptive_compression == True
    
    print("✓ Settings schema verified")


def verify_performance_characteristics():
    """Verify performance characteristics are documented."""
    print("\nVerifying performance characteristics...")
    
    doc_file = project_root / "docs" / "intelligent-context-management.md"
    doc_content = doc_file.read_text()
    
    # Check key sections exist
    required_sections = [
        "Performance Characteristics",
        "Token Reduction Expectations",
        "Computational Overhead",
        "Troubleshooting",
        "Best Practices"
    ]
    
    for section in required_sections:
        assert section in doc_content, f"Missing section: {section}"
    
    # Check performance metrics are mentioned
    performance_terms = [
        "token reduction",
        "compression ratio",
        "computational overhead",
        "memory usage"
    ]
    
    for term in performance_terms:
        assert term.lower() in doc_content.lower(), f"Missing term: {term}"
    
    print("✓ Performance characteristics verified")


def main():
    """Run final verification."""
    print("=" * 60)
    print("Final Verification of Intelligent Context Documentation")
    print("=" * 60)
    
    tests = [
        verify_documentation_structure,
        verify_code_examples,
        verify_cli_integration,
        verify_settings_schema,
        verify_performance_characteristics,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"✗ {test.__name__} failed: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ {test.__name__} failed with error: {e}")
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"Verification Results: {passed} passed, {failed} failed")
    
    if failed > 0:
        print("\nDocumentation verification failed.")
        sys.exit(1)
    else:
        print("\n✓ All documentation verification tests passed!")
        print("\nDocumentation is comprehensive and properly integrated.")
        sys.exit(0)


if __name__ == "__main__":
    main()