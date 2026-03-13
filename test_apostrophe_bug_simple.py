"""Simple test to understand the apostrophe bug."""

# Let's trace through the logic for "This isn't"
text = "This isn't"
print(f"Text: {text}")
print(f"Length: {len(text)}")

# Find the apostrophe position
apostrophe_pos = text.find("'")
print(f"Apostrophe position: {apostrophe_pos}")
print(f"Character at apostrophe_pos: '{text[apostrophe_pos]}'")
print(f"Character before apostrophe: '{text[apostrophe_pos-1]}'")
print(f"Character after apostrophe: '{text[apostrophe_pos+1]}'")

# Check the condition from _process_char
i = apostrophe_pos
if i > 0 and (text[i - 1].isalnum() or text[i - 1] == "_"):
    print(f"Previous character is alnum/underscore: True")
    
    # Check if it's a string prefix (looking backwards for r/u/b/f)
    j = i - 1
    while j >= 0 and text[j].lower() in ("r", "u", "b", "f"):
        j -= 1
    
    # If we found at least one prefix character and the character before
    # the prefix is not alphanumeric or underscore, it's a string prefix
    if j < i - 1 and (j < 0 or not (text[j].isalnum() or text[j] == "_")):
        print("It's a string prefix")
    else:
        print("Not a string prefix")
        # Check if next character is also alnum (apostrophe in word)
        if i + 1 < len(text) and (text[i + 1].isalnum() or text[i + 1] == "_"):
            print("Next character is alnum/underscore: True -> It's an apostrophe in a word")
        else:
            print("Next character is NOT alnum/underscore OR i+1 >= len(text): False -> Treat as string delimiter")

# Now test with apostrophe at end of text
text2 = "isn't"
print(f"\nText2: {text2}")
print(f"Length: {len(text2)}")

# The apostrophe is at position 3 in "isn't"
i2 = 3
print(f"Character at position {i2}: '{text2[i2]}'")
print(f"Character after apostrophe (i2+1={i2+1}): index {i2+1} {'is' if i2+1 < len(text2) else 'is NOT'} < len(text2)={len(text2)}")

if i2 + 1 < len(text2):
    print(f"Character at i2+1: '{text2[i2+1]}'")
    print(f"Is alnum/underscore? {text2[i2+1].isalnum() or text2[i2+1] == '_'}")
else:
    print("i2+1 is out of bounds")

# Test with word ending with apostrophe at end of line
text3 = "isn't\n"
print(f"\nText3: {repr(text3)}")
print(f"Length: {len(text3)}")

# Find apostrophe
i3 = text3.find("'")
print(f"Apostrophe position: {i3}")
print(f"Character after apostrophe: '{text3[i3+1]}' (code: {ord(text3[i3+1])})")
print(f"Is '\\n' alnum? {text3[i3+1].isalnum()}")
print(f"Is '\\n' underscore? {text3[i3+1] == '_'}")