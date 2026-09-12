"""
Where the true answer to a working-memory question comes from: what the run knows it set
up, rather than a second reading of the twin the question is answered from.

A scene a run stood and a scene a look misread are one twin to a query, so a true answer
read off that twin agrees with every answer whatever the twin holds. Each case here
states what the run stood, leaves the twin holding what a look would have made of it,
and asks whether the score follows.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.robots.robot_parts import AbstractRobot
from semantic_digital_twin.spatial_types.spatial_types import Point3
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.connections import FixedConnection
from semantic_digital_twin.world_description.shape_collection import ShapeCollection
from semantic_digital_twin.world_description.world_entity import Body

from experiments.episodes.episode import Episode
from experiments.montessori.perception.imagination import piece_mesh
from experiments.montessori.pieces import KNOWN_PIECE_BY_CATEGORY
from experiments.montessori.scenarios import (
    DetectionRelabelled,
    LayoutArea,
    MontessoriSortingScenario,
    PerceivedPoseOffset,
    PieceLayout,
    SortingScene,
    SortingStep,
)
from experiments.montessori.semantics import (
    MONTESSORI_SHAPE_CLASSES,
    MontessoriShapeCategory,
)
from experiments.montessori.watched_run import WatchedSortingRun
from experiments.questions.question import Memory, SceneAsSetUp
from experiments.questions.working_memory import ObjectPlaces, ObjectsSeen

from .test_episode_recording import TrialsKeptInMemory
from .test_montessori_scenarios import (
    HOW_FAR_A_PERTURBATION_MOVES_SOMETHING,
    SEED,
    SyntheticGrasperWatchesTheSceneStandStill,
    board_and_the_arm,
)

MISREAD_PIECE = MontessoriShapeCategory.CUBE
"""
The piece a look in this module reports as something it is not.
"""

REPORTED_SHAPE = MontessoriShapeCategory.SPHERE
"""
The shape it is reported as, which is a shape of the set like any other.
"""

REPORTED_BY_A_LOOK = "reported"
"""
The prefix a piece stands under when a look rather than the run put it there.
"""

A_DRIFT_SMALLER_THAN_THE_TOLERANCE = 0.001
"""
How far a piece is nudged, in metres, to stand for the settling a scene does under
gravity: well inside what a place may differ by and still count as where it was put.
"""

# %% the scene a run stood, and its own account of it


@dataclass
class ASceneTheRunStood:
    """
    One scene a run set up, and the account of it the run can give without reading the
    twin a second time.
    """

    scenario: MontessoriSortingScenario
    """
    The scenario that stood it.
    """

    world: World
    """
    The twin the scene stands in.
    """

    as_set_up: SceneAsSetUp
    """
    What the run knows it set up, which is what its questions are scored against.
    """

    @property
    def robot(self) -> AbstractRobot:
        """
        The robot every question is put to.
        """
        return SortingScene(self.world).robot


def watched(scenario: MontessoriSortingScenario) -> WatchedSortingRun:
    """
    One watched run of the given scenario, keeping its trials in memory.

    :param scenario: The scenario the run runs.
    """
    return WatchedSortingRun(
        episode=Episode.from_run(scenario), records_trials=TrialsKeptInMemory()
    )


@pytest.fixture()
def area() -> LayoutArea:
    """
    The patch of table the pieces stand on.
    """
    return LayoutArea.on_the_table_beside_the_board()


@pytest.fixture()
def stood(area: LayoutArea) -> ASceneTheRunStood:
    """
    The static run's scene, stood as its layout says and not yet acted on.
    """
    scenario = SyntheticGrasperWatchesTheSceneStandStill(
        layout=PieceLayout.randomized(seed=SEED, area=area),
        world_builder=board_and_the_arm(),
    )
    world = scenario.build_world()
    return ASceneTheRunStood(
        scenario=scenario,
        world=world,
        as_set_up=watched(scenario).scene_as_set_up(scenario, world),
    )


# %% what a look that misread the scene leaves in the twin


def stand_the_piece_the_look_reported(
    world: World, relabelled: DetectionRelabelled
) -> None:
    """
    Leave the twin holding what a look that misread one piece leaves in it: where the
    piece of one shape stood, a piece of the shape it was reported as stands instead,
    under a name of its own, since a scene the robot holds by looking holds what the
    look said was there.

    :param world: The twin the scene stands in.
    :param relabelled: What the look made of which piece.
    """
    scene = SortingScene(world)
    misread = scene.shape_of(relabelled.category)
    stands_at = misread.root.global_transform
    name = PrefixedName(str(relabelled.reported_as), REPORTED_BY_A_LOOK)
    reported = Body.from_shape_collection(
        name,
        ShapeCollection([piece_mesh(KNOWN_PIECE_BY_CATEGORY[relabelled.reported_as])]),
    )
    with world.modify_world():
        world.remove_semantic_annotation(misread)
        world.remove_kinematic_structure_entity(misread.root)
        world.add_connection(
            FixedConnection(
                parent=world.root,
                child=reported,
                parent_T_connection_expression=stands_at,
            )
        )
        world.add_semantic_annotation(
            MONTESSORI_SHAPE_CLASSES[relabelled.reported_as](name=name, root=reported)
        )


def stand_the_piece_where_the_look_reported(
    world: World, offset: PerceivedPoseOffset
) -> None:
    """
    Leave the twin holding one piece where a look reported it rather than where the run
    stood it.

    :param world: The twin the scene stands in.
    :param offset: Which piece is reported how far from where it stands.
    """
    scene = SortingScene(world)
    stands_at = scene.position_of(offset.category)
    scene.stand_the_piece_at(
        offset.category,
        Point3(
            float(stands_at.x) + float(offset.offset.x),
            float(stands_at.y) + float(offset.offset.y),
            float(stands_at.z) + float(offset.offset.z),
        ),
    )


# %% which objects are there


def test_the_objects_of_a_scene_nobody_misread_are_the_ones_the_run_stood(
    stood: ASceneTheRunStood,
):
    """
    The case the others are read against: the twin holds exactly what the run stood, so
    the answer and the run's own account of the scene agree.
    """
    assert ObjectsSeen(scene=stood.as_set_up).matches_ground_truth(stood.robot) is True


def test_a_piece_the_twin_calls_by_another_shape_is_not_one_the_run_stood(
    stood: ASceneTheRunStood,
):
    """
    The tautology this module exists to break: the twin holds a piece the run never
    stood, and a true answer read off that same twin would call the answer right.
    """
    stand_the_piece_the_look_reported(
        stood.world,
        DetectionRelabelled(
            step=SortingStep.ANSWER, category=MISREAD_PIECE, reported_as=REPORTED_SHAPE
        ),
    )

    assert ObjectsSeen(scene=stood.as_set_up).matches_ground_truth(stood.robot) is False


# %% where the objects are


def test_the_places_of_a_scene_nobody_misread_are_where_the_run_stood_them(
    stood: ASceneTheRunStood,
):
    assert ObjectPlaces(scene=stood.as_set_up).matches_ground_truth(stood.robot) is True


def test_a_piece_reported_far_from_where_it_stands_is_not_where_the_run_put_it(
    stood: ASceneTheRunStood,
):
    stand_the_piece_where_the_look_reported(
        stood.world,
        PerceivedPoseOffset(
            step=SortingStep.ANSWER,
            category=MISREAD_PIECE,
            offset=HOW_FAR_A_PERTURBATION_MOVES_SOMETHING,
        ),
    )

    assert (
        ObjectPlaces(scene=stood.as_set_up).matches_ground_truth(stood.robot) is False
    )


def test_a_piece_that_only_drifted_still_stands_where_the_run_put_it(
    stood: ASceneTheRunStood,
):
    """
    A scene settles under gravity between being stood and being asked about, so a place
    is allowed to differ by less than any change anyone makes to the scene.
    """
    scene = SortingScene(stood.world)
    drifted_from = scene.position_of(MISREAD_PIECE)
    scene.stand_the_piece_at(
        MISREAD_PIECE,
        Point3(
            float(drifted_from.x) + A_DRIFT_SMALLER_THAN_THE_TOLERANCE,
            float(drifted_from.y),
            float(drifted_from.z),
        ),
    )

    assert ObjectPlaces(scene=stood.as_set_up).matches_ground_truth(stood.robot) is True


# %% a whole run


def test_an_unperturbed_run_answers_every_working_memory_question_it_is_scored_on(
    area: LayoutArea,
):
    """
    Nothing acts on this run's scene, so every question the run can state a true answer
    for is answered right - which is what makes a wrong score elsewhere mean something.
    """
    scenario = SyntheticGrasperWatchesTheSceneStandStill(
        layout=PieceLayout.randomized(seed=SEED, area=area),
        world_builder=board_and_the_arm(),
    )
    run = watched(scenario)

    run.run(scenario)

    [trial] = run.records_trials.trials
    scored = [
        query
        for query in trial.queries
        if query.question.memory is Memory.WORKING
        and query.answered_correctly is not None
    ]
    assert scored
    assert all(query.answered_correctly for query in scored), [
        query.text for query in scored if not query.answered_correctly
    ]
