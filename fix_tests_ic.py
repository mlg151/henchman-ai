import os
import glob
import re

files = glob.glob('tests/utils/test_intelligent_context*.py')

for f in files:
    content = open(f).read()
    orig = content
    
    # Add _ApostropheDetector import if it uses parser._is_apostrophe_in_word
    if "parser._is_apostrophe_in_word" in content and "_ApostropheDetector" not in content:
        content = content.replace("from henchman.utils.intelligent_context_parser import _ParserState", 
                                  "from henchman.utils.intelligent_context_parser import _ParserState, _ApostropheDetector")

    if "parser._is_apostrophe_in_word" in content and "_ApostropheDetector" not in content:
        # Fallback if not added above
        content = content.replace("import pytest", "import pytest\nfrom henchman.utils.intelligent_context_parser import _ApostropheDetector")
    
    # Fix the duplicate arg
    content = content.replace("_ApostropheDetector.is_apostrophe_in_word(_ApostropheDetector, ", "_ApostropheDetector.is_apostrophe_in_word(")
    
    # Replace the method call
    content = re.sub(r'(\w+)\._is_apostrophe_in_word\((.*?),\s*(.*?)\)', r'_ApostropheDetector.is_apostrophe_in_word(\1, \2, \3)', content)

    # Fix _check_closing_fence
    if "_check_closing_fence" in content:
        if "FenceParams" not in content:
            content = content.replace("from henchman.utils.intelligent_context_parser import _ParserState", 
                                      "from henchman.utils.intelligent_context_parser import _ParserState\nfrom henchman.utils.intelligent_context_types import FenceParams")
            if "from henchman.utils.intelligent_context_parser import _ParserState" not in content:
                 content = content.replace("import pytest", "import pytest\nfrom henchman.utils.intelligent_context_types import FenceParams")
                 
        # The old signature was: parser._check_closing_fence(content, i, opening_count)
        # New: parser._check_fence(i, FenceParams(content=content, opening_count=opening_count))
        # Be careful with the regex here
        def repl(match):
            parser_var = match.group(1)
            content_var = match.group(2)
            i_var = match.group(3)
            count_var = match.group(4)
            return f"{parser_var}._check_fence({i_var}, FenceParams(content={content_var}, opening_count={count_var}))"
        
        content = re.sub(r'(\w+)\._check_closing_fence\((.*?),\s*(.*?),\s*(.*?)\)', repl, content)

    if orig != content:
        open(f, 'w').write(content)
        print(f"Fixed {f}")
