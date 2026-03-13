import re

with open('src/henchman/tools/builtins/pattern_search.py', 'r') as f:
    content = f.read()

dataclass_def = """@dataclass
class PatternSearchParams:
    \"\"\"Parameters for pattern search.\"\"\"
    desc: str
    root_path: str
    max_results: int
    search_strategy: str

def _execute_pattern_search(params: PatternSearchParams) -> ToolResult:
"""

# Replace the def _execute_pattern_search(...) with the dataclass version
content = re.sub(r"def _execute_pattern_search\([\s\S]*?\) -> ToolResult:", dataclass_def, content)

# Now replace the usages of those variables inside _execute_pattern_search
content = content.replace("params.desc)", "desc)")  # Just in case
content = content.replace("desc=", "params.desc=")
content = content.replace("Path(root_path)", "Path(params.root_path)")
content = content.replace("{root_path}", "{params.root_path}")
content = content.replace("search_strategy not in", "params.search_strategy not in")
content = content.replace("{search_strategy}", "{params.search_strategy}")
content = content.replace("not desc:", "not params.desc:")
content = content.replace("_extract_structural_patterns(desc)", "_extract_structural_patterns(params.desc)")
content = content.replace("_extract_keywords(desc)", "_extract_keywords(params.desc)")
content = content.replace("search_strategy ==", "params.search_strategy ==")
content = content.replace("max_results=max_results", "max_results=params.max_results")
content = content.replace("[:max_results]", "[:params.max_results]")

# Finally, update the call site in execute
content = re.sub(
    r"_execute_pattern_search\([\s\S]*?\)",
    "_execute_pattern_search(PatternSearchParams(desc=description, root_path=path, max_results=top_k, search_strategy=strategy))",
    content
)

# And add the import for dataclass if needed
if "from dataclasses import dataclass" not in content:
    content = content.replace("import re\n", "import re\nfrom dataclasses import dataclass\n")

with open('src/henchman/tools/builtins/pattern_search.py', 'w') as f:
    f.write(content)
