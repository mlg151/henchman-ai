import os
import re

files_to_update = [
    "tests/utils/test_intelligent_compaction.py",
    "tests/utils/test_intelligent_truncation_refactoring.py",
    "tests/utils/test_coverage_boost.py",
]

for file_path in files_to_update:
    with open(file_path, "r") as f:
        content = f.read()
    
    # Add import
    if "from henchman.utils.intelligent_context_config import IntelligentContextParams" not in content:
        content = content.replace(
            "from henchman.utils.intelligent_context import IntelligentContextManager",
            "from henchman.utils.intelligent_context import IntelligentContextManager\nfrom henchman.utils.intelligent_context_config import IntelligentContextParams"
        )
    
    # Replace IntelligentContextManager(max_tokens=XXX)
    content = re.sub(
        r"IntelligentContextManager\(max_tokens=([^,)]+)\)",
        r"IntelligentContextManager(params=IntelligentContextParams(max_tokens=\1))",
        content
    )
    
    # Replace IntelligentContextManager(max_tokens=XXX, cluster_similarity_threshold=YYY)
    content = re.sub(
        r"IntelligentContextManager\(max_tokens=([^,)]+),\s*cluster_similarity_threshold=([^,)]+)\)",
        r"IntelligentContextManager(params=IntelligentContextParams(max_tokens=\1, cluster_similarity_threshold=\2))",
        content
    )

    # Replace IntelligentContextManager()
    content = re.sub(
        r"IntelligentContextManager\(\)",
        r"IntelligentContextManager(params=IntelligentContextParams())",
        content
    )
    
    with open(file_path, "w") as f:
        f.write(content)

print("Updated tests successfully.")
