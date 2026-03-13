"""Test primitive obsession fix for intelligent_context.py."""

import pytest
from henchman.providers.base import Message
from henchman.utils.intelligent_context import (
    IntelligentContextManager,
    IntelligentContextParams,
    IntelligentContextConfig,
)


def test_init_with_params_object():
    """Test that IntelligentContextManager can be initialized with params object."""
    # Create params object
    params = IntelligentContextParams(
        max_tokens=4000,
        max_protected_ratio=0.3,
        importance_threshold=0.5,
        cluster_similarity_threshold=0.7,
        adaptive_compression=True
    )
    
    # Test that the manager can be created (it internally creates params from primitives)
    manager = IntelligentContextManager(
        max_tokens=params.max_tokens,
        max_protected_ratio=params.max_protected_ratio,
        importance_threshold=params.importance_threshold,
        cluster_similarity_threshold=params.cluster_similarity_threshold,
        adaptive_compression=params.adaptive_compression
    )
    
    assert manager.config.max_tokens == 4000
    assert manager.config.max_protected_ratio == 0.3
    assert manager.config.importance_threshold == 0.5
    assert manager.config.cluster_similarity_threshold == 0.7
    assert manager.config.adaptive_compression is True


def test_init_with_config_object():
    """Test that IntelligentContextManager can be initialized with config object."""
    config = IntelligentContextConfig(
        max_tokens=6000,
        max_protected_ratio=0.4,
        importance_threshold=0.6,
        cluster_similarity_threshold=0.8,
        adaptive_compression=False
    )
    
    manager = IntelligentContextManager(config=config)
    
    assert manager.config.max_tokens == 6000
    assert manager.config.max_protected_ratio == 0.4
    assert manager.config.importance_threshold == 0.6
    assert manager.config.cluster_similarity_threshold == 0.8
    assert manager.config.adaptive_compression is False


def test_init_with_defaults():
    """Test that IntelligentContextManager uses defaults when parameters are None."""
    manager = IntelligentContextManager()
    
    # Check that defaults are used
    from henchman.utils.intelligent_context import IntelligentContextConstants
    assert manager.config.max_tokens == IntelligentContextConstants.DEFAULT_MAX_TOKENS
    assert manager.config.max_protected_ratio == IntelligentContextConstants.DEFAULT_MAX_PROTECTED_RATIO
    assert manager.config.importance_threshold == IntelligentContextConstants.DEFAULT_IMPORTANCE_THRESHOLD
    assert manager.config.cluster_similarity_threshold == IntelligentContextConstants.DEFAULT_CLUSTER_SIMILARITY_THRESHOLD
    assert manager.config.adaptive_compression is True


def test_from_params_classmethod():
    """Test that from_params class method works correctly."""
    params = IntelligentContextParams(
        max_tokens=5000,
        max_protected_ratio=0.35,
        importance_threshold=0.55,
        cluster_similarity_threshold=0.75,
        adaptive_compression=False
    )
    
    config = IntelligentContextConfig.from_params(params=params)
    
    assert config.max_tokens == 5000
    assert config.max_protected_ratio == 0.35
    assert config.importance_threshold == 0.55
    assert config.cluster_similarity_threshold == 0.75
    assert config.adaptive_compression is False


def test_primitive_parameters_backward_compatibility():
    """Test that primitive parameters still work for backward compatibility."""
    manager = IntelligentContextManager(
        max_tokens=3000,
        max_protected_ratio=0.25,
        importance_threshold=0.45,
        cluster_similarity_threshold=0.65,
        adaptive_compression=True
    )
    
    assert manager.config.max_tokens == 3000
    assert manager.config.max_protected_ratio == 0.25
    assert manager.config.importance_threshold == 0.45
    assert manager.config.cluster_similarity_threshold == 0.65
    assert manager.config.adaptive_compression is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])