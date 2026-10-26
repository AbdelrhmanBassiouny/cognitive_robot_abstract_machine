"""
Stress the world modification policies with a writer thread that keeps adding and
removing bodies while reader threads compute forward kinematics, the way a control loop
reads a world another component edits.

Run with ``python stress_threads.py [seconds]``; prints a JSON report to stdout.
"""

from __future__ import annotations

import json
import sys
import threading
import time
from collections import Counter
from dataclasses import dataclass, field, asdict

from typing_extensions import Dict, List

from benchmark_policies import (
    ConnectionKind,
    attach_body,
    build_chain,
    make_body,
    make_world,
)
from semantic_digital_twin.world import World, WorldModificationPolicy


@dataclass
class StressReport:
    """
    What the readers and the writer observed under one policy.
    """

    policy: str
    guarded_reader: bool
    writer_cycles: int = 0
    writer_errors: Dict[str, int] = field(default_factory=dict)
    reads: int = 0
    reads_skipped_while_modified: int = 0
    reader_errors: Dict[str, int] = field(default_factory=dict)
    hung_threads: List[str] = field(default_factory=list)


def writer(world: World, stop: threading.Event, report: StressReport) -> None:
    errors = Counter()
    index = 0
    while not stop.is_set():
        index += 1
        try:
            with world.modify_world():
                body = make_body(f"transient_{index}")
                attach_body(world, world.root, body, ConnectionKind.REVOLUTE)
            with world.modify_world():
                world.remove_kinematic_structure_entity(body)
            world.commit_modifications()
            report.writer_cycles += 1
        except Exception as error:
            errors[type(error).__name__] += 1
    report.writer_errors = dict(errors)


def reader(
    world: World, stop: threading.Event, report: StressReport, guarded: bool
) -> None:
    errors = Counter()
    while not stop.is_set():
        if guarded and world.world_is_being_modified:
            # what giskardpy's control loop does before touching the world
            report.reads_skipped_while_modified += 1
            time.sleep(0.0001)
            continue
        try:
            for body in list(world.kinematic_structure_entities):
                world.compute_forward_kinematics_np(world.root, body)
            report.reads += 1
        except Exception as error:
            errors[type(error).__name__] += 1
        time.sleep(0.0001)
    report.reader_errors = dict(errors)


def run(policy: WorldModificationPolicy, seconds: float, guarded: bool) -> StressReport:
    world = make_world(WorldModificationPolicy.EXPLICIT)
    build_chain(world, 20, ConnectionKind.REVOLUTE, prefix="existing")
    world.get_world_model_manager().policy = policy
    report = StressReport(policy=policy, guarded_reader=guarded)
    reader_report = StressReport(policy=policy, guarded_reader=guarded)
    stop = threading.Event()
    threads = [
        threading.Thread(
            target=writer, args=(world, stop, report), daemon=True, name="writer"
        ),
        threading.Thread(
            target=reader,
            args=(world, stop, reader_report, guarded),
            daemon=True,
            name="reader",
        ),
    ]
    for thread in threads:
        thread.start()
    time.sleep(seconds)
    stop.set()
    for thread in threads:
        thread.join(timeout=10)
    report.reads = reader_report.reads
    report.reads_skipped_while_modified = reader_report.reads_skipped_while_modified
    report.reader_errors = reader_report.reader_errors
    if any(thread.is_alive() for thread in threads):
        report.writer_errors["DeadlockOrHang"] = 1
        report.hung_threads = [thread.name for thread in threads if thread.is_alive()]
    return report


if __name__ == "__main__":
    seconds = float(sys.argv[1]) if len(sys.argv) > 1 else 10.0
    print(
        json.dumps(
            [
                asdict(run(policy, seconds, guarded))
                for guarded in (True, False)
                for policy in WorldModificationPolicy
            ],
            indent=1,
        )
    )
