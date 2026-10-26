"""
Benchmark the world modification policies of the prototype against each other.

Run with ``python benchmark_policies.py`` from an environment that has
``semantic_digital_twin`` installed; it prints a JSON report to stdout.
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass, field, asdict
from enum import StrEnum

from typing_extensions import Callable, Dict, List, Optional

from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.spatial_types import HomogeneousTransformationMatrix, Vector3
from semantic_digital_twin.world import (
    World,
    WorldModelManager,
    WorldModificationPolicy,
    WorldModificationPolicyEnvironmentVariable,
)
from semantic_digital_twin.world_description.connections import (
    FixedConnection,
    RevoluteConnection,
)
from semantic_digital_twin.world_description.geometry import Box, Scale
from semantic_digital_twin.world_description.shape_collection import ShapeCollection
from semantic_digital_twin.world_description.world_entity import Body

# %% world construction

LAZY_COMPILATION = (
    os.environ.get(WorldModificationPolicyEnvironmentVariable.LAZY_COMPILATION, "")
    == "1"
)
"""
Whether the benchmarked worlds recompile derived data lazily.
"""


class ConnectionKind(StrEnum):
    """
    Which connection the benchmark attaches each new body with.
    """

    FIXED = "fixed"
    REVOLUTE = "revolute"


def make_world(policy: WorldModificationPolicy) -> World:
    world = World(
        _model_manager=WorldModelManager(
            policy=policy, lazy_compilation=LAZY_COMPILATION
        )
    )
    with world.modify_world():
        world.add_body(Body(name=PrefixedName("root")))
    world.commit_modifications()
    return world


def make_body(name: str) -> Body:
    return Body(
        name=PrefixedName(name),
        collision=ShapeCollection(shapes=[Box(scale=Scale(0.1, 0.1, 0.1))]),
    )


def attach_body(world: World, parent: Body, child: Body, kind: ConnectionKind) -> None:
    offset = HomogeneousTransformationMatrix.from_xyz_rpy(x=0.1)
    if kind == ConnectionKind.FIXED:
        connection = FixedConnection(
            parent=parent, child=child, parent_T_connection_expression=offset
        )
    else:
        connection = RevoluteConnection.create_with_dofs(
            world=world,
            parent=parent,
            child=child,
            axis=Vector3.Z(),
            parent_T_connection_expression=offset,
        )
    world.add_connection(connection)


def build_chain(
    world: World, count: int, kind: ConnectionKind, prefix: str = "link"
) -> List[Body]:
    """
    Append ``count`` bodies to the root as a chain, the way a parser or a user script
    would: one ``modify_world`` block around the whole loop.
    """
    parent = world.root
    bodies = []
    with world.modify_world():
        for index in range(count):
            child = make_body(f"{prefix}_{index}")
            attach_body(world, parent, child, kind)
            bodies.append(child)
            parent = child
    world.commit_modifications()
    return bodies


# %% measurements


@dataclass
class Measurement:
    """
    One timed scenario under one policy.
    """

    scenario: str
    policy: str
    size: int
    seconds: Optional[float] = None
    committed_blocks: Optional[int] = None
    error: Optional[str] = None


def measure(
    scenario: str,
    policy: WorldModificationPolicy,
    size: int,
    setup: Callable[[], World],
    action: Callable[[World], None],
) -> Measurement:
    world = setup()
    blocks_before = world.get_world_model_manager().committed_block_count
    start = time.perf_counter()
    try:
        action(world)
        world.commit_modifications()
    except Exception as error:  # the benchmark reports breakage instead of stopping
        return Measurement(
            scenario, policy, size, error=f"{type(error).__name__}: {error}"[:200]
        )
    seconds = time.perf_counter() - start
    return Measurement(
        scenario,
        policy,
        size,
        seconds=seconds,
        committed_blocks=world.get_world_model_manager().committed_block_count
        - blocks_before,
    )


def spawn_and_remove(world: World) -> None:
    """
    The single-object case: add one body next to the root, read its pose, remove it.
    """
    body = make_body("spawned")
    with world.modify_world():
        attach_body(world, world.root, body, ConnectionKind.FIXED)
    world.compute_forward_kinematics_np(world.root, body)
    with world.modify_world():
        world.remove_kinematic_structure_entity(body)


def build_and_query_interleaved(count: int) -> Callable[[World], None]:
    """
    Add bodies one by one and read each new pose before adding the next, a pattern no
    deferred commit can coalesce.
    """

    def action(world: World) -> None:
        parent = world.root
        for index in range(count):
            child = make_body(f"queried_{index}")
            with world.modify_world():
                attach_body(world, parent, child, ConnectionKind.FIXED)
            world.compute_forward_kinematics_np(world.root, child)
            parent = child

    return action


def main(sizes: List[int]) -> List[Measurement]:
    results = []
    for size in sizes:
        for policy in WorldModificationPolicy:
            for kind in ConnectionKind:
                results.append(
                    measure(
                        f"build_chain_{kind}",
                        policy,
                        size,
                        lambda: make_world(policy),
                        lambda world: build_chain(world, size, kind),
                    )
                )
            results.append(
                measure(
                    "spawn_and_remove_in_world_of_size",
                    policy,
                    size,
                    lambda: _prebuilt(policy, size),
                    spawn_and_remove,
                )
            )
            results.append(
                measure(
                    "build_and_query_interleaved",
                    policy,
                    size,
                    lambda: make_world(policy),
                    build_and_query_interleaved(size),
                )
            )
            print(json.dumps(asdict(results[-1])), file=sys.stderr)
    return results


def _prebuilt(policy: WorldModificationPolicy, size: int) -> World:
    """
    A world of ``size`` revolute links built in one block, switched to ``policy``.
    """
    world = make_world(WorldModificationPolicy.EXPLICIT)
    build_chain(world, size, ConnectionKind.REVOLUTE, prefix="existing")
    world.get_world_model_manager().policy = policy
    return world


if __name__ == "__main__":
    sizes = [int(argument) for argument in sys.argv[1:]] or [10, 50, 100, 200]
    print(json.dumps([asdict(result) for result in main(sizes)], indent=1))
