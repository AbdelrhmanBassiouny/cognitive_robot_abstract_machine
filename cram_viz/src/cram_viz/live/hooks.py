"""Hooks that attach the bridge to a running coraplex/giskardpy demo.

IMPORTANT: every world access (FK for poses etc.) happens on the SIMULATION
thread itself, inside the Executor.tick hook. Reading the world from a separate
sampler thread corrupts the native solver's heap (malloc: unaligned fastbin
chunk) — the HTTP handlers therefore only ever serve the last finished
snapshot dict.
"""

import os

from cram_viz.live.bridge import BRIDGE


def _install_tick_hook():
    """Bind the bridge to the executing world and snapshot on every sim tick.

    IMPORTANT: every world access (FK for poses etc.) happens HERE, on the
    simulation thread itself. Reading the world from a separate sampler thread
    corrupts the native solver's heap (malloc: unaligned fastbin chunk) — the
    HTTP handlers therefore only ever serve the last finished snapshot dict.
    """
    from giskardpy.executor import Executor
    orig_tick = Executor.tick

    def tick(self, *a, **kw):
        r = orig_tick(self, *a, **kw)
        if BRIDGE.world is None:
            BRIDGE.world = self.context.world
            BRIDGE._bind()
            print("[live_viz] attached to world (robot=%s, %d joints)"
                  % (type(BRIDGE.robot).__name__ if BRIDGE.robot else "?", len(BRIDGE._conns)),
                  flush=True)
        try:
            BRIDGE.apply_moves()       # viewer drags land in the real world here
            BRIDGE.snapshot()
            # plan tree + statechart, same thread, same rule: only cached dicts
            # ever leave for the HTTP handlers
            BRIDGE.observe_chart(getattr(self, "motion_statechart", None))
            BRIDGE._ticks += 1
            if BRIDGE._ticks % 5 == 0:
                BRIDGE.snapshot_plan()
        except Exception:
            pass
        return r
    Executor.tick = tick


def _install_plan_hooks():
    """Follow the coraplex plan: which Plan is executing, and which plan nodes
    the currently running giskard executable belongs to.

    Both hooks fire on the thread that runs the plan (the same one that ticks the
    executor), so they may touch plan objects directly."""
    try:
        from coraplex.plans.plan import Plan
    except Exception:
        return                      # not a coraplex demo — plan tab stays empty

    orig_perform = Plan.perform

    def perform(self, *a, **kw):
        BRIDGE._plan = self
        try:
            BRIDGE.snapshot_plan()
        except Exception:
            pass
        return orig_perform(self, *a, **kw)
    Plan.perform = perform

    try:
        from coraplex.plans.executables import GiskardExecutable
    except Exception:
        return

    orig_execute = GiskardExecutable.execute

    def execute(self, *a, **kw):
        BRIDGE.bind_motion_group(self)
        try:
            r = orig_execute(self, *a, **kw)
        except BaseException:
            BRIDGE.freeze_motion_group(self, "FAILED")
            BRIDGE.snapshot_plan()
            raise
        BRIDGE.freeze_motion_group(self, "SUCCEEDED")
        BRIDGE.snapshot_plan()
        return r
    GiskardExecutable.execute = execute


def _install_mesh_hook():
    """Remember every mesh an object is built from (STL/OBJ/DAE/… — all go
    through MeshParser.parse), so the bridge can serve its geometry to the
    viewer. The body name matches the mesh file's basename."""
    try:
        from semantic_digital_twin.adapters.mesh import MeshParser
    except Exception:
        return
    orig = MeshParser.parse

    def parse(self, *a, **kw):
        try:
            fp = getattr(self, "file_path", None)
            if fp:
                BRIDGE._mesh_files[os.path.basename(fp).lower()] = fp
        except Exception:
            pass
        return orig(self, *a, **kw)
    MeshParser.parse = parse
