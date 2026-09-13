"""
Asking the frozen question set of a scene, and checking every answer against what the
twin actually holds.

The scene is a two-arm robot with a table in front of it, a cube and a cylinder standing
on the table and a second cube in its hand, so every bucket working memory can be asked
about today has something to be right or wrong about.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from krrood.adapters.json_serializer import from_json, to_json
from krrood.entity_query_language.predicate import Relation
from typing_extensions import Type
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.reasoning.predicates import Near, SupportedBy
from semantic_digital_twin.spatial_types.spatial_types import (
    HomogeneousTransformationMatrix,
    Point3,
)
from semantic_digital_twin.robots.minimal_robot import MinimalRobot
from semantic_digital_twin.robots.robot_parts import AbstractRobot
from semantic_digital_twin.testing import two_arm_robot_world
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.connections import FixedConnection
from semantic_digital_twin.world_description.geometry import Box, Color, Scale
from semantic_digital_twin.world_description.shape_collection import ShapeCollection
from semantic_digital_twin.world_description.world_entity import Body
from segmind.datastructures.events import (
    DetectionEvent,
    PickUpEvent,
    TranslationEvent,
)
from typing_extensions import List

from experiments.questions.question import (
    BloomLevel,
    Bucket,
    GroundTruthSource,
    Memory,
    PlacedObject,
    RequiredFact,
    SceneAsSetUp,
)
from experiments.questions.question import QuestionedThings
from experiments.questions.question_set import QuestionSet
from experiments.questions.long_term_memory import AnythingMovedInTheEpisode
from experiments.questions.working_memory import (
    AnythingMoved,
    BeliefAgreesWithPerception,
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
    stands_in_the_scene_of,
)
from krrood.adapters.json_serializer import from_json, to_json
from krrood.entity_query_language.predicate import Relation
from typing_extensions import Type

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

WHERE_THE_TABLE_STANDS = 1.0
"""
How far in front of the world's root the table is fixed, in metres.
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

    robot: AbstractRobot
    """
    The robot every question is put to, which is what the questions read their own links
    and their own hand from.
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

    point_of_view: HomogeneousTransformationMatrix
    """
    Where this scene is looked at from, which is what makes left and right mean anything
    in it.
    """

    events: List[DetectionEvent]
    """
    What the segmentation saw happen in this scene.

    Held here because the symbol graph tracks what is alive rather than keeping it
    alive, so an event nothing holds is one the robot no longer remembers.
    """

    as_set_up: SceneAsSetUp
    """
    What this scene was stood to be, said from the numbers it was built from rather than
    read back off the twin, which is what its questions are scored against.
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
    (robot_root,) = [
        entity
        for entity in world.kinematic_structure_entities
        if entity.parent_kinematic_structure_entity is world.root
    ]
    robot = MinimalRobot.from_branch_in_world(robot_root)
    hand = robot.bodies[-1]

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
                    x=WHERE_THE_TABLE_STANDS, reference_frame=world.root
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

    events = [
        TranslationEvent(tracked_object=cube),
        PickUpEvent(tracked_object=cube),
    ]
    point_of_view = HomogeneousTransformationMatrix.from_xyz_rpy(x=3.0)
    as_set_up = SceneAsSetUp(
        objects=[
            PlacedObject(
                name=table.name,
                place=Point3(WHERE_THE_TABLE_STANDS, 0.0, 0.0),
            ),
            PlacedObject(
                name=cube.name,
                place=Point3(
                    WHERE_THE_TABLE_STANDS, DISTANCE_ACROSS_THE_TABLE, standing_height
                ),
                standing_on=table.name,
            ),
            PlacedObject(
                name=cylinder.name,
                place=Point3(
                    WHERE_THE_TABLE_STANDS, -DISTANCE_ACROSS_THE_TABLE, standing_height
                ),
                standing_on=table.name,
            ),
        ],
        object_in_the_hand=held_cube.name,
    )
    return QuestionedScene(
        world=world,
        robot=robot,
        table=table,
        cube=cube,
        cylinder=cylinder,
        held_cube=held_cube,
        own_body_name=hand.name,
        point_of_view=point_of_view,
        events=events,
        as_set_up=as_set_up,
        question_set=QuestionSet.over_working_memory(
            QuestionedThings(
                object_asked_about=cube,
                object_compared_against=cylinder,
                object_in_the_hand=held_cube,
                own_body_asked_about=hand.name,
                point_of_view=point_of_view,
                scene=as_set_up,
            )
        ),
    )


@pytest.fixture
def robot(scene: QuestionedScene) -> AbstractRobot:
    """
    The robot of that scene, which is what its questions are put to.
    """
    return scene.robot


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
    side = SideOfAnotherObject(
        subject=scene.cube,
        other=scene.cylinder,
        side=Side.LEFT,
        point_of_view=scene.point_of_view,
    )
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
    scene: QuestionedScene, robot: AbstractRobot
):
    assert ObjectsSeen().ask(robot) == [scene.table, scene.cube, scene.cylinder]


def test_a_body_standing_in_no_world_is_not_among_the_objects_seen(
    scene: QuestionedScene, robot: AbstractRobot
):
    """
    The symbol graph tracks every body ever made, a piece taken out of a scene and one
    that was never put in one included; the robot is asked about its own scene.
    """
    stray = dye("stray", CUBE_COLOUR, Scale(OBJECT_EDGE, OBJECT_EDGE, OBJECT_EDGE))

    assert stray.has_collision()
    assert ObjectsSeen().ask(robot) == [scene.table, scene.cube, scene.cylinder]
    assert SupportingSurfaces(subject=scene.cube).ask(robot) == [scene.table]


def test_an_entity_the_symbol_graph_has_lost_stands_in_no_scene(robot: AbstractRobot):
    """
    The symbol graph keeps only a weak reference to each entity, and hands out None for
    one that has been garbage collected while a query still ranges over it.
    """
    assert bool(stands_in_the_scene_of(None, robot)) is False


def test_the_colours_are_the_ones_the_shapes_carry(robot: AbstractRobot):
    assert ObjectColours().ask(robot) == [TABLE_COLOUR, CUBE_COLOUR, CYLINDER_COLOUR]


def test_the_places_are_where_the_scene_stood_the_objects(
    scene: QuestionedScene, robot: AbstractRobot
):
    question = ObjectPlaces(scene=scene.as_set_up)
    assert question.matches_ground_truth(robot)


# %% support and spatial relations


def test_the_cube_stands_on_the_table(scene: QuestionedScene, robot: AbstractRobot):
    assert SupportingSurfaces(subject=scene.cube).ask(robot) == [scene.table]


def test_the_cube_is_left_of_the_cylinder_and_not_right_of_it(
    scene: QuestionedScene, robot: AbstractRobot
):
    left, right = (
        SideOfAnotherObject(
            subject=scene.cube,
            other=scene.cylinder,
            side=side,
            point_of_view=scene.point_of_view,
        )
        for side in (Side.LEFT, Side.RIGHT)
    )
    assert left.ask(robot) is True
    assert right.ask(robot) is False


# %% whether the eyes and the belief agree


def believed_of(
    scene: QuestionedScene, *contradicted: Type[Relation]
) -> BeliefAgreesWithPerception:
    """
    What a look made of the belief about the cube: it bore out everything unless the
    test names a relation it did not, in which case someone else acted on the cube.

    :param scene: The scene the cube stands in.
    :param contradicted: The kinds of relation the look did not bear out.
    """
    return BeliefAgreesWithPerception(
        subject=scene.cube,
        contradicted=list(contradicted),
        nothing_was_found=False,
        perturbed=bool(contradicted),
    )


def test_whether_the_eyes_and_the_belief_agree_is_a_spatial_question(
    scene: QuestionedScene,
):
    asked = believed_of(scene)

    assert asked.bucket is Bucket.SUPPORT_AND_SPATIAL_RELATIONS
    assert asked.answer_type is bool


def test_a_scene_on_its_own_is_not_asked_whether_its_eyes_and_belief_agree(
    scene: QuestionedScene,
):
    """
    A belief and the look that checked it are what this question is about, and a scene
    holds neither, so it joins the set only where such a check happened.
    """
    assert (
        BeliefAgreesWithPerception.asked_of(
            QuestionedThings(
                object_asked_about=scene.cube,
                object_compared_against=scene.cylinder,
                object_in_the_hand=scene.held_cube,
                own_body_asked_about=scene.own_body_name,
                point_of_view=scene.point_of_view,
                scene=scene.as_set_up,
            )
        )
        == []
    )
    assert BeliefAgreesWithPerception not in [
        type(question) for question in scene.question_set.questions
    ]


def test_a_look_that_bore_out_every_believed_relation_agrees_with_the_belief(
    scene: QuestionedScene, robot: AbstractRobot
):
    asked = believed_of(scene)

    assert asked.ask(robot) is True
    assert asked.solutions(robot) == []
    assert asked.matches_ground_truth(robot)


def test_a_look_that_contradicts_a_believed_relation_disagrees_with_the_belief(
    scene: QuestionedScene, robot: AbstractRobot
):
    asked = believed_of(scene, SupportedBy, Near)

    assert asked.ask(robot) is False
    assert asked.solutions(robot) == [SupportedBy, Near]
    assert asked.matches_ground_truth(robot)


def test_a_look_that_found_nothing_disagrees_though_it_contradicts_no_relation(
    scene: QuestionedScene, robot: AbstractRobot
):
    """
    An absence contradicts no relation in particular and is still the two accounts
    failing to agree, which is what a relabelled detection leaves behind.
    """
    asked = BeliefAgreesWithPerception(
        subject=scene.cube, contradicted=[], nothing_was_found=True, perturbed=True
    )

    assert asked.ask(robot) is False
    assert asked.matches_ground_truth(robot)


def test_an_object_nobody_else_acted_on_is_meant_to_agree(
    scene: QuestionedScene, robot: AbstractRobot
):
    """
    Ground truth in simulation: the two accounts differ exactly when someone other than
    the robot acted on the object, or on what the look reported of it.
    """
    unperturbed = BeliefAgreesWithPerception(
        subject=scene.cube, contradicted=[], nothing_was_found=False, perturbed=False
    )
    perturbed = BeliefAgreesWithPerception(
        subject=scene.cube, contradicted=[], nothing_was_found=False, perturbed=True
    )

    assert unperturbed.ground_truth(robot) is True
    assert perturbed.ground_truth(robot) is False


def test_whether_the_eyes_and_the_belief_agree_round_trips_with_what_failed(
    scene: QuestionedScene,
):
    """
    Which relations the look did not bear out is part of what was asked, so a recorded
    query keeps them rather than only the verdict.
    """
    asked = believed_of(scene, SupportedBy, Near)

    restored = from_json(to_json(asked))

    assert type(restored) is BeliefAgreesWithPerception
    assert restored.contradicted == [SupportedBy, Near]
    assert restored.subject.name == scene.cube.name
    assert restored.perturbed is True


# %% temporal and agency


def test_the_event_log_says_something_moved(robot: AbstractRobot):
    assert AnythingMoved().ask(robot) is True


def test_the_object_that_moved_is_the_one_the_event_named(
    scene: QuestionedScene, robot: AbstractRobot
):
    assert ObjectsThatMoved().ask(robot) == [scene.cube]


def test_an_object_moved_after_being_picked_up_is_one_the_robot_moved_itself(
    scene: QuestionedScene, robot: AbstractRobot
):
    assert ObjectsTheRobotMoved().ask(robot) == [scene.cube]


def test_only_the_object_with_a_pick_up_event_was_picked_up(
    scene: QuestionedScene, robot: AbstractRobot
):
    assert PickedUpRecently(subject=scene.cube).ask(robot) is True
    assert PickedUpRecently(subject=scene.cylinder).ask(robot) is False


# %% embodiment


def test_only_the_object_hanging_from_the_robot_is_in_its_hand(
    scene: QuestionedScene, robot: AbstractRobot
):
    assert HeldInTheHand(subject=scene.held_cube).ask(robot) is True
    assert HeldInTheHand(subject=scene.cube).ask(robot) is False


# %% self-model


def test_the_place_of_a_link_is_where_the_twin_puts_it(
    scene: QuestionedScene, robot: AbstractRobot
):
    question = PlaceOfOwnBody(body_name=scene.own_body_name)
    assert question.matches_ground_truth(robot)


def test_the_robot_counts_the_links_the_twin_says_are_its_own(
    scene: QuestionedScene, robot: AbstractRobot
):
    assert NumberOfOwnBodies().ask(robot) == len(robot.bodies)
    assert scene.held_cube in robot.bodies


def test_the_robot_counts_the_joints_it_can_move(robot: AbstractRobot):
    question = NumberOfOwnDegreesOfFreedom()
    assert question.ask(robot) == question.ground_truth(robot)


# %% every question at once


def test_every_question_of_the_set_answers_its_own_ground_truth(
    scene: QuestionedScene, robot: AbstractRobot
):
    for question in scene.question_set.questions:
        assert question.matches_ground_truth(robot), question.english


def test_every_question_of_the_set_reads_as_a_question(scene: QuestionedScene):
    for question in scene.question_set.questions:
        assert question.english.endswith("?")


# %% persisted as the question actually asked, not only its class


def test_a_question_with_no_fields_of_its_own_round_trips_by_class_alone():
    """
    A working-memory question typically adds nothing beyond its class, so persisting it
    is persisting which subclass it is.
    """
    restored = from_json(to_json(ObjectsSeen()))

    assert type(restored) is ObjectsSeen


def test_a_question_with_its_own_fields_round_trips_with_them():
    """
    A long-term-memory question's own fields are part of what it asked - here, which
    episode - so persisting only the class would lose it.
    """
    asked = AnythingMovedInTheEpisode(episode_identifier="episode-42")

    restored = from_json(to_json(asked))

    assert type(restored) is AnythingMovedInTheEpisode
    assert restored.episode_identifier == "episode-42"
