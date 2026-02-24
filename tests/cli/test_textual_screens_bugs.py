"""Tests for bugs in textual_screens.py."""

from unittest.mock import MagicMock

from henchman.cli.textual_screens import ConfirmToolScreen
from henchman.tools.base import ConfirmationRequest


def test_bug14_confirm_tool_screen_json_serialization():
    """Bug 14: ConfirmToolScreen._build_params_label has bare except clause.
    
    Severity: Low (code quality)
    Description: Uses bare `except Exception:` instead of catching specific
    JSON serialization errors. Also doesn't handle non-string params well.
    """
    # Create a ConfirmationRequest with non-JSON-serializable params
    class NonSerializable:
        def __str__(self):
            return "<NonSerializable object>"

    request = ConfirmationRequest(
        tool_name="test_tool",
        description="Test tool",
        risk_level="medium",
        params={"key": NonSerializable()},  # Contains non-serializable object
    )

    screen = ConfirmToolScreen(request)

    # This should not crash
    labels = screen._build_params_label()

    # Should return a list with one Label
    assert len(labels) == 1
    # Check it's a Label widget
    from textual.widgets import Label
    assert isinstance(labels[0], Label)

    # The bug: uses bare `except Exception:` instead of `except (TypeError, ValueError):`


def test_bug15_provider_screen_build_options():
    """Bug 15: ProviderScreen._build_options assumes specific structure.
    
    Severity: Medium (potential crashes)
    Description: Assumes settings.providers has specific attributes and
    that cfg is a dict. Could crash with malformed settings.
    """
    from henchman.cli.textual_screens import ProviderScreen

    # Test with None settings
    options = ProviderScreen._build_options(None)
    assert options == [("No providers configured", "none")]

    # Test with empty settings
    settings = MagicMock()
    settings.providers = None
    options = ProviderScreen._build_options(settings)
    assert options == [("No providers configured", "none")]

    # Test with providers but no known providers configured
    settings.providers = MagicMock()
    settings.providers.default = "test"
    # Mock that getattr returns None for known providers
    options = ProviderScreen._build_options(settings)
    assert options == [("No providers configured", "none")]

    # Test with malformed provider config (not a dict)
    settings.providers.deepseek = "not-a-dict"
    options = ProviderScreen._build_options(settings)
    # Should handle non-dict config gracefully
    assert "deepseek" not in str(options)  # Should be filtered out


def test_bug16_help_screen_static_content():
    """Bug 16: HelpScreen has hardcoded keybindings.
    
    Severity: Low (maintenance issue)
    Description: Keybindings are hardcoded in compose() method instead of
    being configurable or derived from app settings.
    """
    from henchman.cli.textual_screens import HelpScreen

    screen = HelpScreen()
    # Can't easily test compose() without Textual framework
    # But we can check that keybindings are hardcoded
    import inspect
    source = inspect.getsource(screen.compose)
    assert "Enter          Submit message" in source
    assert "Ctrl+Q / Ctrl+C    Quit" in source

    # This is a design issue, not necessarily a bug
    # But hardcoded UI strings are harder to maintain and internationalize
