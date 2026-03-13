"""Test that removing dead code doesn't break functionality."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from henchman.utils.intelligent_context import (
    IntelligentContextManager,
    ContentExtractor,
    ConversationTypeDetector,
    ImportanceSorter,
    MessageSafetyEnforcer,
    TokenCounterWrapper,
    IntelligentTruncator,
    _ToolSequenceValidator,
    SequenceValidator,
    MessagePreserver,
    CompressionConfig,
    IntelligentCompactionResult,
    ResultCreationParams,
    SummaryGenerator,
)

from henchman.utils.intelligent_context_config import (
    IntelligentContextConfig,
    IntelligentContextParams,
)

def test_imports():
    """Test that all necessary imports work."""
    # Test that we can create instances
    config = IntelligentContextConfig()
    params = IntelligentContextParams()
    manager = IntelligentContextManager()
    
    assert config is not None
    assert params is not None
    assert manager is not None
    
    # Test that ContentExtractor methods work
    content = "Error: Something went wrong\nTool: some_tool()"
    error_sections = ContentExtractor.extract_error_sections(content)
    tool_sections = ContentExtractor.extract_tool_sections(content)
    
    # These might return empty lists if no patterns match
    assert isinstance(error_sections, list)
    assert isinstance(tool_sections, list)
    
    print("All imports and basic functionality work correctly")

def test_config_creation():
    """Test that config creation works with params."""
    params = IntelligentContextParams(
        max_tokens=4000,
        max_protected_ratio=0.2,
        importance_threshold=0.6,
        cluster_similarity_threshold=0.8,
        adaptive_compression=True,
    )
    
    config = IntelligentContextConfig.from_params(params=params)
    
    assert config.max_tokens == 4000
    assert config.max_protected_ratio == 0.2
    assert config.importance_threshold == 0.6
    assert config.cluster_similarity_threshold == 0.8
    assert config.adaptive_compression is True
    
    print("Config creation with params works correctly")

def test_manager_creation():
    """Test that manager creation works."""
    # Test with individual parameters
    manager1 = IntelligentContextManager(
        max_tokens=4000,
        max_protected_ratio=0.2,
        importance_threshold=0.6,
        cluster_similarity_threshold=0.8,
        adaptive_compression=True,
    )
    
    assert manager1 is not None
    
    # Test with params object
    params = IntelligentContextParams(
        max_tokens=4000,
        max_protected_ratio=0.2,
        importance_threshold=0.6,
        cluster_similarity_threshold=0.8,
        adaptive_compression=True,
    )
    
    manager2 = IntelligentContextManager.from_params(params=params)
    assert manager2 is not None
    
    print("Manager creation works correctly")

if __name__ == "__main__":
    test_imports()
    test_config_creation()
    test_manager_creation()
    print("\nAll tests passed!")