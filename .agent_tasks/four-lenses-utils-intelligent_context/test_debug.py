"""Debug the backtick bug."""

import sys
sys.path.insert(0, 'src')

# Monkey-patch the function to add debug prints
import henchman.utils.intelligent_context as ic_module

original_extract_code_blocks = ic_module.ContentExtractor.extract_code_blocks

def debug_extract_code_blocks(content):
    print(f"\n=== DEBUG extract_code_blocks ===")
    print(f"Content: {repr(content)}")
    
    if not content:
        print("Empty content, returning []")
        return []
    
    code_blocks = []
    i = 0
    content_length = len(content)
    
    while i < content_length:
        # Look for the start of a code block
        # Code blocks should be preceded by newline or at start of content
        if content[i:i+3] == "```" and (i == 0 or content[i-1] == '\n'):
            print(f"\nFound potential code block start at position {i}")
            # Find the end of the opening backticks
            start_pos = i
            i += 3

            # Check for language specification
            # Language must be followed by whitespace or newline
            lang_start = i
            language = ""
            has_language = False

            # Read potential language (alphanumeric and underscore only, like \w+ in regex)
            while i < content_length and (content[i].isalnum() or content[i] == '_'):
                i += 1
                has_language = True

            if has_language:
                language = content[lang_start:i].strip()
                print(f"  Language: '{language}'")

            # Check if there's whitespace after language
            # If no whitespace and we read something, it's not a language
            if has_language and i < content_length and content[i] not in (' ', '\t', '\n', '\r'):
                # What we read wasn't a language, it's part of the code
                # Reset i to lang_start and treat it as code
                print(f"  No whitespace after language, resetting")
                i = lang_start
                language = ""
                has_language = False

            # Skip whitespace after language (or after opening backticks if no language)
            while i < content_length and content[i] in (' ', '\t', '\n', '\r'):
                i += 1

            # Now find the matching closing backticks
            # We need to handle nested backticks inside the code block
            code_start = i
            backtick_count = 0
            in_string = False
            string_char = None
            triple_quote = False
            raw_string = False  # Track if we're in a raw string (r"", r"", etc.)
            escape_next = False
            
            print(f"  Starting to look for closing backticks from position {i}")

            while i < content_length:
                char = content[i]
                
                # Only print interesting characters
                if char == '`' or char == '\n' or (i - code_start < 50):
                    print(f"    pos={i}, char={repr(char)}, in_string={in_string}, backtick_count={backtick_count}, escape_next={escape_next}")

                # Handle escape sequences
                if escape_next:
                    escape_next = False
                    char_was_escaped = True
                else:
                    char_was_escaped = False

                if char == '\\':
                    # Handle escape sequences
                    if in_string and raw_string:
                        # In raw strings, backslashes are LITERAL characters
                        # They do NOT escape the following character
                        # (Except in the deprecated case where \ escapes the quote,
                        # but we ignore that for simplicity and correctness)
                        # Don't set escape_next, treat backslash as literal
                        pass
                    else:
                        # Regular string or not in string: backslash escapes next character
                        escape_next = True
                        i += 1
                        continue

                # Handle string literals
                if not in_string and char in ('"', "'"):
                    # Check if this is a raw string (r"", R"", etc.)
                    # Look backwards for string prefix
                    is_raw = False
                    if i > 0:
                        # Check for single-character prefixes (r, R, u, U, b, B, f, F)
                        prev_char = content[i-1]
                        if prev_char.lower() in ('r', 'u', 'b', 'f') and (
                            i == 1 or (i >= 2 and not content[i-2].isalnum() and content[i-2] != '_')
                        ):
                            # Might be a raw string prefix
                            # Need to check if it's actually a prefix (not part of identifier)
                            # For simplicity, assume it's a prefix if preceded by whitespace or start
                            is_raw = (prev_char.lower() == 'r')
                        # TODO: Handle combined prefixes (rf, fr, rb, br, etc.)
                        # This is a simplified implementation

                    # Check if this is a triple-quoted string
                    if i + 2 < content_length and content[i+1] == char and content[i+2] == char:
                        # Triple-quoted string
                        in_string = True
                        string_char = char
                        triple_quote = True
                        raw_string = is_raw
                        i += 2  # Skip the other two quotes
                        print(f"      Entered triple-quoted string with char {char}, raw={raw_string}")
                    else:
                        # Single-quoted string
                        in_string = True
                        string_char = char
                        triple_quote = False
                        raw_string = is_raw
                        print(f"      Entered string with char {char}, raw={raw_string}")
                elif in_string and char == string_char and not char_was_escaped:
                    if triple_quote:
                        # Check if this is the closing triple quote
                        if i + 2 < content_length and content[i+1] == char and content[i+2] == char:
                            in_string = False
                            string_char = None
                            triple_quote = False
                            raw_string = False
                            i += 2  # Skip the other two quotes
                            print(f"      Exited triple-quoted string")
                    else:
                        # Single-quoted string ends here
                        in_string = False
                        string_char = None
                        triple_quote = False
                        raw_string = False
                        print(f"      Exited string")

                # Count backticks when not inside a string and not escaped
                # Special case: if we see newline followed by backticks, count them
                # even if we're in a string (handles syntax errors like unclosed strings)
                # but NOT if we're in a triple-quoted string
                if char == '`' and not char_was_escaped:
                    # Check if this might be the start of closing backticks
                    # Look for pattern: (newline or start) + ``` + (newline or end)
                    is_triple_backticks = i + 2 < content_length and content[i:i+3] == '```'
                    if is_triple_backticks:
                        # Check if preceded by newline or at start
                        preceded_by_newline_or_start = i == 0 or content[i-1] == '\n'
                        print(f"      Found triple backticks at {i}, preceded_by_newline_or_start={preceded_by_newline_or_start}")

                        # For closing backticks inside a code block, we require:
                        # 1. They're at the start of a line (preceded by newline) OR at end of content
                        # 2. We've already started counting (in the middle of a sequence)
                        # The "followed by newline" check is too permissive - backticks in code
                        # could be at end of line too.
                        if preceded_by_newline_or_start or (i + 3 == content_length) or backtick_count > 0:
                            # Count them only if we're not in a string
                            # (Backticks inside strings should never count as closing backticks)
                            if not in_string:
                                backtick_count += 1
                                print(f"        Incremented backtick_count to {backtick_count}")
                            else:
                                # In any string (single, double, or triple-quoted), don't count
                                backtick_count = 0
                                print(f"        In string, reset backtick_count to 0")
                        else:
                            # Not a closing backtick pattern - reset count
                            backtick_count = 0
                            print(f"        Not closing pattern, reset backtick_count to 0")
                    elif backtick_count > 0:
                        # We're in the middle of counting backticks (2nd or 3rd backtick)
                        if not in_string:
                            backtick_count += 1
                            print(f"        Incremented backtick_count to {backtick_count} (2nd/3rd backtick)")
                        else:
                            backtick_count = 0
                            print(f"        In string, reset backtick_count to 0 (2nd/3rd backtick)")
                    else:
                        # Not a closing backtick pattern - reset count
                        backtick_count = 0
                        print(f"        Single backtick, reset backtick_count to 0")
                else:
                    backtick_count = 0
                    # print(f"        Not a backtick, reset backtick_count to 0")

                # Check for closing triple backticks
                if backtick_count == 3:
                    # Found closing backticks
                    code_end = i - 2  # Position before the first `
                    code_content = content[code_start:code_end].rstrip()
                    print(f"    Found closing backticks! Code content length: {len(code_content)}")

                    if code_content.strip():
                        # Preserve language if present
                        if language:
                            code_blocks.append(f"```{language}\n{code_content}\n```")
                        else:
                            code_blocks.append(f"```\n{code_content}\n```")
                        print(f"    Added code block")

                    i += 1  # Move past the closing backticks
                    break

                i += 1
            else:
                # No closing backticks found - malformed code block, skip it
                print(f"    No closing backticks found, skipping")
                i = start_pos + 1  # Continue searching from after the opening
        else:
            i += 1
    
    print(f"\nReturning {len(code_blocks)} code blocks")
    return code_blocks

# Test with the failing case
ic_module.ContentExtractor.extract_code_blocks = debug_extract_code_blocks
from henchman.utils.intelligent_context import ContentExtractor

content = '''```python
# Line starting with backtick
`this looks like closing but isn't`
print("done")
```'''

print("Testing the failing case...")
blocks = ContentExtractor.extract_code_blocks(content)
print(f"\nResult: {len(blocks)} blocks")
if blocks:
    print(f"Block: {repr(blocks[0])}")