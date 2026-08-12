"""
Hooks that attach the bridge to a running coraplex/giskardpy demo.

Each hook installs a :class:`LiveHooks` method in place of one CRAM method; that
method forwards what it observes to the bridge, and all of the interpretation lives
there. Installing is idempotent, so the two documented ways of starting live mode can
be combined safely.

.. warning:: Every world access (forward kinematics for poses etc.) happens on
   the *simulation* thread itself, inside the ``Executor.tick`` hook. Reading
   the world from a separate sampler thread corrupts the native solver's heap
   — the HTTP handlers therefore only ever serve the last finished snapshot
   dict.
"""

from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import Any, Callable

from coraplex.plans.executables import GiskardExecutable
from coraplex.plans.plan import Plan
from giskardpy.executor import Executor
from semantic_digital_twin.adapters.gazebo import GazeboParser
from semantic_digital_twin.adapters.mesh import MeshParser
from semantic_digital_twin.adapters.mjcf import MJCFParser
from semantic_digital_twin.adapters.urdf import URDFParser
from semantic_digital_twin.world import World

from cramera.logging_setup import get_logger
from cramera.live.bridge import BRIDGE, Bridge, LiveHook, TaskStatusName
from cramera.monkey_patch import MethodPatch
from cramera.onboard.bundle_urdf import BundleReport
from cramera.onboard.bundle_world import BundledWorld

logger = get_logger(__name__)


# %% wrappers forwarded to the bridge
@dataclass(frozen=True)
class LiveHooks:
    """
    Thin per-CRAM-method wrappers that forward what they observe to a bridge.

    Kept as real methods, rather than as closures defined inside the ``install_*``
    functions, so each one is independently callable and testable.
    """

    bridge: Bridge
    """
    The bridge every wrapper forwards its observations to.
    """

    def _observe_tick(
        self,
        original: Callable[..., None],
        executor: Executor,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """
        Run the real tick, then let the bridge observe its result.

        :param original: The real, unpatched ``Executor.tick`` bound method.
        :param executor: The executor whose tick is being run.
        :param args: Positional arguments forwarded to the wrapped call.
        :param kwargs: Keyword arguments forwarded to the wrapped call.
        """
        result = original(executor, *args, **kwargs)
        # a demo may build a second world and execute there; follow the world that is
        # actually ticking instead of the first one ever seen
        if self.bridge.world is not executor.context.world:
            self.bridge.attach(executor.context.world)
        try:
            self.bridge.observe_tick(executor.motion_statechart)
        except Exception:
            # boundary guard: a visualization bug must never take the robot demo
            # down, so this hook swallows everything the bridge raises
            logger.exception("bridge snapshot failed this tick")
        return result

    def _begin_plan(
        self, original: Callable[..., Any], plan: Plan, *args: Any, **kwargs: Any
    ) -> Any:
        """
        Capture the plan the moment it starts performing.

        :param original: The real, unpatched ``Plan.perform`` bound method.
        :param plan: The plan starting to perform.
        :param args: Positional arguments forwarded to the wrapped call.
        :param kwargs: Keyword arguments forwarded to the wrapped call.
        """
        self.bridge.begin_plan(plan)
        return original(plan, *args, **kwargs)

    def _track_motion_group(
        self,
        original: Callable[..., None],
        executable: GiskardExecutable,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """
        Track this executable's motion group and freeze its final status.

        :param original: The real, unpatched ``GiskardExecutable.execute`` bound method.
        :param executable: The executable whose motion group is tracked.
        :param args: Positional arguments forwarded to the wrapped call.
        :param kwargs: Keyword arguments forwarded to the wrapped call.
        """
        self.bridge.bind_motion_group(executable)
        try:
            result = original(executable, *args, **kwargs)
        except BaseException:
            self.bridge.freeze_motion_group(executable, TaskStatusName.FAILED)
            raise
        self.bridge.freeze_motion_group(executable, TaskStatusName.SUCCEEDED)
        return result

    def _remember_mesh_file(
        self,
        original: Callable[..., World],
        mesh_parser: MeshParser,
        *args: Any,
        **kwargs: Any,
    ) -> World:
        """
        Remember this mesh's file path before parsing it.

        :param original: The real, unpatched ``MeshParser.parse`` bound method.
        :param mesh_parser: The parser about to parse the mesh.
        :param args: Positional arguments forwarded to the wrapped call.
        :param kwargs: Keyword arguments forwarded to the wrapped call.
        """
        if mesh_parser.file_path:
            self.bridge.remember_mesh_file(mesh_parser.file_path)
        return original(mesh_parser, *args, **kwargs)

    def _remember_urdf_source(
        self,
        original: Callable[..., URDFParser],
        cls: type,
        file_path: str,
        **kwargs: Any,
    ) -> URDFParser:
        """
        Parse as usual, but remember this URDF/xacro source file.

        :param original: The real, unpatched ``URDFParser.from_file`` classmethod.
        :param cls: The ``URDFParser`` class the method is bound to.
        :param file_path: Path of the URDF/xacro source file being parsed.
        :param kwargs: Keyword arguments forwarded to the wrapped call.
        """
        self.bridge.remember_model_source(file_path, BundleReport.of_source)
        return original(cls, file_path, **kwargs)

    def _remember_gazebo_source(
        self,
        original: Callable[..., GazeboParser],
        cls: type,
        file_path: str,
        **kwargs: Any,
    ) -> GazeboParser:
        """
        Parse as usual, but remember this Gazebo/SDF world or model source file.

        :param original: The real, unpatched ``GazeboParser.from_file`` classmethod.
        :param cls: The ``GazeboParser`` class the method is bound to.
        :param file_path: Path of the source file being parsed.
        :param kwargs: Keyword arguments forwarded to the wrapped call.
        """
        self.bridge.remember_model_source(file_path, BundledWorld.of_gazebo_source)
        return original(cls, file_path, **kwargs)

    def _remember_mjcf_source(
        self,
        original: Callable[..., None],
        mjcf_parser: MJCFParser,
        file_path: str,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """
        Initialize as usual, but remember this MJCF source file.

        :param original: The real, unpatched ``MJCFParser.__init__`` bound method.
        :param mjcf_parser: The parser being initialized.
        :param file_path: Path of the source file.
        :param args: Positional arguments forwarded to the wrapped call.
        :param kwargs: Keyword arguments forwarded to the wrapped call.
        """
        self.bridge.remember_model_source(file_path, BundledWorld.of_mjcf_source)
        return original(mjcf_parser, file_path, *args, **kwargs)

    def _remember_model_bodies(
        self,
        original: Callable[..., World],
        parser: Any,
        *args: Any,
        **kwargs: Any,
    ) -> World:
        """
        Parse as usual, then remember the bodies the parsed model world consists of.

        The bridge keeps these bodies out of the live object overlay, because the live
        scene bundle already renders them.

        :param original: The real, unpatched ``parse`` bound method.
        :param parser: The parser whose model world was parsed.
        :param args: Positional arguments forwarded to the wrapped call.
        :param kwargs: Keyword arguments forwarded to the wrapped call.
        """
        world = original(parser, *args, **kwargs)
        self.bridge.remember_model_bodies([str(body.name) for body in world.bodies])
        return world


_LIVE_HOOKS = LiveHooks(bridge=BRIDGE)


# %% world and motion
def install_tick_hook() -> None:
    """
    Bind the bridge to the executing world and snapshot on every simulation tick.
    """
    if not BRIDGE.claim_hook(LiveHook.TICK):
        logger.debug("tick hook already installed")
        return
    MethodPatch(Executor, "tick").install(_LIVE_HOOKS._observe_tick)


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
    MethodPatch(Plan, "perform").install(_LIVE_HOOKS._begin_plan)
    MethodPatch(GiskardExecutable, "execute").install(_LIVE_HOOKS._track_motion_group)


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
    MethodPatch(MeshParser, "parse").install(_LIVE_HOOKS._remember_mesh_file)


def install_model_source_hooks() -> None:
    """
    Remember every URDF/xacro, Gazebo/SDF and MJCF file the world is built from, so a
    snapshot of the running demo can be bundled on demand (see
    :mod:`cramera.live.live_bundle`) — the same three sources
    :meth:`~cramera.onboard.demo.Recorder.install_asset_hooks` tracks for onboarding.
    Each parser's ``parse`` is patched too, so the bridge knows which world bodies the
    bundled models render and keeps them out of the object overlay.

    Must be installed before the demo parses its world, same as
    :func:`install_mesh_hook` — a source parsed before this hook is installed is never
    seen.
    """
    if not BRIDGE.claim_hook(LiveHook.MODEL_SOURCE):
        logger.debug("model source hooks already installed")
        return
    MethodPatch(URDFParser, "from_file").install(_LIVE_HOOKS._remember_urdf_source)
    MethodPatch(GazeboParser, "from_file").install(_LIVE_HOOKS._remember_gazebo_source)
    MethodPatch(MJCFParser, "__init__").install(_LIVE_HOOKS._remember_mjcf_source)
    for parser_class in (URDFParser, GazeboParser, MJCFParser):
        MethodPatch(parser_class, "parse").install(_LIVE_HOOKS._remember_model_bodies)
