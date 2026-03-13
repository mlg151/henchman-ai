# Test if r"test\\\\\\" is valid Python
try:
    exec('s = r"test\\\\\\"')
    print("r\"test\\\\\\\\\\\\\" is valid")
except SyntaxError as e:
    print(f"r\"test\\\\\\\\\\\\\" is invalid: {e}")

# Test if r"test\\\\" is valid (even backslashes)
try:
    exec('s = r"test\\\\"')
    print("r\"test\\\\\\\\\" is valid")
except SyntaxError as e:
    print(f"r\"test\\\\\\\\\" is invalid: {e}")