"""
:class:`PickUpActionReal`/:class:`InsertionActionReal`: the members of
:class:`~experiments.tracy_experiments.pick_and_place_action.ActuatorDrivenAction` that
carry a resolved plan out on the physical Tracy, beside the MuJoCo-driven ones in
:mod:`~experiments.tracy_experiments.pick_and_place_action`.

A resolved ``PickUpAction``/``InsertionAction`` cannot simply be performed under
:attr:`~coraplex.datastructures.enums.ExecutionType.REAL`: an insertion reduces to a
:class:`~coraplex.robot_plans.actions.core.placing.PlaceAction`, whose release is a
:class:`~coraplex.robot_plans.motions.gripper.MoveGripperMotion`, and Giskard's Tracy
interface has no command channel for the real fingers -- the motion never returns. So
the arm is driven through Giskard and the fingers through their own Robotiq action
server, which is what :mod:`~experiments.tracy_experiments.pickup.pickup_demo_real`
already does for a pick and a place written out by hand.

What the two actions do between them is one pick-and-place split at the lift: the
pick-up opens the fingers, reaches, closes them to the width its piece asks for and
lifts; the insertion carries the piece over the opening, lowers it, lets go and retracts.
While the piece is carried, the knuckle joint is watched for it slipping out of the pads.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field

from typing_extensions import Callable, List, Self

from coraplex.datastructures.dataclasses import Context
from coraplex.datastructures.enums import Arms, MovementType
from coraplex.datastructures.grasp import GraspDescription
from coraplex.plans.attachment_nodes import ReAttachNode
from coraplex.plans.factories import code, sequential
from coraplex.plans.plan_node import PlanNode
from coraplex.robot_plans.actions.base import ActionDescription
from coraplex.robot_plans.actions.core.insertion import (
    DEFAULT_HOVER_HEIGHT,
    InsertionAction,
)
from coraplex.robot_plans.actions.core.pick_up import PickUpAction, ReachAction
from coraplex.robot_plans.actions.core.robot_body import ParkArmsAction
from coraplex.robot_plans.mixins import ManipulatesBodies
from coraplex.robot_plans.motions.gripper import MoveToolCenterPointMotion
from experiments.episodes.observer import EpisodeObserver
from experiments.montessori.semantics import MontessoriShapeCategory
from experiments.tracy_experiments.montessori.grasp_widths import GraspCloseTable
from experiments.tracy_experiments.montessori.gripper_feedback import (
    GraspVerdict,
    GripperJointStateListener,
    LiveGraspGuard,
    confirm_grasp,
    reclose_setpoint_for,
)
from experiments.tracy_experiments.pick_and_place_action import ActuatorDrivenAction
from experiments.tracy_experiments.robotiq_gripper import RobotiqGripperController
from semantic_digital_twin.datastructures.definitions import GripperState
from semantic_digital_twin.semantic_annotations.semantic_annotations import Aperture
from semantic_digital_twin.spatial_types.spatial_types import Pose
from semantic_digital_twin.world_description.world_entity import Body

logger = logging.getLogger(__name__)

GRASP_HEIGHT_OFFSET = 0.04
"""
Height, in metres, the reach, grasp and lift are aimed above a piece's own centre.

The same offset
:mod:`~experiments.tracy_experiments.pickup.pickup_demo_real` reaches a perceived piece
with: a piece a look stood rests on the surface it was seen on, so the model sits where
the real object does, and this lifts the grasp target back up by the distance the pieces
used to be spawned hovering.
"""

SLIP_WATCH_INTERVAL_SECONDS = 1.0
"""
Seconds between the slip watch's re-closes while a piece is carried to its opening.
"""

SLIP_WATCH_JOIN_TIMEOUT_SECONDS = 2.0
"""
How long the carry waits for its slip watch to finish once the carry itself is done.
"""

# %% what the physical robot offers an action


@dataclass
class TracyActuators:
    """
    What an action drives on the physical Tracy: Giskard for the arm, the Robotiq action
    server for the fingers, and the knuckle's own joint states for whether a piece is
    still held.

    The counterpart of
    :class:`~experiments.tracy_experiments.pick_and_place_action.SimulatedActuators`.
    """

    context: Context
    """
    Plan context bound to the live world and the robot it holds.
    """

    gripper: RobotiqGripperController
    """
    Direct Robotiq finger control, which Giskard cannot command.
    """

    gripper_listener: GripperJointStateListener
    """
    Live knuckle-position feed for the arm that does the picking, read by the slip
    watch.
    """

    tool_frame: Body
    """
    The picking arm's tool frame, the parent a held piece is attached to.
    """

    close_table: GraspCloseTable = field(default_factory=GraspCloseTable)
    """
    How far the fingers close for a piece of each shape.
    """

    grasp_height_offset: float = GRASP_HEIGHT_OFFSET
    """
    See :data:`GRASP_HEIGHT_OFFSET`.
    """

    slip_watch_interval: float = SLIP_WATCH_INTERVAL_SECONDS
    """
    See :data:`SLIP_WATCH_INTERVAL_SECONDS`.
    """

    observer: EpisodeObserver = field(default_factory=EpisodeObserver)
    """
    What keeps every plan driven through here for the episode the run records.
    """

    slipped: Callable[[Body, GraspVerdict], None] = field(
        default=lambda body, verdict: None
    )
    """
    Told of every slip-watch verdict while a piece is carried, so a run can report one.
    """

    def perform_and_record(self, plan: PlanNode) -> None:
        """
        Perform one plan and keep it for the episode, its nodes carrying when they ran.

        :param plan: The plan to perform.
        """
        plan.perform()
        self.observer.performed(plan)

    def grasp_target_above(self, body: Body) -> Pose:
        """
        :param body: The piece to be taken hold of, standing where a look saw it.
        :return: Where the reach, grasp and lift are aimed: the piece's own position
            raised by :attr:`grasp_height_offset`, held at the identity orientation.

        A perceived piece can rest turned any way it happens to lie, and the reach is not
        aimed at that turn -- :class:`~coraplex.datastructures.grasp.GraspDescription`
        alone decides how the gripper is turned to it.
        """
        world = self.context.world
        position = body.global_transform.to_position()
        return Pose.from_xyz_rpy(
            float(position.x),
            float(position.y),
            float(position.z) + self.grasp_height_offset,
            reference_frame=world.root,
        )

    def carry_watching_for_slip(
        self, body: Body, close_setpoint: float, carry: Callable[[], None]
    ) -> None:
        """
        Run ``carry`` while watching the knuckle joint for ``body`` slipping out of the
        pads.

        The knuckle is read first: fingers that closed on nothing mean the grasp missed,
        and there is nothing to watch. Otherwise a re-close just past ``close_setpoint``
        is commanded every :attr:`slip_watch_interval` seconds for as long as ``carry``
        runs.

        :param body: The piece being carried.
        :param close_setpoint: The piece's own close setpoint, which sizes the re-close.
        :param carry: Runs the motion that carries the piece.
        """
        confirmation = confirm_grasp(self.gripper_listener.latest_closure)
        logger.info("%s: grasp check -> %s.", body.name.name, confirmation.verdict)
        if confirmation.slip_detector is None:
            carry()
            return

        guard = LiveGraspGuard(
            controller=self.gripper,
            listener=self.gripper_listener,
            arm=self.gripper_listener.arm,
            slip_detector=confirmation.slip_detector,
            period=self.slip_watch_interval,
            reclose_setpoint=reclose_setpoint_for(close_setpoint),
        )
        carry_done = threading.Event()
        watcher = threading.Thread(
            target=guard.watch,
            args=(
                lambda: not carry_done.is_set(),
                lambda verdict: self._report(body, verdict),
            ),
            daemon=True,
            name=f"slip-watch-{body.name.name}",
        )
        watcher.start()
        try:
            carry()
        finally:
            carry_done.set()
            watcher.join(timeout=SLIP_WATCH_JOIN_TIMEOUT_SECONDS)

    def _report(self, body: Body, verdict: GraspVerdict) -> None:
        """
        Log one slip-watch poll and pass it on to whoever is listening.

        :param body: The piece being carried.
        :param verdict: The poll's held-or-slipped verdict.
        """
        logger.info("%s: slip watch -> %s.", body.name.name, verdict)
        self.slipped(body, verdict)


# %% the two actions


@dataclass
class PickUpActionReal(
    ActionDescription,
    ManipulatesBodies,
    ActuatorDrivenAction[PickUpAction, TracyActuators],
):
    """
    :class:`~coraplex.robot_plans.actions.core.pick_up.PickUpAction` carried out on the
    physical Tracy: the fingers are opened, the arm reaches the piece the way the grasp
    says, the fingers close to the width that piece asks for, and the piece is lifted
    clear of what it was resting on.
    """

    object_designator: Body
    """
    The piece to pick up, as the world holds it.
    """

    shape_category: MontessoriShapeCategory
    """
    What shape the piece is, which says how far the fingers close on it.
    """

    arm: Arms
    """
    Which arm picks it up.
    """

    grasp_description: GraspDescription
    """
    How the piece is taken hold of, which says how the gripper is turned to reach it.
    """

    lab: TracyActuators
    """
    The robot this is driven on.
    """

    @classmethod
    def carrying_out(cls, action: PickUpAction, lab: TracyActuators) -> Self:
        return cls(
            object_designator=action.object_designator.root,
            shape_category=action.object_designator.shape_category,
            arm=action.arm,
            grasp_description=action.grasp_description,
            lab=lab,
        )

    @property
    def manipulated_bodies(self) -> List[Body]:
        """
        The body this action acts on.
        """
        return [self.object_designator]

    @property
    def close_setpoint(self) -> float:
        """
        How far the fingers close on this piece.
        """
        return self.lab.close_table.setpoint_for(self.shape_category)

    @property
    def _action_plan(self) -> PlanNode:
        return code(self._run)

    def _run(self) -> None:
        lab = self.lab
        body = self.object_designator
        grasp_target = lab.grasp_target_above(body)
        _, _, lift_to = self.grasp_description.pose_sequence(grasp_target, body)

        reach = sequential(
            [
                ReachAction(
                    target_pose=grasp_target,
                    object_designator=body,
                    arm=self.arm,
                    grasp_description=self.grasp_description,
                )
            ],
            context=lab.context,
        ).plan
        lift = sequential(
            [
                ReAttachNode(body=body, new_parent=lab.tool_frame),
                MoveToolCenterPointMotion(
                    lift_to,
                    self.arm,
                    allow_gripper_collision=True,
                    movement_type=MovementType.TRANSLATION,
                ),
            ],
            context=lab.context,
        ).plan

        lab.gripper.move(self.arm, GripperState.OPEN)
        lab.perform_and_record(reach)
        lab.gripper.close_to(self.arm, self.close_setpoint)
        lab.perform_and_record(lift)


@dataclass
class InsertionActionReal(
    ActionDescription,
    ManipulatesBodies,
    ActuatorDrivenAction[InsertionAction, TracyActuators],
):
    """
    :class:`~coraplex.robot_plans.actions.core.insertion.InsertionAction` carried out on
    the physical Tracy: the held piece is carried over the opening, lowered onto it, let
    go so it falls through, and the arm retracts and parks.

    What separates this from a place is where the release pose comes from: it is read off
    the opening the piece goes through, so the piece is let go over that opening however
    the opening stands.
    """

    object_designator: Body
    """
    The piece to put through :attr:`target`.
    """

    shape_category: MontessoriShapeCategory
    """
    What shape the piece is, which sizes the slip watch's re-close while it is carried.
    """

    target: Aperture
    """
    The opening the piece goes through.
    """

    arm: Arms
    """
    Which arm carries it.
    """

    grasp_description: GraspDescription
    """
    How the piece is held, which says how the gripper is turned to carry and release it.
    """

    lab: TracyActuators
    """
    The robot this is driven on.
    """

    hover_height: float = DEFAULT_HOVER_HEIGHT
    """
    How far above :attr:`target`'s own origin, along its own axis, the piece is let go.
    """

    @classmethod
    def carrying_out(cls, action: InsertionAction, lab: TracyActuators) -> Self:
        return cls(
            object_designator=action.object_designator.root,
            shape_category=action.object_designator.shape_category,
            target=action.target,
            arm=action.arm,
            grasp_description=action.grasp_description,
            lab=lab,
            hover_height=action.hover_height,
        )

    @property
    def manipulated_bodies(self) -> List[Body]:
        """
        The body this action acts on.
        """
        return [self.object_designator]

    @property
    def release_pose(self) -> Pose:
        """
        Where the piece's own centre is let go, in the world root frame:

        :attr:`hover_height` above the opening's origin along its own axis.
        """
        world = self.lab.context.world
        return world.transform(
            Pose.from_xyz_rpy(
                0.0, 0.0, self.hover_height, reference_frame=self.target.root
            ),
            world.root,
        )

    @property
    def _action_plan(self) -> PlanNode:
        return code(self._run)

    def _run(self) -> None:
        lab = self.lab
        body = self.object_designator
        world = lab.context.world
        transport_to, lower_to, retract_to = self.grasp_description.pose_sequence(
            self.release_pose, body, reverse=True
        )

        carry = sequential(
            [
                MoveToolCenterPointMotion(
                    transport_to, self.arm, allow_gripper_collision=False
                ),
                MoveToolCenterPointMotion(
                    lower_to,
                    self.arm,
                    allow_gripper_collision=True,
                    movement_type=MovementType.CARTESIAN,
                ),
            ],
            context=lab.context,
        ).plan
        retract_and_park = sequential(
            [
                ReAttachNode(body=body, new_parent=world.root),
                MoveToolCenterPointMotion(
                    retract_to,
                    self.arm,
                    allow_gripper_collision=True,
                    movement_type=MovementType.TRANSLATION,
                ),
                # Park before anything else so the arm clears the board on its way back
                # rather than dragging the gripper across it.
                ParkArmsAction(self.arm),
            ],
            context=lab.context,
        ).plan

        lab.carry_watching_for_slip(
            body,
            lab.close_table.setpoint_for(self.shape_category),
            lambda: lab.perform_and_record(carry),
        )
        lab.gripper.move(self.arm, GripperState.OPEN)
        lab.perform_and_record(retract_and_park)
