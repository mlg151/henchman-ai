#!/usr/bin/env python3
"""Test the compatibility checking functionality."""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from henchman.extensions.plugin_manager import PluginManager
from henchman.extensions.models import PluginMetadata, PluginCompatibility

async def test_compatibility():
    """Test compatibility checking."""
    manager = PluginManager()
    
    # Test 1: Compatible plugin
    metadata1 = PluginMetadata(
        name="test-plugin",
        version="1.0.0",
        description="A test plugin",
        author="Test Author",
        entry_points={"henchman_extensions": "test.plugin:TestPlugin"},
        compatibility=PluginCompatibility(
            henchman=">=0.1.0",
            python=">=3.8"
        )
    )
    
    result1 = await manager._check_compatibility(metadata1)
    print(f"Test 1 (compatible): {result1}")
    assert result1 == True, "Should be compatible"
    
    # Test 2: Incompatible Henchman version
    metadata2 = PluginMetadata(
        name="test-plugin",
        version="1.0.0",
        description="A test plugin",
        author="Test Author",
        entry_points={"henchman_extensions": "test.plugin:TestPlugin"},
        compatibility=PluginCompatibility(
            henchman=">=100.0.0",  # Future version
            python=">=3.8"
        )
    )
    
    result2 = await manager._check_compatibility(metadata2)
    print(f"Test 2 (incompatible Henchman): {result2}")
    assert result2 == False, "Should be incompatible due to Henchman version"
    
    # Test 3: Incompatible Python version
    metadata3 = PluginMetadata(
        name="test-plugin",
        version="1.0.0",
        description="A test plugin",
        author="Test Author",
        entry_points={"henchman_extensions": "test.plugin:TestPlugin"},
        compatibility=PluginCompatibility(
            henchman=">=0.1.0",
            python=">=100.0.0"  # Future Python version
        )
    )
    
    result3 = await manager._check_compatibility(metadata3)
    print(f"Test 3 (incompatible Python): {result3}")
    assert result3 == False, "Should be incompatible due to Python version"
    
    # Test 4: Invalid version specifier
    metadata4 = PluginMetadata(
        name="test-plugin",
        version="1.0.0",
        description="A test plugin",
        author="Test Author",
        entry_points={"henchman_extensions": "test.plugin:TestPlugin"},
        compatibility=PluginCompatibility(
            henchman="invalid-specifier",
            python=">=3.8"
        )
    )
    
    result4 = await manager._check_compatibility(metadata4)
    print(f"Test 4 (invalid specifier): {result4}")
    assert result4 == False, "Should be incompatible due to invalid specifier"
    
    # Test 5: OS compatibility
    metadata5 = PluginMetadata(
        name="test-plugin",
        version="1.0.0",
        description="A test plugin",
        author="Test Author",
        entry_points={"henchman_extensions": "test.plugin:TestPlugin"},
        compatibility=PluginCompatibility(
            henchman=">=0.1.0",
            python=">=3.8",
            os=["windows"]  # Assuming we're not on Windows
        )
    )
    
    result5 = await manager._check_compatibility(metadata5)
    print(f"Test 5 (OS incompatible): {result5}")
    # This test might pass or fail depending on the actual OS
    
    print("\nAll tests passed!")

if __name__ == "__main__":
    asyncio.run(test_compatibility())