"""Python quality findings must describe real source and honest scan coverage."""

import json

import pytest

from henchman.tools.builtins.python_ast import PythonAstTool

BODY = '''    values = []
    for item in items:
        cleaned = item.strip()
        if cleaned:
            values.append(cleaned.casefold())
    return values
'''


async def quality(path, **kwargs):
    result = await PythonAstTool().execute(path=str(path), action="quality", **kwargs)
    assert result.content.startswith("{"), result.content
    return result, json.loads(result.content)


async def test_duplicate_reports_both_locations_and_qualified_method(tmp_path):
    (tmp_path / "a.py").write_text("def normalize(items):\n" + BODY)
    (tmp_path / "b.py").write_text("class Adapter:\n    def clean(items):\n" + "".join(
        "    " + line for line in BODY.splitlines(keepends=True)
    ))
    result, report = await quality(tmp_path)
    assert result.success
    assert report["complete"]
    assert report["files_analyzed"] == 2
    clones = [f for f in report["findings"] if f["smell_type"] == "Duplicate Code"]
    assert len(clones) == 1
    assert clones[0]["symbol_name"] == "Adapter.clean"
    assert clones[0]["line"] == 2
    assert clones[0]["file"].endswith("b.py")
    assert "a.py" in clones[0]["message"]
    assert "normalize" in clones[0]["message"]


async def test_changed_literal_or_call_is_not_reported_as_duplicate(tmp_path):
    for name, call, value in [("a", "save", "yes"), ("b", "delete", "no")]:
        source = f"def {name}(items):\n" + BODY.replace(
            "values.append(cleaned.casefold())", f"values.append({call}(cleaned, {value!r}))"
        )
        (tmp_path / f"{name}.py").write_text(source)
    result, report = await quality(tmp_path)
    assert result.success
    assert not [f for f in report["findings"] if f["smell_type"] == "Duplicate Code"]


async def test_broken_source_prevents_clean_scan_claim(tmp_path):
    (tmp_path / "broken.py").write_text("def bad(:\n")
    (tmp_path / "valid.py").write_text("def ok():\n    return 1\n")
    result, report = await quality(tmp_path)
    assert not result.success
    assert not report["complete"]
    assert report["files_analyzed"] == 1
    assert any(e["file"].endswith("broken.py") for e in report["errors"])


async def test_pep263_source_is_decoded_without_executing_it(tmp_path):
    source = tmp_path / "encoded.py"
    source.write_bytes(b"# coding: latin-1\nraise RuntimeError('caf\xe9')\n")
    result, report = await quality(source)
    assert result.success
    assert report["files_analyzed"] == 1


async def test_dependency_directories_are_pruned_before_parsing(tmp_path):
    (tmp_path / "main.py").write_text("value = 1\n")
    for name in [".venv", "node_modules", "__pycache__", ".agent_tasks"]:
        folder = tmp_path / name
        folder.mkdir()
        (folder / "broken.py").write_text("not valid python!!")
    result, report = await quality(tmp_path)
    assert result.success
    assert report["files_analyzed"] == 1
    assert ".venv" in report["excluded_directories"]


async def test_file_budget_reports_partial_scan_instead_of_success(tmp_path):
    for name in ["a", "b"]:
        (tmp_path / f"{name}.py").write_text("value = 1\n")
    result, report = await quality(tmp_path, max_files=1)
    assert not result.success
    assert report["truncated"]
    assert report["files_analyzed"] == 1


async def test_finding_budget_is_explicit(tmp_path):
    for name in ["a", "b", "c"]:
        (tmp_path / f"{name}.py").write_text(f"def {name}(items):\n" + BODY)
    result, report = await quality(tmp_path, max_findings=1)
    assert not result.success
    assert report["truncated"]
    assert len(report["findings"]) == 1


async def test_oversized_source_is_reported_not_silently_skipped(tmp_path):
    source = tmp_path / "large.py"
    source.write_bytes(b"#" + b"x" * (1024 * 1024))
    result, report = await quality(source)
    assert not result.success
    assert report["files_analyzed"] == 0
    assert report["errors"]


@pytest.mark.parametrize("options", [{"max_files": 0}, {"max_files": True}, {"max_findings": -1}])
async def test_invalid_limits_fail_before_scanning(tmp_path, options):
    result = await PythonAstTool().execute(path=str(tmp_path), action="quality", **options)
    assert not result.success
    assert result.error


async def test_unrecognized_action_is_not_silently_ignored(tmp_path):
    path = tmp_path / "valid.py"
    path.write_text("value = 1\n")
    result = await PythonAstTool().execute(path=str(path), action="qualty")
    assert not result.success
    assert "action" in result.error


async def test_runtime_tool_search_exposes_quality_and_registry_executes_it(tmp_path):
    from henchman.cli.tool_manager import ToolManager

    (tmp_path / "a.py").write_text("def first(items):\n" + BODY)
    (tmp_path / "b.py").write_text("def second(items):\n" + BODY)
    manager = ToolManager()
    manager.bind_runtime(project_root=tmp_path)
    manager.register_builtin_tools()
    found = await manager.registry.execute("tool_search", {"query": "python_ast"})
    assert found.success
    assert "quality" in found.content
    result = await manager.registry.execute("python_ast", {"path": str(tmp_path), "action": "quality"})
    assert result.success
    findings = json.loads(result.content)["findings"]
    assert any(f["smell_type"] == "Duplicate Code" for f in findings)
