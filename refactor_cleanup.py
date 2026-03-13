import re
import sys

try:
    content = open('src/henchman/utils/intelligent_context.py').read()

    import_additions = """
from henchman.utils.intelligent_context_parser import _ParserState
from henchman.utils.intelligent_context_types import FenceResult, IntelligentContextConstants, FenceParams
"""

    if "_ParserState" not in content[:1000]:
        content = content.replace("from henchman.utils.intelligent_context_extractor import ContentExtractor", "from henchman.utils.intelligent_context_extractor import ContentExtractor\n" + import_additions)

    def remove_class(class_name, text):
        pattern = re.compile(rf"^(?:@dataclass\n)?class {class_name}\b.*?(?=^class |^def |^@)", re.DOTALL | re.MULTILINE)
        return pattern.sub("", text)

    classes = [
        "FenceResult", "_StringState", "_ContractionParams", "_ApostropheDetector", "CharProcessParams", "_ParserState",
        "IntelligentContextConstants", "FenceParams", "ContentExtractor", "TruncationParams"
    ]

    for cls in classes:
        content = remove_class(cls, content)

    # Some classes might be the last one in the file or followed by another thing, so let's be careful.
    # The previous regex works well if there's another class or def.
    # If the file has leftover bits of _ParserState, we'll see it.

    content = re.sub(r'\n{3,}', '\n\n', content)

    open('src/henchman/utils/intelligent_context.py', 'w').write(content)
    print("Done refactoring")
except Exception as e:
    print("Error:", e)
    sys.exit(1)
