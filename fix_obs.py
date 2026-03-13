import re

# Fix pattern_search.py primitive obsession
with open('src/henchman/tools/builtins/pattern_search.py', 'r') as f:
    content = f.read()

# Instead of repeating args, we rename them slightly in the helper function
content = content.replace('def _execute_pattern_search(\n    description: str,\n    path: str,\n    top_k: int,\n    strategy: str,\n)', 'def _execute_pattern_search(\n    desc: str,\n    root_path: str,\n    max_results: int,\n    search_strategy: str,\n)')
content = content.replace('description)', 'desc)')
content = content.replace('description=', 'desc=')
content = content.replace('Path(path)', 'Path(root_path)')
content = content.replace('Path not found: {path}', 'Path not found: {root_path}')
content = content.replace('strategy not in', 'search_strategy not in')
content = content.replace('strategy}', 'search_strategy}')
content = content.replace('not description', 'not desc')
content = content.replace('_extract_structural_patterns(description)', '_extract_structural_patterns(desc)')
content = content.replace('_extract_keywords(description)', '_extract_keywords(desc)')
content = content.replace('strategy ==', 'search_strategy ==')
content = content.replace('if not struct_patterns and not keywords', 'if not struct_patterns and not keywords')
content = content.replace('max_results=top_k', 'max_results=top_k')
content = content.replace('[:top_k]', '[:max_results]')

with open('src/henchman/tools/builtins/pattern_search.py', 'w') as f:
    f.write(content)

# Fix research_notes.py primitive obsession
with open('src/henchman/tools/builtins/research_notes.py', 'r') as f:
    content = f.read()

content = content.replace('def _execute_research_notes(\n    action: str,\n    tag: str,\n    content: str,\n    query: str,\n    notes_dir: Path | None,\n)', 'def _execute_research_notes(\n    op: str,\n    note_tag: str,\n    note_content: str,\n    search_query: str,\n    notes_dir: Path | None,\n)')
content = content.replace('action not in', 'op not in')
content = content.replace("action '", "action '")
content = content.replace('action}', 'op}')
content = content.replace('action ==', 'op ==')
content = content.replace('query)', 'search_query)')
content = content.replace('not query', 'not search_query')
content = content.replace('not tag', 'not note_tag')
content = content.replace("tag '", "note_tag '")
content = content.replace('tag}', 'note_tag}')
content = content.replace('content=', 'note_content=')
content = content.replace('tag=', 'note_tag=')
content = content.replace('op=action', 'op=action')

with open('src/henchman/tools/builtins/research_notes.py', 'w') as f:
    f.write(content)
