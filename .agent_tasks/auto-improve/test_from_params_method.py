"""Test the new from_params class method for IntelligentContextManager."""

import pytest
from henchman.utils.intelligent_context import (
    IntelligentContextManager,
    IntelligentContextParams,
    IntelligentContextConfig,
)


def test_from_params_classmethod():
    """Test that from_params class method works correctly."""
    params = IntelligentContextParams(
        max_tokens=5000,
        max_protected_ratio=0.35,
        importance_threshold=0.55,
        cluster_similarity_threshold=0.75,
        adaptive_compression=False
    )
    
    manager = IntelligentContextManager.from_params(params=params)
    
    assert manager.config.max_tokens == 5000
    assert manager.config.max_protected_ratio == 0.35
    assert manager.config.importance_threshold == 0.55
    assert manager.config.cluster_similarity_threshold == 0.75
    assert manager.config.adaptive_compression is False


def test_from_params_with_config():
    """Test that from_params with config parameter ignores params."""
    params = IntelligentContextParams(
        max_tokens=5000,
        max_protected_ratio=0.35,
        importance_threshold=0.55,
        cluster_similarity_threshold=0.75,
        adaptive_compression=False
    )
    
    config = IntelligentContextConfig(
        max_tokens=7000,
        max_protected_ratio=0.45,
        importance_threshold=0.65,
        cluster_similarity_threshold=0.85,
        adaptive_compression=True
    )
    
    manager = IntelligentContextManager.from_params(params=params, config=config)
    
    # Should use config, not params
    assert manager.config.max_tokens == 7000
    assert manager.config.max_protected_ratio == 0.45
    assert manager.config.importance_threshold == 0.65
    assert manager.config.cluster_similarity_threshold == 0.85
    assert manager.config.adaptive_compression is True


def test_from_params_equivalence():
    """Test that from_params produces same result as constructor with primitives."""
    params = IntelligentContextParams(
        max_tokens=4000,
        max_protected_ratio=0.3,
        importance_threshold=0.5,
        cluster_similarity_threshold=0.7,
        adaptive_compression=True
    )
    
    manager1 = IntelligentContextManager.from_params(params=params)
    manager2 = IntelligentContextManager(
        max_tokens=params.max_tokens,
        max_protected_ratio=params.max_protected_ratio,
        importance_threshold=params.importance_threshold,
        cluster_similarity_threshold=params.cluster_similarity_threshold,
        adaptive_compression=params.adaptive_compression
    )
    
    assert manager1.config.max_tokens == manager2.config.max_tokens
    assert manager1.config.max_protected_ratio == manager2.config.max_protected_ratio
    assert manager1.config.importance_threshold == manager2.config.importance_threshold
    assert manager1.config.cluster_similarity_threshold == manager2.config.cluster_similarity_threshold
    assert manager1.config.adaptive_compression == manager2.config.adaptive_compression


if __name__ == "__main__":
    pytest.main([__file__, "-v"])