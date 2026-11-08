"""Prepare one actual, fixed-query retrieval result before model dispatch."""
from __future__ import annotations

import hashlib
import json
import time

import contract as c
import fixtures
from henchman.tools.base import ToolResult


class RetrievalDenied(c.Denied):
    """Keep failed preparation evidence while refusing provider dispatch."""

    def __init__(self, receipt):
        self.receipt = receipt
        super().__init__('Retrieval preparation refused: ' + receipt['reason'])


def finalize_verification(plans, plan_id, expected_run, *, correlated):
    """Recheck current declared inputs after all owned cleanup has joined."""
    try:
        status = plans.verification_status(plan_id)
    except Exception as error:
        return {'current': False, 'error_type': type(error).__name__}
    current = (correlated is True and isinstance(expected_run, str) and bool(expected_run)
               and isinstance(status, dict) and status.get('run_id') == expected_run
               and status.get('current_checks_passed') is True)
    return {'current': current, 'status': status}


async def prepare_retrieval(registry, case, arm):
    if case not in fixtures.CASES or arm not in ('baseline', 'repository'):
        raise c.Denied('Unknown fixed fixture or comparison arm')
    args = {'description': fixtures.spec(case)['query'], 'path': '.', 'top_k': 5,
            'strategy': 'combined' if arm == 'baseline' else 'repository'}
    started = time.monotonic()
    receipt = {'arguments': args, 'status': 'failed', 'reason': 'invalid_response'}
    try:
        response = await registry.execute('pattern_search', args)
    except Exception as error:
        receipt.update(reason='dispatch_error', error_type=type(error).__name__,
                       elapsed_seconds=time.monotonic() - started)
        raise RetrievalDenied(receipt) from None
    receipt['elapsed_seconds'] = time.monotonic() - started
    if not isinstance(response, ToolResult) or not isinstance(response.content, str):
        raise RetrievalDenied(receipt)
    content = response.content.encode('utf-8')
    receipt['content_sha256'] = hashlib.sha256(content).hexdigest()
    receipt['content_bytes'] = len(content)
    if len(content) > c.RAW_LIMIT:
        receipt['reason'] = 'result_too_large'
        raise RetrievalDenied(receipt)
    receipt['content'] = response.content
    receipt['success'] = response.success
    receipt['structured'] = response.structured_content if response.structured_content_present else None
    if not response.success:
        receipt['reason'] = 'tool_failure'
        raise RetrievalDenied(receipt)
    if arm == 'repository':
        report = receipt['structured']
        try:
            if not isinstance(report, dict) or json.loads(response.content) != report:
                raise ValueError('structured response mismatch')
            if report.get('kind') != 'repository_evidence' or report.get('complete') is not True:
                receipt['reason'] = 'partial_or_invalid_report'
                raise RetrievalDenied(receipt)
        except (ValueError, TypeError):
            receipt['reason'] = 'malformed_report'
            raise RetrievalDenied(receipt) from None
    receipt['status'] = 'complete'
    receipt.pop('reason')
    return receipt
