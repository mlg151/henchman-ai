"""Debug the merge_ranges bug more carefully."""

from henchman.agents.working_memory import WorkingMemory, LineRange

def test_debug():
    memory = WorkingMemory(current_task="Test")
    
    range1 = LineRange(10, 20)
    range2 = LineRange(15, 25)
    
    print(f"range1 id: {id(range1)}, range1: {range1}")
    print(f"range2 id: {id(range2)}, range2: {range2}")
    
    # Call _merge_ranges
    merged = memory._merge_ranges([range1, range2])
    
    print(f"\nAfter _merge_ranges:")
    print(f"range1: {range1}, id: {id(range1)}")
    print(f"range2: {range2}, id: {id(range2)}")
    print(f"merged: {merged}")
    if merged:
        print(f"merged[0]: {merged[0]}, id: {id(merged[0])}")
        print(f"range1 is merged[0]: {range1 is merged[0]}")
    
    # Let me look at the actual _merge_ranges implementation
    print("\nLooking at _merge_ranges source...")
    # Actually, I need to check if there's something else going on
    
    # Let me trace through manually
    print("\nManual trace:")
    ranges = [range1, range2]
    if not ranges:
        print("  ranges is empty")
    
    # Sort ranges by start line
    sorted_ranges = sorted(ranges, key=lambda r: r.start)
    print(f"  sorted_ranges: {sorted_ranges}")
    print(f"  sorted_ranges[0] is range1: {sorted_ranges[0] is range1}")
    print(f"  sorted_ranges[1] is range2: {sorted_ranges[1] is range2}")
    
    # Merge overlapping or adjacent ranges
    merged2: list[LineRange] = []
    for rng in sorted_ranges:
        print(f"\n  Processing rng: {rng}, id: {id(rng)}")
        if not merged2:
            print(f"    merged2 is empty, appending rng")
            merged2.append(rng)
            print(f"    merged2: {merged2}")
            continue
        
        last = merged2[-1]
        print(f"    last: {last}, id: {id(last)}")
        print(f"    rng.start ({rng.start}) <= last.end + 1 ({last.end + 1})? {rng.start <= last.end + 1}")
        if rng.start <= last.end + 1:
            print(f"    Overlapping or adjacent")
            print(f"    last.end before: {last.end}")
            last.end = max(last.end, rng.end)
            print(f"    last.end after: {last.end}")
            print(f"    merged2 after modification: {merged2}")
        else:
            print(f"    Not overlapping, appending rng")
            merged2.append(rng)
    
    print(f"\n  Final merged2: {merged2}")
    print(f"  range1 after manual trace: {range1}")
    print(f"  range2 after manual trace: {range2}")

if __name__ == "__main__":
    test_debug()