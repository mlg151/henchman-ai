import os
import re

files_to_fix = [
    "tests/utils/test_intelligent_context_apostrophe_bug_final.py",
    "tests/utils/test_intelligent_context_bug_yve.py",
    "tests/utils/test_intelligent_context_contraction_bug.py",
    "tests/utils/test_intelligent_context_contraction_bug_fixed.py",
    "tests/utils/test_intelligent_context_four_lenses_bug.py",
    "tests/utils/test_intelligent_context_four_lenses_bug_final.py",
    "tests/utils/test_intelligent_context_four_lenses_real_bug.py",
    "tests/utils/test_intelligent_context_index_error_bug_final.py",
    "tests/utils/test_intelligent_context_mayve_bug.py",
    "tests/utils/test_intelligent_context_real_bug.py",
    "tests/utils/test_intelligent_context_real_bug_final.py",
    "tests/utils/test_intelligent_context_yve_bug_final.py",
    "tests/utils/test_intelligent_context.py",
    "tests/utils/test_intelligent_context_bug_fix_verification.py",
    "tests/utils/test_intelligent_context_index_error_bug.py"
]

for file_path in files_to_fix:
    if not os.path.exists(file_path):
        print(f"Skipping {file_path}, not found.")
        continue
        
    with open(file_path, 'r') as f:
        content = f.read()
    
    # 1. Fix mixed imports
    # If ContentExtractor is imported from parser, move it to extractor
    if 'from henchman.utils.intelligent_context_parser import' in content and 'ContentExtractor' in content:
        # Check if ContentExtractor is in the import list
        import_match = re.search(r'from henchman\.utils\.intelligent_context_parser import ([^\n]+)', content)
        if import_match and 'ContentExtractor' in import_match.group(1):
            # Remove ContentExtractor from parser import
            parser_imports = [i.strip() for i in import_match.group(1).split(',')]
            parser_imports = [i for i in parser_imports if i and i != 'ContentExtractor']
            
            if parser_imports:
                new_parser_import = f"from henchman.utils.intelligent_context_parser import {', '.join(parser_imports)}"
                content = content.replace(import_match.group(0), new_parser_import)
            else:
                # Remove the whole line if empty
                content = content.replace(import_match.group(0) + '\n', '')
            
            # Add or update extractor import
            if 'from henchman.utils.intelligent_context_extractor import ContentExtractor' not in content:
                content = "from henchman.utils.intelligent_context_extractor import ContentExtractor\n" + content

    # 2. Fix doubled _ApostropheDetector argument
    content = content.replace('_ApostropheDetector.is_apostrophe_in_word(_ApostropheDetector,', '_ApostropheDetector.is_apostrophe_in_word(')

    with open(file_path, 'w') as f:
        f.write(content)
    print(f"Fixed {file_path}")
