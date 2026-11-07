"""UI-0.1 deterministic rendered scenarios without model or persistence I/O."""

from __future__ import annotations

import asyncio
from pathlib import Path

from textual.pilot import Pilot

from henchman.cli import textual_app
from henchman.cli.textual_app import HenchmanTextualApp
from henchman.cli.textual_config import TextualConfig
from henchman.cli.textual_messages import AgentContentMessage
from henchman.cli.textual_mixins import _NullProvider
from henchman.cli.textual_widgets import ChatPane
from henchman.config.schema import Settings

SCENARIO_VERSION = "UI-0.1"
VIEWPORTS = [(80, 24), (120, 40), (160, 50)]


async def settle_layout(pilot: Pilot) -> None:
    """Wait for layout and its deferred viewport callbacks, without timed sleeps.

    Pilot.pause drains messages queued at entry, then requests a frame. A resize
    can schedule a viewport callback in that frame, so observe the next one too.
    """
    for _ in range(2):
        await pilot.pause()
        painted = asyncio.Event()
        pilot.app.call_after_refresh(painted.set)
        await asyncio.wait_for(painted.wait(), timeout=5)


class InteractionApp(HenchmanTextualApp):
    """Keep production layout, events and actions; isolate external services."""

    CSS_PATH = str(Path(textual_app.__file__).with_name("henchman.tcss"))

    def __init__(self, root: Path) -> None:
        super().__init__(
            provider=_NullProvider(), settings=Settings(),
            config=TextualConfig(auto_save=False, history_file=root / "history"),
        )
        self.submitted: list[str] = []

    def _initialize_core_components(self) -> None:
        pass

    def _populate_context_tree(self) -> None:
        pass

    def _show_welcome(self) -> None:
        pass

    def _load_history(self) -> None:
        pass

    def _refresh_workspace_widgets(self) -> None:
        pass

    async def _route_input(self, user_input: str, chat: ChatPane) -> None:
        self.submitted.append(user_input)


class SlowTranscript:
    """Release one deterministic chunk at a time without provider-latency noise."""

    def __init__(self, app: HenchmanTextualApp) -> None:
        self.app = app
        self.ready = asyncio.Event()
        self.pending: asyncio.Queue[tuple[str, str] | None] = asyncio.Queue()

    async def run(self) -> None:
        self.ready.set()
        while (item := await self.pending.get()) is not None:
            self.app.post_message(AgentContentMessage(item[1], source_agent=item[0]))
            self.pending.task_done()

    async def emit(self, source: str, content: str) -> None:
        await self.pending.put((source, content))
        await self.pending.join()


def populate_history(chat: ChatPane) -> None:
    """Use stable Unicode/long-path content large enough to scroll at every width."""
    for number in range(40):
        chat.add_user_message(
            f"History {number}: café /workspace/long-directory-name/module_{number}.py "
            + "readable text " * 8,
        )
