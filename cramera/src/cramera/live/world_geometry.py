"""
Writing a running world's own geometry as URDF, for a demo that parsed none.

A world assembled in code, or parsed out of MJCF/SDF, leaves the viewer nothing to
draw: only URDF/xacro sources are remembered as they are read, and there are none. The
world itself still describes every body, so it is serialized here the same way
:mod:`cramera.onboard.demo` serializes one for a recorded bundle -- but into the
process's own temporary directory, referencing the meshes the world already loaded
instead of copying them.

The robot is written as a branch of its own, in its base link's frame, because the
bridge publishes that link's pose separately: the viewer places the branch by placing
its root. Everything else becomes one environment model, minus the bodies the viewer
already draws and moves as loose objects.

.. warning:: Writing a model reads the world (forward kinematics for every body's
   pose), so it may only run on the thread that owns the world -- in practice inside
   the ``Executor.tick`` hook, like every other world access the bridge makes.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

from typing_extensions import ClassVar, List, Optional, Set, TYPE_CHECKING

from cramera.live.model_source import GeneratedModelSource
from cramera.logging_setup import get_logger
from cramera.onboard.world_to_urdf import OriginalMeshFiles, UrdfDocument

if TYPE_CHECKING:
    from semantic_digital_twin.robots.robot_parts import AbstractRobot
    from semantic_digital_twin.world import World
    from semantic_digital_twin.world_description.world_entity import Body

logger = get_logger(__name__)


@dataclass
class GeneratedWorldModels:
    """
    The URDF models written from a running world, and where they were written.
    """

    ROBOT_MODEL_NAME: ClassVar[str] = "robot"
    """
    Name of the model describing the robot's own branch.
    """

    ENVIRONMENT_MODEL_NAME: ClassVar[str] = "environment"
    """
    Name of the model describing everything the robot's branch does not.
    """

    directory: Optional[Path] = None
    """
    Temporary directory the models are written under, created on the first write.
    """

    generation: int = 0
    """
    How many times the world has been written so far.

    Each write goes into a subdirectory of its own, so a model already being served is
    never overwritten underneath the viewer reading it.
    """

    def write(
        self,
        world: World,
        robot: Optional[AbstractRobot],
        drawn_as_objects: Set[str],
    ) -> List[GeneratedModelSource]:
        """
        Write the world as a robot model plus an environment model.

        :param world: The world to serialize, as it stands now.
        :param robot: The robot bound to that world, or None when it has none.
        :param drawn_as_objects: Names of the bodies the viewer already draws and moves
            itself, which would otherwise appear a second time, motionless.
        :return: The models written, in the order the viewer should be told about them.
        """
        self.generation += 1
        output_directory = self._output_directory()
        branch = self._robot_branch(world, robot)
        branch_names = {str(body.name) for body in branch}
        sources = []
        if branch:
            report = UrdfDocument.of_branch(
                branch,
                self.ROBOT_MODEL_NAME,
                output_directory,
                OriginalMeshFiles.in_place(),
            )
            sources.append(GeneratedModelSource(path=report.urdf, robot=True))
        environment = [
            body
            for body in world.bodies_topologically_sorted
            if str(body.name) not in branch_names
            and str(body.name) not in drawn_as_objects
        ]
        if environment:
            report = UrdfDocument.of_bodies(
                environment,
                self.ENVIRONMENT_MODEL_NAME,
                output_directory,
                OriginalMeshFiles.in_place(),
            )
            sources.append(GeneratedModelSource(path=report.urdf, robot=False))
        logger.info(
            "wrote the live world as %d model(s): %d robot bodies, %d environment "
            "bodies, %d drawn as objects",
            len(sources),
            len(branch),
            len(environment),
            len(drawn_as_objects),
        )
        return sources

    @staticmethod
    def _robot_branch(world: World, robot: Optional[AbstractRobot]) -> List[Body]:
        """
        The robot's bodies, root first, or nothing when no robot is bound.

        Taken in the world's own topological order rather than the branch walk's, so
        the document reads root-downwards.

        :param world: The world the robot stands in.
        :param robot: The robot whose branch is wanted, or None.
        """
        if robot is None:
            return []
        branch = {
            str(entity.name)
            for entity in world.get_kinematic_structure_entities_of_branch(robot.root)
        }
        return [
            body
            for body in world.bodies_topologically_sorted
            if str(body.name) in branch
        ]

    def _output_directory(self) -> str:
        """
        A directory of this write's own, under a temporary root created on demand.
        """
        if self.directory is None:
            self.directory = Path(tempfile.mkdtemp(prefix="cramera-live-world-"))
        return str(self.directory / str(self.generation))
