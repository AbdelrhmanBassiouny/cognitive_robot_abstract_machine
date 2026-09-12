"""
What the controller was constrained by, asked of the live chart rather than of a store.
"""

from giskardpy.executor import Executor
from giskardpy.motion_statechart.context import MotionStatechartContext
from giskardpy.motion_statechart.goals.collision_avoidance import (
    CollisionAvoidanceTask,
    ExternalCollisionAvoidance,
    UpdateTemporaryCollisionRules,
)
from giskardpy.motion_statechart.graph_node import EndMotion, Task
from giskardpy.motion_statechart.monitors.monitors import LocalMinimumReached
from giskardpy.motion_statechart.motion_statechart import MotionStatechart
from giskardpy.motion_statechart.tasks.cartesian_tasks import CartesianPosition
from giskardpy.motion_statechart.tasks.joint_tasks import (
    JointPositionList,
    JointState,
    JointVelocityLimit,
)
from giskardpy.qp.constraint import GiskardConstraint
from giskardpy.qp.enforcement_strategy import VelocityStrategy
from krrood.entity_query_language.factories import (
    an,
    contains,
    entity,
    flat_variable,
    not_,
    variable,
)
from krrood.entity_query_language.predicate import HasType
from semantic_digital_twin.collision_checking.collision_rules import (
    AvoidExternalCollisions,
)
from semantic_digital_twin.robots.robot_parts import AbstractRobot
from semantic_digital_twin.spatial_types.spatial_types import Point3
from semantic_digital_twin.world import World
from typing_extensions import List

JOINT_GOAL = 0.5
"""
The position the joint task drives its joint to, in meters.
"""

MAX_JOINT_VELOCITY = 0.1
"""
The speed the velocity task caps the same joint at, in meters per second.
"""

REACHED_DISTANCE = 1.0
"""
How far along x the cartesian task reaches, in meters, which is past the environment the
collision avoidance keeps the robot clear of.
"""

BUFFER_ZONE_DISTANCE = 0.05
"""
The distance from which on collision avoidance pushes back, in meters.
"""

VIOLATED_DISTANCE = 0.0
"""
The distance below which a collision counts as violated, in meters.
"""

# %% comparing answers


def constraint_identities(constraints: List[GiskardConstraint]) -> List[int]:
    """
    The identities of the given constraints, which answers are compared by.

    A constraint's dataclass equality compares its symbolic expression, and that has no
    truth value while free variables are left in it.

    :param constraints: The constraints to take the identities of.
    """
    return [id(constraint) for constraint in constraints]


# %% the charts the questions are asked of


def chart_that_holds_a_position_and_a_velocity_task(world: World) -> MotionStatechart:
    """
    A compiled chart whose two tasks constrain one joint in different ways.

    :param world: The world the chart is compiled against.
    """
    connection = world.controlled_connections[0]
    chart = MotionStatechart()
    chart.add_nodes(
        [
            position := JointPositionList(
                goal_state=JointState.from_mapping({connection: JOINT_GOAL})
            ),
            JointVelocityLimit(
                connections=[connection], max_velocity=MAX_JOINT_VELOCITY
            ),
            end := EndMotion(),
        ]
    )
    end.start_condition = position.observation_variable
    Executor(MotionStatechartContext(world=world)).compile(chart)
    return chart


def chart_that_reaches_while_avoiding_a_collision(world: World) -> MotionStatechart:
    """
    A compiled chart that reaches for a point while keeping the robot clear of what is
    around it.

    :param world: The world the chart is compiled against.
    """
    robot = world.get_semantic_annotations_by_type(AbstractRobot)[0]
    chart = MotionStatechart()
    chart.add_nodes(
        [
            UpdateTemporaryCollisionRules(
                temporary_rules=[
                    AvoidExternalCollisions(
                        robot=robot,
                        buffer_zone_distance=BUFFER_ZONE_DISTANCE,
                        violated_distance=VIOLATED_DISTANCE,
                    )
                ]
            ),
            CartesianPosition(
                root_link=world.root,
                tip_link=robot.root,
                goal_point=Point3(x=REACHED_DISTANCE, reference_frame=world.root),
            ),
            ExternalCollisionAvoidance(robot=robot),
            local_minimum := LocalMinimumReached(),
        ]
    )
    chart.add_node(EndMotion.when_true(local_minimum))
    Executor(MotionStatechartContext(world=world)).compile(chart)
    return chart


# %% which constraints a task gave the controller


def test_the_constraints_of_one_task_type_are_answered_without_a_handed_domain(
    prismatic_bot,
):
    """
    A node is in the symbol graph from the moment it is made, so asking what one kind of
    task constrained ranges over what the process already tracks instead of being handed
    the chart.
    """
    chart = chart_that_holds_a_position_and_a_velocity_task(prismatic_bot)
    [position_task] = chart.get_nodes_by_type(JointPositionList)

    task = variable(type_=JointPositionList)
    constraint = flat_variable(task.constraints)
    answered = list(
        an(entity(constraint).where(contains(chart.nodes, task))).evaluate()
    )

    assert position_task.constraints
    assert constraint_identities(answered) == constraint_identities(
        position_task.constraints
    )


def test_a_node_that_was_never_built_constrained_nothing(prismatic_bot):
    """
    A node only gets its constraints when it is built, and one that never was answers
    with none rather than refusing to be read.
    """
    connection = prismatic_bot.controlled_connections[0]

    task = JointPositionList(
        goal_state=JointState.from_mapping({connection: JOINT_GOAL})
    )

    assert task.constraints == []


# %% which kind of constraint it is


def test_velocity_constraints_are_told_apart_by_their_enforcement_strategy(
    prismatic_bot,
):
    """
    A constraint on a joint's speed is enforced differently from one on where the joint
    should end up, and that strategy is what a question about the kind asks for.
    """
    chart = chart_that_holds_a_position_and_a_velocity_task(prismatic_bot)
    [velocity_task] = chart.get_nodes_by_type(JointVelocityLimit)
    [position_task] = chart.get_nodes_by_type(JointPositionList)

    task = variable(type_=Task)
    constraint = flat_variable(task.constraints)
    answered = list(
        an(
            entity(constraint).where(
                contains(chart.nodes, task),
                constraint.enforcement_strategy == VelocityStrategy,
            )
        ).evaluate()
    )

    assert constraint_identities(answered) == constraint_identities(
        velocity_task.constraints
    )
    assert set(constraint_identities(answered)).isdisjoint(
        constraint_identities(position_task.constraints)
    )


def test_collision_avoidance_constraints_are_left_out_by_their_task_type(
    cylinder_bot_world,
):
    """
    Keeping clear of things is a kind of task rather than a kind of constraint, so
    everything the robot was constrained by other than that is asked for by excluding
    that type.
    """
    chart = chart_that_reaches_while_avoiding_a_collision(cylinder_bot_world)
    [reaching_task] = chart.get_nodes_by_type(CartesianPosition)
    keeping_clear = [
        constraint
        for node in chart.get_nodes_by_type(CollisionAvoidanceTask)
        for constraint in node.constraints
    ]

    task = variable(type_=Task)
    constraint = flat_variable(task.constraints)
    answered = list(
        an(
            entity(constraint).where(
                contains(chart.nodes, task),
                not_(HasType(task, CollisionAvoidanceTask)),
            )
        ).evaluate()
    )

    assert keeping_clear
    assert set(constraint_identities(answered)).isdisjoint(
        constraint_identities(keeping_clear)
    )
    assert set(constraint_identities(reaching_task.constraints)).issubset(
        constraint_identities(answered)
    )
