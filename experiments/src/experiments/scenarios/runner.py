"""
Running the trials a report is measured over.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from typing_extensions import Generic, List, Sequence

from krrood.patterns.subclass_safe_generic import SubClassSafeGeneric

from experiments.experiment_definitions import DEFAULT_CONFIDENCE_LEVEL
from experiments.scenarios.report import Metric, Report
from experiments.scenarios.scenario import (
    Condition,
    Perturbation,
    RobotType,
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


@dataclass
class ScenarioRunner(Generic[WorldType, RobotType], SubClassSafeGeneric):
    """
    Runs the trials of a scenario, records what each one did, and reports over them.

    A runner that measures the trials of one kind of scenario binds that scenario's
    world and robot, so what it may be handed is part of its type.
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
        scenario: Scenario[WorldType, RobotType],
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
        scenario: Scenario[WorldType, RobotType],
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
        started_at = time.perf_counter()
        log.record(
            TrialStarted(
                moment=0.0,
                scenario_name=scenario.name,
                execution_kind=scenario.execution_kind,
            )
        )
        try:
            for condition in conditions:
                condition.apply(world)
                log.record(
                    ConditionApplied(
                        moment=time.perf_counter() - started_at, condition=condition
                    )
                )
            for step in scenario.steps(world):
                for perturbation in perturbations:
                    if perturbation.step is not step.name:
                        continue
                    perturbation.apply(world)
                    log.record(
                        PerturbationApplied(
                            moment=time.perf_counter() - started_at,
                            perturbation=perturbation,
                        )
                    )
                self.perform_step(scenario, step, world)
                log.record(
                    StepPerformed(
                        moment=time.perf_counter() - started_at, step=step.name
                    )
                )
            outcome = (
                TrialOutcome.SUCCEEDED
                if scenario.goal.is_reached(world)
                else TrialOutcome.FAILED
            )
            duration = time.perf_counter() - started_at
            log.record(TrialFinished(moment=duration, outcome=outcome))
        finally:
            scenario.release_world(world)
        return Trial(
            scenario_name=scenario.name,
            execution_kind=scenario.execution_kind,
            conditions=tuple(conditions),
            perturbations=tuple(perturbations),
            outcome=outcome,
            duration=duration,
            log=log,
        )

    def perform_step(
        self,
        scenario: Scenario[WorldType, RobotType],
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
