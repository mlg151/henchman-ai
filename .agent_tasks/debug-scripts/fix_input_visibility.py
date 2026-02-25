#!/usr/bin/env python3
"""Fix for Textual Input visibility issue."""

from textual.app import App, ComposeResult
from textual.widgets import Footer, Header, Input, Static


class FixedInputTest(App):
    """Test app with fixed Input styling."""

    CSS = """
    Screen {
        background: $surface;
        color: $text;
    }
    
    #main {
        height: 1fr;
        padding: 1;
    }
    
    #input {
        width: 100%;
        height: 3;
        border: solid $primary;
        background: $panel;
        color: $text;
    }
    
    #status {
        height: 1;
        margin-top: 1;
        color: $text-muted;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Type in the box below - text should appear as you type:", id="main")
        yield Input(
            id="input",
            placeholder="Type here and text should appear immediately...",
        )
        yield Static("Status: Ready", id="status")
        yield Footer()

    def on_mount(self) -> None:
        input_widget = self.query_one("#input", Input)
        input_widget.focus()
        print("Input widget focused. Type something - you should see text appear.")

    def on_input_changed(self, event: Input.Changed) -> None:
        """Called when input text changes."""
        status = self.query_one("#status", Static)
        status.update(f"Status: Typing - '{event.value}'")

if __name__ == "__main__":
    print("=== Testing Input Visibility Fix ===")
    print("If text appears as you type, the fix works.")
    print("If not, there's a deeper Textual issue.")
    app = FixedInputTest()
    app.run()
