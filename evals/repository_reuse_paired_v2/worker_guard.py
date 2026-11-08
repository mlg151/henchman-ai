"""Exact fixture and tool guard; never a filesystem sandbox."""
from __future__ import annotations

import json
import os
from pathlib import Path

import fixtures
from henchman.tools.base import ToolResult
from henchman.tools.builtins.file_edit import EditFileTool
from henchman.tools.builtins.file_read import ReadFileTool
from henchman.tools.builtins.file_write import WriteFileTool
from henchman.tools.builtins.pattern_search import PatternSearchTool
from henchman.tools.builtins.tier6_tools import VerifyPlanExecutionTool
from henchman.utils.retry import RetryConfig


def allowed_subprocess(argv, cwd, root, case, checker, executable):
    """Allow only fixed verifier/formatter or explicit read-only Git queries."""
    try:
        if not isinstance(argv, (list, tuple)):
            return False
        if any(not isinstance(part, str) for part in argv):
            return False
        args = list(argv)
        spec = fixtures.spec(case)
        paths = {*spec['protected'], spec['target']}
        current = Path(cwd or os.getcwd())
        black = [executable, '-I', '-m', 'black', '--quiet', '--workers', '1', '--safe', '--', str(root / spec['target'])]
        if args == black and current in (root, (root / spec['target']).parent):
            return True
        if current != root:
            return False
        if args == [executable, '-B', str(checker), case]:
            return True
        if args == ['uname', '-p']:
            return True
        ignore_prefix = ['git', '-c', 'core.fsmonitor=false', '-C', str(root), 'check-ignore', '--no-index', '-q', '--']
        if args[:len(ignore_prefix)] == ignore_prefix:
            return len(args) == len(ignore_prefix) + 1 and args[-1] in paths
        prefix = ['git', '--literal-pathspecs']
        if args[:len(prefix)] != prefix:
            return False
        remainder = args[len(prefix):]
        if remainder[:2] == ['-c', 'core.fsmonitor=false']:
            remainder = remainder[2:]
        fixed = (
            ['rev-parse', '--verify', '--quiet', 'HEAD'],
            ['symbolic-ref', '--quiet', 'HEAD'],
            ['show-ref', '--verify', '--quiet', 'refs/heads/reuse-eval'],
            ['ls-files', '-z', '--cached'],
            ['ls-files', '-z', '--others', '--exclude-standard'],
            ['ls-files', '-z', '--cached', '--ignored', '--exclude-standard'],
        )
        if remainder in fixed:
            return True
        return (len(remainder) == 4 and remainder[:3] == ['ls-files', '--error-unmatch', '--']
                and remainder[3] in paths)
    except (OSError, TypeError, ValueError):
        return False


def bind_guard(registry, root, case, plan_id, denials, searches):
    spec = fixtures.spec(case)
    allowed_types = (ReadFileTool, WriteFileTool, EditFileTool, PatternSearchTool, VerifyPlanExecutionTool)
    identities = {tool.name: (tool, getattr(tool.execute, '__func__', None))
                  for tool in registry._tools.values()}
    allowed_reads = {root / path for path in (*spec['protected'], spec['target'])}
    allowed_reads.add(root / '.henchman/plans/verification.json')
    target = root / spec['target']

    def protected_intact():
        try:
            for relative, expected in spec['protected'].items():
                path = root / relative
                if (path.is_symlink() or path.resolve() != path or not path.is_file()
                    or path.stat().st_nlink != 1 or path.stat().st_size > 8192
                    or path.read_bytes() != expected.encode()):
                    return False
            return True
        except OSError:
            return False

    def guard(tool, params):
        reason = None
        try:
            if (Path.cwd() != root or type(tool) not in allowed_types
                or identities.get(tool.name) != (tool, getattr(tool.execute, '__func__', None))):
                reason = 'Tool or working directory escaped the fixed comparison'
            elif len(json.dumps(params, allow_nan=False).encode()) > 16384:
                reason = 'Tool arguments exceed the comparison bound'
            elif not protected_intact():
                reason = 'Protected fixture bytes or identities changed'
            elif type(tool) is VerifyPlanExecutionTool:
                if params != {'action': 'verify', 'plan_id': plan_id}:
                    reason = 'Only the held verifier invocation is available'
            elif type(tool) is PatternSearchTool:
                description, path = params.get('description'), params.get('path', '.')
                top_k, strategy = params.get('top_k', 10), params.get('strategy', 'combined')
                if (not isinstance(description, str) or not 1 <= len(description) <= 4096
                    or path != '.' or type(top_k) is not int or not 1 <= top_k <= 20
                    or strategy not in ('combined', 'repository', 'semantic', 'structural')
                    or not set(params) <= {'description', 'path', 'top_k', 'strategy'}):
                    reason = 'Search parameters escaped the fixed project bound'
                else:
                    searches.append({'description': description, 'path': path,
                                     'top_k': top_k, 'strategy': strategy})
            else:
                raw = params.get('path')
                if (not isinstance(raw, str) or not raw or '\x00' in raw
                    or '\\' in raw or raw.startswith('~') or '..' in Path(raw).parts):
                    reason = 'An explicit fixture path is required'
                else:
                    candidate = Path(raw)
                    path = candidate if candidate.is_absolute() else root / candidate
                    paths = allowed_reads if type(tool) is ReadFileTool else {target}
                    if (path not in paths or path.resolve(strict=True) != path or path.is_symlink()
                        or not path.is_file() or path.stat().st_nlink != 1 or path.stat().st_size > 65536):
                        reason = 'Path is outside the held fixture scope'
        except (OSError, ValueError, TypeError, OverflowError):
            reason = 'Fixture or tool parameters could not be validated'
        if reason:
            denials.append(reason)
            return ToolResult(content=reason, success=False, error=reason)
        return None

    registry.bind_execution_guard(guard)
    registry.set_retry_config(RetryConfig(max_retries=0))

    async def confirm(_request):
        return True

    registry.set_confirmation_handler(confirm)
    return guard
