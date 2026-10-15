from __future__ import annotations

from dataclasses import field, dataclass

from typing_extensions import Optional
from itertools import combinations

import krrood.symbolic_math.symbolic_math as sm
from giskardpy.motion_statechart.context import MotionControlContext
from krrood.ormatic.utils import classproperty
from cramph.node import EndedByOwner, SucceedsOnObservingTrue
from cramph.context import ContextExtension, StatechartContext
from cramph.data_types import ObservationStateValues
from giskardpy.motion_statechart.data_types import DefaultWeights
from giskardpy.motion_statechart.exceptions import (
    UnexpectedWorldEntityCountError,
    CollisionViolatedError,
)
from giskardpy.motion_statechart.graph_node import (
    MotionStatechartNode,
    MotionNodeArtifacts,
)
from cramph.node import CompositeNode, NodeArtifacts, CancelStatechart
from giskardpy.motion_statechart.graph_node import Task
from cramph.plotters.plot_specs import NodePlotSpec, plot_specification_field
from krrood.symbolic_math.symbolic_math import Scalar, FloatVariable
from semantic_digital_twin.collision_checking.collision_groups import CollisionGroup
from semantic_digital_twin.collision_checking.collision_matrix import (
    CollisionRule,
    CollisionMatrix,
)
from semantic_digital_twin.collision_checking.collision_rules import (
    AllowCollisionForEndEffector,
    AvoidSelfCollisions,
)
from semantic_digital_twin.collision_checking.collision_variable_managers import (
    SelfCollisionVariableManager,
    ExternalCollisionVariableManager,
)
from semantic_digital_twin.robots.robot_parts import AbstractRobot, EndEffector
from semantic_digital_twin.spatial_types import (
    Vector3,
    Point3,
)
from semantic_digital_twin.world_description.world_entity import (
    KinematicStructureEntity,
    Body,
)


@dataclass(eq=False, repr=False, kw_only=True)
class _CollisionAvoidanceTask(Task):
    """
    Superclass with helper methods for collision avoidance tasks.
    """

    @classproperty
    def required_context_extensions(cls) -> tuple[type[ContextExtension], ...]:
        return super().required_context_extensions + (MotionControlContext,)


@dataclass(eq=False, repr=False, kw_only=True)
class _CancelBecauseCollisionViolated(CancelStatechart):
    """
    Cancels the motion when one of the collision avoidance tasks it watches is violated.
    """

    tasks: list[_CollisionAvoidanceTask]
    """
    The list of collision avoidance tasks to check for collisions.
    """

    exception: Exception = field(init=False, default=Exception)
    """
    Set to init=False, because this class creates its own exception.
    """

    @classproperty
    def required_context_extensions(cls) -> tuple[type[ContextExtension], ...]:
        return super().required_context_extensions + (MotionControlContext,)

    def build(self, context: StatechartContext) -> NodeArtifacts:
        self.start_condition = self.create_violation_condition()
        return NodeArtifacts()

    def create_violation_condition(self) -> Scalar:
        """
        :return: An expression that is True as soon as one of :attr:`tasks` observes a
            violated collision. Without tasks there is nothing to violate, so it stays False.
        """
        if len(self.tasks) == 0:
            return Scalar.const_false()
        return sm.logic_or(*[node.observes_false for node in self.tasks])


@dataclass(eq=False, repr=False, kw_only=True)
class _ExternalCollisionAvoidanceNode(_CollisionAvoidanceTask):
    """
    Avoids external collisions between a collision group and its collision_index-closest
    object in the environment.

    Moves `root_T_tip @ tip_P_contact` in `root_T_contact_normal` direction until the
    distance is larger than buffer_zone.
    """

    body: Body
    """
    The root body of the collision group avoiding external collisions.
    """

    max_velocity: float = 0.2
    """
    The maximum velocity for the collision avoidance task.
    """

    collision_index: int = 0
    """
    The index of the closest object in the collision group.

    e.g. of collision_index=1 it will avoid the 2. closest contact.
    """

    _external_collision_manager: Optional[ExternalCollisionVariableManager] = field(
        default=None, init=False, repr=False
    )
    """
    The external collision variable manager of the context this node is built in.
    """

    def build(self, context: StatechartContext) -> NodeArtifacts:
        """
        Registers the collision group of :attr:`body` with the external collision
        variable manager of `context`, which this node reads from then on.
        """
        self._external_collision_manager = context.require_extension(
            MotionControlContext
        ).external_collision_manager
        self._external_collision_manager.register_group_of_body(self.body)
        return super().build(context)

    @property
    def external_collision_manager(self) -> ExternalCollisionVariableManager:
        """
        :return: The external collision variable manager this node was built with.
        """
        return self._external_collision_manager

    @property
    def collision_group(self) -> CollisionGroup:
        """
        :return: The collision group avoiding external collisions.
        """
        return self.external_collision_manager.get_collision_group(self.body)

    @property
    def root_V_contact_normal(self) -> Vector3:
        return self.external_collision_manager.get_root_V_contact_normal_symbol(
            self.collision_group, self.collision_index
        )

    @property
    def group_a_P_point_on_a(self) -> Point3:
        return self.external_collision_manager.get_group_a_P_point_on_a_symbol(
            self.collision_group, self.collision_index
        )

    @property
    def contact_distance(self):
        return self.external_collision_manager.get_contact_distance_symbol(
            self.collision_group, self.collision_index
        )

    @property
    def buffer_zone_distance(self):
        return self.external_collision_manager.get_buffer_distance_symbol(
            self.collision_group, self.collision_index
        )

    @property
    def violated_distance(self):
        return self.external_collision_manager.get_violated_distance_symbol(
            self.collision_group, self.collision_index
        )

    @property
    def has_collision_data(self) -> Scalar:
        return self.root_V_contact_normal.norm() == 0


@dataclass(eq=False, repr=False, kw_only=True)
class _ExternalCollisionHasData(_ExternalCollisionAvoidanceNode):
    """
    Monitors whether data was computed for the external collision avoidance task.
    """

    def build_artifacts(self, context: StatechartContext) -> MotionNodeArtifacts:
        artifacts = MotionNodeArtifacts()

        artifacts.observation = self.has_collision_data

        return artifacts


@dataclass(eq=False, repr=False, kw_only=True)
class _ExternalCollisionAvoidanceTask(_ExternalCollisionAvoidanceNode):
    """
    Avoids external collisions between a collision group and its collision_index-closest
    object in the environment.

    Moves `root_T_tip @ tip_P_contact` in `root_T_contact_normal` direction until the
    distance is larger than buffer_zone. Its observation turns false once the distance
    drops below violated_distance.
    """

    max_velocity: float = 0.2
    """
    The maximum velocity for the collision avoidance task.
    """

    @property
    def tip(self) -> KinematicStructureEntity:
        return self.collision_group.root

    def create_weight(self, context: StatechartContext) -> sm.Scalar:
        """
        Creates a weight expression for this task which is scaled by the number of
        external collisions.
        """
        max_avoided_bodies = self.collision_group.get_max_avoided_bodies(
            context.world.collision_manager
        )
        number_of_external_collisions = 0
        for index in range(max_avoided_bodies):
            has_collision_data = (
                self.external_collision_manager.get_root_V_contact_normal_symbol(
                    self.collision_group, index
                ).norm()
            )
            is_active = has_collision_data > 0
            number_of_external_collisions += is_active
        weight = sm.Scalar(
            data=DefaultWeights.WEIGHT_COLLISION_AVOIDANCE
        ).safe_division(sm.min(number_of_external_collisions, max_avoided_bodies))
        return weight

    def is_no_collision_violated(self, context: StatechartContext) -> Scalar:
        max_avoided_bodies = self.collision_group.get_max_avoided_bodies(
            context.world.collision_manager
        )
        return sm.logic_all(
            [
                self.contact_distance >= self.violated_distance
                for _ in range(max_avoided_bodies)
            ]
        )

    def build_artifacts(self, context: StatechartContext) -> MotionNodeArtifacts:
        artifacts = MotionNodeArtifacts()

        root_T_group_a = context.world.compose_forward_kinematics_expression(
            context.world.root, self.tip
        )

        root_V_point_on_a = (root_T_group_a @ self.group_a_P_point_on_a).vector3

        # the position distance is not accurate, but the derivative is still correct
        a_projected_on_normal = self.root_V_contact_normal @ root_V_point_on_a

        lower_limit = self.buffer_zone_distance - self.contact_distance

        artifacts.constraints.add_inequality_constraint(
            reference_velocity=self.max_velocity,
            lower_error=lower_limit,
            upper_error=float("inf"),
            quadratic_weight=DefaultWeights.WEIGHT_COLLISION_AVOIDANCE,
            task_expression=a_projected_on_normal,
        )

        artifacts.observation = self.is_no_collision_violated(context)

        return artifacts


@dataclass(eq=False, repr=False, kw_only=True)
class _CancelBecauseExternalCollisionViolated(_CancelBecauseCollisionViolated):
    """
    Cancels the motion by raising an exception detailing which external collision tasks
    were violated.
    """

    tasks: list[_ExternalCollisionAvoidanceTask]
    """
    The list of external collision avoidance tasks to check for collisions.
    """

    exception: Exception = field(init=False, default=Exception)
    """
    Set to init=False, because this class creates its own exception.
    """

    def build_artifacts(self, context: StatechartContext) -> NodeArtifacts:
        self.start_condition = sm.logic_or(
            *[node.observes_false for node in self.tasks]
        )
        return NodeArtifacts()

    def create_exception(self, context: StatechartContext) -> CollisionViolatedError:
        violated_tasks = [
            task
            for task in self.tasks
            if task.observation_state == ObservationStateValues.FALSE
        ]
        collisions = []
        thresholds = []
        for task in violated_tasks:
            collision = context.require_extension(
                MotionControlContext
            ).external_collision_manager.last_closest_contacts[task.collision_group][0]
            collisions.append(collision)
            thresholds.append(task.violated_distance.evaluate()[0])
        return CollisionViolatedError(
            violated_collisions=collisions, thresholds=thresholds
        )


@dataclass(eq=False, repr=False, kw_only=True)
class UpdateTemporaryCollisionRules(EndedByOwner, MotionStatechartNode):
    """
    Keeps temporary collision rules in force while it runs, next to the temporary rules
    of every other node running at the same time.
    """

    temporary_rules: list[CollisionRule]
    """
    The rules in force while this node runs.
    """

    @classmethod
    def for_end_effector(
        cls, end_effector: EndEffector
    ) -> UpdateTemporaryCollisionRules:
        """
        :param end_effector: The end effector that may touch its surroundings.
        :return: A node that lets this end effector, together with whatever it holds,
            collide with the environment.
        """
        return cls(
            temporary_rules=[AllowCollisionForEndEffector(end_effector=end_effector)]
        )

    def build_artifacts(self, context: StatechartContext) -> MotionNodeArtifacts:
        artifacts = MotionNodeArtifacts()
        artifacts.observation = sm.Scalar.const_true()
        return artifacts

    def on_start(self, context: StatechartContext):
        """
        :raises TemporaryCollisionRulesDependOnOrder: If it would matter whether
            :attr:`temporary_rules` or the temporary rules already in force are applied
            first.
        """
        context.world.collision_manager.put_temporary_rules_in_force(
            self.temporary_rules
        )

    def on_end(self, context: StatechartContext):
        context.world.collision_manager.take_temporary_rules_out_of_force(
            self.temporary_rules
        )


@dataclass(eq=False, repr=False, kw_only=True)
class SetInitialTemporaryCollisionRules(SucceedsOnObservingTrue, MotionStatechartNode):
    """
    Updates the temporary collision rules for the robot.
    """

    temporary_rules: list[CollisionRule]
    collision_matrix: CollisionMatrix = field(init=False)
    set_on_build: bool = True
    """
    Whether to set the collision matrix on build.
    """

    def build_artifacts(self, context: StatechartContext) -> MotionNodeArtifacts:
        artifacts = MotionNodeArtifacts()
        # safe old rules
        old_temporary_rules = list(context.world.collision_manager.temporary_rules)

        # compute collision matrix with new rules
        context.world.collision_manager.clear_temporary_rules()
        context.world.collision_manager.extend_temporary_rule(self.temporary_rules)
        context.world.collision_manager.update_collision_matrix()
        self.collision_matrix = context.world.collision_manager.collision_matrix

        # restore old rules
        if not self.set_on_build:
            context.world.collision_manager.clear_temporary_rules()
            context.world.collision_manager.extend_temporary_rule(old_temporary_rules)
            context.world.collision_manager.update_collision_matrix()

        artifacts.observation = sm.Scalar.const_true()
        return artifacts

    def on_start(self, context: StatechartContext):
        context.world.collision_manager.set_collision_matrix(self.collision_matrix)


@dataclass(eq=False, repr=False, kw_only=True)
class ExternalCollisionAvoidance(EndedByOwner, CompositeNode):
    """
    A goal combining an ExternalCollisionDistanceMonitor and an
    ExternalCollisionAvoidanceTask. One pair will be added for all collision groups of
    the robot. The task will only be active if the monitor detects that a collision is
    close.

    ..note:: This goal expands into one node pair per collision group, so its children are
        left out of drawings. Set `plot_specifications.collapse_children` to False to draw them.
    """

    plot_specifications: NodePlotSpec = plot_specification_field(
        NodePlotSpec.create_collapsed_composite_node_style
    )

    robot: AbstractRobot = None
    """
    The robot for which the collision avoidance goal is defined.
    """

    max_velocity: float = 0.2
    """
    The maximum velocity for the collision avoidance task.
    """

    cancel_if_collision_violated: bool = True
    """
    If True, the motion will be canceled if a collision is violated.
    """

    @classproperty
    def required_context_extensions(cls) -> tuple[type[ContextExtension], ...]:
        return super().required_context_extensions + (MotionControlContext,)

    def expand(self, context: StatechartContext) -> None:
        """
        Add one monitor and task pair per collision group of :attr:`robot` and closest
        object it avoids.

        Only the structure is decided here; the children register their collision groups
        when they are built, in the context that runs them.
        """
        if self.robot is None:
            robots = context.world.get_semantic_annotations_by_type(AbstractRobot)
            if len(robots) != 1:
                raise UnexpectedWorldEntityCountError(
                    node=self,
                    expected_count=1,
                    actual_count=len(robots),
                    entity_type=AbstractRobot,
                )
            self.robot = robots[0]
        external_collision_manager = context.require_extension(
            MotionControlContext
        ).external_collision_manager
        groups = []
        for body in self.robot.bodies_with_collision:
            if not context.world.collision_manager.get_max_avoided_bodies(body):
                continue
            group = external_collision_manager.get_collision_group(body)
            if group not in groups:
                groups.append(group)

        robot_bodies = self.robot.bodies

        tasks = []

        for group in groups:
            if group.root not in robot_bodies:
                continue
            max_avoided_bodies = group.get_max_avoided_bodies(
                context.world.collision_manager
            )
            for index in range(max_avoided_bodies):
                distance_monitor = _ExternalCollisionHasData(
                    name=f"{self.name}/monitor({group.root.name.name, index})",
                    body=group.root,
                    collision_index=index,
                )
                self._add_child_to_statechart(distance_monitor)

                task = _ExternalCollisionAvoidanceTask(
                    name=f"{self.name}/task({group.root.name.name, index})",
                    body=group.root,
                    max_velocity=self.max_velocity,
                    collision_index=index,
                )
                self._add_child_to_statechart(task)
                task.pause_condition = distance_monitor.observes_true
                tasks.append(task)

        if self.cancel_if_collision_violated:
            self._add_child_to_statechart(
                _CancelBecauseExternalCollisionViolated(
                    tasks=tasks,
                    name="External Collision Violated",
                )
            )


@dataclass(eq=False, repr=False, kw_only=True)
class ExternalCollisionDistanceMonitor(EndedByOwner, MotionStatechartNode):
    """
    Monitors the distance to the closest external object for a specific collision group
    of a body. Turns True if the distance falls below a given threshold.

    .. note:: the input bodies are only used to look up the collision groups.
    """

    body: Body
    """
    The robot body to monitor.
    """

    threshold: float
    """
    Distance threshold in meters.
    """

    collision_index: int = 0
    """Index of the closest collision (0 = closest, 1 = second closest, etc.)."""

    @classproperty
    def required_context_extensions(cls) -> tuple[type[ContextExtension], ...]:
        return super().required_context_extensions + (MotionControlContext,)

    def build_artifacts(self, context: StatechartContext) -> MotionNodeArtifacts:
        # 1. Access the shared external collision manager
        # This automatically registers the manager with the CollisionManager
        manager = context.require_extension(
            MotionControlContext
        ).external_collision_manager

        # 2. Register the body to ensure the manager tracks its collisions
        manager.register_group_of_body(self.body)
        group = manager.get_collision_group(self.body)

        # 3. Retrieve the symbolic variable for the contact distance
        distance_symbol = manager.get_contact_distance_symbol(
            group=group, idx=self.collision_index
        )

        # 4. Return an observation artifact
        # The node's observation_variable will be True when distance < threshold
        return MotionNodeArtifacts(observation=distance_symbol < self.threshold)


@dataclass(eq=False, repr=False, kw_only=True)
class _SelfCollisionAvoidanceNode(_CollisionAvoidanceTask):
    """
    Avoids self collisions between two collision groups.

    Moves `group_a_P_point_on_a @ group_b_P_point_on_b` in
    `group_a_T_group_b_contact_normal` direction until the distance is larger than
    buffer_zone.
    """

    body_a: Body
    """
    The root body of the first collision group to avoid self collisions with.
    """

    body_b: Body
    """
    The root body of the second collision group to avoid self collisions with.
    """

    max_velocity: float = 0.2
    """
    The maximum velocity for the collision avoidance task.
    """

    _self_collision_manager: Optional[SelfCollisionVariableManager] = field(
        default=None, init=False, repr=False
    )
    """
    The self collision variable manager of the context this node is built in.
    """

    def build(self, context: StatechartContext) -> NodeArtifacts:
        """
        Registers the combination of the collision groups of :attr:`body_a` and
        :attr:`body_b` with the self collision variable manager of `context`, which this
        node reads from then on.
        """
        self._self_collision_manager = context.require_extension(
            MotionControlContext
        ).self_collision_manager
        self._self_collision_manager.register_groups_of_body_combination(
            self.body_a, self.body_b
        )
        return super().build(context)

    @property
    def self_collision_manager(self) -> SelfCollisionVariableManager:
        """
        :return: The self collision variable manager this node was built with.
        """
        return self._self_collision_manager

    @property
    def collision_group_a(self) -> CollisionGroup:
        """
        :return: The first collision group to avoid self collisions with.
        """
        return self.self_collision_manager.body_pair_to_group_pair(
            self.body_a, self.body_b
        )[0]

    @property
    def collision_group_b(self) -> CollisionGroup:
        """
        :return: The second collision group to avoid self collisions with.
        """
        return self.self_collision_manager.body_pair_to_group_pair(
            self.body_a, self.body_b
        )[1]

    @property
    def group_a_P_point_on_a(self) -> Point3:
        return self.self_collision_manager.get_group_a_P_point_on_a_symbol(
            self.collision_group_a, self.collision_group_b
        )

    @property
    def group_b_P_point_on_b(self) -> Point3:
        return self.self_collision_manager.get_group_b_P_point_on_b_symbol(
            self.collision_group_a, self.collision_group_b
        )

    @property
    def group_b_V_contact_normal(self) -> Vector3:
        return self.self_collision_manager.get_group_b_V_contact_normal_symbol(
            self.collision_group_a, self.collision_group_b
        )

    @property
    def contact_distance(self) -> FloatVariable:
        return self.self_collision_manager.get_contact_distance_symbol(
            self.collision_group_a,
            self.collision_group_b,
        )

    @property
    def buffer_zone_distance(self) -> FloatVariable:
        return self.self_collision_manager.get_buffer_distance_symbol(
            self.collision_group_a, self.collision_group_b
        )

    @property
    def violated_distance(self) -> FloatVariable:
        return self.self_collision_manager.get_violated_distance_symbol(
            self.collision_group_a, self.collision_group_b
        )

    @property
    def has_collision_data(self) -> Scalar:
        return self.group_b_V_contact_normal.norm() == 0


@dataclass(eq=False, repr=False, kw_only=True)
class _SelfCollisionHasData(_SelfCollisionAvoidanceNode):
    """
    Monitors whether data was computed for the self collision avoidance task.
    """

    def build_artifacts(self, context: StatechartContext) -> MotionNodeArtifacts:
        artifacts = MotionNodeArtifacts()

        artifacts.observation = self.has_collision_data

        return artifacts


@dataclass(eq=False, repr=False, kw_only=True)
class _SelfCollisionAvoidanceTask(_SelfCollisionAvoidanceNode):
    """
    Avoids self collisions between two collision groups.

    Moves `group_a_P_point_on_a @ group_b_P_point_on_b` in
    `group_a_T_group_b_contact_normal` direction until the distance is larger than
    buffer_zone. Its observation turns false once the distance drops below
    violated_distance.
    """

    max_velocity: float = 0.2
    """
    The maximum velocity for the collision avoidance task.
    """

    def is_collision_not_violated(self) -> Scalar:
        return self.contact_distance >= self.violated_distance

    def build_artifacts(self, context: StatechartContext) -> MotionNodeArtifacts:
        artifacts = MotionNodeArtifacts()

        group_b_T_group_a = context.world.compose_forward_kinematics_expression(
            self.collision_group_b.root, self.collision_group_a.root
        )

        group_b_P_point_on_a = group_b_T_group_a @ self.group_a_P_point_on_a

        group_b_V_point_on_b_to_point_on_a = (
            group_b_P_point_on_a - self.group_b_P_point_on_b
        )

        a_projected_on_normal = (
            self.group_b_V_contact_normal @ group_b_V_point_on_b_to_point_on_a
        )

        lower_limit = self.buffer_zone_distance - self.contact_distance

        artifacts.constraints.add_inequality_constraint(
            reference_velocity=self.max_velocity,
            lower_error=lower_limit,
            upper_error=float("inf"),
            quadratic_weight=DefaultWeights.WEIGHT_COLLISION_AVOIDANCE,
            task_expression=a_projected_on_normal,
        )

        artifacts.observation = self.is_collision_not_violated()
        return artifacts


@dataclass(eq=False, repr=False, kw_only=True)
class _CancelBecauseSelfCollisionViolated(_CancelBecauseCollisionViolated):
    """
    Cancels the motion by raising an exception detailing which self collision tasks were
    violated.
    """

    tasks: list[_SelfCollisionAvoidanceTask]
    """
    The list of self collision avoidance tasks to check for collisions.
    """

    exception: Exception = field(init=False, default=Exception)
    """
    Set to init=False, because this class creates its own exception.
    """

    def build_artifacts(self, context: StatechartContext) -> NodeArtifacts:
        self.start_condition = sm.logic_or(
            *[node.observes_false for node in self.tasks]
        )
        return NodeArtifacts()

    def create_exception(self, context: StatechartContext) -> CollisionViolatedError:
        violated_tasks = [
            task
            for task in self.tasks
            if task.observation_state == ObservationStateValues.FALSE
        ]
        collisions = []
        thresholds = []
        for task in violated_tasks:
            collision = context.require_extension(
                MotionControlContext
            ).self_collision_manager.last_closest_contacts[
                task.collision_group_a, task.collision_group_b
            ][
                0
            ]
            collisions.append(collision)
            thresholds.append(task.violated_distance.evaluate()[0])
        return CollisionViolatedError(
            violated_collisions=collisions, thresholds=thresholds
        )


@dataclass(eq=False, repr=False, kw_only=True)
class SelfCollisionAvoidance(EndedByOwner, CompositeNode):
    """
    A goal combining a SelfCollisionDistanceMonitor and a SelfCollisionAvoidanceTask.
    One pair will be added for all collision groups of the robot. The task will only be
    active if the monitor detects that a collision is close.

    ..note:: This goal expands into one node pair per checked body combination, so its
        children are left out of drawings. Set `plot_specifications.collapse_children` to False to
        draw them.
    """

    plot_specifications: NodePlotSpec = plot_specification_field(
        NodePlotSpec.create_collapsed_composite_node_style
    )

    robot: AbstractRobot = None
    """
    The robot for which the collision avoidance goal is defined.
    """

    max_velocity: float = 0.2
    """
    The maximum velocity for the collision avoidance task.
    """

    cancel_if_collision_violated: bool = True
    """
    If True, the motion will be canceled if a collision is violated.
    """

    @classproperty
    def required_context_extensions(cls) -> tuple[type[ContextExtension], ...]:
        return super().required_context_extensions + (MotionControlContext,)

    def create_self_collision_matrix(
        self, context: StatechartContext
    ) -> CollisionMatrix:
        """
        Creates a collision matrix that contains all body combinations except those that
        are always filtered.

        We need this because we don't know how the collision matrix might change during
        the motion
        """
        collision_matrix = CollisionMatrix()
        avoid_self_collisions = AvoidSelfCollisions(robot=self.robot)
        avoid_self_collisions.update(context.world)
        avoid_self_collisions.apply_to_collision_matrix(collision_matrix)
        for (
            ignore_collision_rule
        ) in context.world.collision_manager.ignore_collision_rules:
            ignore_collision_rule.apply_to_collision_matrix(collision_matrix)
        return collision_matrix

    def expand(self, context: StatechartContext) -> None:
        """
        Add one monitor and task pair per checked combination of collision groups of
        :attr:`robot`.

        Only the structure is decided here; the children register their combination
        of collision groups when they are built, in the context that runs them.
        """
        if self.robot is None:
            robots = context.world.get_semantic_annotations_by_type(AbstractRobot)
            if len(robots) != 1:
                raise UnexpectedWorldEntityCountError(
                    node=self,
                    expected_count=1,
                    actual_count=len(robots),
                    entity_type=AbstractRobot,
                )
            self.robot = robots[0]

        self_collision_manager = context.require_extension(
            MotionControlContext
        ).self_collision_manager
        collision_matrix = self.create_self_collision_matrix(context)

        kinematic_structure_entities = self.robot.kinematic_structure_entities

        tasks = []

        for group_a, group_b in combinations(
            self_collision_manager.collision_groups, 2
        ):
            if (
                group_a.root not in kinematic_structure_entities
                or group_b.root not in kinematic_structure_entities
            ):
                # this is no self collision
                continue
            if not collision_matrix.is_collision_groups_combination_checked(
                group_a, group_b
            ):
                # skip because this self collision is never checked
                continue
            group_a, group_b = self_collision_manager.body_pair_to_group_pair(
                group_a.root, group_b.root
            )

            distance_monitor = _SelfCollisionHasData(
                name=f"{self.name}/{group_a.root.name.name, group_b.root.name.name}/monitor",
                body_a=group_a.root,
                body_b=group_b.root,
            )
            self._add_child_to_statechart(distance_monitor)

            task = _SelfCollisionAvoidanceTask(
                name=f"{self.name}/{group_a.root.name.name, group_b.root.name.name}/task",
                body_a=group_a.root,
                body_b=group_b.root,
                max_velocity=self.max_velocity,
            )
            self._add_child_to_statechart(task)
            task.pause_condition = distance_monitor.observes_true
            tasks.append(task)

        if self.cancel_if_collision_violated:
            self._add_child_to_statechart(
                _CancelBecauseSelfCollisionViolated(
                    name="self collision violated", tasks=tasks
                )
            )


@dataclass(eq=False, repr=False, kw_only=True)
class SelfCollisionDistanceMonitor(EndedByOwner, MotionStatechartNode):
    """
    Monitors the distance to the closest external object for the group of a body.

    Turns True if the distance falls below a given threshold.
    .. note:: the input bodies are only used to look up the collision groups.
    """

    body_a: Body
    """
    First robot body to monitor.
    """

    body_b: Body
    """
    Second robot body to monitor.
    """

    threshold: float
    """
    Distance threshold in meters.
    """

    @classproperty
    def required_context_extensions(cls) -> tuple[type[ContextExtension], ...]:
        return super().required_context_extensions + (MotionControlContext,)

    def build_artifacts(self, context: StatechartContext) -> MotionNodeArtifacts:
        manager = context.require_extension(MotionControlContext).self_collision_manager

        manager.register_groups_of_body_combination(self.body_a, self.body_b)
        group_a, group_b = manager.body_pair_to_group_pair(self.body_a, self.body_b)

        distance_symbol = manager.get_contact_distance_symbol(group_a, group_b)

        return MotionNodeArtifacts(observation=distance_symbol < self.threshold)
