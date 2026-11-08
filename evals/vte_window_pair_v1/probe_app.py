"""Production Textual controls with deterministic service-free work."""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

from tests.cli.ui_scenarios import InteractionApp, populate_history
from henchman.cli.textual_widgets import ChatPane

root = Path(sys.argv[1])
history_count = int(sys.argv[2]) if len(sys.argv) > 2 else 40


class NativeProbe(InteractionApp):
    def on_mount(self) -> None:
        super().on_mount()
        chat = self.query_one(ChatPane)
        if history_count == 40:
            populate_history(chat)
        else:
            for number in range(history_count):
                chat.add_user_message(f'History {number}: ' + 'readable text ' * 8)
        self.set_timer(180, self.exit)
        self.call_after_refresh(self.ready)

    def ready(self) -> None:
        from textual.widgets import TextArea
        area = self.query_one(TextArea)
        bar = self.query_one('#status-bar')
        (root / 'app-ready.json').write_text(json.dumps({
            'input_region': list(area.region), 'status_region': list(bar.region),
            'size': list(self.size), 'monotonic_ns': time.monotonic_ns(),
        }))

    async def _route_input(self, user_input: str, chat: ChatPane) -> None:
        self.submitted.append(user_input)
        (root / 'worker-ready.json').write_text(json.dumps({'input': user_input}))
        try:
            await asyncio.Event().wait()
        finally:
            (root / 'worker-cancelling.json').write_text(json.dumps({'monotonic_ns': time.monotonic_ns()}))
            await asyncio.sleep(1)
            (root / 'worker-finished.json').write_text(json.dumps({'input': user_input}))


NativeProbe(root).run()
