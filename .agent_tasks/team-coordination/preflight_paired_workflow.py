"""Check each frozen variant on all actual roles, without calling an API."""

import argparse
import hashlib
import json
from pathlib import Path

from evals.helpers import EvalTestRig, MockProvider
import henchman.agents.prompts as prompts


def main(variant: str) -> None:
    root = Path(__file__).resolve().parent
    path = root / f"workflow-prompts-{variant}.json"
    raw = path.read_bytes()
    frozen = json.loads(raw)
    for name, value in frozen.items():
        setattr(prompts, name, value)
    rig = EvalTestRig(provider=MockProvider(), profile="team")
    try:
        rig.setup("paired-frozen-prompts-preflight")
        roles = rig.orchestrator.pool._agents
        assert set(roles) == set(frozen["ROLE_TEMPLATES"])
        for role, agent in roles.items():
            system = agent.system_prompt
            assert system.count(frozen["ROLE_TEMPLATES"][role]) == 1, role
            for name in ("BASE_IDENTITY", "BASE_RULES", "BASE_CONSTRAINTS"):
                assert system.count(frozen[name]) == 1, (role, name)
            assert "* Working directory: " + str(rig.test_dir.resolve()) in system
            assert system.count("<environment_context>") == 1
        print(json.dumps({"variant": variant, "roles": sorted(roles),
                          "prompt_sha256": hashlib.sha256(raw).hexdigest(),
                          "api_calls": 0, "passed": True}))
    finally:
        rig.cleanup()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", choices=("baseline", "candidate"), required=True)
    main(parser.parse_args().variant)
