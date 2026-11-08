"""Textual presentation preferences that do not change execution state."""

from rich.text import Text
from textual.widgets import LoadingIndicator


class StaticLoadingIndicator(LoadingIndicator):
    """Keep loading visibility and input interception without periodic redraws."""

    def on_mount(self) -> None:
        # Textual also invokes the base mount handler, which starts its timer.
        # Stop it after those handlers finish, retaining their normal lifecycle.
        self.call_later(self._stop_decorative_refresh)

    def _stop_decorative_refresh(self) -> None:
        self.auto_refresh = None

    def render(self) -> Text:
        return Text("Loading...")
