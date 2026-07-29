"""
Hooks that attach the bridge to a running coraplex/giskardpy demo.

.. warning:: Every world access (forward kinematics for poses etc.) happens on
   the *simulation* thread itself, inside the ``Executor.tick`` hook. Reading
   the world from a separate sampler thread corrupts the native solver's heap
   — the HTTP handlers therefore only ever serve the last finished snapshot
   dict.
"""

from __future__ import annotations

import logging
from pathlib import Path

from coraplex.plans.executables import GiskardExecutable
from coraplex.plans.plan import Plan
from giskardpy.executor import Executor
from semantic_digital_twin.adapters.mesh import MeshParser

from cram_viz.live.bridge import BRIDGE

logger = logging.getLogger(__name__)


def install_tick_hook(plan_snapshot_tick_interval: int = 5) -> None:
    """
    Bind the bridge to the executing world and snapshot on every sim tick.

    The plan tree is only re-walked every plan_snapshot_tick_interval ticks.
    """
    original_tick = Executor.tick

    def tick(self, *args, **kwargs):
        """
        Run the real tick, then bind/snapshot the bridge off its result.
        """
        result = original_tick(self, *args, **kwargs)
        if BRIDGE.world is None:
            BRIDGE.world = self.context.world
            BRIDGE._bind()
            logger.info(
                "attached to world (robot=%s, %d joints)",
                type(BRIDGE.robot).__name__ if BRIDGE.robot else "?",
                len(BRIDGE._connections),
            )
        try:
            BRIDGE.apply_moves()  # viewer drags land in the real world here
            BRIDGE.snapshot()
            BRIDGE.observe_chart(self.motion_statechart)
            BRIDGE._ticks += 1
            if BRIDGE._ticks % plan_snapshot_tick_interval == 0:
                BRIDGE.snapshot_plan()
        except Exception:
            # boundary guard: a visualization bug must never take the robot
            # demo down — this is the single intentional broad except
            logger.exception("bridge snapshot failed this tick")
        return result

    Executor.tick = tick


def install_plan_hooks() -> None:
    """
    Follow the coraplex plan: which plan executes, and which plan nodes the currently
    running giskard executable belongs to.

    Both hooks fire on the thread that runs the plan (the same one that ticks the
    executor), so they may touch plan objects directly.
    """
    original_perform = Plan.perform

    def perform(self, *args, **kwargs):
        """
        Capture the plan the moment it starts performing.
        """
        BRIDGE._plan = self
        BRIDGE.snapshot_plan()
        return original_perform(self, *args, **kwargs)

    Plan.perform = perform

    original_execute = GiskardExecutable.execute

    def execute(self, *args, **kwargs):
        """
        Track this executable's motion group and freeze its final status.
        """
        BRIDGE.bind_motion_group(self)
        try:
            result = original_execute(self, *args, **kwargs)
        except BaseException:
            BRIDGE.freeze_motion_group(self, "FAILED")
            BRIDGE.snapshot_plan()
            raise
        BRIDGE.freeze_motion_group(self, "SUCCEEDED")
        BRIDGE.snapshot_plan()
        return result

    GiskardExecutable.execute = execute


def install_mesh_hook() -> None:
    """
    Remember every mesh an object is built from, so the bridge can serve its geometry to
    the viewer.

    All mesh formats go through ``MeshParser.parse``; the body name matches the mesh
    file's basename.
    """
    original_parse = MeshParser.parse

    def parse(self, *args, **kwargs):
        """
        Remember this mesh's file path before parsing it.
        """
        if self.file_path:
            BRIDGE._mesh_files[Path(self.file_path).name.lower()] = self.file_path
        return original_parse(self, *args, **kwargs)

    MeshParser.parse = parse
