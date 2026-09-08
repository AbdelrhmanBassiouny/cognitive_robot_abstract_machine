"""
Asking the frozen question set of a scene, and checking every answer against what the
twin actually holds.

The scene is a two-arm robot with a table in front of it, a cube and a cylinder standing
on the table and a second cube in its hand, so every bucket working memory can be asked
about today has something to be right or wrong about.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pytest
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.spatial_types.spatial_types import (
    HomogeneousTransformationMatrix,
    SpatialType,
)
from semantic_digital_twin.testing import two_arm_robot_world
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.connections import FixedConnection
from semantic_digital_twin.world_description.geometry import Box, Color, Scale
from semantic_digital_twin.world_description.shape_collection import ShapeCollection
from semantic_digital_twin.world_description.world_entity import Body
from segmind.datastructures.events import PickUpEvent, TranslationEvent
from typing_extensions import Any, List

from experiments.questions.question import (
    BloomLevel,
    Bucket,
    GroundTruthSource,
    Memory,
    RequiredFact,
)
from experiments.questions.question_set import QuestionedThings, QuestionSet
from experiments.questions.working_memory import (
    AnythingMoved,
    HeldInTheHand,
    NumberOfOwnBodies,
    NumberOfOwnDegreesOfFreedom,
    ObjectColours,
    ObjectPlaces,
    ObjectsSeen,
    ObjectsThatMoved,
    ObjectsTheRobotMoved,
    PickedUpRecently,
    PlaceOfOwnBody,
    Side,
    SideOfAnotherObject,
    SupportingSurfaces,
    WorkingMemory,
)

TABLE_COLOUR = Color(0.5, 0.3, 0.1)
"""
What the table is painted, so a colour answer can be told apart from the objects' own.
"""

CUBE_COLOUR = Color(1.0, 0.0, 0.0)
"""
What the cube on the table is painted.
"""

CYLINDER_COLOUR = Color(0.0, 0.0, 1.0)
"""
What the cylinder on the table is painted.
"""

HELD_CUBE_COLOUR = Color(0.0, 1.0, 0.0)
"""
What the cube in the robot's hand is painted.
"""

TABLE_TOP_HEIGHT = 0.05
"""
How thick the table's top is, which is what an object standing on it stands above.
"""

OBJECT_EDGE = 0.1
"""
How wide the cube and the cylinder are, which is what puts them clear of each other.
"""

DISTANCE_ACROSS_THE_TABLE = 0.2
"""
How far to either side of the table's middle the cube and the cylinder stand, which is
what makes one of them left of the other.
"""

# %% the scene every question is asked of


def dye(name: str, colour: Color, scale: Scale) -> Body:
    """
    A body of one box, painted, and named.

    :param name: What the body is called.
    :param colour: What it is painted.
    :param scale: How big the box is.
    """
    body = Body(name=PrefixedName(name))
    body.collision = ShapeCollection(
        [
            Box(
                scale=scale,
                origin=HomogeneousTransformationMatrix.from_xyz_rpy(
                    reference_frame=body
                ),
                color=colour,
            )
        ],
        reference_frame=body,
    )
    return body


@dataclass
class QuestionedScene:
    """
    The scene the frozen set is asked of, and everything the questions single out in it.
    """

    world: World
    """
    The twin the whole scene stands in.
    """

    own_bodies: List[Body]
    """
    The links the robot is made of, taken before anything was put in its hand.
    """

    table: Body
    """
    What the objects stand on.
    """

    cube: Body
    """
    The object most questions are about, and the one the robot moved.
    """

    cylinder: Body
    """
    The object the cube is placed against, and the one nothing happened to.
    """

    held_cube: Body
    """
    The object hanging from the robot's hand.
    """

    own_body_name: PrefixedName
    """
    The robot's own link the self-model questions are about.
    """

    working_memory: WorkingMemory
    """
    What the robot holds right now in this scene.
    """

    question_set: QuestionSet
    """
    The frozen set, asked of this scene.
    """


@pytest.fixture
def scene(two_arm_robot_world: World) -> QuestionedScene:
    """
    A robot with a table in front of it, a cube and a cylinder standing on the table,
    and a second cube in its hand, with the cube reported moved and picked up.
    """
    world = two_arm_robot_world
    own_bodies = list(world.bodies)
    hand = own_bodies[-1]

    table = dye("table", TABLE_COLOUR, Scale(1.0, 1.0, TABLE_TOP_HEIGHT))
    cube = dye("cube", CUBE_COLOUR, Scale(OBJECT_EDGE, OBJECT_EDGE, OBJECT_EDGE))
    cylinder = dye(
        "cylinder", CYLINDER_COLOUR, Scale(OBJECT_EDGE, OBJECT_EDGE, OBJECT_EDGE)
    )
    held_cube = dye(
        "held_cube", HELD_CUBE_COLOUR, Scale(OBJECT_EDGE, OBJECT_EDGE, OBJECT_EDGE)
    )
    standing_height = (TABLE_TOP_HEIGHT + OBJECT_EDGE) / 2

    with world.modify_world():
        world.add_connection(
            FixedConnection(
                parent=world.root,
                child=table,
                parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                    x=1.0, reference_frame=world.root
                ),
            )
        )
        for standing, sideways in (
            (cube, DISTANCE_ACROSS_THE_TABLE),
            (cylinder, -DISTANCE_ACROSS_THE_TABLE),
        ):
            world.add_connection(
                FixedConnection(
                    parent=table,
                    child=standing,
                    parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                        y=sideways, z=standing_height, reference_frame=table
                    ),
                )
            )
        world.add_connection(
            FixedConnection(
                parent=hand,
                child=held_cube,
                parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                    reference_frame=hand
                ),
            )
        )

    working_memory = WorkingMemory(
        world=world,
        own_bodies=own_bodies,
        point_of_view=HomogeneousTransformationMatrix.from_xyz_rpy(x=3.0),
        events=[
            TranslationEvent(tracked_object=cube),
            PickUpEvent(tracked_object=cube),
        ],
    )
    return QuestionedScene(
        world=world,
        own_bodies=own_bodies,
        table=table,
        cube=cube,
        cylinder=cylinder,
        held_cube=held_cube,
        own_body_name=hand.name,
        working_memory=working_memory,
        question_set=QuestionSet.over_working_memory(
            QuestionedThings(
                object_asked_about=cube,
                object_compared_against=cylinder,
                object_in_the_hand=held_cube,
                own_body_asked_about=hand.name,
            )
        ),
    )


@pytest.fixture
def memory(scene: QuestionedScene) -> WorkingMemory:
    """
    What the robot of that scene holds right now.
    """
    return scene.working_memory


def answers_agree(answered: Any, true: Any) -> bool:
    """
    Whether an answer and the truth are the same thing.

    Places are compared as numbers, because two poses standing for the same place are
    two objects and the twin's own equality says so.

    :param answered: What the question answered.
    :param true: What the twin actually holds.
    """
    if isinstance(answered, SpatialType):
        return np.allclose(answered.to_np(), true.to_np())
    if isinstance(answered, list):
        return len(answered) == len(true) and all(
            answers_agree(one, other) for one, other in zip(answered, true)
        )
    return answered == true


# %% what a question declares about itself


def test_a_question_reads_its_answer_type_off_its_binding():
    assert ObjectsSeen().answer_type == List[Body]
    assert NumberOfOwnBodies().answer_type is int
    assert AnythingMoved().answer_type is bool


def test_working_memory_questions_are_understanding_questions(scene: QuestionedScene):
    for question in scene.question_set.questions:
        assert question.memory is Memory.WORKING
        assert question.bloom_level is BloomLevel.UNDERSTANDING


def test_the_working_memory_set_covers_every_bucket_it_can_be_asked_today(
    scene: QuestionedScene,
):
    assert scene.question_set.buckets == [
        Bucket.SCENE,
        Bucket.SUPPORT_AND_SPATIAL_RELATIONS,
        Bucket.TEMPORAL_AND_AGENCY,
        Bucket.EMBODIMENT,
        Bucket.SELF_MODEL,
    ]


def test_a_spatial_question_declares_that_it_reads_the_point_of_view(
    scene: QuestionedScene,
):
    side = SideOfAnotherObject(subject=scene.cube, other=scene.cylinder, side=Side.LEFT)
    assert RequiredFact.POINT_OF_VIEW in side.required_facts
    assert RequiredFact.POINT_OF_VIEW not in ObjectsSeen().required_facts


def test_ground_truth_is_the_twin_in_simulation_and_a_human_check_on_the_robot():
    from coraplex.datastructures.enums import ExecutionType

    assert (
        GroundTruthSource.for_execution(ExecutionType.SIMULATED)
        is GroundTruthSource.TWIN
    )
    assert (
        GroundTruthSource.for_execution(ExecutionType.REAL)
        is GroundTruthSource.CALIBRATED_TWIN_AND_HUMAN_CHECK
    )


# %% scene


def test_the_objects_seen_are_the_bodies_that_are_not_the_robot(
    scene: QuestionedScene, memory: WorkingMemory
):
    assert ObjectsSeen().ask(memory) == [
        scene.table,
        scene.cube,
        scene.cylinder,
        scene.held_cube,
    ]


def test_the_colours_are_the_ones_the_shapes_carry(memory: WorkingMemory):
    assert ObjectColours().ask(memory) == [
        TABLE_COLOUR,
        CUBE_COLOUR,
        CYLINDER_COLOUR,
        HELD_CUBE_COLOUR,
    ]


def test_the_places_are_where_the_twin_puts_the_objects(memory: WorkingMemory):
    question = ObjectPlaces()
    assert answers_agree(question.ask(memory), question.ground_truth(memory))


# %% support and spatial relations


def test_the_cube_stands_on_the_table(scene: QuestionedScene, memory: WorkingMemory):
    assert SupportingSurfaces(subject=scene.cube).ask(memory) == [scene.table]


def test_the_cube_is_left_of_the_cylinder_and_not_right_of_it(
    scene: QuestionedScene, memory: WorkingMemory
):
    left = SideOfAnotherObject(subject=scene.cube, other=scene.cylinder, side=Side.LEFT)
    right = SideOfAnotherObject(
        subject=scene.cube, other=scene.cylinder, side=Side.RIGHT
    )
    assert left.ask(memory) is True
    assert right.ask(memory) is False


# %% temporal and agency


def test_the_event_log_says_something_moved(memory: WorkingMemory):
    assert AnythingMoved().ask(memory) is True


def test_the_object_that_moved_is_the_one_the_event_named(
    scene: QuestionedScene, memory: WorkingMemory
):
    assert ObjectsThatMoved().ask(memory) == [scene.cube]


def test_an_object_moved_after_being_picked_up_is_one_the_robot_moved_itself(
    scene: QuestionedScene, memory: WorkingMemory
):
    assert ObjectsTheRobotMoved().ask(memory) == [scene.cube]


def test_only_the_object_with_a_pick_up_event_was_picked_up(
    scene: QuestionedScene, memory: WorkingMemory
):
    assert PickedUpRecently(subject=scene.cube).ask(memory) is True
    assert PickedUpRecently(subject=scene.cylinder).ask(memory) is False


# %% embodiment


def test_only_the_object_hanging_from_the_robot_is_in_its_hand(
    scene: QuestionedScene, memory: WorkingMemory
):
    assert HeldInTheHand(subject=scene.held_cube).ask(memory) is True
    assert HeldInTheHand(subject=scene.cube).ask(memory) is False


# %% self-model


def test_the_place_of_a_link_is_where_the_twin_puts_it(
    scene: QuestionedScene, memory: WorkingMemory
):
    question = PlaceOfOwnBody(body_name=scene.own_body_name)
    assert answers_agree(question.ask(memory), question.ground_truth(memory))


def test_the_robot_counts_its_own_links_and_not_what_it_is_holding(
    scene: QuestionedScene, memory: WorkingMemory
):
    assert NumberOfOwnBodies().ask(memory) == len(scene.own_bodies)
    assert scene.held_cube not in scene.own_bodies


def test_the_robot_counts_the_joints_it_can_move(memory: WorkingMemory):
    question = NumberOfOwnDegreesOfFreedom()
    assert question.ask(memory) == question.ground_truth(memory)


# %% every question at once


def test_every_question_of_the_set_answers_its_own_ground_truth(
    scene: QuestionedScene, memory: WorkingMemory
):
    for question in scene.question_set.questions:
        assert answers_agree(
            question.ask(memory), question.ground_truth(memory)
        ), question.english


def test_every_question_of_the_set_reads_as_a_question(scene: QuestionedScene):
    for question in scene.question_set.questions:
        assert question.english.endswith("?")
