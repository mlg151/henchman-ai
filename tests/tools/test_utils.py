"""Tests for tools/utils.py."""
from __future__ import annotations

from pathlib import Path

from henchman.tools.utils import (
    create_parameter_schema,
    create_path_parameter_schema,
    validate_directory_path,
    validate_file_path,
)


class TestValidateFilePath:
    """Tests for validate_file_path."""

    def test_returns_none_for_valid_file(self, tmp_path: Path) -> None:
        """Returns None for valid file path."""
        f = tmp_path / "test.txt"
        f.write_text("content")
        result = validate_file_path(str(f))
        assert result is None

    def test_returns_error_for_empty_path(self) -> None:
        """Returns ToolResult error for empty path."""
        result = validate_file_path("")
        assert result is not None
        assert result.success is False
        assert "No path" in result.content

    def test_returns_error_for_missing_file(self) -> None:
        """Returns ToolResult error for non-existent file."""
        result = validate_file_path("/nonexistent/path/file.txt")
        assert result is not None
        assert result.success is False
        assert "not found" in result.content


class TestValidateDirectoryPath:
    """Tests for validate_directory_path."""

    def test_returns_none_for_valid_dir(self, tmp_path: Path) -> None:
        """Returns None for valid directory."""
        result = validate_directory_path(str(tmp_path))
        assert result is None

    def test_returns_error_for_empty_path(self) -> None:
        """Returns ToolResult error for empty directory path."""
        result = validate_directory_path("")
        assert result is not None
        assert result.success is False
        assert "No directory" in result.content

    def test_returns_error_for_missing_dir(self) -> None:
        """Returns ToolResult error for non-existent directory."""
        result = validate_directory_path("/nonexistent/dir/path")
        assert result is not None
        assert result.success is False
        assert "not found" in result.content

    def test_returns_error_when_path_is_file(self, tmp_path: Path) -> None:
        """Returns ToolResult error when path is a file, not directory."""
        f = tmp_path / "file.txt"
        f.write_text("content")
        result = validate_directory_path(str(f))
        assert result is not None
        assert result.success is False
        assert "not a directory" in result.content.lower()


class TestCreateParameterSchema:
    """Tests for create_parameter_schema."""

    def test_basic_schema(self) -> None:
        """Creates schema with required params."""
        schema = create_parameter_schema(["name", "value"])
        assert schema["type"] == "object"
        assert "name" in schema["properties"]
        assert "value" in schema["properties"]
        assert schema["required"] == ["name", "value"]

    def test_with_optional_params(self) -> None:
        """Includes optional params in properties."""
        optional = {"count": {"type": "integer", "description": "Count"}}
        schema = create_parameter_schema(["name"], optional_params=optional)
        assert "count" in schema["properties"]
        assert "name" in schema["required"]
        assert "count" not in schema["required"]

    def test_without_optional_params(self) -> None:
        """Works without optional_params."""
        schema = create_parameter_schema(["path"])
        assert "path" in schema["properties"]


class TestCreatePathParameterSchema:
    """Tests for create_path_parameter_schema."""

    def test_default_schema(self) -> None:
        """Creates default path schema."""
        schema = create_path_parameter_schema()
        assert "path" in schema["properties"]
        assert "path" in schema["required"]

    def test_with_additional_params(self) -> None:
        """Includes additional params in schema."""
        additional = {"encoding": {"type": "string", "description": "Encoding"}}
        schema = create_path_parameter_schema(additional_params=additional)
        assert "encoding" in schema["properties"]

    def test_with_custom_required(self) -> None:
        """Respects custom required list."""
        schema = create_path_parameter_schema(required=["path", "encoding"])
        assert "path" in schema["required"]
        assert "encoding" in schema["required"]
