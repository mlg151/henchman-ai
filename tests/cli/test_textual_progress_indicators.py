"""Tests for progress indicators in textual UI."""

from henchman.cli.textual_app import ProgressIndicator


class TestProgressIndicators:
    """Tests for ProgressIndicator widget."""

    def test_progress_indicator_widget_creation(self):
        """Test that progress indicator widget can be created."""
        indicator = ProgressIndicator()
        assert indicator._message == ""
        assert indicator._kind == ""
        assert indicator.is_visible is False

    def test_progress_shown_during_tool_execution(self):
        """Test that progress indicator shows tool execution message."""
        indicator = ProgressIndicator()
        indicator.show("Running read_file...", kind="tool")
        assert indicator.is_visible is True
        assert indicator._kind == "tool"
        rendered = str(indicator.render())
        assert "🔧" in rendered
        assert "Running read_file" in rendered

    def test_progress_shown_during_agent_work(self):
        """Test that progress indicator shows agent work message."""
        indicator = ProgressIndicator()
        indicator.show("Thinking...", kind="agent")
        assert indicator.is_visible is True
        assert indicator._kind == "agent"
        rendered = str(indicator.render())
        assert "⏳" in rendered
        assert "Thinking" in rendered

    def test_progress_indicator_position(self):
        """Test that progress indicator hides properly."""
        indicator = ProgressIndicator()
        indicator.show("Working...")
        assert indicator.is_visible is True
        indicator.hide()
        assert indicator.is_visible is False
        assert indicator._message == ""
        rendered = str(indicator.render())
        assert rendered == ""
