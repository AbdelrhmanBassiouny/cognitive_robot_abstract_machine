"""
The command line that records one episode: every choice it offers parses to the member
that names it, a perceived scene is a run on the robot whose pieces stand where the
camera finds them, the episode's identifier is printed before anything else, and a
database that would only live in memory is refused before a world is built.
"""

from __future__ import annotations

import uuid

import pytest
from coraplex.datastructures.enums import ExecutionType

from experiments.montessori.record_episode import (
    CHOICES_CLASH_EXIT_CODE,
    DEFAULT_REPETITIONS,
    ExecutionChoice,
    InMemoryDatabaseRefused,
    LayoutChoice,
    PerceivedSceneCannotBeLaidOut,
    PerceivedSceneNeedsTheRobot,
    PerturbationChoice,
    RecordingOption,
    ScenarioChoice,
    SceneChoice,
    main,
    parse_arguments,
    scene_of,
)
from experiments.montessori.results_database import (
    DATABASE_URI_ENVIRONMENT_VARIABLE,
    IN_MEMORY_DATABASE_URI,
)
from experiments.montessori.scenarios import (
    DetectionRelabelled,
    LayoutAsFound,
    PerceivedPoseOffset,
    PieceLayout,
    PieceShoved,
    SortingStep,
    TargetHoleMoved,
    TracyHoldsAPiece,
    TracyIsIdleWhileAPieceIsPushed,
    TracySortsAPiece,
    TracyWatchesTheSceneStandStill,
)
from experiments.tracy_experiments.montessori.scene_builder import TracyOnItsOwnTable

from .test_episode_recording import UNREACHABLE_URI

LIGHTING_THE_PAPER_DOES_NOT_RECORD = "lighting-changed"
"""
The perturbation the command line used to offer and no longer does.
"""

A_PERCEIVED_SCENE_ON_THE_ROBOT = [
    RecordingOption.SCENE,
    SceneChoice.PERCEIVED.value,
    RecordingOption.EXECUTION,
    ExecutionChoice.REAL.value,
]
"""
The two options a run over the scene the robot's camera finds is asked with.
"""

# %% every choice parses


@pytest.mark.parametrize("scenario", list(ScenarioChoice))
def test_every_scenario_parses_to_its_member(scenario: ScenarioChoice):
    arguments = parse_arguments([RecordingOption.SCENARIO, scenario.value])

    assert arguments.scenario is scenario


@pytest.mark.parametrize("layout", list(LayoutChoice))
def test_every_layout_parses_to_its_member(layout: LayoutChoice):
    arguments = parse_arguments([RecordingOption.LAYOUT, layout.value])

    assert arguments.layout is layout


@pytest.mark.parametrize("perturbation", list(PerturbationChoice))
def test_every_perturbation_parses_to_its_member(perturbation: PerturbationChoice):
    arguments = parse_arguments([RecordingOption.PERTURBATION, perturbation.value])

    assert arguments.perturbation is perturbation


@pytest.mark.parametrize("execution", list(ExecutionChoice))
def test_every_execution_parses_to_its_member(execution: ExecutionChoice):
    arguments = parse_arguments([RecordingOption.EXECUTION, execution.value])

    assert arguments.execution is execution


def test_a_built_scene_parses_to_its_member():
    arguments = parse_arguments([RecordingOption.SCENE, SceneChoice.BUILT.value])

    assert arguments.scene is SceneChoice.BUILT


def test_a_perceived_scene_parses_to_its_member():
    arguments = parse_arguments(A_PERCEIVED_SCENE_ON_THE_ROBOT)

    assert arguments.scene is SceneChoice.PERCEIVED


@pytest.mark.parametrize("step", list(SortingStep))
def test_every_step_a_perturbation_can_strike_at_parses_to_its_member(step):
    arguments = parse_arguments([RecordingOption.PERTURBATION_STEP, step.value])

    assert arguments.perturbation_step is step


def test_a_run_records_in_simulation_once_unless_told_otherwise():
    arguments = parse_arguments([])

    assert arguments.execution is ExecutionChoice.SIMULATED
    assert arguments.scene is SceneChoice.BUILT
    assert arguments.layout is LayoutChoice.RANDOMIZED
    assert arguments.repetitions == DEFAULT_REPETITIONS
    assert arguments.record_bag is False
    assert arguments.headless is False
    assert arguments.database_uri is None
    assert arguments.perturbation is None


def test_the_flags_are_read(tmp_path):
    arguments = parse_arguments(
        [
            RecordingOption.REPETITIONS,
            "3",
            RecordingOption.RECORD_BAG,
            RecordingOption.HEADLESS,
            RecordingOption.DATABASE_URI,
            IN_MEMORY_DATABASE_URI,
        ]
    )

    assert arguments.repetitions == 3
    assert arguments.record_bag is True
    assert arguments.headless is True
    assert arguments.database_uri == IN_MEMORY_DATABASE_URI


# %% what the choices stand for


@pytest.mark.parametrize(
    "choice, scenario_class",
    [
        (ScenarioChoice.SCENE_STANDS_STILL, TracyWatchesTheSceneStandStill),
        (ScenarioChoice.ROBOT_SORTS_A_PIECE, TracySortsAPiece),
        (ScenarioChoice.PIECE_PUSHED_WHILE_IDLE, TracyIsIdleWhileAPieceIsPushed),
        (ScenarioChoice.PIECE_HELD_WHEN_ASKED, TracyHoldsAPiece),
    ],
)
def test_a_scenario_choice_names_the_scenario_it_builds(choice, scenario_class):
    arguments = parse_arguments([RecordingOption.SCENARIO, choice.value])

    assert arguments.scenario_type is scenario_class
    assert type(arguments.scenario_instance(TracyOnItsOwnTable())) is scenario_class


@pytest.mark.parametrize(
    "choice, perturbation_class",
    [
        (PerturbationChoice.TARGET_HOLE_MOVED, TargetHoleMoved),
        (PerturbationChoice.PIECE_SHOVED, PieceShoved),
        (PerturbationChoice.PERCEIVED_POSE_OFFSET, PerceivedPoseOffset),
        (PerturbationChoice.DETECTION_RELABELLED, DetectionRelabelled),
    ],
)
def test_a_perturbation_choice_builds_the_perturbation_it_names(
    choice, perturbation_class
):
    arguments = parse_arguments(
        [
            RecordingOption.PERTURBATION,
            choice.value,
            RecordingOption.PERTURBATION_STEP,
            SortingStep.SETTLE.value,
        ]
    )

    [perturbation] = arguments.perturbations()

    assert type(perturbation) is perturbation_class
    assert perturbation.step is SortingStep.SETTLE


def test_the_command_line_offers_no_lighting_perturbation():
    """
    The paper records no lighting condition, so a run cannot be asked for one.
    """
    with pytest.raises(SystemExit):
        parse_arguments(
            [RecordingOption.PERTURBATION, LIGHTING_THE_PAPER_DOES_NOT_RECORD]
        )


def test_asking_for_no_perturbation_applies_none():
    assert parse_arguments([]).perturbations() == []


def test_the_execution_choice_names_the_execution_type():
    assert ExecutionChoice.SIMULATED.execution_type is ExecutionType.SIMULATED
    assert ExecutionChoice.REAL.execution_type is ExecutionType.REAL


def test_a_real_run_is_a_real_scenario_and_is_not_filmed():
    scenario = parse_arguments(
        [RecordingOption.EXECUTION, ExecutionChoice.REAL.value]
    ).scenario_instance(TracyOnItsOwnTable())

    assert scenario.execution_type is ExecutionType.REAL
    assert scenario.filmed is False


def test_a_simulated_run_is_filmed():
    scenario = parse_arguments([]).scenario_instance(TracyOnItsOwnTable())

    assert scenario.execution_type is ExecutionType.SIMULATED
    assert scenario.filmed is True


# %% where the scene comes from


def test_a_perceived_scene_finds_its_pieces_unless_told_otherwise():
    arguments = parse_arguments(A_PERCEIVED_SCENE_ON_THE_ROBOT)

    assert arguments.layout is LayoutChoice.AS_FOUND
    assert type(arguments.piece_layout()) is LayoutAsFound


def test_a_perceived_scene_can_be_told_to_find_its_pieces():
    arguments = parse_arguments(
        A_PERCEIVED_SCENE_ON_THE_ROBOT
        + [RecordingOption.LAYOUT, LayoutChoice.AS_FOUND.value]
    )

    assert arguments.layout is LayoutChoice.AS_FOUND


def test_a_built_scene_can_find_its_pieces_too():
    """
    The pieces a built scene stands in its own row are a layout as much as a drawn one.
    """
    arguments = parse_arguments([RecordingOption.LAYOUT, LayoutChoice.AS_FOUND.value])

    assert arguments.scene is SceneChoice.BUILT
    assert type(arguments.piece_layout()) is LayoutAsFound


@pytest.mark.parametrize(
    "layout", [LayoutChoice.RANDOMIZED, LayoutChoice.NEARLY_AMBIGUOUS]
)
def test_a_built_scene_draws_its_layout(layout: LayoutChoice):
    arguments = parse_arguments([RecordingOption.LAYOUT, layout.value])

    assert type(arguments.piece_layout()) is PieceLayout


def test_a_perceived_scene_needs_the_robot():
    with pytest.raises(PerceivedSceneNeedsTheRobot) as refused:
        parse_arguments([RecordingOption.SCENE, SceneChoice.PERCEIVED.value])

    assert refused.value.execution is ExecutionChoice.SIMULATED


@pytest.mark.parametrize(
    "layout", [LayoutChoice.RANDOMIZED, LayoutChoice.NEARLY_AMBIGUOUS]
)
def test_a_perceived_scene_cannot_be_laid_out(layout: LayoutChoice):
    with pytest.raises(PerceivedSceneCannotBeLaidOut) as refused:
        parse_arguments(
            A_PERCEIVED_SCENE_ON_THE_ROBOT + [RecordingOption.LAYOUT, layout.value]
        )

    assert refused.value.layout is layout


def test_clashing_choices_end_the_run_before_anything_is_printed(capsys):
    exit_code = main(
        A_PERCEIVED_SCENE_ON_THE_ROBOT
        + [RecordingOption.LAYOUT, LayoutChoice.RANDOMIZED.value]
    )

    assert exit_code == CHOICES_CLASH_EXIT_CODE
    printed = capsys.readouterr()
    assert printed.out == ""
    assert LayoutChoice.AS_FOUND.value in printed.err


def test_a_built_scene_is_tracys_table_as_its_description_builds_it():
    arguments = parse_arguments([])

    with scene_of(arguments) as world_builder:
        assert type(world_builder) is TracyOnItsOwnTable


def test_only_a_perceived_scene_or_a_bag_needs_ros():
    assert parse_arguments([]).needs_ros is False
    assert parse_arguments([RecordingOption.RECORD_BAG]).needs_ros is True
    assert parse_arguments(A_PERCEIVED_SCENE_ON_THE_ROBOT).needs_ros is True


# %% the database it records to


def test_a_database_that_would_live_in_memory_is_refused(capsys):
    """
    An episode recorded to memory is lost with the process, which is what the run is
    started to avoid.
    """
    with pytest.raises(InMemoryDatabaseRefused) as refused:
        main([RecordingOption.DATABASE_URI, UNREACHABLE_URI])

    assert DATABASE_URI_ENVIRONMENT_VARIABLE in refused.value.suggest_correction()


def test_an_in_memory_database_asked_for_by_name_is_refused_too():
    with pytest.raises(InMemoryDatabaseRefused):
        main([RecordingOption.DATABASE_URI, IN_MEMORY_DATABASE_URI])


def test_the_episode_identifier_is_printed_before_anything_else(capsys):
    with pytest.raises(InMemoryDatabaseRefused):
        main([RecordingOption.DATABASE_URI, UNREACHABLE_URI])

    first_line = capsys.readouterr().out.splitlines()[0]
    assert uuid.UUID(hex=first_line).hex == first_line
