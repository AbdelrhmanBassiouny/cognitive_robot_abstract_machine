from __future__ import annotations

from dataclasses import dataclass, field

from cramph.context import StatechartContext
from giskardpy.motion_statechart.binding_policy import (
    ForwardKinematicsBinding,
    GoalBindingPolicy,
)
from giskardpy.motion_statechart.graph_node import MotionNodeArtifacts
from giskardpy.motion_statechart.tasks.cartesian_tasks import CartesianTask
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.spatial_types import Point3, Vector3
from semantic_digital_twin.world_description.world_entity import (
    KinematicStructureEntity,
)


@dataclass(eq=False, repr=False, kw_only=True)
class Pointing(CartesianTask):
    """
    Will orient pointing_axis at goal_point.
    """

    goal_point: Point3
    """
    Where to point pointing_axis at.
    """

    pointing_axis: Vector3
    """
    The axis of tip_link that will be used for pointing.
    """

    max_velocity: float = 0.3
    """
    Reference angular velocity for normalization in rad/s.
    """

    threshold: float = 0.01
    """
    Observation is true if the pointing angle is below this threshold.
    """

    @property
    def goal_reference_frame(self) -> KinematicStructureEntity:
        return self.goal_point.reference_frame

    @property
    def aim_point(self) -> Point3:
        """
        :return: The point :attr:`pointing_axis` is oriented at, expressed in
            :attr:`goal_reference_frame`.
        """
        return self.goal_point

    def build_artifacts(self, context: StatechartContext) -> MotionNodeArtifacts:
        """
        Build motion constraints that swing the pointing axis onto :attr:`aim_point`.

        :param context: Provides access to world model and kinematic expressions.
        :return: The artifacts of this task, whose error is the angle between the
            pointing axis and the goal direction.
        """
        artifacts = MotionNodeArtifacts()
        goal_reference_frame_P_goal_point = self.aim_point

        tip_V_pointing_axis = context.world.transform(
            target_frame=self.tip_link, spatial_object=self.pointing_axis
        )
        tip_V_pointing_axis.scale(1)

        root_T_tip = context.world.compose_forward_kinematics_expression(
            self.root_link, self.tip_link
        )

        root_P_goal_point = (
            self.root_T_goal_reference_frame @ goal_reference_frame_P_goal_point
        )

        root_V_goal_axis = root_P_goal_point - root_T_tip.position
        root_V_goal_axis.scale(1)
        root_V_pointing_axis = root_T_tip @ tip_V_pointing_axis
        root_V_pointing_axis.visualisation_frame = self.tip_link
        root_V_goal_axis.visualisation_frame = self.tip_link

        tip_V_goal_axis = root_T_tip.inverse() @ root_V_goal_axis
        tip_V_goal_axis.scale(1)
        artifacts.geometry.add_vector_goal_constraints(
            frame_V_current=tip_V_goal_axis,
            frame_V_goal=tip_V_pointing_axis,
            reference_velocity=self.max_velocity,
            quadratic_weight=self.weight,
        )
        self.add_goal_and_current_debug_expressions(
            artifacts, goal=root_V_goal_axis, current=root_V_pointing_axis
        )

        artifacts.error = root_V_pointing_axis.angle_between(root_V_goal_axis)
        return artifacts


@dataclass(eq=False, repr=False, kw_only=True)
class PointingBeside(Pointing):
    """
    Will orient pointing_axis at a point beside goal_point, moved horizontally at right
    angles to the line of sight from :attr:`viewpoint` to goal_point.

    The line of sight is taken where :attr:`viewpoint` stands when the goal is bound,
    see :attr:`binding_policy`.
    """

    viewpoint: KinematicStructureEntity
    """
    The entity whose line of sight to goal_point decides which way is sideways.
    """

    sideways_offset: float
    """
    How far the point pointed at lies to the left of goal_point, as seen from
    :attr:`viewpoint`; a negative offset lies to the right.
    """

    _viewpoint_binding: ForwardKinematicsBinding = field(init=False, repr=False)
    """
    Binds where :attr:`viewpoint` stands relative to the goal reference frame.
    """

    _world_root_binding: ForwardKinematicsBinding = field(init=False, repr=False)
    """
    Binds the world root relative to the goal reference frame, which says where up is.
    """

    def set_up(self, context: StatechartContext) -> None:
        """
        Additionally binds :attr:`viewpoint` and the world root, which the sideways
        direction is described against.
        """
        super().set_up(context)
        self._viewpoint_binding = ForwardKinematicsBinding(
            name=PrefixedName("goal_ref_T_viewpoint", str(self.name)),
            root=self.goal_reference_frame,
            tip=self.viewpoint,
            float_variable_data=context.float_variable_data,
        )
        self._world_root_binding = ForwardKinematicsBinding(
            name=PrefixedName("goal_ref_T_world_root", str(self.name)),
            root=self.goal_reference_frame,
            tip=context.world.root,
            float_variable_data=context.float_variable_data,
        )
        self._viewpoint_binding.bind(context.world)
        self._world_root_binding.bind(context.world)

    def on_start(self, context: StatechartContext) -> None:
        super().on_start(context)
        if self.binding_policy == GoalBindingPolicy.Bind_on_start:
            self._viewpoint_binding.bind(context.world)
            self._world_root_binding.bind(context.world)

    @property
    def aim_point(self) -> Point3:
        goal_reference_frame_V_line_of_sight = (
            self.goal_point - self._viewpoint_binding.root_T_tip.position
        )
        goal_reference_frame_T_world_root = self._world_root_binding.root_T_tip
        goal_reference_frame_V_up = goal_reference_frame_T_world_root @ Vector3.Z(
            reference_frame=goal_reference_frame_T_world_root.child_frame
        )
        goal_reference_frame_V_left = goal_reference_frame_V_up.cross(
            goal_reference_frame_V_line_of_sight
        )
        goal_reference_frame_V_left.scale(self.sideways_offset)
        return self.goal_point + goal_reference_frame_V_left


@dataclass(eq=False, repr=False, kw_only=True)
class PointingCone(CartesianTask):
    """
    Will orient pointing_axis at goal_point with a cone-shaped tolerance region.
    """

    goal_point: Point3
    """
    Where to point pointing_axis at.
    """

    pointing_axis: Vector3
    """
    The axis of tip_link that will be used for pointing.
    """

    cone_theta: float = 0.0
    """
    Slack cone region in radians.
    """

    max_velocity: float = 0.3
    """
    Reference angular velocity for normalization in rad/s.
    """

    threshold: float = 0.01
    """
    Observation is true if the pointing angle is below this threshold.
    """

    @property
    def goal_reference_frame(self) -> KinematicStructureEntity:
        return self.goal_point.reference_frame

    def build_artifacts(self, context: StatechartContext) -> MotionNodeArtifacts:
        """
        Build motion constraints that swing the pointing axis into the goal cone.

        :param context: Provides access to world model and kinematic expressions.
        :return: The artifacts of this task, whose error is the angle between the
            pointing axis and the nearest direction inside the cone.
        """
        artifacts = MotionNodeArtifacts()
        tip_V_pointing_axis = context.world.transform(
            target_frame=self.tip_link, spatial_object=self.pointing_axis
        )
        tip_V_pointing_axis.scale(1)

        root_T_tip = context.world.compose_forward_kinematics_expression(
            self.root_link, self.tip_link
        )

        root_P_goal_point = self.root_T_goal_reference_frame @ self.goal_point

        root_V_goal_axis = root_P_goal_point - root_T_tip.position
        root_V_goal_axis.scale(1)
        root_V_pointing_axis = root_T_tip.dot(tip_V_pointing_axis)
        root_V_pointing_axis.visualisation_frame = self.tip_link

        root_V_goal_axis.visualisation_frame = self.tip_link

        root_V_goal_axis_proj = root_V_pointing_axis.project_to_cone(
            root_V_goal_axis, self.cone_theta
        )
        root_V_goal_axis_proj.visualisation_frame = self.tip_link

        artifacts.geometry.add_vector_goal_constraints(
            frame_V_current=root_V_pointing_axis,
            frame_V_goal=root_V_goal_axis_proj,
            reference_velocity=self.max_velocity,
            quadratic_weight=self.weight,
        )
        self.add_goal_and_current_debug_expressions(
            artifacts, goal=root_V_goal_axis_proj, current=root_V_pointing_axis
        )

        artifacts.error = root_V_pointing_axis.angle_between(root_V_goal_axis_proj)
        return artifacts
