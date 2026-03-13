"""Test for ar"test" bug in intelligent_context.py."""

# Test the logic for ar"test"
text = 'ar"test"'
print(f"Text: {text}")
print(f"Length: {len(text)}")

# Find the double quote position
quote_pos = text.find('"')
print(f"Double quote position: {quote_pos}")
print(f"Character at quote_pos: '{text[quote_pos]}'")
print(f"Character before quote: '{text[quote_pos-1]}'")
print(f"Character after quote: '{text[quote_pos+1]}'")

# Simulate the logic from _process_char
i = quote_pos
if i > 0 and (text[i - 1].isalnum() or text[i - 1] == "_"):
    print(f"\nPrevious character is alnum/underscore: True")
    
    # Check if it's a string prefix (looking backwards for r/u/b/f)
    j = i - 1
    while j >= 0 and text[j].lower() in ("r", "u", "b", "f"):
        j -= 1
    
    print(f"After looking backwards: j = {j}")
    print(f"j < i - 1? {j} < {i-1} = {j < i - 1}")
    
    # If we found at least one prefix character and the character before
    # the prefix is not alphanumeric or underscore, it's a string prefix
    if j < i - 1 and (j < 0 or not (text[j].isalnum() or text[j] == "_")):
        print("It's a string prefix -> should call handle_string_start")
    else:
        print("Not a string prefix")
        # Check if next character is also alnum (apostrophe in word)
        if i + 1 < len(text) and (text[i + 1].isalnum() or text[i + 1] == "_"):
            print(f"Next character '{text[i+1]}' is alnum/underscore: True -> BUG! Treats as apostrophe in word")
            print("But actually 'ar\"test\"' means variable 'ar' followed by string '\"test\"'")
            print("So the \" should be a string delimiter, not an apostrophe!")
        else:
            print("Next character is NOT alnum/underscore OR i+1 >= len(text): False -> Treat as string delimiter")

# Now test with r"test" (correct case)
print("\n\nTesting r\"test\":")
text2 = 'r"test"'
quote_pos2 = text2.find('"')
i2 = quote_pos2
print(f"Text: {text2}")
print(f"Double quote position: {i2}")
print(f"Character before quote: '{text2[i2-1]}'")

if i2 > 0 and (text2[i2 - 1].isalnum() or text2[i2 - 1] == "_"):
    print("Previous character is alnum/underscore: True")
    
    j2 = i2 - 1
    while j2 >= 0 and text2[j2].lower() in ("r", "u", "b", "f"):
        j2 -= 1
    
    print(f"After looking backwards: j2 = {j2}")
    print(f"j2 < i2 - 1? {j2} < {i2-1} = {j2 < i2 - 1}")
    
    if j2 < i2 - 1 and (j2 < 0 or not (text2[j2].isalnum() or text2[j2] == "_")):
        print("It's a string prefix -> should call handle_string_start (CORRECT)")
    else:
        print("Not a string prefix (WRONG - r is a string prefix!)")