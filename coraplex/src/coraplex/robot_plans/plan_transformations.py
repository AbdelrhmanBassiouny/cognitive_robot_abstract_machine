from __future__ import annotations

from abc import ABC
from dataclasses import dataclass

from typing_extensions import TYPE_CHECKING, Generic, List, Optional

from coraplex.datastructures.enums import (
    DetectionTechnique,
    InsertionPosition,
    ReachFraction,
)
from coraplex.exceptions import (
    ClosingGoalNotFound,
    ReachHasNoFinalApproach,
    ToolPathNotFound,
)
from coraplex.locations.locations import ReachabilityLocation
from coraplex.plans.underspecified import UnderspecifiedNode
from coraplex.plans.plan_transformation import (
    InsertionTransformation,
    MatchedType,
    PlanTransformation,
)
from coraplex.robot_plans.actions.base import Action
from coraplex.robot_plans.actions.composite.facing import FaceAndLookAtAction
from coraplex.robot_plans.actions.composite.tool_based import ToolMotionAction
from coraplex.robot_plans.actions.composite.transporting import (
    MoveAndOpenAction,
    MoveAndPickUpAction,
    PickAndPlaceAction,
)
from coraplex.robot_plans.actions.core.container import CloseAction, OpenAction
from coraplex.robot_plans.actions.core.misc import DetectAction
from coraplex.robot_plans.actions.core.navigation import (
    DrivesBase,
    FaceAtAction,
    LookAtAction,
    NavigateAction,
)
from coraplex.robot_plans.actions.core.pick_up import PickUpAction, ReachAction
from coraplex.robot_plans.actions.core.robot_body import ParkArmsAction
from cramph.composites import CramLanguageNode, Parallel
from cramph.node import StatechartNode
from giskardpy.motion_statechart.data_types import DefaultWeights
from giskardpy.motion_statechart.goals.cartesian_goals import DifferentialDriveBaseGoal
from giskardpy.motion_statechart.goals.open_close import Close
from giskardpy.motion_statechart.tasks.align_planes import AlignPlanes
from giskardpy.motion_statechart.tasks.cartesian_tasks import (
    CartesianPose,
    CartesianPosition,
    CartesianPositionTrajectory,
)
from krrood.entity_query_language.core.variable import Variable
from krrood.entity_query_language.factories import a, variable
from krrood.entity_query_language.query.match import Match
from krrood.patterns.subclass_safe_generic import SubClassSafeGeneric
from semantic_digital_twin.reasoning.predicates import InsideOf
from semantic_digital_twin.grasping.grasp_candidates import (
    GraspCandidate,
    HasGraspCandidates,
)
from semantic_digital_twin.robots.justin import Justin
from semantic_digital_twin.robots.robot_parts import Arm
from semantic_digital_twin.robots.stretch import Stretch
from semantic_digital_twin.robots.tiago import Tiago
from semantic_digital_twin.semantic_annotations.mixins import HasRootBody
from semantic_digital_twin.semantic_annotations.semantic_annotations import Drawer
from semantic_digital_twin.spatial_types.spatial_types import Pose, Vector3
from coraplex.plans.context_extensions import (
    ExecutionMode,
    RobotAccess,
    StatementGrounding,
)
from cramph.context import StatechartContext

if TYPE_CHECKING:
    from semantic_digital_twin.world import World


# %% perceiving before a grasp


@dataclass
class DetectBeforeGrasp(InsertionTransformation[ReachAction]):
    """
    Looks at the object and detects it before a reach makes its final approach, so that
    the approach acts on a freshly perceived pose instead of the one the world holds.
    """

    @property
    def position(self) -> InsertionPosition:
        return InsertionPosition.BEFORE

    def is_applicable(self, plan_node: ReachAction) -> bool:
        return True

    def final_approach(self, plan_node: ReachAction) -> StatechartNode:
        """
        :param plan_node: The reach
        :raises ReachHasNoFinalApproach: If no step of the reach moves its tool center
            point, which it has none of before it is expanded.
        :return: The last step of the reach moving the tool center point of its arm,
            which brings the gripper onto the object, whatever a transformation put
            after it.
        """
        body = plan_node.action_body
        steps = [] if body is None else body.children
        for step in reversed(steps):
            if self._moves_the_tool_center_point(step, plan_node.arm):
                return step
        raise ReachHasNoFinalApproach(plan_node)

    @staticmethod
    def _moves_the_tool_center_point(step: StatechartNode, arm: Arm) -> bool:
        """
        :return: Whether a Cartesian goal in `step` moves the tool center point of
            `arm`.
        """
        return any(
            isinstance(node, (CartesianPose, CartesianPosition))
            and node.tip_link is arm.end_effector.tool_frame
            for node in [step, *step.descendants]
        )

    def anchor(self, plan_node: ReachAction) -> StatechartNode:
        return self.final_approach(plan_node)

    def nodes_to_insert(self, plan_node: ReachAction) -> List[StatechartNode]:
        approached_pose = plan_node.grasp_pose_sequence(
            plan_node.grasp.grasp_pose, plan_node.arm.end_effector, plan_node.grasp
        ).grasp
        return [
            LookAtAction(approached_pose),
            DetectAction(
                DetectionTechnique.TYPES,
                object_sem_annotation=type(plan_node.grasp.graspable),
                accept_first_if_multiple=True,
            ),
        ]


# %% opening what the object lies in


@dataclass
class DrawerOpening(
    InsertionTransformation[MatchedType],
    Generic[MatchedType],
    SubClassSafeGeneric,
    ABC,
):
    """
    The shared part of the rewrites that open the drawers an object lies in.
    """

    minimum_containment_ratio: float = 0.9
    """
    How much of the object has to lie within a drawer for it to count as being in it.
    """

    minimum_opening_ratio: float = 0.9
    """
    How far along its travel a drawer has to stand pulled out to count as open already.
    """

    @property
    def position(self) -> InsertionPosition:
        return InsertionPosition.BEFORE

    def _closed_drawers_containing(
        self, annotation: HasRootBody, world: World
    ) -> List[Drawer]:
        """
        :param annotation: The object to locate
        :param world: The world the object and the drawers belong to
        :return: The drawers the object lies in that do not already stand open.
        """
        object_body = annotation.root
        return [
            drawer
            for drawer in world.get_semantic_annotations_by_type(Drawer)
            if InsideOf(object_body, drawer.root).compute_containment_ratio()
            > self.minimum_containment_ratio
            and drawer.opening_ratio < self.minimum_opening_ratio
        ]

    def opening_nodes(
        self, drawer: Drawer, arm: Arm, context: StatechartContext
    ) -> List[StatechartNode]:
        """
        :param drawer: The drawer to open
        :param arm: The arm that opens it
        :param context: The context of the statechart the opening is inserted in,
            holding the robot that opens the drawer and the seed its standing pose is
            sampled with
        :return: The opening, from a standing pose tried together with it.
        """
        handle_pose = Pose(reference_frame=drawer.handle.root)
        open_the_drawer = a(MoveAndOpenAction)(
            navigate=a(NavigateAction)(
                target_location=variable(
                    Pose,
                    domain=ReachabilityLocation(
                        handle_pose,
                        arm,
                        ReachFraction.ACCESSING,
                        context=context,
                        seed=context.require_extension(
                            StatementGrounding
                        ).sampling_seed,
                    ),
                )
            ),
            face_and_look_at=a(FaceAndLookAtAction)(
                face_at=a(FaceAtAction)(target=handle_pose),
                look_at=a(LookAtAction)(target=handle_pose),
            ),
            open_container=a(OpenAction)(handle=drawer.handle, arm=arm),
        )
        return [UnderspecifiedNode(statement=open_the_drawer)]

    def anchor(self, plan_node: StatechartNode) -> StatechartNode:
        return plan_node


@dataclass
class OpenDrawerBeforePickUp(DrawerOpening[PickUpAction]):
    """
    Opens the drawers an object lies in before the robot picks it up, so that it reaches
    into an open drawer instead of a closed one.

    Nothing else positions the robot for a pick-up of its own, and opening a drawer
    leaves the robot standing at its handle, so the rewrite ends by parking and driving
    to a pose the object itself can be reached from.
    """

    def is_applicable(self, plan_node: PickUpAction) -> bool:
        return bool(
            self._closed_drawers_containing(plan_node.grasp.graspable, plan_node.world)
        )

    def nodes_to_insert(self, plan_node: PickUpAction) -> List[StatechartNode]:
        graspable = plan_node.grasp.graspable
        nodes = []
        for drawer in self._closed_drawers_containing(graspable, plan_node.world):
            nodes.extend(self.opening_nodes(drawer, plan_node.arm, plan_node.context))
        drive_to_the_object = a(NavigateAction)(
            target_location=variable(
                Pose,
                # A location samples its poses only once the drive is grounded, by
                # which time the drawers this rewrite opens stand open.
                domain=ReachabilityLocation(
                    Pose(reference_frame=graspable.root),
                    plan_node.arm,
                    context=plan_node.context,
                    seed=plan_node.sampling_seed,
                ),
            ),
        )
        nodes.extend(
            [
                ParkArmsAction(plan_node.robot.all_arms),
                UnderspecifiedNode(statement=drive_to_the_object),
            ]
        )
        return nodes


@dataclass
class PickUpTarget:
    """
    The object a pick-up takes hold of, and the arm it takes hold with.
    """

    graspable: HasGraspCandidates
    """
    The object that is picked up.
    """

    arm: Arm
    """
    The arm that picks it up.
    """


@dataclass
class OpenDrawerBeforeMoveAndPickUp(DrawerOpening[MoveAndPickUpAction]):
    """
    Opens the drawers an object lies in before the robot moves to it and picks it up.

    The opening precedes the whole move-and-pick-up, whose own drive then positions the
    robot at the object. When every candidate of a move-and-pick-up still to be grounded
    picks up the same object with the same arm, the drawer is opened once in front of
    it, so every candidate is grounded and tried with the drawer standing open.
    Otherwise each candidate gets its own opening, inside the sequence it is tried in.
    """

    def matches_node(self, plan_node: StatechartNode) -> bool:
        if isinstance(plan_node, UnderspecifiedNode):
            return issubclass(plan_node.statement._type_, MoveAndPickUpAction)
        return super().matches_node(plan_node)

    def is_applicable(
        self, plan_node: MoveAndPickUpAction | UnderspecifiedNode
    ) -> bool:
        target = self._pick_up_target(plan_node)
        return target is not None and bool(
            self._closed_drawers_containing(target.graspable, plan_node.context.world)
        )

    def nodes_to_insert(
        self, plan_node: MoveAndPickUpAction | UnderspecifiedNode
    ) -> List[StatechartNode]:
        target = self._pick_up_target(plan_node)
        nodes = []
        for drawer in self._closed_drawers_containing(
            target.graspable, plan_node.context.world
        ):
            nodes.extend(self.opening_nodes(drawer, target.arm, plan_node.context))
        if isinstance(plan_node, UnderspecifiedNode):
            # The candidates are grounded after the opening, which leaves the arms at
            # the handle, where they would stand in collision at every standing pose.
            robot = plan_node.context.require_extension(RobotAccess).robot
            nodes.append(ParkArmsAction(robot.all_arms))
        return nodes

    def _pick_up_target(
        self, plan_node: MoveAndPickUpAction | UnderspecifiedNode
    ) -> Optional[PickUpTarget]:
        """
        :param plan_node: A node this matches.
        :return: What the move-and-pick-up picks up and with which arm, or ``None`` if
            it is still to be grounded and its candidates differ in either.
        """
        if isinstance(plan_node, UnderspecifiedNode):
            return self._pick_up_target_shared_by_candidates_of(plan_node.statement)
        pick_up = plan_node.pick_up
        return PickUpTarget(graspable=pick_up.grasp.graspable, arm=pick_up.arm)

    @staticmethod
    def _pick_up_target_shared_by_candidates_of(
        move_and_pick_up: Match[MoveAndPickUpAction],
    ) -> Optional[PickUpTarget]:
        """
        :param move_and_pick_up: A move-and-pick-up still to be grounded.
        :return: The object and arm every one of its candidates picks up with, or
            ``None`` if they are not the same for all of them, or not known before
            grounding.
        """
        grasp = move_and_pick_up.pick_up.grasp.apply_mapping_on_external_root(
            move_and_pick_up
        )
        arm = move_and_pick_up.pick_up.arm.apply_mapping_on_external_root(
            move_and_pick_up
        )
        grasps = grasp._domain_ if isinstance(grasp, Variable) else [grasp]
        if not isinstance(arm, Arm):
            return None
        if not all(isinstance(candidate, GraspCandidate) for candidate in grasps):
            return None
        graspables = {candidate.graspable for candidate in grasps}
        if len(graspables) != 1:
            return None
        [graspable] = graspables
        return PickUpTarget(graspable=graspable, arm=arm)


# %% parking around a pick-and-place


@dataclass
class ParkArmsAroundPickAndPlaceSteps(PlanTransformation[PickAndPlaceAction]):
    """
    Parks the robot's arms before the pick-up of a pick-and-place, between it and the
    place, and after the place, so that neither step starts with the arms wherever the
    one before it left them.
    """

    def is_applicable(self, plan_node: PickAndPlaceAction) -> bool:
        return True

    def apply(self, plan_node: PickAndPlaceAction) -> None:
        steps = plan_node.action_body
        for step in list(steps.nodes):
            steps.insert_before(step, ParkArmsAction(plan_node.robot.all_arms))
        steps.insert_after(steps.nodes[-1], ParkArmsAction(plan_node.robot.all_arms))


# %% parking before anything else


@dataclass
class ParkArmsBeforeFirstAction(InsertionTransformation[Action]):
    """
    Parks the robot's arms in front of the first action of a plan.

    An action that is grounded against the world, such as a drive to a pose the object
    can be reached from, judges the robot in the configuration it is in. Arms left
    wherever an earlier plan dropped them stand in collision at every candidate pose,
    which rules out the whole location before it is ever checked for reachability.
    """

    @property
    def position(self) -> InsertionPosition:
        return InsertionPosition.BEFORE

    def is_applicable(self, plan_node: Action) -> bool:
        return self._first_action_of_the_plan_of(plan_node) is plan_node and (
            not isinstance(plan_node, ParkArmsAction)
        )

    def anchor(self, plan_node: Action) -> StatechartNode:
        return plan_node

    def nodes_to_insert(self, plan_node: Action) -> List[StatechartNode]:
        return [ParkArmsAction(plan_node.robot.all_arms)]

    @staticmethod
    def _first_action_of_the_plan_of(node: StatechartNode) -> Optional[Action]:
        """
        :param node: A node of a plan.
        :return: The action of that plan that runs first.
        """
        root = node.path[-1] if node.path else node
        return next(
            (
                candidate
                for candidate in [root, *root.descendants]
                if isinstance(candidate, Action)
            ),
            None,
        )


# %% keeping the torso upright while using a tool


@dataclass
class KeepTheTorsoUprightWhileUsingATool(InsertionTransformation[ToolMotionAction]):
    """
    Keeps Justin's torso upright while it moves a tool, which no other robot needs: its
    torso would otherwise lean into the motion.
    """

    @property
    def position(self) -> InsertionPosition:
        return InsertionPosition.LAST_CHILD

    def is_applicable(self, plan_node: ToolMotionAction) -> bool:
        return isinstance(plan_node.robot, Justin)

    def anchor(self, plan_node: ToolMotionAction) -> StatechartNode:
        """
        :return: The goal holding the tool on its path, beside which the torso is held.
        :raises ToolPathNotFound: If the action holds no goal moving the tool along a
            path.
        """
        for node in plan_node.descendants:
            if isinstance(node, Parallel) and any(
                isinstance(child, CartesianPositionTrajectory) for child in node.nodes
            ):
                return node
        raise ToolPathNotFound(plan_node)

    def nodes_to_insert(self, plan_node: ToolMotionAction) -> List[StatechartNode]:
        root = plan_node.controlled_root
        torso_tip = plan_node.robot.mobile_base.torso.tip
        return [
            AlignPlanes(
                tip_link=torso_tip,
                root_link=root,
                tip_normal=Vector3.X(torso_tip),
                goal_normal=Vector3.Z(root),
                weight=DefaultWeights.WEIGHT_ABOVE_COLLISION_AVOIDANCE.value,
            )
        ]


# %% driving a differential drive


@dataclass
class DriveWithTheDifferentialDrive(PlanTransformation[DrivesBase], ABC):
    """
    Moves the base of a robot with a goal for its differential drive, which turns
    towards a pose, drives there and turns again, instead of a goal that asks the base
    to move sideways.
    """

    def apply(self, plan_node: DrivesBase) -> None:
        plan_node.replace_action_body(
            plan_node.create_body_driving_with(
                lambda target: DifferentialDriveBaseGoal(
                    diff_drive_connection=plan_node.robot.drive,
                    goal_pose=target,
                    threshold=plan_node.base_pose_threshold,
                )
            )
        )


@dataclass
class DriveStretchWithItsDifferentialDrive(DriveWithTheDifferentialDrive):
    """
    Moves the base of a Stretch with a goal for its differential drive, simulated or
    not.
    """

    def is_applicable(self, plan_node: DrivesBase) -> bool:
        return isinstance(plan_node.robot, Stretch)


@dataclass
class DriveSimulatedTiagoWithItsDifferentialDrive(DriveWithTheDifferentialDrive):
    """
    Moves the base of a simulated Tiago with a goal for its differential drive.
    """

    def is_applicable(self, plan_node: DrivesBase) -> bool:
        return (
            isinstance(plan_node.robot, Tiago)
            and plan_node.context.require_extension(ExecutionMode).simulated
        )


# %% closing a container


@dataclass
class KeepStretchInFrontOfTheContainerItCloses(PlanTransformation[CloseAction]):
    """
    Keeps a simulated Stretch standing in front of the container it closes and holding
    on to the handle, so that it closes the container by pushing its arm forward.
    """

    def is_applicable(self, plan_node: CloseAction) -> bool:
        return (
            isinstance(plan_node.robot, Stretch)
            and plan_node.context.require_extension(ExecutionMode).simulated
        )

    @staticmethod
    def closing_goal(plan_node: CloseAction) -> Close:
        """
        :param plan_node: The close action.
        :return: The goal closing the container.
        :raises ClosingGoalNotFound: If the action holds no goal closing a container,
            which it has none of before it is expanded.
        """
        for node in plan_node.descendants:
            if isinstance(node, Close):
                return node
        raise ClosingGoalNotFound(plan_node)

    def apply(self, plan_node: CloseAction) -> None:
        closing_goal = self.closing_goal(plan_node)
        handle = closing_goal.environment_link
        tool_frame = closing_goal.tip_link
        robot_root = plan_node.robot.root
        CramLanguageNode.running(closing_goal).replace(
            closing_goal,
            Parallel(
                [
                    CartesianPose(
                        name="Keep holding handle",
                        root_link=handle,
                        tip_link=tool_frame,
                        goal_pose=Pose(reference_frame=tool_frame),
                    ),
                    AlignPlanes(
                        root_link=plan_node.world.root,
                        tip_link=robot_root,
                        goal_normal=Vector3.X(handle),
                        tip_normal=Vector3.NEGATIVE_Y(robot_root),
                    ),
                    Close(
                        tip_link=tool_frame,
                        environment_link=handle,
                        goal_joint_state=closing_goal.goal_joint_state,
                    ),
                ]
            ),
        )
