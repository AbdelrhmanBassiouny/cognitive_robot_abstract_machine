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
"""

from __future__ import annotations

import importlib.util
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType

import coraplex
from typing_extensions import Optional, Type

from coraplex.datastructures.dataclasses import Context
from coraplex.demonstrations import RobotDemonstration
from coraplex.plans.plan import Plan
from coraplex.plans.plan_node import PlanNode
from coraplex.visualization import PluginVisualization
from cramera.live.visualization import LiveVisualization
from cramera.paths import data_directory
from segmind.event_segmentation import Segmind
from semantic_digital_twin.robots.pr2 import PR2
from semantic_digital_twin.world import World

from experiments.eql_showcase.episodic_memory import RunDatabase
from experiments.eql_showcase.showcase import EqlShowcase

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

    showcase: Optional[EqlShowcase] = field(init=False, default=None)
    """
    The showcase offering this run's knowledge, once its world exists.
    """

    def acquire_world(self) -> World:
        world = super().acquire_world()
        self.showcase = EqlShowcase(world, database=self.run_database)
        self._offer_showcase()
        return world

    def run(self) -> World:
        world = super().run()
        self.showcase.remember_run(self.run_label)
        return world

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


def main(collision_avoidance: bool = True) -> None:
    """
    Run the place setting with the EQL showcase.

    :param collision_avoidance: Whether every motion state chart avoids collisions.
    """
    showcased_place_setting()(
        used_robot=PR2,
        collision_avoidance=collision_avoidance,
        run_label=PLACE_SETTING_LABEL,
        run_database=RunDatabase(data_directory() / RUN_DATABASE_FILE),
    ).run()


if __name__ == "__main__":
    main()
