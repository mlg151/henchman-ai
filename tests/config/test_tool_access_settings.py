"""Explicit empty roots remain denial settings through normal configuration."""

import pytest
from pydantic import ValidationError

from henchman.config.schema import Settings


def test_tool_access_defaults_and_explicit_empty_roots():
    defaults = Settings().tools
    assert defaults.filesystem_read_roots is None
    assert defaults.filesystem_write_roots is None
    assert defaults.network_access == "unrestricted"
    settings = Settings(tools={
        "filesystem_read_roots": ["."], "filesystem_write_roots": [], "network_access": "disabled",
    })
    assert settings.tools.model_dump(exclude_unset=True) == {
        "filesystem_read_roots": ["."], "filesystem_write_roots": [], "network_access": "disabled",
    }


@pytest.mark.parametrize("value", ["all", [""], ["   "], [1]])
@pytest.mark.parametrize("field", ["filesystem_read_roots", "filesystem_write_roots"])
def test_invalid_root_lists_are_rejected(field, value):
    with pytest.raises(ValidationError):
        Settings(tools={field: value})


def test_unknown_network_mode_is_not_silently_unrestricted():
    with pytest.raises(ValidationError):
        Settings(tools={"network_access": "allow"})
