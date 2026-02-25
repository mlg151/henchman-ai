#!/usr/bin/env python3
"""Minimal test for Textual Input - simplest possible."""

from textual.app import App
from textual.widgets import Input


class AbsoluteMinimalInput(App):
    def compose(self):
        yield Input(placeholder="Type here...")

    def on_mount(self):
        self.query_one(Input).focus()

if __name__ == "__main__":
    print("Launching minimal Input test...")
    print("If you can't see text as you type, Textual has a terminal issue.")
    AbsoluteMinimalInput().run()
