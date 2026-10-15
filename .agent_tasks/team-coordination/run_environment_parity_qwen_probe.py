"""One bounded live probe; load the user's key in memory, never into an artifact."""
from __future__ import annotations

import asyncio
import json
import os
import re
import shlex
import shutil
import time
from contextlib import aclosing
from contextvars import ContextVar
from pathlib import Path

from evals.helpers import EvalTestRig
from evals.run_team import _environment, _close_clients, _redact, _secrets, _write_report
from evals.test_team_python_workflow import _PROMPT, run_team_python_workflow
from henchman.config.schema import Settings
from henchman.providers.factory import create_configured_provider

ROOT = Path(__file__).resolve().parent
REPORT = ROOT / 'environment-parity-qwen-live-report.json'
ARTIFACTS = ROOT / 'environment-parity-qwen-live-artifacts'
MODEL = 'qwen/qwen3-coder-next'
REQUEST_LIMIT = 24
TIMEOUT = 480.0


def load_key() -> None:
    for line in (Path.home() / '.bashrc').read_text().splitlines():
        if re.match(r'^\s*(?:export\s+)?OPENROUTER_API_KEY\s*=', line):
            values = shlex.split(line.split('=', 1)[1].strip(), comments=True)
            if len(values) == 1 and '$' not in values[0] and '`' not in values[0]:
                os.environ['OPENROUTER_API_KEY'] = values[0]
                return
    raise RuntimeError('No literal OpenRouter key was found')


async def main() -> None:
    load_key()
    settings = Settings.model_validate({
        'providers': {'default': 'openrouter', 'openrouter': {
            'api_key': '${OPENROUTER_API_KEY}', 'model': MODEL, 'max_tokens': 8192,
            'stream_options': {'include_usage': True},
            'extra_body': {'provider': {'max_price': {'prompt': 0.5, 'completion': 1.0}}},
        }},
        'context': {'max_tokens': 262144},
        'agents': {'max_delegation_retries': 0, 'max_delegation_turns': 12},
    })
    provider = create_configured_provider(settings.providers)
    provider._client.max_retries = 0
    original_stream = provider.chat_completion_stream
    original_process = provider._process_stream_response
    requests: list[dict] = []
    request_lock = asyncio.Lock()
    active_record: ContextVar[dict | None] = ContextVar('probe_record', default=None)

    original_create = provider._client.chat.completions.create

    async def measured_create(**params):
        body = params.get('extra_body') or {}
        requested = body.get('reasoning')
        if requested is not None:
            raise RuntimeError('Unsupported reasoning option reached Qwen SDK request')
        record = active_record.get()
        if record is None:
            raise RuntimeError('Actual SDK request has no measurement record')
        user_contents = [message.get('content', '') for message in params.get('messages', [])
                         if message.get('role') == 'user' and isinstance(message.get('content'), str)]
        mission = next((content for content in user_contents if '## Mission\n' in content), None)
        record['mission_context'] = {
            'mission_section_present': mission is not None,
            'complete_original_mission_present': mission is not None and ('## Mission\n' + _PROMPT) in mission,
            'original_mission_characters': len(_PROMPT),
        }
        system_contents = [message.get('content', '') for message in params.get('messages', [])
                           if message.get('role') == 'system' and isinstance(message.get('content'), str)]
        record['environment_context'] = {
            'actual_workspace_present': any(('* Working directory: ' + str(rig.test_dir.resolve())) in content for content in system_contents),
            'structured_environment_present': any('<environment_context>' in content for content in system_contents),
        }
        record['sdk_request_options'] = {
            'reasoning': requested, 'model': params.get('model'),
            'max_tokens': params.get('max_tokens'),
        }
        return await original_create(**params)

    provider._client.chat.completions.create = measured_create

    async def measured_response(response):
        record = active_record.get()

        async def observed_chunks():
            async for wire in response:
                if record is not None:
                    usage = getattr(wire, 'usage', None)
                    details = getattr(usage, 'completion_tokens_details', None)
                    count = getattr(details, 'reasoning_tokens', None)
                    if isinstance(count, int) and not isinstance(count, bool):
                        record['reasoning_tokens'] = count
                    for choice in wire.choices:
                        for field in ('content', 'reasoning', 'reasoning_content'):
                            value = getattr(choice.delta, field, None)
                            if isinstance(value, str):
                                record['wire_chars'][field] += len(value)
                        if getattr(choice.delta, 'reasoning_details', None):
                            record['structured_reasoning_observed'] = True
                yield wire

        async with aclosing(observed_chunks()) as raw:
            async with aclosing(original_process(raw)) as parsed:
                async for chunk in parsed:
                    if record is not None and chunk.thinking:
                        record['retained_reasoning_chars'] += len(chunk.thinking)
                    if record is not None and chunk.tool_calls:
                        record['requested_calls'].extend(
                            {'id': call.id, 'name': call.name} for call in chunk.tool_calls
                        )
                    yield chunk

    provider._process_stream_response = measured_response

    async def guarded_stream(messages, tools=None, **kwargs):
        async with request_lock:
            if len(requests) >= REQUEST_LIMIT:
                raise RuntimeError('Live probe global request limit reached')
            estimated = provider.estimate_input_tokens(messages, tools)
            if estimated > 65536:
                raise RuntimeError('Live probe estimated input limit exceeded')
            record = {'index': len(requests) + 1, 'estimated_input_tokens': estimated,
                      'messages': len(messages), 'tools': len(tools or []), 'usage': None,
                      'wire_chars': {'content': 0, 'reasoning': 0, 'reasoning_content': 0},
                      'retained_reasoning_chars': 0,
                      'outbound_reasoning_chars': sum(len(m.reasoning_content or '') for m in messages),
                      'requested_calls': [],
                      'structured_reasoning_observed': False}
            requests.append(record)
        print(json.dumps({'request_started': record['index'], 'input_estimate': estimated,
                          'tools': record['tools']}), flush=True)
        started = time.perf_counter()
        token = active_record.set(record)
        try:
            async with aclosing(original_stream(messages, tools, **kwargs)) as stream:
                async for chunk in stream:
                    if chunk.usage is not None:
                        record['usage'] = dict(chunk.usage)
                    if chunk.finish_reason is not None:
                        record['finish_reason'] = chunk.finish_reason.value
                    yield chunk
        finally:
            active_record.reset(token)
            record['duration_seconds'] = round(time.perf_counter() - started, 3)
            print(json.dumps({'request_finished': record['index'],
                              'finish_reason': record.get('finish_reason'),
                              'duration_seconds': record['duration_seconds']}), flush=True)

    provider.chat_completion_stream = guarded_stream
    rig = EvalTestRig(provider=provider, profile='team', settings=settings)
    report: dict = {'environment': _environment(), 'model': MODEL, 'request_limit': REQUEST_LIMIT, 'timeout': TIMEOUT,
                    'context_window': 262144, 'input_estimate_guard': 65536, 'output_tokens': 8192,
                    'sdk_retries': 0, 'requests': requests, 'task_verified': False,
                    'pricing_source': 'https://openrouter.ai/api/v1/models',
                    'pricing_snapshot_per_million': {'input': 0.12, 'output': 0.8},
                    'change': 'Align team evaluation environment with actual CLI workspace snapshot and authoritative tool observations; task VERSION3, role workflow guidance, model/context/request/deadline/call/round/output bounds unchanged; actual SDK observes workspace presence without retaining system messages',
                    'baseline_report': 'retry-lint-qwen-live-report.json', 'preceding_unavailable_route': 'qwen-coder-live-report.json'}
    try:
        rig.setup('live-qwen-coder-team-python')
        result = await run_team_python_workflow(rig, max_iterations=12, timeout=TIMEOUT)
        report.update(result=result, profile=rig.profile_metadata, success=result['success'])
        report['tool_evidence'] = [
            {'actor': log.source_agent, 'id': log.tool_call_id, 'name': log.tool_name,
             'arguments': {key: value for key, value in log.arguments.items()
                           if key not in {'content', 'code'}},
             'success': log.success, 'result': log.result[:2048],
             'request_index': log.request_index, 'result_index': log.result_index}
            for log in rig.get_all_tool_calls()
        ]
        ARTIFACTS.mkdir(parents=True, exist_ok=True)
        for name in ('normalization.py', 'label_index.py', 'label_cli.py', 'test_labels.py', 'pyproject.toml'):
            source = rig.test_dir / name
            if source.is_file():
                shutil.copyfile(source, ARTIFACTS / name)
    except Exception as exc:
        report.update(success=False, error={'type': type(exc).__name__, 'message': str(exc)})
    finally:
        clients = [provider, *rig.providers]
        errors = await _close_clients(clients)
        rig.cleanup()
        if errors:
            report.update(success=False, cleanup_errors=errors)
        report['usage_complete'] = bool(requests) and all(row['usage'] is not None for row in requests)
        report['reasoning_observation'] = {
            'requested': None,
            'sdk_requests_verified': sum('sdk_request_options' in row for row in requests),
            'wire_reasoning_chars': sum(row['wire_chars']['reasoning'] + row['wire_chars']['reasoning_content'] for row in requests),
            'structured_reasoning_observed': any(row['structured_reasoning_observed'] for row in requests),
            'usage_reasoning_complete': bool(requests) and all(isinstance(row.get('reasoning_tokens'), int) for row in requests),
            'observed_usage_reasoning_tokens': sum(row.get('reasoning_tokens') or 0 for row in requests),
        }
        if report['usage_complete']:
            input_tokens = sum(row['usage'].get('prompt_tokens', 0) for row in requests)
            output_tokens = sum(row['usage'].get('completion_tokens', 0) for row in requests)
            report['observed_usage'] = {'prompt_tokens': input_tokens, 'completion_tokens': output_tokens}
            report['estimated_uncached_cost_usd'] = (input_tokens * 0.12 + output_tokens * 0.8) / 1_000_000
        _write_report(REPORT, _redact(report, _secrets(settings)))
        print(json.dumps({'report': str(REPORT), 'success': report.get('success'),
                          'requests': len(requests), 'usage_complete': report['usage_complete']}), flush=True)


if __name__ == '__main__':
    asyncio.run(main())
