import re
import sys

try:
    content = open('src/henchman/utils/intelligent_context.py').read()

    import_additions = """
from henchman.utils.intelligent_context_detector import ConversationTypeDetector
from henchman.utils.intelligent_context_summarizer import SummaryGenerator
"""

    if "ConversationTypeDetector" not in content[:1000]:
        content = content.replace("from henchman.utils.intelligent_context_extractor import ContentExtractor", "from henchman.utils.intelligent_context_extractor import ContentExtractor\n" + import_additions)

    def remove_class(class_name, text):
        pattern = re.compile(rf"^(?:@dataclass\n)?class {class_name}\b.*?(?=^class |^def |^@)", re.DOTALL | re.MULTILINE)
        return pattern.sub("", text)

    classes = [
        "ConversationTypeDetector", "SummaryGenerator", "_ConversationHistory", "MessageClusterer", "_MessageClusteringParams",
        "RoleTracker", "SystemPromptAnalyzer" # just in case any nested classes were moved too
    ]

    for cls in classes:
        content = remove_class(cls, content)

    # Some classes might be the last one in the file.
    # The regex won't catch the very last class if there is no next class/def.
    for cls in classes:
        pattern = re.compile(rf"^(?:@dataclass\n)?class {cls}\b.*$", re.DOTALL | re.MULTILINE)
        # only do this if it's the ONLY thing left or at the very end
        # Actually it's safer to just check if it's still there and do a targeted replace
        pass

    content = re.sub(r'\n{3,}', '\n\n', content)

    open('src/henchman/utils/intelligent_context.py', 'w').write(content)
    print("Done refactoring intelligent_context.py")
except Exception as e:
    print("Error:", e)
    sys.exit(1)
