"""Test configuration and fixtures for pytest."""
import sys
from pathlib import Path

# Add src directory to Python path to ensure tests import local version
# instead of any installed version
src_dir = Path(__file__).parent.parent / "src"
src_dir_str = str(src_dir)

# Remove src_dir if it's already in path (might be at wrong position)
if src_dir_str in sys.path:
    sys.path.remove(src_dir_str)

# Insert at the beginning to ensure it's found first
sys.path.insert(0, src_dir_str)
