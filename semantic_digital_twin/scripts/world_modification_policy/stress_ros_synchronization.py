"""
Stress the ROS world synchronization under each world modification policy: one world
builds a chain of bodies, a second world mirrors it over ROS.

Run with ``python stress_ros_synchronization.py [bodies]`` with ROS sourced; prints a
JSON report to stdout.
"""

from __future__ import annotations

import json
import sys
import threading
import time
from dataclasses import dataclass, asdict, field

import rclpy
from rclpy.executors import SingleThreadedExecutor
from typing_extensions import Callable, Dict, Optional

from krrood.adapters.json_serializer import to_json
from benchmark_policies import ConnectionKind, attach_body, make_body
from semantic_digital_twin.adapters.ros.world_synchronizer import WorldSynchronizer
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.world import (
    World,
    WorldModelManager,
    WorldModificationPolicy,
)
from semantic_digital_twin.world_description.world_entity import Body

# %% measurements


@dataclass
class SynchronizationReport:
    """
    What the mirrored world saw of one build under one policy.
    """

    policy: str
    connection_kind: str
    bodies: int
    commit_before_waiting: bool
    sender_error: Optional[str] = None
    build_seconds: Optional[float] = None
    model_messages: int = 0
    state_messages: int = 0
    payload_bytes: int = 0
    mirrored_within_seconds: Optional[float] = None
    mirror_body_count: int = 0
    source_body_count: int = 0
    mirror_matches_source: bool = False


def wait_until(condition: Callable[[], bool], timeout: float) -> Optional[float]:
    start = time.perf_counter()
    while time.perf_counter() - start < timeout:
        if condition():
            return time.perf_counter() - start
        time.sleep(0.01)
    return None


def run(
    node,
    policy: WorldModificationPolicy,
    kind: ConnectionKind,
    bodies: int,
    commit_before_waiting: bool,
) -> SynchronizationReport:
    report = SynchronizationReport(policy, kind, bodies, commit_before_waiting)
    source = World(
        name="source",
        _model_manager=WorldModelManager(policy=WorldModificationPolicy.EXPLICIT),
    )
    mirror = World(name="mirror")
    mirror_synchronizer = WorldSynchronizer(node=node, _world=mirror)
    source_synchronizer = WorldSynchronizer(node=node, _world=source)
    source_synchronizer.wait_until_connected()
    # bring the mirror up to the source's root before measuring
    with source.modify_world():
        source.add_body(Body(name=PrefixedName("root")))
    wait_until(lambda: len(mirror.kinematic_structure_entities) == 1, timeout=10.0)
    source.get_world_model_manager().policy = policy

    original_publish = source_synchronizer.publish

    def counting_publish(message) -> None:
        if message.modification_block is not None:
            report.model_messages += 1
        if message.state_update is not None:
            report.state_messages += 1
        report.payload_bytes += len(json.dumps(to_json(message)))
        original_publish(message)

    source_synchronizer.publish = counting_publish

    start = time.perf_counter()
    try:
        parent = source.root
        with source.modify_world():
            for index in range(bodies):
                child = make_body(f"mirrored_{index}")
                attach_body(source, parent, child, kind)
                parent = child
        if commit_before_waiting:
            source.commit_modifications()
    except Exception as error:
        report.sender_error = f"{type(error).__name__}: {error}"[:200]
    report.build_seconds = time.perf_counter() - start

    expected = len(source.kinematic_structure_entities)
    report.source_body_count = expected
    report.mirrored_within_seconds = wait_until(
        lambda: len(mirror.kinematic_structure_entities) == expected, timeout=10.0
    )
    report.mirror_body_count = len(mirror.kinematic_structure_entities)
    report.mirror_matches_source = {
        entity.id for entity in source.kinematic_structure_entities
    } == {entity.id for entity in mirror.kinematic_structure_entities} and {
        dof.id for dof in source.degrees_of_freedom
    } == {
        dof.id for dof in mirror.degrees_of_freedom
    }
    source.commit_modifications()
    source_synchronizer.close()
    mirror_synchronizer.close()
    return report


def main(bodies: int, policies: list) -> list:
    rclpy.init()
    node = rclpy.create_node("world_modification_policy_stress")
    executor = SingleThreadedExecutor()
    executor.add_node(node)
    thread = threading.Thread(target=executor.spin, daemon=True)
    thread.start()
    results = []
    try:
        for policy in policies:
            for kind in ConnectionKind:
                for commit_before_waiting in (True, False):
                    results.append(
                        asdict(run(node, policy, kind, bodies, commit_before_waiting))
                    )
                    print(json.dumps(results[-1]), file=sys.stderr)
    finally:
        executor.shutdown()
        node.destroy_node()
        rclpy.shutdown()
    return results


if __name__ == "__main__":
    bodies = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    policies = [WorldModificationPolicy(argument) for argument in sys.argv[2:]] or list(
        WorldModificationPolicy
    )
    print(json.dumps(main(bodies, policies), indent=1))
