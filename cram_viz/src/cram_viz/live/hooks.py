"""
Hooks that attach the bridge to a running coraplex/giskardpy demo.

Each hook wraps one CRAM method and forwards what it observes to the bridge; all
of the interpretation lives there. Installing is idempotent, so the two documented
ways of starting live mode can be combined safely.

.. warning:: Every world access (forward kinematics for poses etc.) happens on
   the *simulation* thread itself, inside the ``Executor.tick`` hook. Reading
   the world from a separate sampler thread corrupts the native solver's heap
   — the HTTP handlers therefore only ever serve the last finished snapshot
   dict.
"""

from __future__ import annotations

import logging

from typing_extensions import Any

from coraplex.plans.executables import GiskardExecutable
from coraplex.plans.plan import Plan
from giskardpy.executor import Executor
from semantic_digital_twin.adapters.mesh import MeshParser
from semantic_digital_twin.world import World

from cram_viz.live.bridge import BRIDGE, LiveHook, TaskStatusName

logger = logging.getLogger(__name__)


# %% world and motion
def install_tick_hook() -> None:
    """
    Bind the bridge to the executing world and snapshot on every simulation tick.
    """
    if not BRIDGE.claim_hook(LiveHook.TICK):
        logger.debug("tick hook already installed")
        return
    original_tick = Executor.tick

    def tick(self: Executor, *args: Any, **kwargs: Any) -> None:
        """
        Run the real tick, then let the bridge observe its result.
        """
        result = original_tick(self, *args, **kwargs)
        if BRIDGE.world is None:
            BRIDGE.attach(self.context.world)
        try:
            BRIDGE.observe_tick(self.motion_statechart)
        except Exception:
            # boundary guard: a visualization bug must never take the robot demo
            # down, so this hook swallows everything the bridge raises
            logger.exception("bridge snapshot failed this tick")
        return result

    Executor.tick = tick


# %% the coraplex plan
def install_plan_hooks() -> None:
    """
    Follow the coraplex plan: which plan executes, and which plan nodes the currently
    running giskard executable belongs to.

    Both hooks fire on the thread that runs the plan (the same one that ticks the
    executor), so they may touch plan objects directly.
    """
    if not BRIDGE.claim_hook(LiveHook.PLAN):
        logger.debug("plan hooks already installed")
        return
    original_perform = Plan.perform

    def perform(self: Plan, *args: Any, **kwargs: Any) -> Any:
        """
        Capture the plan the moment it starts performing.
        """
        BRIDGE.begin_plan(self)
        return original_perform(self, *args, **kwargs)

    Plan.perform = perform

    original_execute = GiskardExecutable.execute

    def execute(self: GiskardExecutable, *args: Any, **kwargs: Any) -> None:
        """
        Track this executable's motion group and freeze its final status.
        """
        BRIDGE.bind_motion_group(self)
        try:
            result = original_execute(self, *args, **kwargs)
        except BaseException:
            BRIDGE.freeze_motion_group(self, TaskStatusName.FAILED)
            raise
        BRIDGE.freeze_motion_group(self, TaskStatusName.SUCCEEDED)
        return result

    GiskardExecutable.execute = execute


# %% object geometry
def install_mesh_hook() -> None:
    """
    Remember every mesh an object is built from, so the bridge can serve its geometry to
    the viewer.

    All mesh formats go through ``MeshParser.parse``; the body name matches the mesh
    file's basename.
    """
    if not BRIDGE.claim_hook(LiveHook.MESH):
        logger.debug("mesh hook already installed")
        return
    original_parse = MeshParser.parse

    def parse(self: MeshParser, *args: Any, **kwargs: Any) -> World:
        """
        Remember this mesh's file path before parsing it.
        """
        if self.file_path:
            BRIDGE.remember_mesh_file(self.file_path)
        return original_parse(self, *args, **kwargs)

    MeshParser.parse = parse
