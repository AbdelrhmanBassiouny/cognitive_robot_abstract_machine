"""
The command line that records one episode: every choice it offers parses to the member
that names it, the episode's identifier is printed before anything else, and a database
that would only live in memory is refused before a world is built.
"""

from __future__ import annotations

import uuid

import pytest
from coraplex.datastructures.enums import ExecutionType

from experiments.montessori.record_episode import (
    DEFAULT_REPETITIONS,
    ExecutionChoice,
    InMemoryDatabaseRefused,
    LayoutChoice,
    PerturbationChoice,
    RecordingOption,
    ScenarioChoice,
    main,
    parse_arguments,
)
from experiments.montessori.results_database import (
    DATABASE_URI_ENVIRONMENT_VARIABLE,
    IN_MEMORY_DATABASE_URI,
)
from experiments.montessori.scenarios import (
    DetectionRelabelled,
    PerceivedPoseOffset,
    PieceShoved,
    SortingStep,
    TargetHoleMoved,
    TracyHoldsAPiece,
    TracyIsIdleWhileAPieceIsPushed,
    TracySortsAPiece,
    TracyWatchesTheSceneStandStill,
)

from .test_episode_recording import UNREACHABLE_URI

LIGHTING_THE_PAPER_DOES_NOT_RECORD = "lighting-changed"
"""
The perturbation the command line used to offer and no longer does.
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


@pytest.mark.parametrize("step", list(SortingStep))
def test_every_step_a_perturbation_can_strike_at_parses_to_its_member(step):
    arguments = parse_arguments([RecordingOption.PERTURBATION_STEP, step.value])

    assert arguments.perturbation_step is step


def test_a_run_records_in_simulation_once_unless_told_otherwise():
    arguments = parse_arguments([])

    assert arguments.execution is ExecutionChoice.SIMULATED
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
def test_a_scenario_choice_builds_the_scenario_it_names(choice, scenario_class):
    scenario = parse_arguments(
        [RecordingOption.SCENARIO, choice.value]
    ).scenario_instance()

    assert type(scenario) is scenario_class


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


def test_a_real_run_is_a_real_scenario():
    scenario = parse_arguments(
        [RecordingOption.EXECUTION, ExecutionChoice.REAL.value]
    ).scenario_instance()

    assert scenario.execution_type is ExecutionType.REAL


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
