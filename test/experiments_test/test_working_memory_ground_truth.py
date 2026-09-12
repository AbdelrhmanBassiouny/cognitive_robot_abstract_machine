"""
Where the true answer to a working-memory question comes from: what the run knows it set
up, rather than a second reading of the twin the question is answered from.

A scene a run stood and a scene a look misread are one twin to a query, so a true answer
read off that twin agrees with every answer whatever the twin holds. Each case here
states what the run stood, leaves the twin holding what a look would have made of it,
and asks whether the score follows.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from typing_extensions import List
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.robots.robot_parts import AbstractRobot
from semantic_digital_twin.spatial_types.spatial_types import Point3
from semantic_digital_twin.world import World

from coraplex.datastructures.enums import ExecutionType

from experiments.episodes.episode import Episode
from experiments.montessori.exceptions import UnknownPieceNamed
from experiments.montessori.scenarios import (
    BoardOnItsOwnTable,
    DetectionRelabelled,
    LayoutArea,
    LayoutAsFound,
    MontessoriSortingScenario,
    PerceivedPoseOffset,
    PerceivingWorldBuilder,
    PieceLayout,
    SortingScene,
    SortingStep,
)
from experiments.montessori.semantics import (
    MONTESSORI_SHAPE_CLASSES,
    MontessoriShapeCategory,
)
from experiments.montessori.watched_run import (
    WHICH_PIECES_WERE_PLACED,
    WatchedSortingRun,
)
from experiments.questions.question import Memory, SceneAsSetUp
from experiments.questions.working_memory import ObjectPlaces, ObjectsSeen

from .test_episode_recording import TrialsKeptInMemory
from .test_montessori_scenarios import (
    HOW_FAR_A_PERTURBATION_MOVES_SOMETHING,
    SEED,
    SyntheticGrasperWatchesTheSceneStandStill,
    board_and_the_arm,
    mounted_arm,
)

MISREAD_PIECE = MontessoriShapeCategory.CUBE
"""
The piece a look in this module reports as something it is not.
"""

REPORTED_SHAPE = MontessoriShapeCategory.CYLINDER
"""
The shape it is reported as.

Any shape with a hole of its own serves; this one shares the cube's colour, so nothing
about the case rests on a colour telling the two apart.
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


def call_the_piece_what_the_look_reported(
    world: World, relabelled: DetectionRelabelled
) -> None:
    """
    Leave the twin calling one piece by the shape a look reported it as, which is what a
    scene the robot holds by looking holds when a detection is misread: the piece stands
    where it stands and the world knows it under another shape's name.

    Renamed where it stands rather than taken down and stood again, so the twin lists
    its bodies in the order it did before and nothing but the name has changed.

    :param world: The twin the scene stands in.
    :param relabelled: What the look made of which piece.
    """
    scene = SortingScene(world)
    misread = scene.shape_of(relabelled.category)
    body = misread.root
    reported = PrefixedName(str(relabelled.reported_as), REPORTED_BY_A_LOOK)
    with world.modify_world():
        world.remove_semantic_annotation(misread)
        body.update_name(reported)
        world.add_semantic_annotation(
            MONTESSORI_SHAPE_CLASSES[relabelled.reported_as](name=reported, root=body)
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
    call_the_piece_what_the_look_reported(
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


# %% the scene a person at the table set up


@dataclass
class TheBoardAndTheArmAsIfPerceived(BoardOnItsOwnTable, PerceivingWorldBuilder):
    """
    A scene builder standing in for one whose scene the robot's camera finds: the pieces
    stand where this package builds them, and a look finds nothing it has not already
    found.
    """

    def perceive(self) -> None:
        """
        Nothing to look with, and nothing a look would change.
        """


@dataclass
class PersonWhoSaysWhatTheyPlaced:
    """
    Stands in for the person at the table: does nothing about what they are told, and
    answers what they are asked with the line they would type.
    """

    says: str
    """
    What they type when they are asked.
    """

    asked: List[str] = field(default_factory=list)
    """
    The questions they have been put, in order.
    """

    @classmethod
    def who_placed(cls, categories: List[MontessoriShapeCategory]):
        """
        Somebody who says they put those pieces on the table.

        :param categories: The shapes they placed.
        """
        return cls(says=", ".join(str(category) for category in categories))

    def carry_out(self, instruction: str) -> None:
        """
        Nothing, since these cases are about what they say rather than what they do.

        :param instruction: What they were told to do.
        """

    def answer(self, question: str) -> str:
        """
        What they type.

        :param question: What they were asked.
        """
        self.asked.append(question)
        return self.says


@dataclass
class ATableTheCameraFound:
    """
    A scene on the robot, standing in the world the robot publishes, before anyone has
    said what was put on the table.
    """

    scenario: MontessoriSortingScenario
    """
    The scenario the run runs on the robot.
    """

    world: World
    """
    The twin, which is what the camera made of the table.
    """

    @classmethod
    def looked_at(cls) -> ATableTheCameraFound:
        """
        One such scene, its pieces standing where this package builds them.
        """
        scenario = SyntheticGrasperWatchesTheSceneStandStill(
            layout=LayoutAsFound(),
            world_builder=TheBoardAndTheArmAsIfPerceived(robot=mounted_arm()),
            execution_type=ExecutionType.REAL,
        )
        return cls(scenario=scenario, world=scenario.build_world())

    @property
    def pieces_standing(self) -> List[MontessoriShapeCategory]:
        """
        The shapes of the pieces standing on the table, in the order the set spells
        them.
        """
        standing = SortingScene(self.world).categories
        return [
            category for category in MontessoriShapeCategory if category in standing
        ]

    def as_the_person_says(
        self, person: PersonWhoSaysWhatTheyPlaced
    ) -> ASceneTheRunStood:
        """
        The run's account of this table, taken from what the person at it says.

        :param person: The person at the table.
        """
        run = watched(self.scenario)
        run.person = person
        return ASceneTheRunStood(
            scenario=self.scenario,
            world=self.world,
            as_set_up=run.scene_as_set_up(self.scenario, self.world),
        )


def test_the_person_at_the_table_is_asked_which_pieces_they_placed():
    """
    On the robot the twin is what the camera made of the table, so the only account of
    the table that is not the camera's is the person's.
    """
    found = ATableTheCameraFound.looked_at()
    person = PersonWhoSaysWhatTheyPlaced.who_placed(found.pieces_standing)

    found.as_the_person_says(person)

    assert person.asked == [WHICH_PIECES_WERE_PLACED]


def test_the_objects_of_a_table_the_camera_read_right_are_the_ones_the_person_placed():
    found = ATableTheCameraFound.looked_at()

    stood = found.as_the_person_says(
        PersonWhoSaysWhatTheyPlaced.who_placed(found.pieces_standing)
    )

    assert ObjectsSeen(scene=stood.as_set_up).matches_ground_truth(stood.robot) is True


def test_a_piece_the_camera_misread_is_not_one_the_person_placed():
    """
    The camera called one piece by another shape and the person says what they really
    put there, so the robot's account of its table and the table disagree.
    """
    found = ATableTheCameraFound.looked_at()
    person = PersonWhoSaysWhatTheyPlaced.who_placed(found.pieces_standing)
    call_the_piece_what_the_look_reported(
        found.world,
        DetectionRelabelled(
            step=SortingStep.ANSWER, category=MISREAD_PIECE, reported_as=REPORTED_SHAPE
        ),
    )

    stood = found.as_the_person_says(person)

    assert ObjectsSeen(scene=stood.as_set_up).matches_ground_truth(stood.robot) is False


def test_a_shape_no_piece_of_the_set_is_is_not_a_piece_anyone_placed():
    found = ATableTheCameraFound.looked_at()

    with pytest.raises(UnknownPieceNamed):
        found.as_the_person_says(PersonWhoSaysWhatTheyPlaced(says="banana"))
