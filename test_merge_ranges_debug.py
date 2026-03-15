"""Debug the merge_ranges bug."""

from henchman.agents.working_memory import WorkingMemory, LineRange

def test_debug():
    memory = WorkingMemory(current_task="Test")
    
    range1 = LineRange(10, 20)
    range2 = LineRange(15, 25)
    
    print(f"range1 id: {id(range1)}, range1: {range1}")
    print(f"range2 id: {id(range2)}, range2: {range2}")
    
    # Call sorted
    sorted_ranges = sorted([range1, range2], key=lambda r: r.start)
    print(f"\nAfter sorted:")
    for i, r in enumerate(sorted_ranges):
        print(f"  sorted_ranges[{i}] id: {id(r)}, range: {r}")
    
    # Now call _merge_ranges
    merged = memory._merge_ranges([range1, range2])
    
    print(f"\nAfter _merge_ranges:")
    print(f"range1: {range1}")
    print(f"range2: {range2}")
    print(f"merged: {merged}")
    
    # Check if they're the same object
    print(f"\nObject equality:")
    print(f"range1 is merged[0]: {range1 is merged[0]}")
    
    # Actually, let me trace through _merge_ranges logic
    print("\nTracing _merge_ranges logic:")
    print("1. sorted_ranges = [range1, range2] (already sorted)")
    print("2. merged = []")
    print("3. Process range1: merged is empty, so merged.append(range1)")
    print("   merged = [range1]")
    print("4. Process range2: last = merged[-1] = range1")
    print("5. Check: range2.start (15) <= range1.end + 1 (21)? True")
    print("6. Modify: last.end = max(range1.end (20), range2.end (25)) = 25")
    print("7. So range1.end becomes 25!")
    
    # But my test shows range1.end is still 20...
    # Let me check the actual implementation again
    
if __name__ == "__main__":
    test_debug()