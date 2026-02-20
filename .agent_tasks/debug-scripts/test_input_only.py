#!/usr/bin/env python3
"""Minimal test for Textual Input widget visibility."""

from textual.app import App, ComposeResult
from textual.widgets import Input, Header, Footer

class InputTestApp(App):
    """Minimal app to test Input widget."""
    
    CSS = """
    Screen {
        layout: vertical;
    }
    
    #input {
        width: 1fr;
        border: solid cyan;
        margin: 1;
    }
    """
    
    def compose(self) -> ComposeResult:
        yield Header()
        yield Input(id="input", placeholder="Type here and you should see text as you type...")
        yield Footer()
    
    def on_mount(self) -> None:
        self.query_one("#input", Input).focus()

if __name__ == "__main__":
    print("Testing Textual Input widget visibility...")
    print("You should see text appear as you type.")
    print("If not, there's a Textual configuration issue.")
    print("\nPress Ctrl+C to exit.")
    app = InputTestApp()
    app.run()