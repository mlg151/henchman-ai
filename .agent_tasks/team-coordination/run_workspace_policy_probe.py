"""Bounded real Explorer behavior check; never persist credentials or reasoning."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import shlex
import time
from contextlib import aclosing
from pathlib import Path

from evals.helpers import EvalTestRig
from evals.run_team import _close_clients, _redact, _secrets, _write_report
from evals.team_runtime import _TeamObservations
from evals.test_python_reuse import _CALLER, _NORMALIZATION
from henchman.cli.headless import run_orchestrator_json
from henchman.config.schema import Settings
from henchman.core.events import EventType
from henchman.providers.factory import create_configured_provider

ROOT = Path(__file__).resolve().parent
MODEL = 'xiaomi/mimo-v2.6-pro'
PROMPT = (
    'Inspect normalization.py and label_index.py. Identify the existing normalizer '
    'and how unique_labels should reuse it, including Unicode, ordering, duplicate '
    'and input-preservation behavior. Return a concise handoff with file paths and '
    'symbols for the engineer. No implementation is requested.'
)


def load_key() -> None:
    for line in (Path.home() / '.bashrc').read_text().splitlines():
        if re.match(r'^\s*(?:export\s+)?OPENROUTER_API_KEY\s*=', line):
            values = shlex.split(line.split('=', 1)[1].strip(), comments=True)
            if len(values) == 1 and '$' not in values[0] and '`' not in values[0]:
                os.environ['OPENROUTER_API_KEY'] = values[0]
                return
    raise RuntimeError('No literal OpenRouter key was found')


async def main(label: str) -> None:
    load_key()
    settings = Settings.model_validate({
        'providers': {'default': 'openrouter', 'openrouter': {
            'api_key': '${OPENROUTER_API_KEY}', 'model': MODEL, 'max_tokens': 4096,
            'stream_options': {'include_usage': True},
            'extra_body': {'provider': {'max_price': {'prompt': 0.5, 'completion': 1.0}}},
        }},
        'context': {'max_tokens': 32768},
        'agents': {'max_delegation_retries': 0},
    })
    provider = create_configured_provider(settings.providers)
    provider._client.max_retries = 0
    original = provider.chat_completion_stream
    requests: list[dict] = []

    async def measured_stream(messages, tools=None, **kwargs):
        if len(requests) >= 8:
            raise RuntimeError('Probe request cap reached')
        row = {'index': len(requests) + 1, 'usage': None}
        requests.append(row)
        started = time.perf_counter()
        try:
            async with aclosing(original(messages, tools, **kwargs)) as stream:
                async for chunk in stream:
                    if chunk.usage is not None:
                        row['usage'] = dict(chunk.usage)
                    yield chunk
        finally:
            row['seconds'] = round(time.perf_counter() - started, 3)
            print(json.dumps({'request': row['index'], 'seconds': row['seconds']}), flush=True)

    provider.chat_completion_stream = measured_stream
    rig = EvalTestRig(provider=provider, profile='team', settings=settings)
    report: dict = {'label': label, 'model': MODEL, 'prompt': PROMPT,
                    'context_window': 32768, 'output_cap': 4096,
                    'max_iterations': 6, 'request_cap': 8, 'timeout': 180,
                    'requests': requests, 'success': False, 'task_verified': False}
    started = time.perf_counter()
    try:
        rig.setup('workspace-policy-probe')
        originals = {'normalization.py': _NORMALIZATION, 'label_index.py': _CALLER}
        for name, content in originals.items():
            rig.create_file(name, content)
        agent = rig.orchestrator.pool.get_agent('explorer')
        agent.base_tool_iterations = 6
        report['prompt_sha256'] = hashlib.sha256(agent.system_prompt.encode()).hexdigest()
        events, logs = [], []
        observation = _TeamObservations(events, logs)
        async with asyncio.timeout(180):
            completed = await run_orchestrator_json(
                rig.orchestrator, PROMPT, observation.record, agent_role='explorer',
            )
        content = ''.join(str(e.data) for e in events if e.type == EventType.CONTENT)
        inspected = all(any(
            log.success and log.tool_name == 'read_file'
            and Path(str(log.arguments.get('path', ''))).name == name
            and symbol in log.result
            for log in logs
        ) for name, symbol in (('normalization.py', 'normalize_label'),
                              ('label_index.py', 'unique_labels')))
        artifacts = [log for log in logs if log.success and log.tool_name in
                     {'write_file', 'edit_file', 'patch_apply', 'research_notes'}]
        unchanged = all(rig.read_file(name) == text for name, text in originals.items())
        report.update(runtime_success=completed, inspected=inspected,
                      source_unchanged=unchanged, artifact_write_calls=len(artifacts),
                      final_response=content[:8192],
                      success=completed and inspected and unchanged and not artifacts,
                      tool_logs=[{'actor': log.source_agent, 'tool': log.tool_name,
                                  'arguments': {key: value for key, value in log.arguments.items()
                                                if key not in {'content', 'code'}},
                                  'success': log.success, 'result': log.result[:2048]}
                                 for log in logs],
                      errors=[str(e.data) for e in events if e.type == EventType.ERROR])
    except Exception as exc:
        report['error'] = {'type': type(exc).__name__, 'message': str(exc)}
    finally:
        errors = await _close_clients([provider, *rig.providers])
        rig.cleanup()
        report['seconds'] = round(time.perf_counter() - started, 3)
        if errors:
            report.update(success=False, cleanup_errors=errors)
        _write_report(ROOT / f'workspace-policy-{label}.json', _redact(report, _secrets(settings)))
        print(json.dumps({'label': label, 'success': report['success'],
                          'requests': len(requests), 'artifact_writes': report.get('artifact_write_calls'),
                          'seconds': report['seconds']}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('label', choices=['before', 'after'])
    asyncio.run(main(parser.parse_args().label))
