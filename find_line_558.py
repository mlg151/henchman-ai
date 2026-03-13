import sys
sys.path.insert(0, 'src')

from henchman.agents.delegation import DelegationRunner
import inspect

# Get the source code
source = inspect.getsource(DelegationRunner._get_target_agent_with_error_handling)
lines = source.split('\n')
for i, line in enumerate(lines, 1):
    print(f"{i}: {line}")