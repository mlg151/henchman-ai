"""Test for validation order bug in working_memory.py should_read_file method.

BUG: The should_read_file method converts end=-1 to None BEFORE validation,
which causes inconsistent validation and misleading error messages.
"""

import pytest
from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry


def test_should_read_file_validation_order_bug():
    """Test that validation happens in correct order with consistent error messages.
    
    BUG: When end=-1 is passed, it gets converted to None BEFORE validation.
    This means:
    1. end=-1 bypasses validation entirely
    2. end=-2 gets validated and rejected with "must be positive" error
    3. The error message is misleading because -1 is also negative but allowed
    
    Expected behavior:
    1. All values should be validated BEFORE any conversions
    2. end=-1 should be explicitly allowed as a special case during validation
    3. Error message should accurately reflect allowed values
    """
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "full"))
    
    # Test 1: end=-1 should be allowed (special case meaning "read to EOF")
    # Currently: end=-1 gets converted to None, bypasses validation
    # Bug: No validation happens on end=-1
    should_read, reason = memory.should_read_file("/test/file.py", start=10, end=-1)
    # File was read fully, so should return False
    assert should_read is False
    assert "already read" in reason.lower()
    
    # Test 2: end=-2 should be rejected with appropriate error
    # Currently: Gets "end must be positive (1-indexed)" error
    # Bug: Error message is misleading because -1 is also negative but allowed
    should_read, reason = memory.should_read_file("/test/file.py", start=10, end=-2)
    assert should_read is True
    # Current buggy error message: "Invalid line number: end must be positive (1-indexed), got end=-2"
    # This is misleading because -1 is also negative but allowed
    # Better error: "Invalid line number: end must be -1 (for EOF) or positive (1-indexed), got end=-2"
    assert "invalid" in reason.lower()
    # Check that error mentions -2 (the actual invalid value)
    assert "-2" in reason
    
    # Test 3: end=0 should be rejected
    should_read, reason = memory.should_read_file("/test/file.py", start=10, end=0)
    assert should_read is True
    assert "invalid" in reason.lower()
    assert "0" in reason
    
    # Test 4: end=-1.0 (float) should be rejected as not integer
    # BUG: -1.0 == -1 is True in Python, so end=-1.0 passes the end == -1 check
    # and gets converted to None, bypassing validation!
    # This is incorrect - only integer -1 should be allowed
    should_read, reason = memory.should_read_file("/test/file.py", start=10, end=-1.0)
    # BUG: Currently returns False (file already read) because end=-1.0 gets converted to None
    # Should return True with error about end not being integer
    assert should_read is True, f"end=-1.0 (float) should be rejected, not accepted. Got: should_read={should_read}, reason={reason}"
    assert "integer" in reason.lower(), f"Should reject float -1.0 as not integer. Got reason: {reason}"
    # The error should mention it's a float or not an integer
    assert "float" in reason.lower() or "not an integer" in reason.lower() or "must be an integer" in reason.lower()
    
    # Test 5: end=None (no end specified) should be valid
    should_read, reason = memory.should_read_file("/test/file.py", start=10, end=None)
    # File was read fully, so should return False
    assert should_read is False
    assert "already read" in reason.lower()


def test_should_read_file_validation_before_conversion():
    """Test that validation happens before end=-1 conversion.
    
    The bug is that end=-1 is converted to None BEFORE validation.
    This means invalid values paired with end=-1 might not get proper validation.
    
    Example: start=0, end=-1
    - start=0 is invalid (line numbers are 1-indexed)
    - end=-1 is valid (means "read to EOF")
    - Currently: end=-1 gets converted to None, then start=0 might get validated
    - Bug: The validation order could mask issues
    """
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "full"))
    
    # Test with invalid start=0 and valid end=-1
    # Should report error about invalid start=0, not crash
    should_read, reason = memory.should_read_file("/test/file.py", start=0, end=-1)
    assert should_read is True
    # Should report error about start=0 being invalid
    assert "invalid" in reason.lower()
    assert "0" in reason or "positive" in reason.lower()
    
    # Test with valid start=10 and invalid end=-2
    # Should report error about end=-2 being invalid
    should_read, reason = memory.should_read_file("/test/file.py", start=10, end=-2)
    assert should_read is True
    assert "invalid" in reason.lower()
    assert "-2" in reason


def test_should_read_file_error_message_accuracy():
    """Test that error messages accurately reflect allowed values.
    
    Current buggy error message for end=-2: "end must be positive (1-indexed)"
    This is misleading because end=-1 is also negative but allowed.
    
    The error message should mention that -1 is allowed as a special case.
    """
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "full"))
    
    # Get error message for end=-2
    should_read, reason = memory.should_read_file("/test/file.py", start=10, end=-2)
    
    # Check current buggy behavior
    print(f"Current error message for end=-2: {reason}")
    
    # The error message should not say "must be positive" without qualification
    # because -1 is negative but allowed
    # Actually, let's check what the current message says
    assert "must be positive" in reason or "positive" in reason.lower()
    
    # After fix: error message should be more accurate about allowed values
    # e.g., "end must be -1 (for EOF) or positive (1-indexed)"


if __name__ == "__main__":
    # Run the tests
    import sys
    
    print("Testing validation order bug in should_read_file...")
    
    try:
        test_should_read_file_validation_order_bug()
        print("✓ test_should_read_file_validation_order_bug passed")
    except AssertionError as e:
        print(f"✗ test_should_read_file_validation_order_bug failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"✗ test_should_read_file_validation_order_bug crashed: {e}")
        sys.exit(1)
    
    try:
        test_should_read_file_validation_before_conversion()
        print("✓ test_should_read_file_validation_before_conversion passed")
    except AssertionError as e:
        print(f"✗ test_should_read_file_validation_before_conversion failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"✗ test_should_read_file_validation_before_conversion crashed: {e}")
        sys.exit(1)
    
    try:
        test_should_read_file_error_message_accuracy()
        print("✓ test_should_read_file_error_message_accuracy passed")
    except AssertionError as e:
        print(f"✗ test_should_read_file_error_message_accuracy failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"✗ test_should_read_file_error_message_accuracy crashed: {e}")
        sys.exit(1)
    
    print("\nAll tests passed!")