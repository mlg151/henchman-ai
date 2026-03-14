"""Test to demonstrate the bug in get_file_insights method."""
from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry

def test_get_file_insights_returns_first_not_most_recent():
    """Test that get_file_insights returns insights from first entry, not most recent."""
    memory = WorkingMemory(current_task="Test")
    
    # Add two entries for same file with different insights
    memory.add_recent_file(WorkingMemoryEntry(
        path="/test/file.py",
        purpose="First read",
        lines_read="1-50",
        key_insights=["First insight"]
    ))
    memory.add_recent_file(WorkingMemoryEntry(
        path="/test/file.py", 
        purpose="Second read",
        lines_read="60-100",
        key_insights=["Second insight", "Third insight"]
    ))
    
    # get_file_insights should return insights from MOST RECENT entry (second read)
    insights = memory.get_file_insights("/test/file.py")
    print(f"Insights returned: {insights}")
    print(f"Expected: ['Second insight', 'Third insight'] (from most recent entry)")
    print(f"Actual: {insights}")
    
    # This is the bug: it returns ['First insight'] from first entry
    assert insights == ["Second insight", "Third insight"], \
        f"Bug: get_file_insights returns {insights}, expected ['Second insight', 'Third insight']"
    
    print("Test would fail with current implementation!")

if __name__ == "__main__":
    test_get_file_insights_returns_first_not_most_recent()