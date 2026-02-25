"""Analyze test coverage for agent.py"""
import ast
from pathlib import Path


def analyze_coverage():
    """Analyze what parts of agent.py are not covered by tests."""
    agent_path = Path("src/henchman/core/agent.py")

    with open(agent_path) as f:
        content = f.read()

    tree = ast.parse(content)

    # Find all function and method definitions
    functions = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            functions.append({
                'name': node.name,
                'lineno': node.lineno,
                'end_lineno': node.end_lineno
            })

    print("Functions in agent.py:")
    for func in functions:
        print(f"  {func['name']}: lines {func['lineno']}-{func['end_lineno']}")

    # Based on coverage report, we need to test:
    # 1. clear_history() - keeps system messages
    # 2. get_messages_for_api() - compaction logic
    # 3. submit_tool_result() - adds tool results
    # 4. _update_protected_token_count()
    # 5. _calculate_protected_count()
    # 6. _try_summarization_compaction()
    # 7. _apply_simple_compaction()
    # 8. _should_skip_stall_check()
    # 9. _detect_stalling_patterns()
    # 10. _check_for_stalling()
    # 11. _process_streaming_response()
    # 12. continue_with_tool_results()

    print("\nKey areas needing test coverage:")
    print("1. Stall detection logic")
    print("2. Compaction logic")
    print("3. Tool result handling")
    print("4. Streaming response processing")

if __name__ == "__main__":
    analyze_coverage()
