from henchman.agents.working_memory import LineRange

# Test LineRange.from_str with invalid ranges
print("Testing LineRange.from_str with invalid ranges:")
print(f"LineRange.from_str('10-5'): {LineRange.from_str('10-5')}")  # start > end
print(f"LineRange.from_str('0-10'): {LineRange.from_str('0-10')}")  # start=0
print(f"LineRange.from_str('-5-10'): {LineRange.from_str('-5-10')}")  # negative
print(f"LineRange.from_str('10--5'): {LineRange.from_str('10--5')}")  # negative
print(f"LineRange.from_str('abc-def'): {LineRange.from_str('abc-def')}")  # not numbers
print(f"LineRange.from_str('10'): {LineRange.from_str('10')}")  # single number
print(f"LineRange.from_str('10-20-30'): {LineRange.from_str('10-20-30')}")  # three parts

# Test LineRange creation with invalid values
print("\nTesting LineRange creation:")
try:
    r = LineRange(10, 5)  # start > end
    print(f"LineRange(10, 5) created: {r}")
except ValueError as e:
    print(f"LineRange(10, 5) raised ValueError: {e}")

try:
    r = LineRange(0, 10)  # start=0
    print(f"LineRange(0, 10) created: {r}")
except ValueError as e:
    print(f"LineRange(0, 10) raised ValueError: {e}")