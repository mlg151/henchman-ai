"""Test exact error message."""

import sys
sys.path.insert(0, 'src')

from henchman.cli.textual_mixins import _InitMixin
import pytest


def test_exact_error() -> None:
    """Test exact error message."""
    mixin = _InitMixin.__new__(_InitMixin)
    mixin._confirm_futures = None
    
    try:
        mixin._cleanup_confirm_futures()
    except AttributeError as e:
        print(f"Error message: {e}")
        print(f"Error args: {e.args}")
        # Check if this matches what pytest expects
        print(f"Matches 'NoneType' object has no attribute 'keys': {'NoneType' in str(e) and 'keys' in str(e)}")
        
        # Now test with pytest
        with pytest.raises(AttributeError) as exc_info:
            mixin._cleanup_confirm_futures()
        print(f"pytest caught: {exc_info.value}")
        print(f"Match check: {exc_info.match('.*NoneType.*keys.*')}")


if __name__ == "__main__":
    test_exact_error()