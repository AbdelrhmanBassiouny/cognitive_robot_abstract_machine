"""
Time parsing the PR2 URDF and then reading one pose under each world modification
policy, with eager and lazy recompilation.

Run with ``python benchmark_urdf.py`` with the ROS overlay sourced; prints JSON lines.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time

from semantic_digital_twin.adapters.urdf import URDFParser
from semantic_digital_twin.robots.pr2 import PR2
from semantic_digital_twin.world import (
    WorldModificationPolicy,
    WorldModificationPolicyEnvironmentVariable,
)


def parse_once() -> dict:
    start = time.perf_counter()
    try:
        world = URDFParser.from_file(PR2.get_ros_file_path()).parse()
        world.compute_forward_kinematics_np(
            world.root, world.kinematic_structure_entities[-1]
        )
    except Exception as error:
        return {"error": f"{type(error).__name__}: {error}"[:160]}
    return {
        "seconds": time.perf_counter() - start,
        "bodies": len(world.kinematic_structure_entities),
        "committed_blocks": world.get_world_model_manager().committed_block_count,
    }


if __name__ == "__main__":
    if len(sys.argv) > 1:
        print(json.dumps(parse_once()))
        sys.exit(0)
    for lazy in ("", "1"):
        for policy in WorldModificationPolicy:
            environment = dict(os.environ)
            environment[WorldModificationPolicyEnvironmentVariable.POLICY] = policy
            environment[WorldModificationPolicyEnvironmentVariable.LAZY_COMPILATION] = (
                lazy
            )
            output = (
                subprocess.run(
                    [sys.executable, __file__, "child"],
                    env=environment,
                    capture_output=True,
                    text=True,
                )
                .stdout.strip()
                .splitlines()
            )
            result = json.loads(output[-1]) if output else {"error": "no output"}
            print(json.dumps({"policy": policy, "lazy": lazy == "1", **result}))
