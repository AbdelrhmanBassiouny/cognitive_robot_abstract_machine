import logging
from dataclasses import dataclass, field

import numpy as np
import pytest
from typing_extensions import Iterable, List, Optional

from coraplex.datastructures.enums import InsertionPosition, ReachFraction
from coraplex.exceptions import (
    CannotMatchOnType,
    ReachHasNoFinalApproach,
)
from coraplex.plans.plan_transformation import (
    InsertionTransformation,
    PlanRewriting,
    PlanTransformation,
    logger as transformation_logger,
)
from coraplex.plans.underspecified import UnderspecifiedNode
from coraplex.robot_plans.actions.base import Action
from coraplex.robot_plans.actions.composite.facing import FaceAndLookAtAction
from coraplex.robot_plans.actions.composite.transporting import (
    MoveAndOpenAction,
    MoveAndPickUpAction,
    TransportAction,
)
from coraplex.robot_plans.actions.core.misc import DetectAction
from coraplex.robot_plans.actions.core.navigation import (
    FaceAtAction,
    LookAtAction,
    NavigateAction,
)
from coraplex.robot_plans.actions.core.pick_up import PickUpAction, ReachAction
from coraplex.robot_plans.actions.core.placing import PlaceAction
from coraplex.robot_plans.actions.core.robot_body import MoveTorsoAction, ParkArmsAction
from coraplex.robot_plans.plan_transformations import (
    DetectBeforeGrasp,
    FreeEndEffectorsOfParallelStepsTogether,
    OpenDrawerBeforeMoveAndPickUp,
    OpenDrawerBeforePickUp,
    ParkArmsAroundPickAndPlaceSteps,
    ParkArmsBeforeFirstAction,
)
from cramph.composites import Attempt, ChildChooser, CramLanguageNode, Sequence
from cramph.composites import Parallel
from cramph.context import ContextExtension
from cramph.context import StatechartContext
from cramph.exceptions import NotRunByLanguageNodeError
from cramph.node import StatechartNode
from cramph.nodes_for_testing import ConstFalseNode
from giskardpy.motion_statechart.goals.collision_avoidance import (
    UpdateTemporaryCollisionRules,
)
from giskardpy.motion_statechart.goals.gripper import MoveGripper
from giskardpy.motion_statechart.tasks.cartesian_tasks import CartesianPose
from giskardpy.motion_statechart.tasks.joint_tasks import JointPositionList
from krrood.entity_query_language.factories import a, variable
from krrood.entity_query_language.query.match import Match
from krrood.exceptions import UnboundGenericParameter
from semantic_digital_twin.datastructures.definitions import GripperState, TorsoState
from semantic_digital_twin.grasping.grasp_candidates import GraspCandidate
from semantic_digital_twin.robots.pr2 import PR2
from semantic_digital_twin.robots.robot_parts import Arm, EndEffector
from semantic_digital_twin.semantic_annotations.mixins import HasRootBody
from semantic_digital_twin.semantic_annotations.semantic_annotations import (
    Drawer,
    Handle,
    Milk,
    Spoon,
)
from semantic_digital_twin.spatial_types.spatial_types import Pose
from semantic_digital_twin.world import World
from ..test_transporting import pick_and_place_of_the_milk
from ...plan_running import context_of, simulated_executor, statechart_of
from ...sampling import SAMPLING_SEED


# %% expanding a plan without running it


def rewritten(
    plan: StatechartNode,
    extensions: List[ContextExtension],
    plan_transformations: Iterable[PlanTransformation] = (),
) -> StatechartNode:
    """
    Expand `plan` in the statechart that would run it, which also rewrites it with
    `plan_transformations`, without running it.

    :return: The plan, rewritten.
    """
    executor = simulated_executor(
        [*extensions, PlanRewriting(transformations=list(plan_transformations))]
    )
    executor.prepare(statechart_of(executor, plan))
    return plan


def steps_of(node: StatechartNode) -> List[StatechartNode]:
    """
    :param node: An expanded action, or a plan language node.
    :return: The steps it runs, in order, which is its body alone for an action whose
        body is a single node.
    """
    body = node.action_body if isinstance(node, Action) else node
    if not isinstance(body, CramLanguageNode):
        return [body]
    return list(body.nodes)


def kind_of(step: StatechartNode) -> type:
    """
    :param step: A step of an expanded action.
    :return: What the step does: the goal it moves the tool center point or a gripper
        with, even when it runs alongside speed caps or collision rules, else its type.
    """
    for goal_type in (CartesianPose, MoveGripper):
        if any(isinstance(node, goal_type) for node in [step, *step.descendants]):
            return goal_type
    return type(step)


def kinds_of_the_steps_of(node: StatechartNode) -> List[type]:
    """
    :return: What every step of `node` does, see :func:`kind_of`.
    """
    return [kind_of(step) for step in steps_of(node)]


def gripper_goal(end_effector: EndEffector, state: GripperState) -> MoveGripper:
    """
    :return: A new goal moving the gripper of `end_effector` to `state`.
    """
    return MoveGripper(end_effector=end_effector, state=state)


def joint_goal_of(torso_move: MoveTorsoAction) -> JointPositionList:
    """
    :return: The goal an expanded torso move runs.
    """
    [goal] = steps_of(torso_move)
    return goal


# %% transformations under test


@dataclass
class MoveGrippersBeforeTorsoMotion(InsertionTransformation[MoveTorsoAction]):
    """
    Puts two distinguishable gripper goals in front of the goal a torso move expands
    into.
    """

    @property
    def position(self) -> InsertionPosition:
        return InsertionPosition.BEFORE

    def is_applicable(self, plan_node: MoveTorsoAction) -> bool:
        return True

    def anchor(self, plan_node: MoveTorsoAction) -> StatechartNode:
        return joint_goal_of(plan_node)

    def nodes_to_insert(self, plan_node: MoveTorsoAction) -> List[StatechartNode]:
        return [
            gripper_goal(plan_node.robot.left_arm.end_effector, GripperState.OPEN),
            gripper_goal(plan_node.robot.right_arm.end_effector, GripperState.CLOSE),
        ]


@dataclass
class MoveGrippersAfterTorsoMotion(MoveGrippersBeforeTorsoMotion):
    """
    Puts the same gripper goals behind that goal instead.
    """

    @property
    def position(self) -> InsertionPosition:
        return InsertionPosition.AFTER


@dataclass
class ParkArmsBeforeTorsoMotion(InsertionTransformation[MoveTorsoAction]):
    """
    Puts an action, which expands in turn, in front of the goal a torso move expands
    into.
    """

    @property
    def position(self) -> InsertionPosition:
        return InsertionPosition.BEFORE

    def is_applicable(self, plan_node: MoveTorsoAction) -> bool:
        return True

    def anchor(self, plan_node: MoveTorsoAction) -> StatechartNode:
        return joint_goal_of(plan_node)

    def nodes_to_insert(self, plan_node: MoveTorsoAction) -> List[StatechartNode]:
        return [ParkArmsAction(plan_node.robot.all_arms)]


@dataclass
class MoveGripperLastInTheReachBody(InsertionTransformation[ReachAction]):
    """
    Puts a gripper goal at the end of the sequence a reach expands into.
    """

    @property
    def position(self) -> InsertionPosition:
        return InsertionPosition.LAST_CHILD

    def is_applicable(self, plan_node: ReachAction) -> bool:
        return True

    def anchor(self, plan_node: ReachAction) -> StatechartNode:
        return plan_node.action_body

    def nodes_to_insert(self, plan_node: ReachAction) -> List[StatechartNode]:
        return [
            gripper_goal(plan_node.robot.right_arm.end_effector, GripperState.CLOSE)
        ]


def reach_action(milk: Milk, view) -> ReachAction:
    """
    :param milk: The object the reach is aimed at.
    :param view: The robot reaching for it.
    :return: A reach at the object's own frame.
    """
    return ReachAction(grasp=GraspCandidate.from_body_origin(milk), arm=view.right_arm)


def detect_actions_of(plan: StatechartNode) -> List[DetectAction]:
    """
    :return: The detections the expanded `plan` performs.
    """
    return [node for node in plan.descendants if isinstance(node, DetectAction)]


# %% what makes a transformation


@dataclass
class TransformationWithoutRewrite(PlanTransformation[MoveTorsoAction]):
    """
    Says which nodes it applies to without saying how to rewrite the plan around them.
    """

    def is_applicable(self, plan_node: MoveTorsoAction) -> bool:
        return True


@dataclass
class TransformationWithoutApplicability(PlanTransformation[MoveTorsoAction]):
    """
    Rewrites the plan without saying whether the case at hand needs it.
    """

    def apply(self, plan_node: MoveTorsoAction) -> None:
        pass


@dataclass
class MoveGripperBeforeEveryAction(InsertionTransformation[Action]):
    """
    Puts a gripper goal in front of every action, whatever its type.
    """

    @property
    def position(self) -> InsertionPosition:
        return InsertionPosition.BEFORE

    def is_applicable(self, plan_node: Action) -> bool:
        return True

    def anchor(self, plan_node: Action) -> StatechartNode:
        return plan_node

    def nodes_to_insert(self, plan_node: Action) -> List[StatechartNode]:
        return [
            gripper_goal(plan_node.robot.right_arm.end_effector, GripperState.CLOSE)
        ]


@dataclass
class TransformationWithoutPosition(InsertionTransformation[MoveTorsoAction]):
    """
    Inserts nodes without saying where they go.
    """

    def anchor(self, plan_node: MoveTorsoAction) -> StatechartNode:
        return plan_node

    def nodes_to_insert(self, plan_node: MoveTorsoAction) -> List[StatechartNode]:
        return [gripper_goal(plan_node.robot.left_arm.end_effector, GripperState.OPEN)]


@dataclass
class TransformationWithoutMatchedType(PlanTransformation):
    """
    Rewrites nothing and binds no type, to be asked what it matches.
    """

    def is_applicable(self, plan_node: StatechartNode) -> bool:
        return True

    def apply(self, plan_node: StatechartNode) -> None:
        pass


@dataclass
class TransformationOnAnUnmatchableType(PlanTransformation[GraspCandidate]):
    """
    Binds a type that is no statechart node.
    """

    def is_applicable(self, plan_node: StatechartNode) -> bool:
        return True

    def apply(self, plan_node: StatechartNode) -> None:
        pass


def test_a_transformation_that_binds_no_type_cannot_say_what_it_matches():
    """
    Which nodes it applies to is part of what a transformation is, so one that binds no
    type has nothing to match on rather than matching every node.
    """
    with pytest.raises(UnboundGenericParameter):
        TransformationWithoutMatchedType().matched_type


def test_a_transformation_bound_to_an_unmatchable_type_is_rejected():
    """
    A transformation selects its nodes by their type, so a type that is no statechart
    node leaves no rule to select by.
    """
    with pytest.raises(CannotMatchOnType):
        TransformationOnAnUnmatchableType().matches_node(
            MoveTorsoAction(TorsoState.HIGH)
        )


def test_a_transformation_that_says_no_rewrite_cannot_be_built():
    """
    How it changes the plan is part of what a transformation is, so one that only says
    which nodes it applies to is incomplete.
    """
    with pytest.raises(TypeError):
        TransformationWithoutRewrite()


def test_a_transformation_that_says_no_applicability_cannot_be_built():
    """
    Whether the case at hand needs it is part of what a transformation is, so one that
    leaves it unsaid is incomplete rather than applying to every case it matches.
    """
    with pytest.raises(TypeError):
        TransformationWithoutApplicability()


def test_a_transformation_that_says_no_position_cannot_be_built():
    """
    Where an insertion goes is part of what the transformation is, so one that leaves it
    unsaid is incomplete rather than placed somewhere by default.
    """
    with pytest.raises(TypeError):
        TransformationWithoutPosition()


@dataclass
class MoveGripperBeforeHighTorso(InsertionTransformation[MoveTorsoAction]):
    """
    Puts a gripper goal in front of a torso move, but only when the torso goes up.
    """

    @property
    def position(self) -> InsertionPosition:
        return InsertionPosition.BEFORE

    def is_applicable(self, plan_node: MoveTorsoAction) -> bool:
        return plan_node.torso_state is TorsoState.HIGH

    def anchor(self, plan_node: MoveTorsoAction) -> StatechartNode:
        return joint_goal_of(plan_node)

    def nodes_to_insert(self, plan_node: MoveTorsoAction) -> List[StatechartNode]:
        return [gripper_goal(plan_node.robot.left_arm.end_effector, GripperState.OPEN)]


def test_a_transformation_the_case_needs_is_applied(pr2_apartment_context):
    """
    A node the transformation matches and whose case needs it is rewritten.
    """
    world, view, extensions = pr2_apartment_context
    plan_transformations = [MoveGripperBeforeHighTorso()]

    plan = rewritten(MoveTorsoAction(TorsoState.HIGH), extensions, plan_transformations)

    assert kinds_of_the_steps_of(plan) == [MoveGripper, JointPositionList]


def test_a_transformation_the_case_does_not_need_is_skipped(pr2_apartment_context):
    """
    Matching the node type is not enough: a case that does not need the transformation
    keeps the plan the action describes itself.
    """
    world, view, extensions = pr2_apartment_context
    plan_transformations = [MoveGripperBeforeHighTorso()]

    plan = rewritten(MoveTorsoAction(TorsoState.LOW), extensions, plan_transformations)

    assert kinds_of_the_steps_of(plan) == [JointPositionList]


def test_a_transformation_bound_to_a_base_type_reaches_every_action(
    pr2_apartment_context,
):
    """
    Binding the base type of all actions selects actions of every type, which a binding
    to one action type cannot express.
    """
    world, view, extensions = pr2_apartment_context
    plan_transformations = [MoveGripperBeforeEveryAction()]

    plan = rewritten(
        Sequence([MoveTorsoAction(TorsoState.HIGH), ParkArmsAction(view.all_arms)]),
        extensions,
        plan_transformations,
    )

    assert kinds_of_the_steps_of(plan) == [
        MoveGripper,
        MoveTorsoAction,
        MoveGripper,
        ParkArmsAction,
    ]


def test_a_transformation_bound_to_an_action_type_selects_the_actions_of_it(
    pr2_apartment_context,
):
    """
    A transformation bound to an action type reports that type and selects the actions
    of it, leaving every other node alone.
    """
    world, view, extensions = pr2_apartment_context
    transformation = MoveGrippersBeforeTorsoMotion()
    torso = MoveTorsoAction(TorsoState.HIGH)
    parking = ParkArmsAction(view.all_arms)

    assert transformation.matched_type is MoveTorsoAction
    assert transformation.matches_node(torso)
    assert not transformation.matches_node(parking)


def test_a_transformation_bound_to_the_base_type_selects_every_action(
    pr2_apartment_context,
):
    """
    A transformation bound to the base type of all actions reports that type and selects
    every action, but not the language node holding them.
    """
    world, view, extensions = pr2_apartment_context
    transformation = MoveGripperBeforeEveryAction()
    torso = MoveTorsoAction(TorsoState.HIGH)

    assert transformation.matched_type is Action
    assert transformation.matches_node(torso)
    assert not transformation.matches_node(Sequence([torso]))


# %% inserting


def test_a_transformation_inserts_its_nodes_before_the_anchor(pr2_apartment_context):
    """
    The nodes are placed in front of the anchor, keeping the order the transformation
    gives them.
    """
    world, view, extensions = pr2_apartment_context
    plan_transformations = [MoveGrippersBeforeTorsoMotion()]

    plan = rewritten(MoveTorsoAction(TorsoState.HIGH), extensions, plan_transformations)

    steps = steps_of(plan)
    assert [kind_of(step) for step in steps] == [
        MoveGripper,
        MoveGripper,
        JointPositionList,
    ]
    assert [step.end_effector for step in steps[:2]] == [
        view.left_arm.end_effector,
        view.right_arm.end_effector,
    ]


def test_a_transformation_inserts_its_nodes_after_the_anchor(pr2_apartment_context):
    """
    Inserting after the anchor keeps the given order too, rather than reversing it by
    pushing every node into the same place behind the anchor.
    """
    world, view, extensions = pr2_apartment_context
    plan_transformations = [MoveGrippersAfterTorsoMotion()]

    plan = rewritten(MoveTorsoAction(TorsoState.HIGH), extensions, plan_transformations)

    steps = steps_of(plan)
    assert [kind_of(step) for step in steps] == [
        JointPositionList,
        MoveGripper,
        MoveGripper,
    ]
    assert [step.end_effector for step in steps[1:]] == [
        view.left_arm.end_effector,
        view.right_arm.end_effector,
    ]


def test_a_transformation_inserts_its_nodes_as_the_last_child_of_the_anchor(
    pr2_apartment_context,
):
    """
    Inserting as the last child makes the node a child of the anchor instead of its
    sibling.
    """
    world, view, extensions = pr2_apartment_context
    milk = world.get_semantic_annotations_by_type(Milk)[0]
    plan_transformations = [MoveGripperLastInTheReachBody()]

    plan = rewritten(reach_action(milk, view), extensions, plan_transformations)

    assert kinds_of_the_steps_of(plan) == [CartesianPose, CartesianPose, MoveGripper]


def test_a_transformation_leaves_actions_of_another_type_alone(pr2_apartment_context):
    """
    A transformation bound to one action type must not rewrite the plan of another one.
    """
    world, view, extensions = pr2_apartment_context
    plan_transformations = [MoveGrippersBeforeTorsoMotion()]

    plan = rewritten(ParkArmsAction(view.all_arms), extensions, plan_transformations)

    assert [node for node in plan.descendants if isinstance(node, MoveGripper)] == []


def test_an_inserted_action_is_expanded(pr2_apartment_context):
    """
    The inserted nodes join the statechart, so an inserted action is expanded like any
    other instead of staying an unexpanded leaf.
    """
    world, view, extensions = pr2_apartment_context
    plan_transformations = [ParkArmsBeforeTorsoMotion()]

    plan = rewritten(MoveTorsoAction(TorsoState.HIGH), extensions, plan_transformations)

    [park] = [node for node in plan.descendants if isinstance(node, ParkArmsAction)]
    assert kinds_of_the_steps_of(park) == [JointPositionList]


def test_a_neighbour_of_a_node_no_language_node_runs_is_rejected(
    pr2_apartment_context,
):
    """
    Only a plan language node can hold a new neighbour, so a plan that is a single
    action has no place for one in front of it.
    """
    world, view, extensions = pr2_apartment_context
    plan_transformations = [MoveGripperBeforeEveryAction()]

    with pytest.raises(NotRunByLanguageNodeError):
        rewritten(MoveTorsoAction(TorsoState.HIGH), extensions, plan_transformations)


# %% detecting before a grasp


def test_the_detection_asks_for_the_object_being_reached_for(pr2_apartment_context):
    """
    The detection has to ask for the object the reach was given, so that a plan grasping
    something else does not query for the wrong thing.
    """
    world, view, extensions = pr2_apartment_context
    milk = world.get_semantic_annotations_by_type(Milk)[0]
    plan_transformations = [DetectBeforeGrasp()]

    plan = rewritten(reach_action(milk, view), extensions, plan_transformations)

    [detection] = detect_actions_of(plan)
    assert detection.object_sem_annotation is type(milk)


def test_the_perception_precedes_the_final_approach(pr2_apartment_context):
    """
    Perceiving is only worth anything before the approach it corrects, so the look and
    the detection go in front of the reach's last step.
    """
    world, view, extensions = pr2_apartment_context
    milk = world.get_semantic_annotations_by_type(Milk)[0]
    plan_transformations = [DetectBeforeGrasp()]

    plan = rewritten(reach_action(milk, view), extensions, plan_transformations)

    assert kinds_of_the_steps_of(plan) == [
        CartesianPose,
        LookAtAction,
        DetectAction,
        CartesianPose,
    ]


def test_the_perception_precedes_the_final_approach_a_step_was_put_behind(
    pr2_apartment_context,
):
    """
    The final approach is the last step moving the tool center point, so a step another
    transformation put behind it does not take its place.
    """
    world, view, extensions = pr2_apartment_context
    milk = world.get_semantic_annotations_by_type(Milk)[0]
    plan_transformations = [MoveGripperLastInTheReachBody(), DetectBeforeGrasp()]

    plan = rewritten(reach_action(milk, view), extensions, plan_transformations)

    assert kinds_of_the_steps_of(plan) == [
        CartesianPose,
        LookAtAction,
        DetectAction,
        CartesianPose,
        MoveGripper,
    ]


def test_a_reach_not_yet_expanded_has_no_final_approach(pr2_apartment_context):
    world, view, extensions = pr2_apartment_context
    milk = world.get_semantic_annotations_by_type(Milk)[0]

    with pytest.raises(ReachHasNoFinalApproach):
        DetectBeforeGrasp().final_approach(reach_action(milk, view))


def test_a_reach_does_not_perceive_without_the_transformation(pr2_apartment_context):
    """
    A reach acts on the pose the world already holds, so it must not spend a detection
    the caller did not ask for.
    """
    world, view, extensions = pr2_apartment_context
    milk = world.get_semantic_annotations_by_type(Milk)[0]

    plan = rewritten(reach_action(milk, view), extensions)

    assert detect_actions_of(plan) == []


def test_a_transformation_on_reaches_also_fires_inside_a_pick_up(pr2_apartment_context):
    """
    The reach a pick-up builds is expanded like any other, so a transformation on
    reaches reaches it without the pick-up having to pass anything down.
    """
    world, view, extensions = pr2_apartment_context
    milk = world.get_semantic_annotations_by_type(Milk)[0]
    plan_transformations = [DetectBeforeGrasp()]

    plan = rewritten(
        PickUpAction(milk.grasp_candidates()[0], view.right_arm),
        extensions,
        plan_transformations,
    )

    [detection] = detect_actions_of(plan)
    assert detection.object_sem_annotation is type(milk)


# %% opening the drawer an object lies in

OPENED_DRAWER_POSITION = 0.3
"""
How far the drawer is pulled out after an opening of it has been built.
"""


def drawer_holding(annotation: HasRootBody, world: World) -> Drawer:
    """
    :param annotation: The object lying in a drawer.
    :param world: The world both belong to.
    :return: The drawer the object hangs under.
    """
    [drawer] = [
        candidate
        for candidate in world.get_semantic_annotations_by_type(Drawer)
        if candidate.root is annotation.root.parent_connection.parent
    ]
    return drawer


def pick_up_action(annotation, arm: Arm) -> PickUpAction:
    """
    :param annotation: The object to pick up.
    :param arm: The arm to pick it up with.
    :return: A pick-up of the object by the first grasp it offers.
    """
    return PickUpAction(annotation.grasp_candidates()[0], arm)


def handle_opened_by(opening: Match) -> Handle:
    """
    :param opening: The step that opens a drawer.
    :return: The handle it opens the drawer by.
    """
    return opening._kwargs_["open_container"]._kwargs_["handle"]


def arm_opening_with(opening: Match) -> Arm:
    """
    :param opening: The step that opens a drawer.
    :return: The arm it opens the drawer with.
    """
    return opening._kwargs_["open_container"]._kwargs_["arm"]


def is_grounding(step: StatechartNode, action_type: type) -> bool:
    """
    :return: Whether `step` grounds an action of `action_type` when it runs.
    """
    return isinstance(step, UnderspecifiedNode) and step.statement._type_ is action_type


def test_the_drawer_is_only_opened_for_an_object_that_lies_in_one(
    pr2_apartment_context,
):
    """
    Opening a drawer is worth doing only for an object lying in one, so the pick-up of
    the spoon needs the transformation and the pick-up of the milk does not.
    """
    world, view, extensions = pr2_apartment_context
    spoon = world.get_semantic_annotations_by_type(Spoon)[0]
    milk = world.get_semantic_annotations_by_type(Milk)[0]
    transformation = OpenDrawerBeforePickUp()

    in_a_drawer = pick_up_action(spoon, view.right_arm)
    in_the_open = pick_up_action(milk, view.right_arm)
    rewritten(Sequence([in_a_drawer, in_the_open]), extensions)

    assert transformation.is_applicable(in_a_drawer)
    assert not transformation.is_applicable(in_the_open)


def test_a_drawer_reports_how_far_it_stands_open(pr2_apartment_context):
    """
    How far a drawer stands open is read from its own travel, so it stands none of the
    way open at the lower limit of its joint and all of the way at the upper one.
    """
    world, view, extensions = pr2_apartment_context
    spoon = world.get_semantic_annotations_by_type(Spoon)[0]
    drawer = drawer_holding(spoon, world)
    connection = drawer.root.parent_connection

    connection.position = connection.dof.limits.lower.position
    world.notify_state_change()
    assert drawer.opening_ratio == 0

    connection.position = connection.dof.limits.upper.position
    world.notify_state_change()
    assert drawer.opening_ratio == 1


def test_a_drawer_that_already_stands_open_needs_no_opening(pr2_apartment_context):
    """
    The opening is worth doing only while the drawer is shut, so a drawer that already
    stands open leaves the pick-up as it is.
    """
    world, view, extensions = pr2_apartment_context
    spoon = world.get_semantic_annotations_by_type(Spoon)[0]
    drawer = drawer_holding(spoon, world)
    transformation = OpenDrawerBeforePickUp()

    pick_up = pick_up_action(spoon, view.right_arm)
    rewritten(Sequence([pick_up]), extensions)
    assert transformation.is_applicable(pick_up)

    connection = drawer.root.parent_connection
    connection.position = connection.dof.limits.upper.position
    world.notify_state_change()

    assert not transformation.is_applicable(pick_up)


def test_opening_a_drawer_tries_its_standing_pose_with_the_opening(
    pr2_apartment_context,
):
    """
    Where the robot stands decides whether the handle can be reached, so the standing
    pose is tried together with the opening rather than chosen before it.
    """
    world, view, extensions = pr2_apartment_context
    drawer = drawer_holding(world.get_semantic_annotations_by_type(Spoon)[0], world)

    [opening] = OpenDrawerBeforeMoveAndPickUp().opening_nodes(
        drawer, view.right_arm, simulated_executor(extensions).context
    )

    assert is_grounding(opening, MoveAndOpenAction)
    assert handle_opened_by(opening.statement) is drawer.handle


def test_opening_a_drawer_stands_where_it_is_opened_from(pr2_apartment_context):
    """
    The robot stands back for opening a container the way it does for any container,
    rather than as close as it would to grasp something that stays put.
    """
    world, view, extensions = pr2_apartment_context
    drawer = drawer_holding(world.get_semantic_annotations_by_type(Spoon)[0], world)

    [opening] = OpenDrawerBeforeMoveAndPickUp().opening_nodes(
        drawer, view.right_arm, simulated_executor(extensions).context
    )
    standing_positions = (
        opening.statement._kwargs_["navigate"]._kwargs_["target_location"]._domain_
    )
    location = standing_positions.domain

    assert location.reach_fraction == ReachFraction.ACCESSING


def test_opening_a_drawer_faces_the_handle_where_it_is_when_it_opens_it(
    pr2_apartment_context,
):
    """
    The opening runs after whatever came before it in the plan, so it turns to the
    handle where that left it rather than where it was when the opening was built.
    """
    world, view, extensions = pr2_apartment_context
    drawer = drawer_holding(world.get_semantic_annotations_by_type(Spoon)[0], world)
    [opening] = OpenDrawerBeforeMoveAndPickUp().opening_nodes(
        drawer, view.right_arm, simulated_executor(extensions).context
    )

    drawer.root.parent_connection.position = OPENED_DRAWER_POSITION
    world.notify_state_change()

    facing = opening.statement._kwargs_["face_and_look_at"]._kwargs_
    for target in [
        facing["face_at"]._kwargs_["target"],
        facing["look_at"]._kwargs_["target"],
    ]:
        np.testing.assert_allclose(
            world.transform(target, world.root).position.to_np(),
            drawer.handle.root.global_pose.position.to_np(),
        )


def test_the_drawer_is_opened_before_a_move_and_pick_up_rather_than_inside_it(
    pr2_apartment_context,
):
    """
    A move-and-pick-up drives to the object before picking it up, so the opening
    precedes the whole step, whose own drive then positions the robot at the object.
    """
    world, view, extensions = pr2_apartment_context
    spoon = world.get_semantic_annotations_by_type(Spoon)[0]
    drawer = drawer_holding(spoon, world)
    plan_transformations = [OpenDrawerBeforeMoveAndPickUp()]

    move_and_pick_up = MoveAndPickUpAction.from_standing_position(
        standing_position=Pose(reference_frame=world.root),
        grasp=spoon.grasp_candidates()[0],
        arm=view.right_arm,
    )
    plan = rewritten(Sequence([move_and_pick_up]), extensions, plan_transformations)

    [opening, moved_and_picked_up] = steps_of(plan)
    assert is_grounding(opening, MoveAndOpenAction)
    assert handle_opened_by(opening.statement) is drawer.handle
    assert moved_and_picked_up is move_and_pick_up


def test_the_drawer_the_object_lies_in_is_opened_before_the_pick_up(
    pr2_apartment_context,
):
    """
    A drawer has to stand open before the gripper goes in, so the opening precedes the
    pick-up, followed by the drive back to where the object can be reached from.
    """
    world, view, extensions = pr2_apartment_context
    spoon = world.get_semantic_annotations_by_type(Spoon)[0]
    drawer = drawer_holding(spoon, world)
    plan_transformations = [OpenDrawerBeforePickUp()]

    plan = rewritten(
        Sequence([pick_up_action(spoon, view.right_arm)]),
        extensions,
        plan_transformations,
    )

    [opening, parking, drive_to_the_spoon, pick_up] = steps_of(plan)
    assert is_grounding(opening, MoveAndOpenAction)
    assert handle_opened_by(opening.statement) is drawer.handle
    assert isinstance(parking, ParkArmsAction)
    assert is_grounding(drive_to_the_spoon, NavigateAction)
    assert isinstance(pick_up, PickUpAction)


def test_the_actions_beside_the_pick_up_are_expanded(pr2_apartment_context):
    """
    The rewrite is inserted beside the node being rewritten rather than below it, and
    the actions in it are expanded all the same.
    """
    world, view, extensions = pr2_apartment_context
    spoon = world.get_semantic_annotations_by_type(Spoon)[0]
    plan_transformations = [OpenDrawerBeforePickUp()]

    plan = rewritten(
        Sequence([pick_up_action(spoon, view.right_arm)]),
        extensions,
        plan_transformations,
    )

    [_, parking, _, _] = steps_of(plan)
    assert kinds_of_the_steps_of(parking) == [JointPositionList]


def test_the_drawer_is_opened_with_the_arm_that_picks_up(pr2_apartment_context):
    """
    Opening with the other arm would leave the robot holding the handle it has to reach
    past, so the opening takes the arm the pick-up was given.
    """
    world, view, extensions = pr2_apartment_context
    spoon = world.get_semantic_annotations_by_type(Spoon)[0]
    plan_transformations = [OpenDrawerBeforePickUp()]

    pick_up = pick_up_action(spoon, view.left_arm)
    plan = rewritten(Sequence([pick_up]), extensions, plan_transformations)

    [opening] = [
        step for step in steps_of(plan) if is_grounding(step, MoveAndOpenAction)
    ]
    assert arm_opening_with(opening.statement) is pick_up.arm


def test_an_object_that_lies_in_no_drawer_is_picked_up_unchanged(pr2_apartment_context):
    """
    An object standing in the open needs no drawer opened for it, so the pick-up keeps
    the plan it describes itself.
    """
    world, view, extensions = pr2_apartment_context
    milk = world.get_semantic_annotations_by_type(Milk)[0]
    plan_transformations = [OpenDrawerBeforePickUp()]
    pick_up = pick_up_action(milk, view.right_arm)

    plan = rewritten(Sequence([pick_up]), extensions, plan_transformations)

    assert steps_of(plan) == [pick_up]


@dataclass
class ChoosesTheGivenChild(ChildChooser):
    """
    Answers a node choosing its child with the child it was given, once.
    """

    child: Optional[StatechartNode] = field(default=None)
    """
    The child handed over, None once it was.
    """

    def choose_child(
        self, node: UnderspecifiedNode, context: StatechartContext
    ) -> Optional[StatechartNode]:
        child, self.child = self.child, None
        return child


def test_the_opening_joins_the_sequence_a_grounded_pick_up_runs_in(
    pr2_apartment_context,
):
    """
    A pick-up written as an underspecified statement is grounded into a candidate while
    the plan runs, and the candidate runs in a sequence of its own.

    The opening has to land in that sequence, otherwise it is not run with the
    candidate.
    """
    world, view, extensions = pr2_apartment_context
    spoon = world.get_semantic_annotations_by_type(Spoon)[0]
    drawer = drawer_holding(spoon, world)
    plan_transformations = [ParkArmsBeforeFirstAction()]
    plan_transformations.append(OpenDrawerBeforePickUp())

    described = pick_up_action(spoon, view.right_arm)
    underspecified = UnderspecifiedNode(
        statement=a(PickUpAction)(grasp=described.grasp, arm=described.arm)
    )
    plan = rewritten(Sequence([underspecified]), extensions, plan_transformations)
    candidate = pick_up_action(spoon, view.right_arm)
    candidate_steps = Sequence([candidate])

    underspecified.choose_child_with(
        ChoosesTheGivenChild(
            child=Attempt(task=candidate_steps, failure_monitors=[ConstFalseNode()])
        ),
        plan.statechart.context,
    )

    [parking, opening, parking_again, drive_to_the_spoon, chosen] = steps_of(
        candidate_steps
    )
    assert chosen is candidate
    assert isinstance(parking, ParkArmsAction)
    assert is_grounding(opening, MoveAndOpenAction)
    assert handle_opened_by(opening.statement) is drawer.handle
    assert isinstance(parking_again, ParkArmsAction)
    assert is_grounding(drive_to_the_spoon, NavigateAction)


def test_the_first_action_of_a_plan_is_preceded_by_parking(pr2_apartment_context):
    world, view, extensions = pr2_apartment_context
    plan_transformations = [ParkArmsBeforeFirstAction()]

    plan = rewritten(
        Sequence([MoveTorsoAction(TorsoState.HIGH)]), extensions, plan_transformations
    )

    assert kinds_of_the_steps_of(plan) == [ParkArmsAction, MoveTorsoAction]


def underspecified_move_and_pick_up_in(plan: StatechartNode) -> UnderspecifiedNode:
    """
    :param plan: A node whose descendants hold one move-and-pick-up left to be grounded.
    :return: That move-and-pick-up's node.
    """
    [move_and_pick_up] = [
        node for node in plan.descendants if is_grounding(node, MoveAndPickUpAction)
    ]
    return move_and_pick_up


def step_before(step: StatechartNode) -> StatechartNode:
    """
    :param step: A step that is not the first of the language node running it.
    :return: The step directly in front of it.
    """
    siblings = steps_of(step.parent_node)
    position = next(index for index, sibling in enumerate(siblings) if sibling is step)
    return siblings[position - 1]


def test_the_drawer_is_opened_once_in_front_of_a_move_and_pick_up_still_to_be_grounded(
    pr2_apartment_context,
):
    """
    Every grasp of the move-and-pick-up is on the spoon, so the drawer is opened in
    front of the step before it is grounded and the arms are parked again, so every
    candidate is tried with the drawer open and the arms out of the way.
    """
    world, view, extensions = pr2_apartment_context
    spoon = world.get_semantic_annotations_by_type(Spoon)[0]
    drawer = drawer_holding(spoon, world)
    plan_transformations = [OpenDrawerBeforeMoveAndPickUp()]

    move_and_pick_up = MoveAndPickUpAction.from_graspable_by_closest_grasps(
        spoon, view.right_arm, context_of(extensions), seed=SAMPLING_SEED
    )
    plan = rewritten(
        Sequence([UnderspecifiedNode(statement=move_and_pick_up)]),
        extensions,
        plan_transformations,
    )

    [opening, parking, still_to_be_grounded] = steps_of(plan)
    assert is_grounding(opening, MoveAndOpenAction)
    assert handle_opened_by(opening.statement) is drawer.handle
    assert arm_opening_with(opening.statement) is view.right_arm
    assert isinstance(parking, ParkArmsAction)
    assert still_to_be_grounded.statement is move_and_pick_up


def test_the_drawer_is_opened_in_front_of_a_transports_pick_up_before_it_is_grounded(
    pr2_apartment_context,
):
    """
    A transport's pick-up is a move-and-pick-up still to be grounded, so the drawer is
    opened once in front of it instead of with each of its candidates.
    """
    world, view, extensions = pr2_apartment_context
    spoon = world.get_semantic_annotations_by_type(Spoon)[0]
    drawer = drawer_holding(spoon, world)
    plan_transformations = [OpenDrawerBeforeMoveAndPickUp()]

    transport = TransportAction.from_graspable_by_closest_grasps(
        spoon,
        Pose(reference_frame=world.root),
        view.right_arm,
        context_of(extensions),
        seed=SAMPLING_SEED,
    )
    plan = rewritten(Sequence([transport]), extensions, plan_transformations)

    parking = step_before(underspecified_move_and_pick_up_in(plan))
    opening = step_before(parking)
    assert isinstance(parking, ParkArmsAction)
    assert is_grounding(opening, MoveAndOpenAction)
    assert handle_opened_by(opening.statement) is drawer.handle
    assert arm_opening_with(opening.statement) is view.right_arm


def test_a_move_and_pick_up_whose_grasps_are_on_several_objects_is_opened_per_candidate(
    pr2_apartment_context,
):
    """
    Which drawer has to be opened depends on the object each candidate picks up, so
    nothing is opened before grounding; each candidate is rewritten on its own.
    """
    world, view, extensions = pr2_apartment_context
    spoon = world.get_semantic_annotations_by_type(Spoon)[0]
    milk = world.get_semantic_annotations_by_type(Milk)[0]
    plan_transformations = [OpenDrawerBeforeMoveAndPickUp()]

    standing_pose = Pose(reference_frame=world.root)
    move_and_pick_up = a(MoveAndPickUpAction)(
        navigate=NavigateAction(standing_pose),
        face_and_look_at=FaceAndLookAtAction(
            face_at=FaceAtAction(standing_pose), look_at=LookAtAction(standing_pose)
        ),
        pick_up=a(PickUpAction)(
            grasp=variable(
                GraspCandidate,
                domain=spoon.grasp_candidates() + milk.grasp_candidates(),
            ),
            arm=view.right_arm,
        ),
    )
    plan = rewritten(
        Sequence([UnderspecifiedNode(statement=move_and_pick_up)]),
        extensions,
        plan_transformations,
    )

    [still_to_be_grounded] = steps_of(plan)
    assert still_to_be_grounded.statement is move_and_pick_up


def test_a_move_and_pick_up_of_an_object_in_no_drawer_is_left_alone(
    pr2_apartment_context,
):
    world, view, extensions = pr2_apartment_context
    milk = world.get_semantic_annotations_by_type(Milk)[0]
    plan_transformations = [OpenDrawerBeforeMoveAndPickUp()]
    move_and_pick_up = MoveAndPickUpAction.from_standing_position(
        standing_position=Pose(reference_frame=world.root),
        grasp=milk.grasp_candidates()[0],
        arm=view.right_arm,
    )

    plan = rewritten(Sequence([move_and_pick_up]), extensions, plan_transformations)

    assert steps_of(plan) == [move_and_pick_up]


def test_a_transport_of_an_object_in_no_drawer_is_left_alone(pr2_apartment_context):
    world, view, extensions = pr2_apartment_context
    milk = world.get_semantic_annotations_by_type(Milk)[0]
    plan_transformations = [OpenDrawerBeforeMoveAndPickUp()]
    transport = TransportAction.from_graspable_by_closest_grasps(
        milk,
        Pose(reference_frame=world.root),
        view.right_arm,
        context_of(extensions),
        seed=SAMPLING_SEED,
    )

    plan = rewritten(Sequence([transport]), extensions, plan_transformations)

    assert isinstance(
        step_before(underspecified_move_and_pick_up_in(plan)), ParkArmsAction
    )


# %% parking around a pick-and-place


def step_types_of(action: Action) -> List[type]:
    """
    :param action: An expanded composite action.
    :return: The type of each step the action runs, in the order they are run, the type
        of the action a step grounds when it is still to be grounded.
    """
    return [
        (step.statement._type_ if isinstance(step, UnderspecifiedNode) else type(step))
        for step in steps_of(action)
    ]


def test_a_pick_and_place_does_not_park_the_arms_by_itself(pr2_apartment_context):
    world, view, extensions = pr2_apartment_context
    pick_and_place = pick_and_place_of_the_milk(world, view.right_arm)

    rewritten(Sequence([pick_and_place]), extensions)

    assert step_types_of(pick_and_place) == [PickUpAction, PlaceAction]


def test_the_arms_are_parked_around_every_step_of_a_pick_and_place(
    pr2_apartment_context,
):
    world, view, extensions = pr2_apartment_context
    plan_transformations = [ParkArmsAroundPickAndPlaceSteps()]
    pick_and_place = pick_and_place_of_the_milk(world, view.right_arm)

    rewritten(Sequence([pick_and_place]), extensions, plan_transformations)

    assert step_types_of(pick_and_place) == [
        ParkArmsAction,
        PickUpAction,
        ParkArmsAction,
        PlaceAction,
        ParkArmsAction,
    ]


# %% freeing the end effectors of steps that run at once


def end_effectors_freed_below(node: StatechartNode) -> List[List[EndEffector]]:
    """
    :param node: An expanded part of a plan.
    :return: The end effectors each collision rules node below `node` frees, in the
        order the plan runs those nodes.
    """
    return [
        [rule.end_effector for rule in rules_node.temporary_rules]
        for rules_node in node.descendants
        if isinstance(rules_node, UpdateTemporaryCollisionRules)
    ]


def pick_ups_of_the_milk_and_the_spoon(world: World, robot: PR2) -> List[PickUpAction]:
    """
    :return: A pick-up of the milk with the left arm and one of the spoon with the
        right arm.
    """
    milk = world.get_semantic_annotations_by_type(Milk)[0]
    spoon = world.get_semantic_annotations_by_type(Spoon)[0]
    return [
        PickUpAction(milk.grasp_candidates()[0], robot.left_arm),
        PickUpAction(spoon.grasp_candidates()[0], robot.right_arm),
    ]


def test_steps_running_at_once_free_the_end_effectors_of_each_other(
    pr2_apartment_context,
):
    world, robot, extensions = pr2_apartment_context
    both_arms = Parallel(pick_ups_of_the_milk_and_the_spoon(world, robot))

    rewritten(both_arms, extensions, [FreeEndEffectorsOfParallelStepsTogether()])

    freed = end_effectors_freed_below(both_arms)
    both_end_effectors = [
        robot.left_arm.end_effector,
        robot.right_arm.end_effector,
    ]
    assert freed == [both_end_effectors] * len(freed)
    assert freed


def test_steps_running_one_after_the_other_free_only_their_own_end_effector(
    pr2_apartment_context,
):
    world, robot, extensions = pr2_apartment_context
    left_pick_up, right_pick_up = pick_ups_of_the_milk_and_the_spoon(world, robot)

    rewritten(
        Sequence([left_pick_up, right_pick_up]),
        extensions,
        [FreeEndEffectorsOfParallelStepsTogether()],
    )

    freed_by_the_left = end_effectors_freed_below(left_pick_up)
    freed_by_the_right = end_effectors_freed_below(right_pick_up)
    assert freed_by_the_left == [[robot.left_arm.end_effector]] * len(freed_by_the_left)
    assert freed_by_the_right == [[robot.right_arm.end_effector]] * len(
        freed_by_the_right
    )


# %% transformations that collide on one node


@dataclass
class MoveLeftGripperBeforeTorso(InsertionTransformation[MoveTorsoAction]):
    """
    Puts a left gripper goal in front of a torso move.
    """

    @property
    def position(self) -> InsertionPosition:
        return InsertionPosition.BEFORE

    def is_applicable(self, plan_node: MoveTorsoAction) -> bool:
        return True

    def anchor(self, plan_node: MoveTorsoAction) -> StatechartNode:
        return plan_node

    def nodes_to_insert(self, plan_node: MoveTorsoAction) -> List[StatechartNode]:
        return [gripper_goal(plan_node.robot.left_arm.end_effector, GripperState.OPEN)]


@dataclass
class MoveRightGripperBeforeTorso(MoveLeftGripperBeforeTorso):
    """
    Puts a right gripper goal there instead.
    """

    def nodes_to_insert(self, plan_node: MoveTorsoAction) -> List[StatechartNode]:
        return [
            gripper_goal(plan_node.robot.right_arm.end_effector, GripperState.CLOSE)
        ]


def warnings_of(caplog) -> List[str]:
    """
    :param caplog: The capture of this test's log records.
    :return: The message of every warning the rewriting reported.
    """
    return [
        record.getMessage()
        for record in caplog.records
        if record.name == transformation_logger.name
        and record.levelno == logging.WARNING
    ]


def test_two_transformations_applied_to_one_node_are_reported(
    pr2_apartment_context, caplog
):
    """
    Whichever transformation rewrites a node first decides what the next one finds, so a
    node more than one of them is applied to is reported.
    """
    world, view, extensions = pr2_apartment_context
    plan_transformations = list(
        [MoveLeftGripperBeforeTorso(), MoveRightGripperBeforeTorso()]
    )
    torso = MoveTorsoAction(TorsoState.HIGH)

    with caplog.at_level(logging.WARNING, logger=transformation_logger.name):
        rewritten(Sequence([torso]), extensions, plan_transformations)

    [warning] = warnings_of(caplog)
    assert str(torso) in warning


def test_the_transformations_that_collide_are_still_applied(pr2_apartment_context):
    """
    The report is a warning rather than a refusal, so both of them rewrite the plan, in
    the order the extensions lists them.
    """
    world, view, extensions = pr2_apartment_context
    plan_transformations = list(
        [MoveLeftGripperBeforeTorso(), MoveRightGripperBeforeTorso()]
    )

    plan = rewritten(
        Sequence([MoveTorsoAction(TorsoState.HIGH)]), extensions, plan_transformations
    )

    assert [step.end_effector for step in steps_of(plan)[:2]] == [
        view.left_arm.end_effector,
        view.right_arm.end_effector,
    ]


def test_a_transformation_the_case_does_not_need_is_no_collision(
    pr2_apartment_context, caplog
):
    """
    Two transformations matching the same node type collide only where both are needed,
    so the one whose case does not apply leaves the other one alone.
    """
    world, view, extensions = pr2_apartment_context
    plan_transformations = list(
        [MoveLeftGripperBeforeTorso(), MoveGripperBeforeHighTorso()]
    )

    with caplog.at_level(logging.WARNING, logger=transformation_logger.name):
        plan = rewritten(
            Sequence([MoveTorsoAction(TorsoState.LOW)]),
            extensions,
            plan_transformations,
        )

    assert warnings_of(caplog) == []
    assert kinds_of_the_steps_of(plan) == [MoveGripper, MoveTorsoAction]
