"""
Running an experiment described as data: a scenario with a goal, the conditions and
perturbations one run applies to it, and the report over its trials.

The scenario here builds a world that only records what was done to it, so every test
runs without a simulator, a robot or a controller.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from typing_extensions import ClassVar, Sequence

from experiments.experiment_definitions import (
    ConfidenceInterval,
    MeanAndStandardDeviation,
    NoMeasurementsError,
)
from experiments.scenarios.report import GoalReached, Report, TrialDuration
from experiments.scenarios.runner import ScenarioRunner
from experiments.scenarios.scenario import (
    Condition,
    ExecutionKind,
    Goal,
    Perturbation,
    Scenario,
    ScenarioStep,
    StepName,
)
from experiments.scenarios.trial import (
    ConditionApplied,
    PerturbationApplied,
    StepPerformed,
    Trial,
    TrialLog,
    TrialOutcome,
)

# %% a scenario that needs no simulator


class SortingStep(StepName):
    """
    The steps the scenario below is divided into.
    """

    PICK_UP = "pick up"
    PUT_DOWN = "put down"


@dataclass
class TwoFingerGripper:
    """
    The robot the scenario below runs on, which the model only ever names as a type.
    """


@dataclass
class RecordedWorld:
    """
    A world that only remembers what was done to it.
    """

    performed_steps: list[SortingStep] = field(default_factory=list)
    """
    The steps performed in this world, in the order they ran.
    """

    piece_pose_is_known: bool = True
    """
    Whether this world still knows where the piece to sort is.
    """

    piece_was_pushed: bool = False
    """
    Whether something moved the piece while the trial was running.
    """

    is_released: bool = False
    """
    Whether the trial that ran in this world has released it again.
    """


@dataclass
class PerformSortingStep(ScenarioStep[RecordedWorld]):
    """
    A step that does nothing but record that it ran.
    """

    def perform(self, world: RecordedWorld) -> None:
        world.performed_steps.append(self.name)


@dataclass
class PieceWasSorted(Goal[RecordedWorld]):
    """
    Success is the piece having been put down where the world said it was.
    """

    def is_reached(self, world: RecordedWorld) -> bool:
        return (
            SortingStep.PUT_DOWN in world.performed_steps
            and world.piece_pose_is_known
            and not world.piece_was_pushed
        )


@dataclass
class WithoutThePiecePose(Condition[RecordedWorld]):
    """
    Takes the piece's pose out of what the world knows.
    """

    def apply(self, world: RecordedWorld) -> None:
        world.piece_pose_is_known = False


@dataclass
class PiecePushedAway(Perturbation[RecordedWorld]):
    """
    Pushes the piece away at the step it names.
    """

    def apply(self, world: RecordedWorld) -> None:
        world.piece_was_pushed = True


@dataclass
class SortOnePiece(Scenario[RecordedWorld, TwoFingerGripper]):
    """
    A scenario that picks the piece up and puts it down again.
    """

    name: ClassVar[str] = "sort one piece"

    goal: Goal[RecordedWorld] = field(default_factory=PieceWasSorted, kw_only=True)
    """
    Sorting the piece is what this scenario counts as success.
    """

    built_worlds: list[RecordedWorld] = field(default_factory=list)
    """
    Every world this scenario has built, so a test can read what a trial did to it.
    """

    def build_world(self) -> RecordedWorld:
        world = RecordedWorld()
        self.built_worlds.append(world)
        return world

    def release_world(self, world: RecordedWorld) -> None:
        world.is_released = True

    def steps(self, world: RecordedWorld) -> Sequence[ScenarioStep[RecordedWorld]]:
        return [PerformSortingStep(name=step) for step in SortingStep]


class StepFailed(Exception):
    """
    Raised by the step below, so a test can see what a trial does when a step fails.
    """


@dataclass
class StepThatCannotRun(ScenarioStep[RecordedWorld]):
    """
    A step that fails instead of doing anything.
    """

    def perform(self, world: RecordedWorld) -> None:
        raise StepFailed()


@dataclass
class SortOnePieceAndFail(SortOnePiece):
    """
    A scenario whose second step cannot run.
    """

    def steps(self, world: RecordedWorld) -> Sequence[ScenarioStep[RecordedWorld]]:
        return [
            PerformSortingStep(name=SortingStep.PICK_UP),
            StepThatCannotRun(name=SortingStep.PUT_DOWN),
        ]


@dataclass
class StepMeasuringRunner(ScenarioRunner[RecordedWorld, TwoFingerGripper]):
    """
    A runner that records every step it performs, the way a measuring runner wraps the
    steps it measures.
    """

    measured_steps: list[StepName] = field(default_factory=list)
    """
    The steps this runner has performed, in order.
    """

    def perform_step(
        self,
        scenario: Scenario[RecordedWorld, TwoFingerGripper],
        step: ScenarioStep[RecordedWorld],
        world: RecordedWorld,
    ) -> None:
        self.measured_steps.append(step.name)
        super().perform_step(scenario, step, world)


def performed_steps(log: TrialLog) -> list[StepName]:
    """
    The steps the log says ran, in order.
    """
    return [entry.step for entry in log.entries if isinstance(entry, StepPerformed)]


# %% what a scenario says about itself


def test_a_scenario_names_the_robot_it_runs_on():
    assert SortOnePiece().robot_type is TwoFingerGripper


def test_a_scenario_runs_in_simulation_unless_it_says_otherwise():
    assert SortOnePiece().execution_kind is ExecutionKind.SIMULATED


# %% running one trial


class TestTrialExecution:
    """
    A trial builds a world, applies what the run varies, performs the scenario's steps
    and decides the outcome by asking the goal.
    """

    def test_the_steps_run_in_the_order_the_scenario_gives_them(self):
        trial = ScenarioRunner().run_trial(SortOnePiece())

        assert performed_steps(trial.log) == [
            SortingStep.PICK_UP,
            SortingStep.PUT_DOWN,
        ]

    def test_a_trial_that_reaches_the_goal_succeeded(self):
        trial = ScenarioRunner().run_trial(SortOnePiece())

        assert trial.outcome is TrialOutcome.SUCCEEDED

    def test_a_trial_that_misses_the_goal_failed(self):
        trial = ScenarioRunner().run_trial(
            SortOnePiece(), conditions=[WithoutThePiecePose()]
        )

        assert trial.outcome is TrialOutcome.FAILED

    def test_the_world_is_released_once_the_trial_has_finished(self):
        scenario = SortOnePiece()

        ScenarioRunner().run_trial(scenario)

        [world] = scenario.built_worlds
        assert world.is_released

    def test_the_trial_records_what_it_ran_under(self):
        condition = WithoutThePiecePose()
        perturbation = PiecePushedAway(step=SortingStep.PUT_DOWN)

        trial = ScenarioRunner().run_trial(
            SortOnePiece(execution_kind=ExecutionKind.REAL),
            conditions=[condition],
            perturbations=[perturbation],
        )

        assert trial.scenario_name == SortOnePiece.name
        assert trial.execution_kind is ExecutionKind.REAL
        assert trial.conditions == (condition,)
        assert trial.perturbations == (perturbation,)

    def test_a_step_that_cannot_run_still_releases_the_world(self):
        scenario = SortOnePieceAndFail()

        with pytest.raises(StepFailed):
            ScenarioRunner().run_trial(scenario)

        [world] = scenario.built_worlds
        assert world.is_released

    def test_a_runner_can_measure_around_every_step(self):
        runner = StepMeasuringRunner()

        runner.run_trial(SortOnePiece())

        assert runner.measured_steps == [SortingStep.PICK_UP, SortingStep.PUT_DOWN]


class TestWhatOneRunVaries:
    """
    A condition is in force for the whole trial, while a perturbation strikes at one
    named step, so the two are applied at different moments.
    """

    def test_a_condition_is_applied_before_the_first_step(self):
        trial = ScenarioRunner().run_trial(
            SortOnePiece(), conditions=[WithoutThePiecePose()]
        )

        entry_types = [type(entry) for entry in trial.log.entries]
        assert entry_types.index(ConditionApplied) < entry_types.index(StepPerformed)

    def test_a_perturbation_is_applied_at_the_step_it_names(self):
        trial = ScenarioRunner().run_trial(
            SortOnePiece(), perturbations=[PiecePushedAway(step=SortingStep.PUT_DOWN)]
        )

        entry_types = [
            type(entry)
            for entry in trial.log.entries
            if isinstance(entry, (StepPerformed, PerturbationApplied))
        ]
        assert entry_types == [StepPerformed, PerturbationApplied, StepPerformed]

    def test_a_perturbation_can_make_the_trial_fail(self):
        trial = ScenarioRunner().run_trial(
            SortOnePiece(), perturbations=[PiecePushedAway(step=SortingStep.PICK_UP)]
        )

        assert trial.outcome is TrialOutcome.FAILED


# %% running the trials of one report


class TestRepeatedTrials:
    """
    A measurement over one trial says nothing about its spread, so a run repeats the
    scenario and reports over every trial it ran.
    """

    def test_every_repetition_runs_in_a_world_of_its_own(self):
        scenario = SortOnePiece()

        ScenarioRunner(repetitions=3).run(scenario)

        assert len(scenario.built_worlds) == 3

    def test_the_report_holds_one_trial_per_repetition(self):
        report = ScenarioRunner(repetitions=3).run(SortOnePiece())

        assert len(report.trials) == 3
        assert report.scenario_name == SortOnePiece.name


# %% what the trials measured


def sorted_trial(outcome: TrialOutcome, duration: float) -> Trial:
    """
    A finished trial with the given outcome, built directly so a report can be measured
    without running anything.
    """
    return Trial(
        scenario_name=SortOnePiece.name,
        execution_kind=ExecutionKind.SIMULATED,
        conditions=(),
        perturbations=(),
        outcome=outcome,
        duration=duration,
        log=TrialLog(),
    )


@pytest.fixture()
def report_over_three_trials() -> Report:
    return Report(
        scenario_name=SortOnePiece.name,
        trials=[
            sorted_trial(TrialOutcome.SUCCEEDED, duration=2.0),
            sorted_trial(TrialOutcome.FAILED, duration=4.0),
            sorted_trial(TrialOutcome.SUCCEEDED, duration=6.0),
        ],
        metrics=[GoalReached(), TrialDuration()],
    )


class TestReport:
    """
    A report turns the trials into the rows a paper prints: one metric per row, with the
    spread and the confidence interval over the trials it was measured on.
    """

    def test_a_metric_is_measured_on_every_trial(
        self, report_over_three_trials: Report
    ):
        summary = report_over_three_trials.summarize(GoalReached())

        assert summary.measurements == MeanAndStandardDeviation.from_measurements(
            [1.0, 0.0, 1.0]
        )

    def test_a_metric_reports_the_interval_its_mean_lies_in(
        self, report_over_three_trials: Report
    ):
        summary = report_over_three_trials.summarize(TrialDuration())

        assert summary.confidence_interval == ConfidenceInterval.for_mean(
            [2.0, 4.0, 6.0]
        )

    def test_the_metric_is_named_after_what_it_measures(
        self, report_over_three_trials: Report
    ):
        summary = report_over_three_trials.summarize(GoalReached())

        assert summary.metric_name == GoalReached.__name__

    def test_every_metric_becomes_a_row(self, report_over_three_trials: Report):
        table = report_over_three_trials.table()

        assert [row.metric_name for row in table.experiments] == [
            GoalReached.__name__,
            TrialDuration.__name__,
        ]

    def test_a_row_reports_the_spread_and_the_interval(
        self, report_over_three_trials: Report
    ):
        assert report_over_three_trials.table().row_class.get_column_names() == [
            "metric_name",
            "measurements",
            "confidence_interval",
        ]

    def test_the_report_renders_as_a_captioned_table(
        self, report_over_three_trials: Report
    ):
        caption = "What the trials of one run measured."

        rendered = report_over_three_trials.render_figure(caption)

        assert rendered.startswith("#figure(")
        assert caption in rendered
        assert GoalReached.__name__ in rendered

    def test_a_report_over_no_trials_has_nothing_to_measure(self):
        report = Report(
            scenario_name=SortOnePiece.name, trials=[], metrics=[GoalReached()]
        )

        with pytest.raises(NoMeasurementsError):
            report.summarize(GoalReached())
