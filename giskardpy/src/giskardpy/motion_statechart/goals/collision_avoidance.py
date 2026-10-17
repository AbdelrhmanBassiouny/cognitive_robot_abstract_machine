from __future__ import annotations

from dataclasses import field, dataclass

from abc import ABC, abstractmethod

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
from krrood.symbolic_math.symbolic_math import Scalar
from semantic_digital_twin.collision_checking.collision_detector import ClosestPoints
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
from semantic_digital_twin.spatial_types import Vector3
from semantic_digital_twin.world_description.world_entity import Body

# %% shared by self and external collision avoidance


@dataclass(eq=False, repr=False, kw_only=True)
class _CollisionAvoidanceTask(ABC, Task):
    """
    Avoids collisions of :attr:`robot` with one inequality constraint per collision it
    avoids.

    A constraint only weighs anything while collision data was computed for its
    collision, so the controller leaves out every collision that is not close.
    """

    robot: AbstractRobot
    """
    The robot whose collisions are avoided.
    """

    max_velocity: float = 0.2
    """
    The maximum velocity for the collision avoidance task.
    """

    @classproperty
    def required_context_extensions(cls) -> tuple[type[ContextExtension], ...]:
        return super().required_context_extensions + (MotionControlContext,)

    @staticmethod
    def _weight_while_close(contact_normal: Vector3) -> Scalar:
        """
        :param contact_normal: The contact normal of one avoided collision, zero while no
            collision data was computed for it.
        :return: The collision avoidance weight while there is collision data, zero
            otherwise.
        """
        return sm.if_eq_zero(
            contact_normal.norm(),
            if_result=0,
            else_result=DefaultWeights.WEIGHT_COLLISION_AVOIDANCE,
        )

    @staticmethod
    def _none_violated(distances: list[tuple[Scalar, Scalar]]) -> Scalar:
        """
        :param distances: The contact distance and the violated distance of every
            avoided collision.
        :return: An expression that is True while no contact distance is below its
            violated distance.
        """
        if not distances:
            return Scalar.const_true()
        return sm.logic_all([contact >= violated for contact, violated in distances])

    @abstractmethod
    def violated_collisions(self) -> list[tuple[ClosestPoints, float]]:
        """
        :return: Every avoided collision whose contact distance is below its violated
            distance, with that violated distance.
        """


@dataclass(eq=False, repr=False, kw_only=True)
class _CancelBecauseCollisionViolated(CancelStatechart):
    """
    Cancels the motion when one of the collision avoidance tasks it watches is violated,
    raising an exception detailing the violated collisions.
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

    def create_exception(self, context: StatechartContext) -> CollisionViolatedError:
        violated = [
            violation
            for task in self.tasks
            if task.observation_state == ObservationStateValues.FALSE
            for violation in task.violated_collisions()
        ]
        return CollisionViolatedError(
            violated_collisions=[collision for collision, _ in violated],
            thresholds=[threshold for _, threshold in violated],
        )


def _the_only_robot(node: CompositeNode, context: StatechartContext) -> AbstractRobot:
    """
    :param node: The collision avoidance goal that was given no robot.
    :param context: The context `node` is expanded in.
    :return: The only robot in the world of `context`.
    :raises UnexpectedWorldEntityCountError: If that world holds no robot or several.
    """
    robots = context.world.get_semantic_annotations_by_type(AbstractRobot)
    if len(robots) != 1:
        raise UnexpectedWorldEntityCountError(
            node=node,
            expected_count=1,
            actual_count=len(robots),
            entity_type=AbstractRobot,
        )
    return robots[0]


# %% external collision avoidance


@dataclass(eq=False, repr=False, kw_only=True)
class _ExternalCollisionAvoidanceTask(_CollisionAvoidanceTask):
    """
    Avoids external collisions between every collision group of :attr:`robot` and the
    objects in the environment closest to it.

    For every avoided contact, moves `root_T_group @ group_P_contact` in the direction
    of its contact normal until the distance is larger than its buffer zone. Its
    observation turns false once a distance drops below its violated distance.
    """

    _external_collision_manager: Optional[ExternalCollisionVariableManager] = field(
        default=None, init=False, repr=False
    )
    """
    The external collision variable manager of the context this node is built in.
    """

    _avoided_contacts: list[tuple[CollisionGroup, int]] = field(
        default_factory=list, init=False, repr=False
    )
    """
    See :attr:`avoided_contacts`.
    """

    @property
    def avoided_contacts(self) -> list[tuple[CollisionGroup, int]]:
        """
        :return: One entry per constraint, in order: the collision group and the rank by
            distance of the environment object it avoids, 0 for the closest.
        """
        return self._avoided_contacts

    def build(self, context: StatechartContext) -> NodeArtifacts:
        """
        Registers every collision group of :attr:`robot` that avoids external collisions
        with the external collision variable manager of `context`, which this node reads
        from then on.
        """
        self._external_collision_manager = context.require_extension(
            MotionControlContext
        ).external_collision_manager
        self._avoided_contacts = []
        for group in self._groups_avoiding_external_collisions(context):
            self._external_collision_manager.register_group_of_body(group.root)
            self._avoided_contacts.extend(
                (group, index)
                for index in range(
                    group.get_max_avoided_bodies(context.world.collision_manager)
                )
            )
        return super().build(context)

    def _groups_avoiding_external_collisions(
        self, context: StatechartContext
    ) -> list[CollisionGroup]:
        """
        :return: The collision groups rooted in :attr:`robot` that hold a body avoiding
            at least one external collision, each once.
        """
        robot_bodies = self.robot.bodies
        groups = []
        for body in self.robot.bodies_with_collision:
            if not context.world.collision_manager.get_max_avoided_bodies(body):
                continue
            group = self._external_collision_manager.get_collision_group(body)
            if group not in groups and group.root in robot_bodies:
                groups.append(group)
        return groups

    def build_artifacts(self, context: StatechartContext) -> MotionNodeArtifacts:
        artifacts = MotionNodeArtifacts()
        manager = self._external_collision_manager
        for group, index in self.avoided_contacts:
            root_T_group = context.world.compose_forward_kinematics_expression(
                context.world.root, group.root
            )
            root_V_point_on_group = (
                root_T_group @ manager.get_group_a_P_point_on_a_symbol(group, index)
            ).vector3
            root_V_contact_normal = manager.get_root_V_contact_normal_symbol(
                group, index
            )
            artifacts.constraints.add_inequality_constraint(
                name=f"{group.root.name}/{index}",
                reference_velocity=self.max_velocity,
                lower_error=manager.get_buffer_distance_symbol(group, index)
                - manager.get_contact_distance_symbol(group, index),
                upper_error=float("inf"),
                quadratic_weight=self._weight_while_close(root_V_contact_normal),
                # the position distance is not accurate, but the derivative is still correct
                task_expression=root_V_contact_normal @ root_V_point_on_group,
            )
        artifacts.observation = self._none_violated(
            [
                (
                    manager.get_contact_distance_symbol(group, index),
                    manager.get_violated_distance_symbol(group, index),
                )
                for group, index in self.avoided_contacts
            ]
        )
        return artifacts

    def violated_collisions(self) -> list[tuple[ClosestPoints, float]]:
        manager = self._external_collision_manager
        violated = []
        for group, index in self.avoided_contacts:
            contact_distance = manager.get_contact_distance_symbol(
                group, index
            ).evaluate()[0]
            violated_distance = manager.get_violated_distance_symbol(
                group, index
            ).evaluate()[0]
            if contact_distance < violated_distance:
                closest_first = sorted(
                    manager.last_closest_contacts[group],
                    key=lambda contact: contact.distance,
                )
                violated.append((closest_first[index], violated_distance))
        return violated


@dataclass(eq=False, repr=False, kw_only=True)
class _CancelBecauseExternalCollisionViolated(_CancelBecauseCollisionViolated):
    """
    Cancels the motion when an external collision is violated.
    """

    tasks: list[_ExternalCollisionAvoidanceTask]
    """
    The external collision avoidance tasks to check for collisions.
    """


@dataclass(eq=False, repr=False, kw_only=True)
class ExternalCollisionAvoidance(EndedByOwner, CompositeNode):
    """
    Avoids external collisions of every collision group of the robot with one task, and
    cancels the motion once one of them is violated.

    ..note:: Its children are left out of drawings. Set
        `plot_specifications.collapse_children` to False to draw them.
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
        Add the task avoiding every external collision of :attr:`robot`, and the node
        cancelling the motion once one is violated.

        The task decides which collisions it avoids when it is built, in the context
        that runs it.
        """
        if self.robot is None:
            self.robot = _the_only_robot(self, context)
        task = _ExternalCollisionAvoidanceTask(
            name=f"{self.name}/task", robot=self.robot, max_velocity=self.max_velocity
        )
        self._add_child_to_statechart(task)
        if self.cancel_if_collision_violated:
            self._add_child_to_statechart(
                _CancelBecauseExternalCollisionViolated(
                    tasks=[task],
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


# %% temporary collision rules


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


# %% self collision avoidance


@dataclass(eq=False, repr=False, kw_only=True)
class _SelfCollisionAvoidanceTask(_CollisionAvoidanceTask):
    """
    Avoids self collisions between every checked combination of two collision groups of
    :attr:`robot`.

    For every combination, moves `group_a_P_point_on_a @ group_b_P_point_on_b` in the
    direction of its contact normal until the distance is larger than its buffer zone.
    Its observation turns false once a distance drops below its violated distance.
    """

    _self_collision_manager: Optional[SelfCollisionVariableManager] = field(
        default=None, init=False, repr=False
    )
    """
    The self collision variable manager of the context this node is built in.
    """

    _checked_combinations: list[tuple[CollisionGroup, CollisionGroup]] = field(
        default_factory=list, init=False, repr=False
    )
    """
    See :attr:`checked_combinations`.
    """

    @property
    def checked_combinations(self) -> list[tuple[CollisionGroup, CollisionGroup]]:
        """
        :return: One combination of collision groups per constraint, in order.
        """
        return self._checked_combinations

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

    def build(self, context: StatechartContext) -> NodeArtifacts:
        """
        Registers every combination of collision groups of :attr:`robot` that the self
        collision matrix checks with the self collision variable manager of `context`,
        which this node reads from then on.
        """
        self._self_collision_manager = context.require_extension(
            MotionControlContext
        ).self_collision_manager
        collision_matrix = self.create_self_collision_matrix(context)
        kinematic_structure_entities = self.robot.kinematic_structure_entities
        self._checked_combinations = []
        for group_a, group_b in combinations(
            self._self_collision_manager.collision_groups, 2
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
            self._self_collision_manager.register_groups_of_body_combination(
                group_a.root, group_b.root
            )
            self._checked_combinations.append(
                self._self_collision_manager.body_pair_to_group_pair(
                    group_a.root, group_b.root
                )
            )
        return super().build(context)

    def build_artifacts(self, context: StatechartContext) -> MotionNodeArtifacts:
        artifacts = MotionNodeArtifacts()
        manager = self._self_collision_manager
        for group_a, group_b in self.checked_combinations:
            group_b_T_group_a = context.world.compose_forward_kinematics_expression(
                group_b.root, group_a.root
            )
            group_b_P_point_on_a = (
                group_b_T_group_a
                @ manager.get_group_a_P_point_on_a_symbol(group_a, group_b)
            )
            group_b_V_point_on_b_to_point_on_a = (
                group_b_P_point_on_a
                - manager.get_group_b_P_point_on_b_symbol(group_a, group_b)
            )
            group_b_V_contact_normal = manager.get_group_b_V_contact_normal_symbol(
                group_a, group_b
            )
            artifacts.constraints.add_inequality_constraint(
                name=f"{group_a.root.name}/{group_b.root.name}",
                reference_velocity=self.max_velocity,
                lower_error=manager.get_buffer_distance_symbol(group_a, group_b)
                - manager.get_contact_distance_symbol(group_a, group_b),
                upper_error=float("inf"),
                quadratic_weight=self._weight_while_close(group_b_V_contact_normal),
                task_expression=group_b_V_contact_normal
                @ group_b_V_point_on_b_to_point_on_a,
            )
        artifacts.observation = self._none_violated(
            [
                (
                    manager.get_contact_distance_symbol(group_a, group_b),
                    manager.get_violated_distance_symbol(group_a, group_b),
                )
                for group_a, group_b in self.checked_combinations
            ]
        )
        return artifacts

    def violated_collisions(self) -> list[tuple[ClosestPoints, float]]:
        manager = self._self_collision_manager
        violated = []
        for group_a, group_b in self.checked_combinations:
            contact_distance = manager.get_contact_distance_symbol(
                group_a, group_b
            ).evaluate()[0]
            violated_distance = manager.get_violated_distance_symbol(
                group_a, group_b
            ).evaluate()[0]
            if contact_distance < violated_distance:
                closest = manager.last_closest_contacts[group_a, group_b][0]
                violated.append((closest, violated_distance))
        return violated


@dataclass(eq=False, repr=False, kw_only=True)
class _CancelBecauseSelfCollisionViolated(_CancelBecauseCollisionViolated):
    """
    Cancels the motion when a self collision is violated.
    """

    tasks: list[_SelfCollisionAvoidanceTask]
    """
    The self collision avoidance tasks to check for collisions.
    """


@dataclass(eq=False, repr=False, kw_only=True)
class SelfCollisionAvoidance(EndedByOwner, CompositeNode):
    """
    Avoids self collisions between every checked combination of collision groups of the
    robot with one task, and cancels the motion once one of them is violated.

    ..note:: Its children are left out of drawings. Set
        `plot_specifications.collapse_children` to False to draw them.
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
        Add the task avoiding every self collision of :attr:`robot`, and the node
        cancelling the motion once one is violated.

        The task decides which combinations of collision groups it avoids when it is
        built, in the context that runs it.
        """
        if self.robot is None:
            self.robot = _the_only_robot(self, context)
        task = _SelfCollisionAvoidanceTask(
            name=f"{self.name}/task", robot=self.robot, max_velocity=self.max_velocity
        )
        self._add_child_to_statechart(task)
        if self.cancel_if_collision_violated:
            self._add_child_to_statechart(
                _CancelBecauseSelfCollisionViolated(
                    name="self collision violated", tasks=[task]
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
