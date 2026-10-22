"""
The PR2 lays a place setting while the cramera viewer offers the EQL showcase.

Run it through the viewer's demo wrapper, then open ``http://localhost:8711``::

    cramera-live experiments/src/experiments/eql_showcase/demo.py

The place setting is coraplex's bullet world demonstration, unchanged: the PR2 carries
the milk, a bowl and a spoon onto the table while segmind segments what it sees. The
showcase only listens in, and offers the world, the detected events and the robot's own
actions to the EQL panel with questions about each. Every finished run is kept in an
SQLite database in the viewer's data directory, and questions about past runs are
answered there, in SQL translated from the same query language.

Once the table is laid the robot takes commands from the panel, such as putting the milk
back, which leave open how to grasp and where to stand; the robot can be paused and
resumed meanwhile, and asked how it resolved what was left open.
"""

from __future__ import annotations

import importlib.util
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType

import coraplex
from typing_extensions import Any, Dict, List, Optional, Type

from coraplex.datastructures.dataclasses import Context
from coraplex.execution_environment import ExecutionEnvironment
from coraplex.demonstrations import RobotDemonstration
from coraplex.plans.plan import Plan
from coraplex.plans.plan_node import PlanNode
from coraplex.visualization import PluginVisualization
from cramera.live.visualization import LiveVisualization
from cramera.paths import data_directory
from segmind.event_segmentation import Segmind
from semantic_digital_twin.robots.pr2 import PR2
from semantic_digital_twin.semantic_annotations.mixins import HasRootBody
from semantic_digital_twin.semantic_annotations.semantic_annotations import Bowl, Milk
from semantic_digital_twin.spatial_types.spatial_types import Pose
from semantic_digital_twin.world import World

from experiments.eql_showcase.commands import RobotCommander
from experiments.eql_showcase.episodic_memory import RunDatabase
from experiments.eql_showcase.showcase import EqlShowcase, ShowcaseQuestions

RUN_DATABASE_FILE = "eql_showcase_runs.sqlite"
"""
The file, in the viewer's data directory, the showcase keeps its finished runs in.
"""

PLACE_SETTING_LABEL = "place setting"
"""
What a run of the place setting demonstration is called among the finished runs.
"""

PLACE_SETTING_DEMO = (
    Path(coraplex.__file__).parents[2]
    / "demos"
    / "coraplex_bullet_world_demo"
    / "demo.py"
)
"""
Coraplex's bullet world demonstration, which lives outside any package and is loaded
from its file.
"""


# %% the showcase listening in on a demonstration


@dataclass
class ShowcasedDemonstration(RobotDemonstration):
    """
    A demonstration whose world, events and actions the EQL showcase offers to the
    viewer while it runs.

    Mixed in ahead of a concrete demonstration, it changes nothing the demonstration
    does; it only hands what the demonstration builds to the showcase.
    """

    run_label: str = "demonstration"
    """
    What a run of this demonstration is called among the finished runs.
    """

    run_database: Optional[RunDatabase] = None
    """
    The database finished runs are kept in and asked about, or None to keep no runs.
    """

    returnable_objects: List[Type[HasRootBody]] = field(default_factory=list)
    """
    The kinds of object the robot can be told to put back where they started.
    """

    takes_commands: bool = False
    """
    Whether the robot goes on taking commands from the viewer once the demonstration's
    own plan is done.
    """

    questions: ShowcaseQuestions = field(default_factory=ShowcaseQuestions.from_file)
    """
    The ready-made questions the showcase offers about this demonstration.
    """

    extra_names: Dict[str, Any] = field(default_factory=dict)
    """
    Further names the showcase's questions and commands may use.
    """

    showcase: Optional[EqlShowcase] = field(init=False, default=None)
    """
    The showcase offering this run's knowledge, once its world exists.
    """

    homes: Dict[Type[HasRootBody], Pose] = field(init=False, default_factory=dict)
    """
    Where each returnable object stood before the plan began.
    """

    def acquire_world(self) -> World:
        world = super().acquire_world()
        self.showcase = EqlShowcase(
            world,
            database=self.run_database,
            questions=self.questions,
            extra_names=self.extra_names,
        )
        self._offer_showcase()
        return world

    def run(self) -> World:
        world = super().run()
        self.showcase.remember_run(self.run_label)
        if self.takes_commands:
            self.serve_commands(world)
        return world

    def serve_commands(self, world: World) -> None:
        """
        Let the viewer command the robot, for as long as the process runs.

        :param world: The world the demonstration acted in.
        """
        commander = RobotCommander(
            context=self.build_context(world),
            execution_environment=lambda: ExecutionEnvironment(
                execution_type=self.execution_type,
                collision_avoidance=self.collision_avoidance,
                real_time_factor=self.real_time_factor,
            ),
            observe_plan=self._observe_command_plan,
            homes=self.homes,
        )
        self.showcase.commander = commander
        self._offer_showcase()
        commander.serve_forever()

    def _observe_command_plan(self, plan: Plan) -> None:
        """
        Show a plan a command became in the viewer, and offer its actions to questions.

        :param plan: The plan about to be performed.
        """
        self.showcase.observe_plan(plan)
        if self.visualization is not None:
            self.visualization.attach_plan(plan)

    def build_context(self, world: World) -> Context:
        if not self.homes:
            self.homes = {
                kind: world.get_semantic_annotations_by_type(kind)[0].root.global_pose
                for kind in self.returnable_objects
            }
        return super().build_context(world)

    def build_plan(self, context: Context) -> Plan | PlanNode:
        built = super().build_plan(context)
        self.showcase.observe_plan(built.plan if isinstance(built, PlanNode) else built)
        return built

    def segment_events(self, world: World) -> AbstractContextManager:
        segmentation = super().segment_events(world)
        if isinstance(segmentation, Segmind):
            self.showcase.observe_events(segmentation.event_logger)
            self._offer_showcase()
        return segmentation

    def _offer_showcase(self) -> None:
        """
        Offer the showcase to the browser viewer, if this run is shown in one.
        """
        if not isinstance(self.visualization, PluginVisualization):
            return
        if not isinstance(self.visualization.provider, LiveVisualization):
            return
        self.showcase.register_with(self.visualization.provider.bridge)


# %% the place setting


def load_place_setting_demo() -> ModuleType:
    """
    Load coraplex's bullet world demonstration from its file.
    """
    specification = importlib.util.spec_from_file_location(
        PLACE_SETTING_DEMO.stem, PLACE_SETTING_DEMO
    )
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def showcased_place_setting() -> Type[RobotDemonstration]:
    """
    The place setting demonstration with the EQL showcase listening in.
    """
    place_setting = load_place_setting_demo().BulletWorldDemonstration

    @dataclass
    class ShowcasedPlaceSetting(ShowcasedDemonstration, place_setting):
        """
        The PR2 laying the place setting, with the EQL showcase listening in.
        """

    return ShowcasedPlaceSetting


def main(collision_avoidance: bool = True, takes_commands: bool = True) -> None:
    """
    Run the place setting with the EQL showcase, then let the viewer command the robot.

    :param collision_avoidance: Whether every motion state chart avoids collisions.
    :param takes_commands: Whether the robot takes commands from the viewer once the
        place setting is laid.
    """
    showcased_place_setting()(
        used_robot=PR2,
        collision_avoidance=collision_avoidance,
        run_label=PLACE_SETTING_LABEL,
        run_database=RunDatabase(data_directory() / RUN_DATABASE_FILE),
        returnable_objects=[Milk, Bowl],
        takes_commands=takes_commands,
    ).run()


if __name__ == "__main__":
    main()
