"""Debug test for TOCTOU bug."""

import sys
sys.path.insert(0, 'src')

from henchman.cli.textual_mixins import _InitMixin


def test_debug_none_attribute() -> None:
    """Debug test."""
    # Create mixin instance
    mixin = _InitMixin.__new__(_InitMixin)
    
    # Set _confirm_futures to None
    mixin._confirm_futures = None
    
    print(f"hasattr(mixin, '_confirm_futures'): {hasattr(mixin, '_confirm_futures')}")
    print(f"mixin._confirm_futures: {mixin._confirm_futures}")
    print(f"type(mixin._confirm_futures): {type(mixin._confirm_futures)}")
    
    # Call the method
    try:
        mixin._cleanup_confirm_futures()
        print("No exception raised!")
    except AttributeError as e:
        print(f"AttributeError raised: {e}")
        raise


if __name__ == "__main__":
    test_debug_none_attribute()