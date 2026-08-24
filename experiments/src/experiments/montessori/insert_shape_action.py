"""
CRAM action that picks up a loose Montessori shape and inserts it through the shape-
sorting board's hole matching its category.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import logging

import rustworkx
from typing_extensions import Optional

from coraplex.datastructures.enums import ApproachDirection, Arms, VerticalAlignment
from coraplex.datastructures.grasp import GraspDescription
from coraplex.plans.factories import sequential
from coraplex.plans.plan_node import PlanNode
from coraplex.robot_plans.actions.base import ActionDescription
from coraplex.robot_plans.actions.core.misc import MoveToReach
from coraplex.robot_plans.actions.core.navigation import NavigateAction
from coraplex.robot_plans.actions.core.pick_up import PickUpAction
from coraplex.robot_plans.actions.core.placing import PlaceAction
from coraplex.robot_plans.actions.core.robot_body import ParkArmsAction
from coraplex.robot_plans.motions.robot_body import MoveJointsMotion
from coraplex.view_manager import ViewManager
from experiments.montessori.semantics import MontessoriShape, ShapeSortingBoard
from experiments.montessori.world import DEFAULT_ROBOT_STANDOFF_DISTANCE
from krrood.entity_query_language.factories import a
from krrood.entity_query_language.query.match import Match
from semantic_digital_twin.exceptions import PointOccupiedError
from semantic_digital_twin.robots.robot_part_mixins import HasMobileBase
from semantic_digital_twin.semantic_annotations.semantic_annotations import Table
from semantic_digital_twin.spatial_types.spatial_types import Point3, Pose, Pose2D
from semantic_digital_twin.world_description.graph_of_convex_sets.base import (
    translate_free_space_to_where_condition,
)
from semantic_digital_twin.world_description.graph_of_convex_sets.boxes import (
    navigation_map_at_target,
)
from semantic_digital_twin.world_description.world_entity import Body

logger = logging.getLogger(__name__)

STANDOFF_CLEARANCE = 0.1
"""
Horizontal clearance kept between a standoff point (see
:meth:`InsertMontessoriShapeAction._standoff_point_near_surface`) and the edge of the
surface it stands off from.

This only needs to step the point off the surface's own 2D-projected footprint (see
that method's docstring), not clear the robot's whole body: unlike
:attr:`InsertMontessoriShapeAction._base_footprint_clearance`, it is independent of the
robot, since inflating it to a wide robot's full footprint would push the pre-grasp
hover point (and, transitively, the base stance :meth:`_move_to_reach` resolves near
it) far enough from the target to put the actual grasp out of comfortable arm reach.
"""


@dataclass
class InsertMontessoriShapeAction(ActionDescription):
    """
    Picks up a loose Montessori shape and inserts it through the shape-sorting board's
    hole matching its category.

    The robot moves to a reachable stance before picking the shape up, and again before
    placing it, so this works regardless of where the robot happens to be standing
    relative to the shape and the board.
    """

    montessori_shape: MontessoriShape
    """
    The loose shape to pick up and insert.
    """

    board: ShapeSortingBoard
    """
    The shape-sorting board whose matching hole the shape is inserted through.
    """

    arm: Arms
    """
    Arm used to pick up and insert the shape.
    """

    grasp_description: Optional[GraspDescription] = None
    """
    Grasp used to pick up the shape; a default top-down grasp is used if not given,
    since the shape rests flat on a table rather than standing on an edge.
    """

    insertion_hover_height: float = 0.03
    """
    Height above the target hole at which the shape is released, so the gripper clears
    the board's surface on approach.
    """

    placing_linear_velocity: float = 0.05
    """
    Linear velocity (m/s) of :class:`~coraplex.robot_plans.actions.core.placing.PlaceAction`'s
    own final descent onto the release pose, passed straight through to it.
    """

    transport_linear_velocity: float = 0.08
    """
    Linear velocity (m/s) :class:`~coraplex.robot_plans.actions.core.placing.PlaceAction`
    carries the held shape at, above the target location and before its final descent,
    passed straight through to it.
    """

    release_opening_velocity: float = 0.07
    """
    Finger joint velocity (m/s) :class:`~coraplex.robot_plans.actions.core.placing.PlaceAction`
    opens the gripper at to release the shape, passed straight through to it.
    """

    retract_linear_velocity: Optional[float] = None
    """
    Linear velocity (m/s) :class:`~coraplex.robot_plans.actions.core.placing.PlaceAction`
    retracts the end effector away from the placed shape at, passed straight through to
    it. ``None`` leaves the speed unconstrained.
    """

    grasp_closing_velocity: float = 0.2
    """
    Velocity (m/s) :class:`~coraplex.robot_plans.actions.core.pick_up.PickUpAction`'s
    fingers close at, passed straight through to it.
    """

    lift_linear_velocity: float = 0.12
    """
    Linear velocity (m/s) :class:`~coraplex.robot_plans.actions.core.pick_up.PickUpAction`
    lifts the shape clear of the table at after grasping, passed straight through to it.
    """

    grasp_stall_minimum_time: float = 0.3
    """
    Minimum stall dwell time (s, see
    :attr:`~coraplex.robot_plans.motions.gripper.MoveGripperMotion.stall_minimum_time`)
    :class:`~coraplex.robot_plans.actions.core.pick_up.PickUpAction`'s CLOSE motion
    waits before considering the grasp stalled, passed straight through to it.
    """

    final_approach_linear_velocity: float = 0.05
    """
    Linear velocity (m/s) :class:`~coraplex.robot_plans.actions.core.pick_up.PickUpAction`
    approaches the shape at during its final Cartesian descent, passed straight through
    to it.
    """

    object_friction: float = 1.5
    """
    Sliding friction coefficient applied to the shape's geom before this pick, overriding
    the world's default, passed straight through to
    :class:`~coraplex.robot_plans.actions.core.pick_up.PickUpAction`.
    """

    target_horizontal_offset: Optional[Point3] = None
    """
    Offset added to the target hole's own (x, y) position before releasing the shape
    above it.

    ``None`` (the default) targets the hole's center exactly; a small nonzero
    offset lets a caller retry a failed insertion (see
    :func:`~experiments.montessori.montessori_demo._insert_all_shapes`) with an actually
    different drop point, rather than repeating the exact same teleport-then-settle that
    just failed.
    """

    @property
    def _base_footprint_clearance(self) -> float:
        """
        How far the robot's own body extends from its base origin, so a point this far
        from an obstacle is clear of the whole base, not just of the origin point
        itself.

        Used to bloat obstacles in :meth:`_move_to_reach`'s navigation map for the
        robot's standing offset: a resolved standing offset is otherwise only checked as
        a zero-radius point against the free space, which lets the robot's real body
        overlap nearby furniture even though that point itself is unobstructed.
        """
        base_bounding_box = self.robot.mobile_base.bounding_box
        return (base_bounding_box.width + base_bounding_box.depth) / 4

    def _standoff_point_near_surface(
        self,
        surface: Body,
        target_position: Point3,
        clearance: float = STANDOFF_CLEARANCE,
    ) -> Pose:
        """
        A point just outside ``surface``'s bounding box, offset from whichever edge is
        nearest to ``target_position``, at ``target_position``'s height.

        :func:`~semantic_digital_twin.world_description.graph_of_convex_sets.boxes.navigation_map_at_target`
        projects obstacles to a 2D floor footprint (any point above or on a wide
        surface like a table or the sorting board reads as occupied, regardless of
        height), so a reach target actually on ``surface`` is never in free space.
        Stepping just past the nearest edge, mirroring
        :meth:`~experiments.montessori.world.MontessoriWorld.spawn_robot`'s own
        ``table_bounding_box.min_x - standoff_distance`` pattern, gives
        :meth:`_move_to_reach` a genuinely free point near the target to reach for.

        :param surface: The body ``target_position`` rests on (or near).
        :param target_position: The position to stand off from.
        :param clearance: Horizontal clearance kept between the returned point and the
            nearest edge of ``surface``'s bounding box; defaults to
            :data:`STANDOFF_CLEARANCE`, the margin for a reach target rather than a
            robot's whole body (see :meth:`_hardcoded_standing_pose`).
        """
        bounding_box = surface.collision.as_bounding_box_collection_in_frame(
            self.world.root
        ).bounding_box()
        x, y = float(target_position.x), float(target_position.y)
        distance_to_edge = {
            "min_x": x - bounding_box.min_x,
            "max_x": bounding_box.max_x - x,
            "min_y": y - bounding_box.min_y,
            "max_y": bounding_box.max_y - y,
        }
        nearest_edge = min(distance_to_edge, key=distance_to_edge.get)
        if nearest_edge == "min_x":
            x = bounding_box.min_x - clearance
        elif nearest_edge == "max_x":
            x = bounding_box.max_x + clearance
        elif nearest_edge == "min_y":
            y = bounding_box.min_y - clearance
        else:
            y = bounding_box.max_y + clearance
        return Pose.from_xyz_rpy(
            x, y, float(target_position.z), reference_frame=self.world.root
        )

    def _hardcoded_standing_pose(self, surface: Body, target_position: Point3) -> Pose:
        """
        A robot base pose standing just off ``surface``'s bounding box, near
        ``target_position``, facing it.

        Used in place of :meth:`_move_to_reach`'s underspecified, Graph-of-Convex-Sets-
        resolved standing offset: that resolution goes through the
        :class:`~krrood.entity_query_language.backends.ProbabilisticBackend` and can
        take a very long time (or appear to hang) to find a satisfying standing offset,
        which gets in the way of first establishing that the pick-and-place and grasp
        mechanics themselves work. :meth:`_standoff_point_near_surface` already computes
        this same kind of point, just with :data:`STANDOFF_CLEARANCE` (a margin sized
        for a reach target, not a robot's whole body); using the robot's own footprint
        clearance instead keeps the base from overlapping ``surface`` while standing
        close enough for the arm to actually reach.

        :param surface: The body ``target_position`` rests on (or near); the base
            stands off this surface's bounding box, not ``target_position`` itself.
        :param target_position: The position the returned pose should face.
        """
        standoff_pose = self._standoff_point_near_surface(
            surface, target_position, clearance=self._base_footprint_clearance
        )
        standoff_position = standoff_pose.to_position()
        x, y = float(standoff_position.x), float(standoff_position.y)
        yaw = math.atan2(float(target_position.y) - y, float(target_position.x) - x)
        return Pose.from_xyz_rpy(x, y, 0.0, yaw=yaw, reference_frame=self.world.root)

    def _grasp_description_query(self) -> Match[GraspDescription]:
        """
        :attr:`grasp_description`, rebuilt through the query DSL.

        The :class:`~krrood.entity_query_language.backends.ProbabilisticBackend`
        (required by :meth:`_move_to_reach`'s underspecified standing offset; see
        ``query_backend`` on :class:`~coraplex.datastructures.dataclasses.Context`)
        needs every field of every ``underspecified(...)``-wrapped action's arguments expressed
        through the query DSL to build its probabilistic circuit, even fields that are
        already fully concrete: passing :attr:`grasp_description` directly raises
        ``ValueError: ... not in domain of variable ...`` once that backend is active.
        """
        return a(GraspDescription)(
            approach_direction=self.grasp_description.approach_direction,
            vertical_alignment=self.grasp_description.vertical_alignment,
            end_effector=self.grasp_description.end_effector,
            rotate_gripper=self.grasp_description.rotate_gripper,
        )

    def _rotate_base_towards_shape_plan(self) -> PlanNode:
        """
        Rotate a bolted arm's own first (shoulder-pan) joint to face
        :attr:`montessori_shape`, before reaching for it.

        A bolted arm (see the ``HasMobileBase``-absent branch of :attr:`_action_plan`)
        has no base to navigate into a comfortable stance with, unlike
        :meth:`_move_to_reach`'s resolved standing offset; it reaches for the shape
        directly from wherever it is bolted via a single Cartesian goal, which Giskard's
        solver resolves through whatever combination of the arm's 7 joints satisfies
        it -- including, when the shape sits well off to the arm's side rather than
        roughly ahead of it, configurations that reach the goal correctly but bend the
        elbow and wrist through an unnecessarily convoluted path to get there. Pre-
        rotating just the shoulder-pan joint towards the shape first, while the rest of
        the arm is still in its parked configuration, gives the following Cartesian
        reach a starting configuration already facing the shape, so it only has to
        resolve the remaining reach rather than a near-full turn.

        :return: A joint-space motion for the arm's own first joint only.
        """
        arm_view = ViewManager.get_arm_view(self.arm, self.robot)
        base_joint = arm_view.active_connections[0]
        robot_base_position = self.robot.root.global_transform.to_position()
        _, _, robot_base_yaw = (
            self.robot.root.global_transform.to_rotation_matrix().to_rpy()
        )
        shape_position = self.montessori_shape.root.global_pose.to_position()
        heading_to_shape = math.atan2(
            float(shape_position.y) - float(robot_base_position.y),
            float(shape_position.x) - float(robot_base_position.x),
        )
        target_joint_angle = heading_to_shape - float(robot_base_yaw)
        target_joint_angle = (target_joint_angle + math.pi) % (2 * math.pi) - math.pi
        return MoveJointsMotion(
            names=[base_joint.name.name], positions=[target_joint_angle]
        )

    def _move_to_reach(self, target: Body, target_pose_end_effector: Pose) -> PlanNode:
        """
        Move the robot to a stance, within the free space of a Graph of Convex Sets
        navigation map built around ``target``, from which ``target_pose_end_effector``
        is reachable by the end effector.

        Mirrors the reach-planning pattern of
        :class:`~experiments.sage_10k.sage10k_actions.Sage10kOpenDoor`: rather than a
        hand-picked standing offset or a costmap search, the robot's standing offset is
        left underspecified and constrained to the navigation map's free space, letting
        it be resolved generatively.

        Two navigation maps are built around ``target``, not one: an unbloated one, at
        the default search range, to find the free region actually touching
        ``target_pose_end_effector`` (bloating this one too would make small objects
        and holes on the board reject standoff points meant to sit just past their own
        edge), and one bloated by :attr:`_base_footprint_clearance` to constrain where
        the robot's own base, which has a real footprint rather than a single point,
        may stand within that same region.

        The standing map's own search range is kept to twice
        :data:`~experiments.montessori.world.DEFAULT_ROBOT_STANDOFF_DISTANCE`, well
        short of the reachability map's default: free space bloated by a wide robot's
        own footprint tends to merge into a few large, far-reaching regions rather
        than fragmenting the way barely-bloated free space does, and the underspecified
        query has no notion of preferring the near part of such a region over its far
        corners, so an unbounded search range risks resolving a standing offset too far
        from ``target`` for the following pickup/placement itself to actually reach.

        :param target: The body to build the navigation map around.
        :param target_pose_end_effector: The pose the end effector should reach.
        :raises PointOccupiedError: If ``target_pose_end_effector`` is not in the
            navigation map's free space, or if no standing room remains for the
            robot's own footprint near it.
        """
        reachability_gcs = navigation_map_at_target(target=target)
        target_node = reachability_gcs.node_of_point(target_pose_end_effector.position)
        if target_node is None:
            raise PointOccupiedError(
                self.world.transform(target_pose_end_effector, self.world.root).position
            )
        reachable_boxes = [
            reachability_gcs.graph[index]
            for index in rustworkx.node_connected_component(
                reachability_gcs.graph,
                reachability_gcs.box_to_index_map[target_node],
            )
        ]

        standing_search_range = 2 * DEFAULT_ROBOT_STANDOFF_DISTANCE
        standing_gcs = navigation_map_at_target(
            target=target,
            search_range_x=standing_search_range,
            search_range_y=standing_search_range,
            bloat_obstacles=self._base_footprint_clearance,
        )
        standing_gcs = standing_gcs.create_subgraph(
            [
                index
                for box, index in standing_gcs.box_to_index_map.items()
                if any(
                    box.intersection_with(reachable_box) is not None
                    for reachable_box in reachable_boxes
                )
            ]
        )
        if not standing_gcs.box_to_index_map:
            raise PointOccupiedError(
                self.world.transform(target_pose_end_effector, self.world.root).position
            )

        reach_query = a(MoveToReach)(
            target_pose_offset_robot=a(Pose2D)(
                x=..., y=..., yaw=..., reference_frame=None
            ),
            hip_rotation=0.0,
            target_pose_end_effector=target_pose_end_effector,
            grasp_description=self._grasp_description_query(),
        )
        where_condition = translate_free_space_to_where_condition(
            standing_gcs.free_space_event,
            reach_query.expression,
            x_variable_name="MoveToReach.target_pose_offset_robot.x",
            y_variable_name="MoveToReach.target_pose_offset_robot.y",
        )
        return reach_query.where(where_condition)

    @property
    def _action_plan(self) -> PlanNode:
        hole = self.board.hole_for(self.montessori_shape)
        offset = Point3(0.0, 0.0, 0.0)
        insertion_pose = self.montessori_shape.insertion_pose_relative_to_hole(
            hole, offset, self.insertion_hover_height
        )
        target_location = self.world.transform(insertion_pose, self.world.root)
        shape_position = self.montessori_shape.root.global_pose.to_position()
        self.grasp_description = self.grasp_description or GraspDescription(
            ApproachDirection.FRONT,
            VerticalAlignment.TOP,
            ViewManager.get_end_effector_view(self.arm, self.robot),

        )

        # A robot with a mobile base reaches whole-body from an underspecified standing
        # offset the ProbabilisticBackend resolves, so it navigates to a stance before
        # each reach and every action is wrapped in the query DSL (``a(...)``) for that
        # backend to build its circuit over. A robot with no mobile base (e.g. a
        # table-bolted Panda; see HasMobileBase) has no stance to resolve and reaches
        # with its arm alone from wherever it is mounted: its whole navigation -- the
        # table lookup, and _hardcoded_standing_pose, which calls self.robot.mobile_base
        # and would raise AttributeError -- is never reached, and its actions are built
        # concretely, since a query with nothing underspecified to resolve fails with
        # EmptyUnderspecified.
        if isinstance(self.robot, HasMobileBase):
            [table] = self.world.get_semantic_annotations_by_type(Table)
            navigate_to_shape: list[PlanNode] = [
                NavigateAction(
                    self._hardcoded_standing_pose(table.root, shape_position)
                )
            ]
            navigate_to_hole: list[PlanNode] = [
                NavigateAction(
                    self._hardcoded_standing_pose(
                        table.root, target_location.to_position()
                    )
                )
            ]
            pick_up_shape: PlanNode = a(PickUpAction)(
                object_designator=self.montessori_shape.root,
                arm=self.arm,
                grasp_description=self._grasp_description_query(),
                grasp_closing_velocity=self.grasp_closing_velocity,
                lift_linear_velocity=self.lift_linear_velocity,
                grasp_stall_minimum_time=self.grasp_stall_minimum_time,
                final_approach_linear_velocity=self.final_approach_linear_velocity,
                object_friction=self.object_friction,
            )
            place_shape: PlanNode = a(PlaceAction)(
                object_designator=self.montessori_shape.root,
                target_location=target_location,
                arm=self.arm,
                placing_linear_velocity=self.placing_linear_velocity,
                transport_linear_velocity=self.transport_linear_velocity,
                release_opening_velocity=self.release_opening_velocity,
                retract_linear_velocity=self.retract_linear_velocity,
            )
        else:
            navigate_to_shape = [self._rotate_base_towards_shape_plan()]
            navigate_to_hole = []
            pick_up_shape = PickUpAction(
                object_designator=self.montessori_shape.root,
                arm=self.arm,
                grasp_description=self.grasp_description,
                grasp_closing_velocity=self.grasp_closing_velocity,
                lift_linear_velocity=self.lift_linear_velocity,
                grasp_stall_minimum_time=self.grasp_stall_minimum_time,
                final_approach_linear_velocity=self.final_approach_linear_velocity,
                object_friction=self.object_friction,
            )
            place_shape = PlaceAction(
                object_designator=self.montessori_shape.root,
                target_location=target_location,
                arm=self.arm,
                placing_linear_velocity=self.placing_linear_velocity,
                transport_linear_velocity=self.transport_linear_velocity,
                release_opening_velocity=self.release_opening_velocity,
                retract_linear_velocity=self.retract_linear_velocity,
            )

        return sequential(
            [
                ParkArmsAction(Arms.BOTH),
                *navigate_to_shape,
                pick_up_shape,
                *navigate_to_hole,
                place_shape,
                ParkArmsAction(Arms.BOTH),
            ]
        )

    def has_fallen_through_hole(self) -> bool:
        """
        Whether :attr:`montessori_shape` currently rests below the board's top surface,
        directly beneath its matching hole, i.e. has actually fallen through that hole
        rather than still resting on top of the board or having never been moved there
        at all.

        :attr:`_action_plan` only ever kinematically teleports the shape to its
        target pose via
        :class:`~coraplex.robot_plans.actions.core.placing.PlaceAction`, which does
        not check whether the shape actually fits through a tight-clearance hole;
        call this only after the shape has had a chance to physically settle (e.g.
        by simulating it in MuJoCo), not right after the action plan finishes.

        :return: ``True`` if the shape's own center is horizontally within the
            hole's footprint and its highest point is below the board's top
            surface.
        """
        hole = self.board.hole_for(self.montessori_shape)
        hole_position = hole.root.global_transform.to_position()
        hole_bounds = hole.root.area.combined_mesh.bounds
        hole_min_x = float(hole_position.x) + hole_bounds[0][0]
        hole_max_x = float(hole_position.x) + hole_bounds[1][0]
        hole_min_y = float(hole_position.y) + hole_bounds[0][1]
        hole_max_y = float(hole_position.y) + hole_bounds[1][1]

        shape_position = self.montessori_shape.root.global_transform.to_position()
        shape_x, shape_y = float(shape_position.x), float(shape_position.y)
        is_below_the_hole = (
            hole_min_x <= shape_x <= hole_max_x and hole_min_y <= shape_y <= hole_max_y
        )

        board_top_z = (
            self.board.root.collision.as_bounding_box_collection_in_frame(
                self.world.root
            )
            .bounding_box()
            .max_z
        )
        shape_top_z = (
            self.montessori_shape.root.collision.as_bounding_box_collection_in_frame(
                self.world.root
            )
            .bounding_box()
            .max_z
        )
        # Temporary diagnostic: which check (horizontal miss vs. resting too high)
        # is actually failing for a shape that doesn't fall through, and whether a
        # box shape's yaw lines up with its hole's.
        hole_roll, hole_pitch, hole_yaw = (
            hole.root.global_transform.to_rotation_matrix().to_rpy()
        )
        shape_roll, shape_pitch, shape_yaw = (
            self.montessori_shape.root.global_transform.to_rotation_matrix().to_rpy()
        )
        logger.info(
            "has_fallen_through_hole(%s): hole_center=(%.4f, %.4f) hole_x=[%.4f, %.4f] "
            "hole_y=[%.4f, %.4f] shape_xy=(%.4f, %.4f) is_below_the_hole=%s "
            "board_top_z=%.4f shape_top_z=%.4f hole_rpy_deg=(%.2f, %.2f, %.2f) "
            "shape_rpy_deg=(%.2f, %.2f, %.2f)",
            self.montessori_shape.name,
            float(hole_position.x),
            float(hole_position.y),
            hole_min_x,
            hole_max_x,
            hole_min_y,
            hole_max_y,
            shape_x,
            shape_y,
            is_below_the_hole,
            board_top_z,
            shape_top_z,
            math.degrees(float(hole_roll)),
            math.degrees(float(hole_pitch)),
            math.degrees(float(hole_yaw)),
            math.degrees(float(shape_roll)),
            math.degrees(float(shape_pitch)),
            math.degrees(float(shape_yaw)),
        )
        return bool(is_below_the_hole and shape_top_z < board_top_z)
