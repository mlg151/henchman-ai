"""Generated test skeletons compile, collect, and remain explicitly unfinished."""

import ast
import os
import subprocess
import sys
from pathlib import Path
from typing import Literal

import pytest

from henchman.tools.builtins.test_gen import TestGenTool
from henchman.tools.registry import ToolRegistry

SOURCE = '''\
def increment(value, /, *, amount=1):
    raise AssertionError("A generated placeholder called application code")

def current_value():
    raise AssertionError("A generated placeholder called application code")

async def fetch(url):
    raise AssertionError("A generated placeholder called application code")

class Counter:
    def __init__(self):
        raise AssertionError("A generated placeholder instantiated application code")

    def update(self, value):
        raise AssertionError("A generated placeholder called application code")

    async def refresh(self):
        raise AssertionError("A generated placeholder called application code")

class Empty:
    pass
'''


@pytest.mark.asyncio
@pytest.mark.parametrize("style", ["class", "function"])
async def test_rendered_templates_have_no_executable_module_level_assertions(
    tmp_path: Path, style: Literal["class", "function"],
) -> None:
    source = tmp_path / "stub_source.py"
    source.write_text(SOURCE, encoding="utf-8")
    result = await TestGenTool().execute(path=str(source), style=style)

    assert result.success
    tree = ast.parse(result.content)
    compile(tree, "generated_test.py", "exec")
    assert all(isinstance(node, (
        ast.Expr, ast.Import, ast.ImportFrom, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef,
    )) for node in tree.body)
    assert all(not isinstance(node, ast.Expr) or isinstance(node.value, ast.Constant)
               for node in tree.body)
    assert not any(isinstance(node, ast.Assert) for node in ast.walk(tree))
    assert "TODO" in result.content
    assert any(isinstance(node, ast.AsyncFunctionDef) for node in ast.walk(tree))


@pytest.mark.asyncio
@pytest.mark.parametrize("style", ["class", "function"])
async def test_written_templates_format_compile_and_collect_as_unimplemented(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, style: Literal["class", "function"],
) -> None:
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "stub_source.py"
    source.write_text(SOURCE, encoding="utf-8")
    output = tmp_path / "test_generated.py"
    registry = ToolRegistry()
    registry.register(TestGenTool())
    registry.add_auto_approve_policy("test_gen")

    result = await registry.execute(
        "test_gen", {"path": str(source), "output_path": str(output), "style": style},
    )

    assert result.success, result.content
    compile(output.read_text(), str(output), "exec")
    run = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(output)],
        cwd=tmp_path, capture_output=True, text=True, timeout=30, check=False,
        env={**os.environ, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"},
    )
    assert run.returncode == 0, run.stdout + run.stderr
    assert "skipped" in run.stdout
    assert "passed" not in run.stdout and "failed" not in run.stdout
