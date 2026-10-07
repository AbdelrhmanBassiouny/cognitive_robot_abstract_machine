"""
Profile where the time of committing one modification block goes, for worlds of growing
size.

Run with ``python profile_commit.py [sizes...]``; prints a JSON report to stdout.
"""

from __future__ import annotations

import cProfile
import json
import pstats
import sys
import time

from typing_extensions import Dict, List

from benchmark_policies import (
    ConnectionKind,
    attach_body,
    build_chain,
    make_body,
    make_world,
)
from semantic_digital_twin.world import WorldModificationPolicy

# %% components of a commit

COMPONENTS: Dict[str, str] = {
    "forward kinematics compile": "forward_kinematics.py:.*\\(compile\\)",
    "forward kinematics expression cache": "forward_kinematics.py:.*\\(update_root_T_kse_expression_cache\\)",
    "collision forward kinematics compile": "collision_detector.py:.*\\(compile_collision_fks\\)",
    "collision shape rebuild": "collision_detector.py:.*\\(create_shape_from_body\\)",
    "validate": "world.py:.*\\(validate\\)",
    "delete orphaned dofs": "world.py:.*\\(delete_orphaned_dofs\\)",
    "state change notification": "world.py:.*\\(notify_state_change\\)",
    "memoization cache clear": "caching.py:.*\\(clear_memoization_cache\\)",
}


def cumulative_seconds(statistics: pstats.Stats, pattern: str) -> float:
    import re

    total = 0.0
    for (file_name, line, function_name), (
        _,
        _,
        _,
        cumulative,
        _,
    ) in statistics.stats.items():
        if re.search(pattern, f"{file_name}:{line}({function_name})"):
            total += cumulative
    return total


def profile_single_commit(size: int, repetitions: int = 5) -> Dict[str, float]:
    world = make_world(WorldModificationPolicy.EXPLICIT)
    build_chain(world, size, ConnectionKind.REVOLUTE, prefix="existing")
    profiler = cProfile.Profile()
    start = time.perf_counter()
    for repetition in range(repetitions):
        body = make_body(f"spawned_{repetition}")
        profiler.enable()
        with world.modify_world():
            attach_body(world, world.root, body, ConnectionKind.FIXED)
        profiler.disable()
    wall = (time.perf_counter() - start) / repetitions
    statistics = pstats.Stats(profiler)
    report = {"size": size, "wall_seconds_per_commit": wall}
    for name, pattern in COMPONENTS.items():
        report[name] = cumulative_seconds(statistics, pattern) / repetitions
    return report


if __name__ == "__main__":
    sizes: List[int] = [int(argument) for argument in sys.argv[1:]] or [
        10,
        50,
        100,
        200,
        400,
    ]
    print(json.dumps([profile_single_commit(size) for size in sizes], indent=1))
