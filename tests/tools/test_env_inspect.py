"""Tests for env_inspect tool."""

import sys

from henchman.tools.base import ToolKind
from henchman.tools.builtins.env_inspect import EnvInspectTool


class TestEnvInspectTool:
    """Tests for EnvInspectTool."""

    def test_name(self) -> None:
        """Tool has correct name."""
        tool = EnvInspectTool()
        assert tool.name == "env_inspect"

    def test_description(self) -> None:
        """Tool has a description."""
        tool = EnvInspectTool()
        assert len(tool.description) > 10

    def test_kind_is_read(self) -> None:
        """Tool is READ kind."""
        tool = EnvInspectTool()
        assert tool.kind == ToolKind.READ

    def test_parameters_schema(self) -> None:
        """Tool has correct parameters schema."""
        tool = EnvInspectTool()
        params = tool.parameters
        assert "properties" in params

    async def test_basic_info(self) -> None:
        """Show basic Python environment info."""
        tool = EnvInspectTool()
        result = await tool.execute()
        assert result.success is True
        assert "Python Environment:" in result.content
        assert sys.version.split()[0] in result.content

    async def test_package_versions(self) -> None:
        """Check specific package versions."""
        tool = EnvInspectTool()
        result = await tool.execute(packages=["pip", "nonexistent_pkg_xyz"])
        assert result.success is True
        assert "pip:" in result.content
        assert "not installed" in result.content

    async def test_show_path(self) -> None:
        """Show sys.path."""
        tool = EnvInspectTool()
        result = await tool.execute(show_path=True)
        assert result.success is True
        assert "sys.path:" in result.content

    async def test_show_env_vars(self) -> None:
        """Show filtered environment variables."""
        tool = EnvInspectTool()
        result = await tool.execute(show_env_vars=True)
        assert result.success is True
        assert "Environment Variables" in result.content

    async def test_project_detection(self) -> None:
        """Detect project type from cwd."""
        tool = EnvInspectTool()
        result = await tool.execute()
        assert result.success is True
        assert "Project" in result.content

    async def test_custom_cwd(self) -> None:
        """Use custom working directory."""
        import tempfile

        tool = EnvInspectTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            result = await tool.execute(cwd=tmpdir)
            assert result.success is True

    def test_secret_filtering(self) -> None:
        """Secret env vars are filtered out."""
        tool = EnvInspectTool()
        safe = tool._get_safe_env_vars()
        for key in safe:
            upper = key.upper()
            assert "SECRET" not in upper or "SECRET" in upper  # Always true, just validates call
        # Check no SECRET/TOKEN/PASSWORD keys
        for key in safe:
            upper = key.upper()
            # None of the secret patterns should appear
            for pattern in ["SECRET", "TOKEN", "PASSWORD", "CREDENTIAL"]:
                assert pattern not in upper

    def test_detect_project_empty_dir(self) -> None:
        """Empty directory has no project indicators."""
        import tempfile
        from pathlib import Path

        tool = EnvInspectTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            indicators = tool._detect_project(Path(tmpdir))
            assert indicators == []

    def test_get_package_version(self) -> None:
        """Test _get_package_version helper."""
        tool = EnvInspectTool()
        assert tool._get_package_version("pip") != "not installed"
        assert tool._get_package_version("nonexistent_pkg_xyz") == "not installed"

    async def test_with_virtualenv(self) -> None:
        """Reports virtual environment when VIRTUAL_ENV is set."""
        import os
        from unittest.mock import patch

        tool = EnvInspectTool()
        env = {**os.environ, "VIRTUAL_ENV": "/path/to/venv", "CONDA_DEFAULT_ENV": ""}
        with patch.dict(os.environ, env, clear=True):
            result = await tool.execute()
            assert result.success is True
            assert "/path/to/venv" in result.content

    async def test_with_conda_env(self) -> None:
        """Reports conda environment when CONDA_DEFAULT_ENV is set."""
        import os
        from unittest.mock import patch

        tool = EnvInspectTool()
        env = {k: v for k, v in os.environ.items() if k not in ("VIRTUAL_ENV", "CONDA_DEFAULT_ENV")}
        env["CONDA_DEFAULT_ENV"] = "myenv"
        env.pop("VIRTUAL_ENV", None)
        with patch.dict(os.environ, env, clear=True):
            result = await tool.execute()
            assert result.success is True
            assert "myenv" in result.content

    async def test_no_venv_no_conda(self) -> None:
        """Reports none when neither VIRTUAL_ENV nor CONDA_DEFAULT_ENV is set."""
        import os
        from unittest.mock import patch

        from henchman.tools.builtins.env_inspect import EnvInspectTool

        tool = EnvInspectTool()
        env = {k: v for k, v in os.environ.items() if k not in ("VIRTUAL_ENV", "CONDA_DEFAULT_ENV")}
        with patch.dict(os.environ, env, clear=True):
            result = await tool.execute()
            assert result.success is True
            assert "(none)" in result.content

    async def test_show_path_includes_entries(self) -> None:
        """show_path=True skips empty strings in sys.path (143->142 branch)."""
        import sys
        from unittest.mock import patch

        from henchman.tools.builtins.env_inspect import EnvInspectTool

        tool = EnvInspectTool()
        # Include empty string in sys.path to trigger 143->142 (if p: False branch)
        with patch.object(sys, "path", ["", "/some/real/path"]):
            result = await tool.execute(show_path=True)
        assert result.success is True
        assert "sys.path" in result.content
        assert "/some/real/path" in result.content

    async def test_show_env_vars_empty_safe_vars(self) -> None:
        """show_env_vars=True shows (none) when no safe vars exist."""
        from unittest.mock import patch

        from henchman.tools.builtins.env_inspect import EnvInspectTool

        tool = EnvInspectTool()
        # Patch _get_safe_env_vars to return empty dict
        with patch.object(tool, "_get_safe_env_vars", return_value={}):
            result = await tool.execute(show_env_vars=True)
            assert result.success is True
            assert "(none)" in result.content
