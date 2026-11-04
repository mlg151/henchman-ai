import pytest
from evals import test_coding_tasks as coding_tasks
from evals.helpers import MockProvider

VALID_SOURCE = """
def greet(name):
    print(f"Hello, {name}!")
    return True
"""


@pytest.mark.asyncio
async def test_fix_syntax_error_success(monkeypatch):
    mock_provider = MockProvider()
    mock_provider.set_tool_response(
        "write_file", {"path": "broken.py", "content": VALID_SOURCE}, "Fixed"
    )

    monkeypatch.setattr("evals.helpers.get_eval_provider", lambda: mock_provider)
    await coding_tasks.test_fix_syntax_error()

    assert len(mock_provider.calls) > 0


@pytest.mark.asyncio
async def test_fix_syntax_error_failure(monkeypatch):
    mock_provider = MockProvider(["Fixed"])

    monkeypatch.setattr("evals.helpers.get_eval_provider", lambda: mock_provider)
    with pytest.raises(AssertionError):
        await coding_tasks.test_fix_syntax_error()
