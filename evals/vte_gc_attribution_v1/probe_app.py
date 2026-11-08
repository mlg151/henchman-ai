"""Outside-checkout bounded timeline instrumentation; production sources unchanged."""
from __future__ import annotations

import asyncio
import cProfile
import functools
import gc
import re
import json
import os
import sys
import threading
import time
import weakref
from pathlib import Path

from tests.cli.ui_scenarios import InteractionApp, populate_history
from henchman.cli.textual_widgets import ChatPane
from textual import events
from textual.screen import Screen
from textual.drivers.linux_driver import LinuxDriver, XTermParser

root = Path(sys.argv[1])
history_count = int(sys.argv[2]) if len(sys.argv) > 2 else 40
trace: list[dict] = []
phase = 'startup'
active = False
profile = cProfile.Profile() if os.environ.get('DIAGNOSTIC_PROFILE') == 'yes' else None
profile_running = False
history_refs = []


def living_history():
    return sum(reference() is not None for reference in history_refs)


def mark(name, **data):
    if active and len(trace) < 100000:
        trace.append({'ns': time.monotonic_ns(), 'name': name, 'phase': phase,
                      'thread': threading.current_thread().name, **data})


def timed(cls, name):
    original = getattr(cls, name)
    @functools.wraps(original)
    def wrapped(self, *args, **kwargs):
        started = time.monotonic_ns()
        try:
            return original(self, *args, **kwargs)
        finally:
            ended = time.monotonic_ns()
            if active:
                mark(name, start_ns=started, duration_ms=(ended-started)/1e6,
                     layout=bool(getattr(self, '_layout_required', False)))
    setattr(cls, name, wrapped)


for method in ('_refresh_layout', '_compositor_refresh', '_on_timer_update'):
    timed(Screen, method)

gc_started = {}
def gc_trace(stage, info):
    generation = info['generation']
    if stage == 'start':
        gc_started[generation] = (time.monotonic_ns(), living_history() if generation == 2 and active else None)
    else:
        start, before = gc_started.pop(generation, (time.monotonic_ns(), None))
        after = living_history() if before is not None else None
        mark('gc', generation=generation, start_ns=start, duration_ms=(time.monotonic_ns()-start)/1e6,
             history_alive_before=before, history_alive_after=after,
             collected=info['collected'], uncollectable=info['uncollectable'])
gc.callbacks.append(gc_trace)

original_feed = XTermParser.feed
@functools.wraps(original_feed)
def traced_feed(self, data):
    if data in ('\x1b', '\r'):
        mark('parser-bytes', value=repr(data))
    yield from original_feed(self, data)
XTermParser.feed = traced_feed

original_message = LinuxDriver.process_message
@functools.wraps(original_message)
def traced_message(self, message):
    if isinstance(message, events.Key):
        mark('driver-key', key=message.key)
    return original_message(self, message)
LinuxDriver.process_message = traced_message

original_write = LinuxDriver.write
@functools.wraps(original_write)
def traced_write(self, data):
    plain = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', data)
    mark('driver-write', size=len(data), cancelling='Cancelling' in plain)
    return original_write(self, data)
LinuxDriver.write = traced_write


class NativeProbe(InteractionApp):
    def on_mount(self) -> None:
        super().on_mount()
        chat = self.query_one(ChatPane)
        if history_count == 40:
            populate_history(chat)
        else:
            for number in range(history_count):
                history_refs.append(weakref.ref(chat.add_user_message(f'History {number}: ' + 'readable text ' * 8)))
        self.set_timer(180, self.exit)
        self.call_after_refresh(self.ready)

    def ready(self) -> None:
        global active
        from textual.widgets import TextArea
        area = self.query_one(TextArea)
        bar = self.query_one('#status-bar')
        (root / 'app-ready.json').write_text(json.dumps({
            'input_region': list(area.region), 'status_region': list(bar.region),
            'size': list(self.size), 'monotonic_ns': time.monotonic_ns(),
        }))
        active = True
        mark('ready', history_widgets_alive=living_history())

    def action_cancel_or_clear(self) -> None:
        mark('cancel-handler-enter')
        super().action_cancel_or_clear()
        mark('cancel-handler-exit')
        self.call_after_refresh(self.cancel_painted)

    def cancel_painted(self) -> None:
        global profile_running
        mark('cancel-after-refresh')
        if profile_running:
            profile.disable()
            profile_running = False
            profile.dump_stats(str(root / 'cancel-profile.pstats'))

    def submitted_painted(self, value):
        mark('submit-after-refresh', input=value)
        (root / 'worker-painted.json').write_text(json.dumps({'input': value}))

    async def _route_input(self, user_input: str, chat: ChatPane) -> None:
        global phase, profile_running
        phase = user_input
        self.submitted.append(user_input)
        mark('worker-ready', input=user_input)
        if profile is not None and user_input == 'probe1':
            profile.enable()
            profile_running = True
        (root / 'worker-ready.json').write_text(json.dumps({'input': user_input}))
        self.call_after_refresh(self.submitted_painted, user_input)
        try:
            await asyncio.Event().wait()
        finally:
            mark('worker-cancelling')
            (root / 'worker-cancelling.json').write_text(json.dumps({'monotonic_ns': time.monotonic_ns()}))
            await asyncio.sleep(1)
            mark('worker-finished')
            (root / 'app-timeline.json').write_text(json.dumps(trace, indent=2) + '\n')
            (root / 'worker-finished.json').write_text(json.dumps({'input': user_input}))


try:
    NativeProbe(root).run()
finally:
    if profile_running:
        profile.disable()
        profile.dump_stats(str(root / 'cancel-profile-incomplete.pstats'))
    (root / 'app-timeline.json').write_text(json.dumps(trace, indent=2) + '\n')
