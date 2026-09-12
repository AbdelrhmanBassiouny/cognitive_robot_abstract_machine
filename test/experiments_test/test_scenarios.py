"""
Running an experiment described as data: a scenario with a goal, the conditions and
perturbations one run applies to it, and the report over its trials.

The scenario here builds a world that only records what was done to it, so every test
runs without a simulator, a robot or a controller.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from io import StringIO

import pytest
from typing_extensions import ClassVar, Sequence

from coraplex.datastructures.enums import ExecutionType
from krrood.entity_query_language.factories import variable
from krrood.entity_query_language.verbalization.pipeline import verbalize_expression
from krrood.entity_query_language.verbalization.vocabulary.parts_of_speech import (
    clause,
    Copula,
    Noun,
    Adjective,
)
from segmind.datastructures.events import ReproducibleEvent
from semantic_digital_twin.robots.robot_parts import AbstractRobot
from semantic_digital_twin.world import World

from experiments.experiment_definitions import (
    ConfidenceInterval,
    MeanAndStandardDeviation,
    NoMeasurementsError,
)
from experiments.scenarios.report import GoalReached, Report, TrialDuration
from experiments.scenarios.runner import ScenarioRunner
from experiments.scenarios.scenario import (
    AbsentPerson,
    EventBroughtAbout,
    Goal,
    NobodyIsThereToAsk,
    PersonAtTheConsole,
    Perturbation,
    Scenario,
    ScenarioCannotPerceive,
    ScenarioCondition,
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


class TwoFingerGripper(AbstractRobot):
    """
    The robot the scenario below runs on, which the model only ever names as a type.
    """


@dataclass
class RecordedWorld(World):
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

    looks_taken: int = 0
    """
    How often the scenario has looked at this world's scene.
    """


@dataclass
class PerformSortingStep(ScenarioStep[RecordedWorld]):
    """
    A step that does nothing but record that it ran.
    """

    def perform(self, world: RecordedWorld) -> None:
        world.performed_steps.append(self.name)


@dataclass(eq=False)
class PieceWasSorted(Goal[RecordedWorld]):
    """
    Success is the piece having been put down where the world said it was.
    """

    def __call__(self) -> bool:
        return (
            SortingStep.PUT_DOWN in self.world.performed_steps
            and self.world.piece_pose_is_known
            and not self.world.piece_was_pushed
        )

    @classmethod
    def _verbalization_fragment_(cls, fields):
        return clause(Noun(fields["world"]), Copula(), Adjective("sorted"))


@dataclass(eq=False)
class GoalWithoutAVerbalization(Goal[RecordedWorld]):
    """
    A goal that states no verbalization fragment, which the model refuses to build.
    """

    def __call__(self) -> bool:
        return True


@dataclass
class WithoutThePiecePose(ScenarioCondition[RecordedWorld]):
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

    def instruction_for_a_person(self) -> str:
        return "Push the piece away."


@dataclass
class PushRecordedAsHappened(ReproducibleEvent):
    """
    An event whose reproduction is recorded by the world it happens in.
    """

    def reproduce(self, world: RecordedWorld) -> None:
        world.piece_was_pushed = True


@dataclass
class PiecePushedAwayAsAnEvent(EventBroughtAbout[RecordedWorld]):
    """
    The piece pushed away as an event of the scene, so on the robot the run looks at
    the scene once the person has pushed it.
    """

    def event_in(self, world: RecordedWorld) -> ReproducibleEvent:
        return PushRecordedAsHappened()

    def instruction_for_a_person(self) -> str:
        return "Push the piece away."


@dataclass
class SortOnePiece(Scenario[RecordedWorld, TwoFingerGripper]):
    """
    A scenario that picks the piece up and puts it down again.
    """

    name: ClassVar[str] = "sort one piece"

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

    def goal(self, world: RecordedWorld) -> Goal[RecordedWorld]:
        return PieceWasSorted(world=world)


@dataclass
class SortOnePieceWithACamera(SortOnePiece):
    """
    The same scenario with a way of looking at its scene, which counts the looks.
    """

    def perceive(self, world: RecordedWorld) -> None:
        world.looks_taken += 1


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
class StepMeasuringRunner(ScenarioRunner[SortOnePiece, RecordedWorld]):
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
        scenario: SortOnePiece,
        step: ScenarioStep[RecordedWorld],
        world: RecordedWorld,
    ) -> None:
        self.measured_steps.append(step.name)
        super().perform_step(scenario, step, world)


@dataclass
class TrialKeepingRunner(ScenarioRunner[SortOnePiece, RecordedWorld]):
    """
    A runner that keeps every trial it finishes, the way a recording runner keeps them
    somewhere that outlives the run.
    """

    kept_trials: list[Trial] = field(default_factory=list)
    """
    The trials this runner has finished, in order.
    """

    def trial_finished(self, scenario: SortOnePiece, trial: Trial) -> None:
        self.kept_trials.append(trial)


def performed_steps(log: TrialLog) -> list[StepName]:
    """
    The steps the log says ran, in order.
    """
    return [entry.step for entry in log.entries if isinstance(entry, StepPerformed)]


# %% what a scenario says about itself


def test_a_scenario_names_the_robot_it_runs_on():
    assert SortOnePiece().robot_type is TwoFingerGripper


def test_a_scenario_runs_in_simulation_unless_it_says_otherwise():
    assert SortOnePiece().execution_type is ExecutionType.SIMULATED


# %% a goal is a predicate over the world a trial finished in


def test_a_goal_answers_whether_it_holds_when_it_is_called():
    world = RecordedWorld()
    world.performed_steps.append(SortingStep.PUT_DOWN)

    assert PieceWasSorted(world=world)() is True


def test_a_goal_that_does_not_hold_answers_that_it_does_not():
    assert PieceWasSorted(world=RecordedWorld())() is False


def test_a_goal_is_asked_about_the_world_the_trial_it_judges_ran_in():
    scenario = SortOnePiece()
    world = scenario.build_world()

    assert scenario.goal(world).world is world


def test_a_goal_that_states_no_verbalization_cannot_be_built():
    with pytest.raises(TypeError):
        GoalWithoutAVerbalization(world=RecordedWorld())


def test_a_goal_verbalizes_as_the_clause_it_states():
    assert (
        verbalize_expression(PieceWasSorted(world=variable(RecordedWorld, [])))
        == "a RecordedWorld is sorted"
    )


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
            SortOnePiece(execution_type=ExecutionType.REAL),
            conditions=[condition],
            perturbations=[perturbation],
        )

        assert trial.scenario_name == SortOnePiece.name
        assert trial.execution_type is ExecutionType.REAL
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

    def test_a_finished_trial_is_offered_before_the_run_is_over(self):
        """
        A runner that keeps its trials somewhere is offered each one as it ends, so a run
        that dies keeps what it had finished rather than nothing.
        """
        runner = TrialKeepingRunner(repetitions=3)

        report = runner.run(SortOnePiece())

        assert runner.kept_trials == report.trials

    def test_a_trial_run_on_its_own_is_offered_too(self):
        runner = TrialKeepingRunner()

        trial = runner.run_trial(SortOnePiece())

        assert runner.kept_trials == [trial]


# %% what the trials measured


def sorted_trial(outcome: TrialOutcome, duration: float) -> Trial:
    """
    A finished trial with the given outcome, built directly so a report can be measured
    without running anything.
    """
    return Trial(
        scenario_name=SortOnePiece.name,
        execution_type=ExecutionType.SIMULATED,
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


# %% a trial on the robot has the person at the scene bring the perturbation about


@dataclass
class TrialStartKeepingRunner(ScenarioRunner[SortOnePiece, RecordedWorld]):
    """
    A runner that keeps the world of every trial it is told has started, the way an
    observing runner starts its clock there.
    """

    started_worlds: list[RecordedWorld] = field(default_factory=list)
    """
    The worlds of the trials that started, in order.
    """

    def trial_started(self, scenario: SortOnePiece, world: RecordedWorld) -> None:
        self.started_worlds.append(world)


@dataclass
class PersonReadingTheWorld:
    """
    A person who reads, each time they are asked to do something, how often the
    trial's world has been looked at so far.
    """

    scenario: SortOnePiece
    """
    The scenario whose latest world is read.
    """

    looks_taken_when_asked: list[int] = field(default_factory=list)
    """
    What the world said each time an instruction was given.
    """

    def carry_out(self, instruction: str) -> None:
        self.looks_taken_when_asked.append(self.scenario.built_worlds[-1].looks_taken)


A_QUESTION_ABOUT_THE_SCENE = "Which pieces did you put on the table?"
"""
Something a run asks the person at the scene, which only they can answer.
"""


class TestThePersonAtTheScene:
    """
    A perturbation is made by someone other than the robot: the run itself in
    simulation, the person at the scene on the robot; and what the scene was set up to
    be is theirs alone to say.
    """

    def test_the_person_is_given_the_perturbations_own_instruction(self):
        perturbation = PiecePushedAway(step=SortingStep.PUT_DOWN)
        person = AbsentPerson()

        ScenarioRunner(person=person).run_trial(
            SortOnePiece(execution_type=ExecutionType.REAL),
            perturbations=[perturbation],
        )

        assert person.asked == [perturbation.instruction_for_a_person()]

    def test_a_simulated_trial_asks_nobody_and_makes_the_change_itself(self):
        person = AbsentPerson()
        scenario = SortOnePiece()

        ScenarioRunner(person=person).run_trial(
            scenario, perturbations=[PiecePushedAway(step=SortingStep.PUT_DOWN)]
        )

        assert person.asked == []
        [world] = scenario.built_worlds
        assert world.piece_was_pushed

    def test_what_the_person_did_is_never_written_into_the_world(self):
        scenario = SortOnePiece(execution_type=ExecutionType.REAL)

        ScenarioRunner(person=AbsentPerson()).run_trial(
            scenario, perturbations=[PiecePushedAway(step=SortingStep.PUT_DOWN)]
        )

        [world] = scenario.built_worlds
        assert not world.piece_was_pushed

    def test_the_console_person_is_shown_the_instruction_and_confirms_with_a_line(
        self,
    ):
        instruction = PiecePushedAway(
            step=SortingStep.PUT_DOWN
        ).instruction_for_a_person()
        output = StringIO()
        keyboard = StringIO("\n")

        PersonAtTheConsole(output=output, keyboard=keyboard).carry_out(instruction)

        assert instruction in output.getvalue()
        assert keyboard.read() == ""

    def test_the_console_person_is_shown_a_question_and_answers_with_a_line(self):
        """
        What the person says is the only account of the scene a run on the robot has
        that the camera did not make, so the run reads their answer rather than only
        waiting for them.
        """
        output = StringIO()

        said = PersonAtTheConsole(
            output=output, keyboard=StringIO("cube, cylinder\n")
        ).answer(A_QUESTION_ABOUT_THE_SCENE)

        assert A_QUESTION_ABOUT_THE_SCENE in output.getvalue()
        assert said == "cube, cylinder"

    def test_a_trial_with_nobody_at_the_scene_cannot_ask_how_it_was_set_up(self):
        with pytest.raises(NobodyIsThereToAsk):
            AbsentPerson().answer(A_QUESTION_ABOUT_THE_SCENE)


class TestAnEventBroughtAbout:
    """
    A perturbation that is an event of the scene is reproduced in a simulated world,
    and on the robot the scene is looked at once the person has brought it about.
    """

    def test_a_simulated_trial_reproduces_the_event_in_its_world(self):
        scenario = SortOnePieceWithACamera()
        person = AbsentPerson()

        ScenarioRunner(person=person).run_trial(
            scenario,
            perturbations=[PiecePushedAwayAsAnEvent(step=SortingStep.PUT_DOWN)],
        )

        [world] = scenario.built_worlds
        assert world.piece_was_pushed
        assert world.looks_taken == 0
        assert person.asked == []

    def test_on_the_robot_the_scene_is_looked_at_once_the_person_has_acted(self):
        scenario = SortOnePieceWithACamera(execution_type=ExecutionType.REAL)
        person = PersonReadingTheWorld(scenario=scenario)

        ScenarioRunner(person=person).run_trial(
            scenario,
            perturbations=[PiecePushedAwayAsAnEvent(step=SortingStep.PUT_DOWN)],
        )

        assert person.looks_taken_when_asked == [0]
        [world] = scenario.built_worlds
        assert world.looks_taken == 1
        assert not world.piece_was_pushed

    def test_a_perturbation_that_is_no_event_has_the_scene_left_unlooked_at(self):
        scenario = SortOnePieceWithACamera(execution_type=ExecutionType.REAL)

        ScenarioRunner(person=AbsentPerson()).run_trial(
            scenario, perturbations=[PiecePushedAway(step=SortingStep.PUT_DOWN)]
        )

        [world] = scenario.built_worlds
        assert world.looks_taken == 0

    def test_a_scenario_that_cannot_look_at_its_scene_says_so(self):
        scenario = SortOnePiece(execution_type=ExecutionType.REAL)

        with pytest.raises(ScenarioCannotPerceive) as refused:
            ScenarioRunner(person=AbsentPerson()).run_trial(
                scenario,
                perturbations=[PiecePushedAwayAsAnEvent(step=SortingStep.PUT_DOWN)],
            )

        assert refused.value.scenario_name == SortOnePiece.name


class TestTrialStart:
    """
    A runner that observes a trial has to know when it started, not only when it ended.
    """

    def test_a_runner_is_told_of_the_trials_world_as_it_starts(self):
        runner = TrialStartKeepingRunner(repetitions=2)
        scenario = SortOnePiece()

        runner.run(scenario)

        assert runner.started_worlds == scenario.built_worlds

    def test_a_trial_starts_before_any_of_its_steps_ran(self):
        steps_when_started: list[list[SortingStep]] = []

        @dataclass
        class StepsAtStartRunner(ScenarioRunner[SortOnePiece, RecordedWorld]):
            def trial_started(self, scenario: SortOnePiece, world: RecordedWorld):
                steps_when_started.append(list(world.performed_steps))

        StepsAtStartRunner().run_trial(SortOnePiece())

        assert steps_when_started == [[]]
