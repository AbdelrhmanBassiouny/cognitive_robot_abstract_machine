"""
Running the trials a report is measured over.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from typing_extensions import Generic, List, Sequence, TypeVar

from krrood.patterns.subclass_safe_generic import SubClassSafeGeneric

from experiments.experiment_definitions import DEFAULT_CONFIDENCE_LEVEL
from experiments.scenarios.report import Metric, Report
from experiments.scenarios.scenario import (
    Condition,
    Perturbation,
    Scenario,
    ScenarioStep,
    WorldType,
)
from experiments.scenarios.trial import (
    ConditionApplied,
    PerturbationApplied,
    StepPerformed,
    Trial,
    TrialFinished,
    TrialLog,
    TrialOutcome,
    TrialStarted,
)

ScenarioType = TypeVar("ScenarioType", bound=Scenario)
"""
The scenario a runner runs.
"""


@dataclass
class ScenarioRunner(Generic[ScenarioType, WorldType], SubClassSafeGeneric):
    """
    Runs the trials of a scenario, records what each one did, and reports over them.

    A runner that measures the trials of one kind of scenario binds that scenario and
    the world it is run in, so what it may be handed is part of its type.
    """

    repetitions: int = 1
    """
    How many trials one run of a scenario is measured over.
    """

    metrics: List[Metric] = field(default_factory=list)
    """
    The metrics the report reads off every finished trial.
    """

    confidence_level: float = DEFAULT_CONFIDENCE_LEVEL
    """
    Two-sided confidence level the report's intervals hold at.
    """

    def run(
        self,
        scenario: ScenarioType,
        conditions: Sequence[Condition[WorldType]] = (),
        perturbations: Sequence[Perturbation[WorldType]] = (),
    ) -> Report:
        """
        Run the scenario as often as this runner repeats it, and report what its trials
        measured.

        :param scenario: The scenario every trial runs.
        :param conditions: The knowledge sources switched for every trial.
        :param perturbations: The changes applied to every trial's world.
        """
        trials = [
            self.run_trial(scenario, conditions, perturbations)
            for _ in range(self.repetitions)
        ]
        return Report(
            scenario_name=scenario.name,
            trials=trials,
            metrics=list(self.metrics),
            confidence_level=self.confidence_level,
        )

    def run_trial(
        self,
        scenario: ScenarioType,
        conditions: Sequence[Condition[WorldType]] = (),
        perturbations: Sequence[Perturbation[WorldType]] = (),
    ) -> Trial:
        """
        Run the scenario once: build its world, take the conditions' knowledge out of
        it, perform every step with the perturbations due at it, and ask the goal how it
        ended.

        :param scenario: The scenario the trial runs.
        :param conditions: The knowledge sources switched for this trial.
        :param perturbations: The changes applied to this trial's world.
        """
        world = scenario.build_world()
        log = TrialLog()
        log.record(
            TrialStarted(
                moment=log.elapsed_seconds,
                scenario_name=scenario.name,
                execution_type=scenario.execution_type,
            )
        )
        try:
            for condition in conditions:
                condition.apply(world)
                log.record(
                    ConditionApplied(moment=log.elapsed_seconds, condition=condition)
                )
            for step in scenario.steps(world):
                for perturbation in perturbations:
                    if perturbation.step is not step.name:
                        continue
                    perturbation.apply(world)
                    log.record(
                        PerturbationApplied(
                            moment=log.elapsed_seconds, perturbation=perturbation
                        )
                    )
                self.perform_step(scenario, step, world)
                log.record(StepPerformed(moment=log.elapsed_seconds, step=step.name))
            outcome = (
                TrialOutcome.SUCCEEDED
                if scenario.goal.is_reached(world)
                else TrialOutcome.FAILED
            )
            duration = log.elapsed_seconds
            log.record(TrialFinished(moment=duration, outcome=outcome))
        finally:
            scenario.release_world(world)
        trial = Trial(
            scenario_name=scenario.name,
            execution_type=scenario.execution_type,
            conditions=tuple(conditions),
            perturbations=tuple(perturbations),
            outcome=outcome,
            duration=duration,
            log=log,
        )
        self.trial_finished(scenario, trial)
        return trial

    def trial_finished(self, scenario: ScenarioType, trial: Trial) -> None:
        """
        Take note of a trial that has just finished.

        A runner that keeps its trials somewhere overrides this; this one keeps them only
        in the report it returns. Called as each trial ends rather than once the run is
        over, so a run that dies keeps what it had finished.

        :param scenario: The scenario the trial ran.
        :param trial: The trial that has finished.
        """

    def perform_step(
        self,
        scenario: ScenarioType,
        step: ScenarioStep[WorldType],
        world: WorldType,
    ) -> None:
        """
        Perform one step of the scenario.

        A runner that measures what a step costs overrides this and measures around the
        call.

        :param scenario: The scenario the step belongs to.
        :param step: The step to perform.
        :param world: The world the trial is running in.
        """
        step.perform(world)
