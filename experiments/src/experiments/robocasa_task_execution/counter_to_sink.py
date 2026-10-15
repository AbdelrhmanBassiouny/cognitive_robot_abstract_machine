"""
A PR2 performs RoboCasa's counter to sink pick and place task with an underspecified
coraplex plan.

RoboCasa composes the kitchen, samples the object to move and says where its own robot
starts. The PR2 is spawned there and given a transport whose standing poses and grasps
are left open; coraplex grounds them by trying candidates against a copy of the world.
The PR2 lets go of the object above the sink, and RoboCasa's physics lets it fall in.
Whether the task succeeded is decided by RoboCasa's own check.

The episode is performed either kinematically or in MuJoCo physics, where the PR2's
servos and drive move it and its fingers hold the object by friction alone.

Run with (the ``experiments`` package must be importable)::

    python -m experiments.robocasa_task_execution.counter_to_sink
    python -m experiments.robocasa_task_execution.counter_to_sink --layout LAYOUT005
    python -m experiments.robocasa_task_execution.counter_to_sink --physics
    python -m experiments.robocasa_task_execution.counter_to_sink --no-collision-avoidance

.. note::
    The kitchen assets must be downloaded once via
    ``python -m robocasa.scripts.download_kitchen_assets`` before an episode can be
    composed.
"""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum

import mujoco

import numpy as np
from typing_extensions import TYPE_CHECKING, Self

from semantic_digital_twin.adapters.robocasa_dataset.mujoco_compat import (
    robocasa_version_assertions_relaxed,
)

with robocasa_version_assertions_relaxed():
    from robocasa.models.scenes.scene_registry import LayoutType, StyleType
    from robocasa.utils import object_utils

from coraplex.datastructures.dataclasses import Context
from coraplex.datastructures.enums import ExecutionType
from coraplex.execution_environment import (
    ExecutionEnvironment,
    PhysicallySimulatedRobot,
)
from coraplex.plans.plan_node import PlanNode
from coraplex.plans.factories import sequential
from experiments.robocasa_task_execution.exceptions import NoClearStandingPose
from coraplex.robot_plans.actions.composite.transporting import TransportAction
from coraplex.robot_plans.actions.core.robot_body import MoveTorsoAction
from semantic_digital_twin.adapters.multi_sim import MujocoSim
from semantic_digital_twin.adapters.robocasa_dataset.loader import (
    RoboCasaDatasetLoader,
    RoboCasaTask,
)
from semantic_digital_twin.adapters.urdf import URDFParser
from semantic_digital_twin.collision_checking.collision_rules import (
    AllowCollisionBetweenGroups,
)
from semantic_digital_twin.datastructures.definitions import (
    StaticJointState,
    TorsoState,
)
from semantic_digital_twin.grasping.grasp_candidates import HasGraspCandidates
from semantic_digital_twin.reasoning.robot_predicates import is_body_gripped
from semantic_digital_twin.robots.pr2 import PR2
from semantic_digital_twin.semantic_annotations.semantic_annotations import Floor
from semantic_digital_twin.spatial_types.spatial_types import (
    HomogeneousTransformationMatrix,
    Point3,
    Pose,
)
from semantic_digital_twin.world_description.connections import OmniDrive

if TYPE_CHECKING:
    from robocasa.environments.kitchen.atomic.kitchen_pick_place import (
        PickPlaceCounterToSink,
    )

logger = logging.getLogger(__name__)


# %% names RoboCasa gives


class RoboCasaTaskName(StrEnum):
    """
    The RoboCasa kitchen task environments performed here.
    """

    PICK_PLACE_COUNTER_TO_SINK = "PickPlaceCounterToSink"


class RoboCasaObjectName(StrEnum):
    """
    The names RoboCasa gives the objects of a pick and place task.
    """

    TARGET = "obj"
    """
    The object the task is about, as opposed to the distractors placed around it.
    """


# %% how an episode ended


@dataclass
class CounterToSinkOutcome:
    """
    How an episode of the counter to sink task ended.
    """

    object_in_sink: bool
    """
    Whether RoboCasa's own check finds the target object inside the sink.
    """

    object_released: bool
    """
    Whether the robot let go of the target object, so that it no longer moves with the
    gripper.
    """

    @property
    def succeeded(self) -> bool:
        """
        Whether the task is accomplished: the target object lies in the sink and the
        robot has let go of it.
        """
        return self.object_in_sink and self.object_released


# %% one episode of the task


@dataclass
class CounterToSinkEpisode:
    """
    One episode of RoboCasa's counter to sink task, with a PR2 standing where RoboCasa
    starts its own robot.
    """

    environment: PickPlaceCounterToSink
    """
    The reset RoboCasa environment the episode was composed in, holding RoboCasa's own
    ground truth such as the inside of the sink.
    """

    task: RoboCasaTask
    """
    The task, bound to the world the PR2 performs it in.
    """

    robot: PR2
    """
    The robot performing the task.
    """

    @classmethod
    def compose(cls, layout: LayoutType, style: StyleType) -> Self:
        """
        Compose a new episode, with the target object and distractors RoboCasa samples
        for it.

        :param layout: The kitchen layout to compose the episode in.
        :param style: The visual style of the kitchen.
        :return: The episode, with the PR2 standing clear of the kitchen at or behind
            RoboCasa's start pose.
        """
        loader = RoboCasaDatasetLoader()
        environment = loader.build_task_environment(
            RoboCasaTaskName.PICK_PLACE_COUNTER_TO_SINK, layout, style
        )
        task = loader.load_task_from_environment(environment)
        world = task.world
        pr2_world = URDFParser.from_file(PR2.get_ros_file_path()).parse()
        with world.modify_world():
            drive = OmniDrive.create_with_dofs(
                parent=world.root, child=pr2_world.root, world=world
            )
            world.merge_world(pr2_world, drive)
            drive.has_hardware_interface = True
        drive.origin = task.robot_base_pose
        episode = cls(environment=environment, task=task, robot=PR2.from_world(world))
        episode.stand_clear_of_the_kitchen()
        return episode

    def stand_clear_of_the_kitchen(
        self, step: float = 0.05, maximum_distance: float = 1.0
    ) -> None:
        """
        Park the arms of the PR2 and step it back from RoboCasa's start pose until it
        collides with nothing, while letting its base rest on the floor.

        :param step: How far the PR2 steps back at a time.
        :param maximum_distance: How far behind the start pose the PR2 stands at most.
        :raises NoClearStandingPose: If the PR2 collides wherever it stands up to
            ``maximum_distance`` behind the start pose.
        """
        world = self.task.world
        with world.modify_world():
            world.collision_manager.add_ignore_collision_rule(
                AllowCollisionBetweenGroups(
                    body_group_a=list(self.robot.bodies_with_collision),
                    body_group_b=[
                        floor.root
                        for floor in world.get_semantic_annotations_by_type(Floor)
                    ],
                )
            )
        world.collision_manager.update_collision_matrix()
        for arm in self.robot.all_arms:
            arm.get_joint_state_by_type(StaticJointState.PARK).apply_to(world)
        start_pose = self.task.robot_base_pose.to_np()
        drive = self.robot.root.parent_connection
        for distance in np.arange(0.0, maximum_distance + step / 2, step):
            start_T_standing_pose = np.eye(4)
            start_T_standing_pose[0, 3] = -distance
            drive.origin = start_pose @ start_T_standing_pose
            if not self.robot.is_in_collision:
                return
        raise NoClearStandingPose(
            start_pose=self.task.robot_base_pose, maximum_distance=maximum_distance
        )

    @property
    def target_object(self) -> HasGraspCandidates:
        """
        The object the task asks to be put into the sink.
        """
        world = self.task.world
        body = world.get_body_by_name(
            self.environment.objects[RoboCasaObjectName.TARGET].root_body
        )
        return next(
            annotation
            for annotation in world.get_semantic_annotations_by_type(HasGraspCandidates)
            if annotation.root is body
        )

    @property
    def target_object_released(self) -> bool:
        """
        Whether the target object no longer moves with the robot: it neither hangs off
        the robot nor lies gripped between the fingers of one of its grippers.
        """
        body = self.target_object.root
        hangs_off_the_robot = (
            body
            in self.task.world.get_kinematic_structure_entities_of_branch(
                self.robot.root
            )
        )
        gripped = any(
            is_body_gripped(body, arm.end_effector) for arm in self.robot.all_arms
        )
        return not hangs_off_the_robot and not gripped

    def placement_pose(self, drop_height: float = 0.1) -> Pose:
        """
        :param drop_height: How far above the rim of the sink the lowest point of the
            target object is let go of.
        :return: Where the target object is let go of: centred over the first basin of
            the sink, oriented as it stands now.
        """
        _, x_corner, y_corner, rim_corner = next(
            iter(self.environment.sink.get_int_sites(relative=False).values())
        )
        basin_center = (x_corner + y_corner) / 2
        world = self.task.world
        body = self.target_object.root
        object_pose = body.global_pose
        lowest_point = (
            body.collision.as_bounding_box_collection_in_frame(world.root)
            .bounding_box()
            .min_z
        )
        height_above_lowest_point = object_pose.to_np()[2, 3] - lowest_point
        return Pose(
            position=Point3(
                basin_center[0],
                basin_center[1],
                rim_corner[2] + height_above_lowest_point + drop_height,
            ),
            orientation=object_pose.quaternion,
            reference_frame=world.root,
        )

    def transport_plan(self, sampling_seed: int) -> PlanNode:
        """
        :param sampling_seed: The seed the standing poses are sampled with.
        :return: The plan carrying the target object from the counter into the sink,
            standing wherever and grasping however a trial finds to work.
        """
        context = Context(self.task.world, self.robot, sampling_seed=sampling_seed)
        transport = TransportAction.from_graspable_by_closest_grasps(
            self.target_object, self.placement_pose(), self.robot.right_arm, context
        )
        return sequential([MoveTorsoAction(TorsoState.HIGH), transport], context)

    def perform(
        self, sampling_seed: int = 42, collision_avoidance: bool = True
    ) -> CounterToSinkOutcome:
        """
        Have the PR2 carry the target object into the sink kinematically, and let
        RoboCasa's physics drop it in.

        :param sampling_seed: The seed the standing poses are sampled with.
        :param collision_avoidance: Whether the PR2 avoids colliding with the kitchen
            and with itself while moving.
        :return: How the episode ended.
        """
        plan = self.transport_plan(sampling_seed)
        with ExecutionEnvironment(
            ExecutionType.KINEMATICALLY_SIMULATED,
            collision_avoidance=collision_avoidance,
        ):
            plan.perform()
        self.let_the_target_object_fall()
        return self.outcome()

    def start_physical_simulation(
        self,
        step_size: timedelta = timedelta(milliseconds=2),
        impedance_ratio: float = 10.0,
    ) -> MujocoSim:
        """
        Start simulating the episode's world in MuJoCo, stepped by whatever performs in
        it.

        Friction is resolved in elliptic cones, and the impedance ratio raised above
        MuJoCo's default of one, as MuJoCo's documentation recommends where objects are
        held by friction.

        :param step_size: How much simulated time one physics step advances.
        :param impedance_ratio: How much harder the contacts resist sliding than
            pressing in; MuJoCo's ``impratio``.
        :return: The started simulation; stop it when done.
        """
        simulation = MujocoSim(
            world=self.task.world,
            headless=True,
            step_size=step_size.total_seconds(),
            integrator=mujoco.mjtIntegrator.mjINT_IMPLICITFAST,
            cone=mujoco.mjtCone.mjCONE_ELLIPTIC,
            impratio=impedance_ratio,
        )
        simulation.start_stepped_simulation()
        return simulation

    def perform_in_physics(
        self,
        simulation: MujocoSim,
        sampling_seed: int = 42,
        collision_avoidance: bool = True,
        settling_time: timedelta = timedelta(seconds=2),
    ) -> CounterToSinkOutcome:
        """
        Have the PR2 carry the target object into the sink in a physical simulation,
        where its fingers hold the object by friction alone and the object falls into
        the sink once they let go.

        :param simulation: The started simulation of the episode's world, see
            :meth:`start_physical_simulation`.
        :param sampling_seed: The seed the standing poses are sampled with.
        :param collision_avoidance: Whether the PR2 avoids colliding with the kitchen
            and with itself while moving.
        :param settling_time: How long the physics runs on after the plan, for the
            object to come to rest.
        :return: How the episode ended.
        """
        plan = self.transport_plan(sampling_seed)
        with PhysicallySimulatedRobot(
            simulation=simulation, collision_avoidance=collision_avoidance
        ):
            plan.perform()
        simulation.step_simulation(settling_time)
        return self.outcome()

    def let_the_target_object_fall(self, settling_time: float = 2.0) -> None:
        """
        Let RoboCasa's physics move the released target object until it comes to rest,
        and put it where it landed. An object the robot still holds stays where it is.

        :param settling_time: How many seconds of simulated time the object falls for.
        """
        if not self.target_object_released:
            return
        joint = self.environment.objects[RoboCasaObjectName.TARGET].joints[0]
        self.copy_target_object_pose_into_robocasa()
        simulation = self.environment.sim
        simulation.data.set_joint_qvel(joint, np.zeros(6))
        for _ in range(round(settling_time / simulation.model.opt.timestep)):
            simulation.step()
        x, y, z, quaternion_w, quaternion_x, quaternion_y, quaternion_z = (
            simulation.data.get_joint_qpos(joint)
        )
        self.target_object.root.parent_connection.origin = (
            HomogeneousTransformationMatrix.from_xyz_quaternion(
                x,
                y,
                z,
                quaternion_x,
                quaternion_y,
                quaternion_z,
                quaternion_w,
                reference_frame=self.task.world.root,
            )
        )

    def copy_target_object_pose_into_robocasa(self) -> None:
        """
        Put the target object in RoboCasa's simulation where it stands in the world.
        """
        world_T_object = self.target_object.root.global_pose
        x, y, z, w = world_T_object.quaternion.to_np()
        self.environment.sim.data.set_joint_qpos(
            self.environment.objects[RoboCasaObjectName.TARGET].joints[0],
            np.concatenate([world_T_object.to_np()[:3, 3], [w, x, y, z]]),
        )
        self.environment.sim.forward()

    def outcome(self) -> CounterToSinkOutcome:
        """
        Judge the current state of the world by RoboCasa's own check, after copying the
        pose of the target object into RoboCasa's simulation.

        :return: How the episode stands.
        """
        self.copy_target_object_pose_into_robocasa()
        return CounterToSinkOutcome(
            object_in_sink=bool(
                object_utils.obj_inside_of(
                    self.environment,
                    RoboCasaObjectName.TARGET,
                    self.environment.sink,
                    partial_check=True,
                )
            ),
            object_released=self.target_object_released,
        )


# %% running an episode from the command line


def _parse_arguments() -> argparse.Namespace:
    """
    Parse the command-line arguments selecting the kitchen and how the episode is
    performed.

    :return: The parsed arguments.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--layout",
        default=LayoutType.LAYOUT001.name,
        choices=[layout.name for layout in LayoutType],
        help="RoboCasa kitchen layout to compose the episode in.",
    )
    parser.add_argument(
        "--style",
        default=StyleType.STYLE001.name,
        choices=[style.name for style in StyleType],
        help="RoboCasa visual style of the kitchen.",
    )
    parser.add_argument(
        "--physics",
        action="store_true",
        help="Perform the episode in MuJoCo physics instead of kinematically.",
    )
    parser.add_argument(
        "--collision-avoidance",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Whether the PR2 avoids colliding with the kitchen and with itself.",
    )
    return parser.parse_args()


def main() -> None:
    """
    Compose one episode of the counter to sink task, have the PR2 perform it and report
    how it ended.
    """
    logging.basicConfig(level=logging.INFO, force=True)
    arguments = _parse_arguments()
    episode = CounterToSinkEpisode.compose(
        LayoutType[arguments.layout], StyleType[arguments.style]
    )
    logger.info("Task: %s", episode.task.instruction)
    if not arguments.physics:
        outcome = episode.perform(collision_avoidance=arguments.collision_avoidance)
        logger.info("Outcome: %s, succeeded: %s", outcome, outcome.succeeded)
        return
    simulation = episode.start_physical_simulation()
    outcome = episode.perform_in_physics(
        simulation, collision_avoidance=arguments.collision_avoidance
    )
    simulation.stop_simulation()
    logger.info("Outcome: %s, succeeded: %s", outcome, outcome.succeeded)


if __name__ == "__main__":
    main()
