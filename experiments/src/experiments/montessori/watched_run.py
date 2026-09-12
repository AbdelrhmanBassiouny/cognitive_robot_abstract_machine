"""
A sorting run watched while it happens: an event monitor ticks against the piece the
script acts on, the frozen working-memory question set is asked at the step the scene is
asked about, what a look made of the robot's own account of the scene is scored as the
look is taken, and every motion state chart a step runs is kept as it finishes.

All of it goes through the run's observer, so the trial the run records carries its
ticks, its scored queries and the motions it ran rather than only its outcome.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from semantic_digital_twin.spatial_types.spatial_types import (
    HomogeneousTransformationMatrix,
)
from semantic_digital_twin.world import World
from typing_extensions import List, Optional, Set

from experiments.episodes.observer import ObserverListener, ObserverMotionListener
from experiments.episodes.recording import EpisodeRecording
from experiments.episodes.trace import JointTraceRecorder
from experiments.montessori.event_monitoring import (
    MontessoriEventMonitor,
    build_shape_monitor_in_scene,
)
from experiments.montessori.scenarios import (
    LookAtTheScene,
    MontessoriSortingScenario,
    HaveTheRobotAct,
    SortingPerturbation,
    SortingScene,
    SortingStep,
)
from experiments.montessori.semantics import MontessoriShapeCategory
from experiments.questions.question import QuestionedThings
from experiments.questions.question_set import QuestionSet
from experiments.questions.working_memory import BeliefAgreesWithPerception
from experiments.scenarios.scenario import ScenarioStep

# %% the run


@dataclass
class WatchedSortingRun(EpisodeRecording[MontessoriSortingScenario, World]):
    """
    A recorded run of a sorting scenario whose trials are watched by an event monitor,
    scored on what each look made of the robot's own account of the scene, and asked the
    working-memory question set when the scene is asked about.
    """

    monitor: Optional[MontessoriEventMonitor] = field(init=False, default=None)
    """
    The monitor watching the trial that is running, or None between trials.
    """

    joints: Optional[JointTraceRecorder] = field(init=False, default=None)
    """
    What traces where every joint stands while the trial runs, or None between trials.
    """

    pieces_acted_on: Set[MontessoriShapeCategory] = field(
        init=False, default_factory=set
    )
    """
    The pieces someone other than the robot has acted on in the trial that is running.

    What the true answer to a question about the robot's own account of a piece rests
    on: a piece nobody else touched is one the look and the belief ought to agree about.
    """

    def trial_started(self, scenario: MontessoriSortingScenario, world: World) -> None:
        """
        Start watching the piece the script acts on, ticking the observer with every
        detection, tracing where every joint of the world stands, and have the steps
        hand their motions to the observer as they finish.

        :param scenario: The scenario the trial runs.
        :param world: The world the trial is about to run in.
        """
        super().trial_started(scenario, world)
        self.pieces_acted_on = set()
        scenario.motion_listener = ObserverMotionListener(observer=self.observer)
        self._stop_watching()
        scene = SortingScene(world)
        self.monitor = build_shape_monitor_in_scene(
            world,
            scene.shape_of(self.watched_category(scenario)),
            listener=ObserverListener(observer=self.observer),
        )
        self.monitor.start()
        self.joints = JointTraceRecorder(
            _world=world, clock=lambda: self.observer.elapsed_seconds
        )

    def perform_step(
        self,
        scenario: MontessoriSortingScenario,
        step: ScenarioStep[World],
        world: World,
    ) -> None:
        """
        Perform the step, take one tick of the monitor after it, and score what the step
        left to be asked: what a look made of the robot's own account of the scene, and
        the whole question set once the scene is asked about.

        The monitor is also ticked from the control cycle of whatever motion the step
        runs; the tick here is what watches a step no motion runs in, such as the scene
        settling under gravity.

        :param scenario: The scenario the step belongs to.
        :param step: The step to perform.
        :param world: The world the trial is running in.
        """
        super().perform_step(scenario, step, world)
        self.monitor.tick()
        if isinstance(step, HaveTheRobotAct) and step.performed is not None:
            self.observer.performed(step.performed)
        if isinstance(step, LookAtTheScene):
            self.observer.ask(
                self.belief_questions(step, world),
                SortingScene(world).robot,
                self.observer.elapsed_seconds,
            )
            return
        if step.name is not SortingStep.ANSWER:
            return
        self.observer.ask(
            self.question_set(scenario, world),
            SortingScene(world).robot,
            self.observer.elapsed_seconds,
        )

    def apply_perturbation(
        self,
        scenario: MontessoriSortingScenario,
        perturbation: SortingPerturbation,
        world: World,
    ) -> None:
        """
        Bring the perturbation about, and note which pieces it acted on.

        The run is the only thing that sees both a perturbation and a look, so it is
        where what the robot ought to have been wrong about is known.

        :param scenario: The scenario the trial runs.
        :param perturbation: The perturbation due at the step about to be performed.
        :param world: The world the trial is running in.
        """
        super().apply_perturbation(scenario, perturbation, world)
        self.pieces_acted_on.update(perturbation.pieces_acted_on)

    def belief_questions(self, step: LookAtTheScene, world: World) -> QuestionSet:
        """
        One question per piece the look was asked about: whether what it reported of
        that piece bore out what the robot believed of it.

        :param step: The look that has just been taken and checked.
        :param world: The world the trial is running in.
        """
        scene = SortingScene(world)
        asked: List[BeliefAgreesWithPerception] = [
            BeliefAgreesWithPerception(
                subject=scene.body_of(category),
                contradicted=[type(violated) for violated in report.violated],
                nothing_was_found=report.nothing_was_found,
                perturbed=category in self.pieces_acted_on,
            )
            for category, report in step.reports.items()
        ]
        return QuestionSet(questions=asked)

    def trial_finished(self, scenario: MontessoriSortingScenario, trial) -> None:
        """
        Stop watching, record the trial with everything observed inside it, and keep the
        trace of its joints beside the episode's other artifacts.

        :param scenario: The scenario the trial ran.
        :param trial: The trial that has finished.
        """
        traced = self._stop_watching()
        super().trial_finished(scenario, trial)
        if self.artifacts is None or traced is None:
            return
        self.artifacts.trial(self.recorded_trials[-1].number).keep_joint_trace(traced)

    @staticmethod
    def watched_category(
        scenario: MontessoriSortingScenario,
    ) -> MontessoriShapeCategory:
        """
        The piece the monitor tracks: the one the script acts on, or the first piece
        standing in the scene for a script that acts on none.

        :param scenario: The scenario whose piece is watched, which has built its scene.
        """
        if scenario.acted_on_category is not None:
            return scenario.acted_on_category
        return scenario.starting_layout.placements[0].piece.category

    @classmethod
    def question_set(
        cls, scenario: MontessoriSortingScenario, world: World
    ) -> QuestionSet:
        """
        The working-memory question set, with the pieces of this scene filled in for the
        questions that single one out.

        The piece the script acts on is what is asked about and what the robot is asked
        whether it holds; the next piece standing in the scene is what it is placed
        against, and the board stands in when the scene holds one piece only.

        :param scenario: The scenario whose scene is asked, which has built its scene.
        :param world: The world the trial is running in.
        """
        scene = SortingScene(world)
        acted_on = cls.watched_category(scenario)
        others = [
            placement.piece.category
            for placement in scenario.starting_layout.placements
            if placement.piece.category is not acted_on
        ]
        compared_against = scene.body_of(others[0]) if others else scene.board.root
        return QuestionSet.over_working_memory(
            QuestionedThings(
                object_asked_about=scene.body_of(acted_on),
                object_compared_against=compared_against,
                object_in_the_hand=scene.body_of(acted_on),
                own_body_asked_about=scene.gripper.name,
                point_of_view=HomogeneousTransformationMatrix(
                    scene.robot.root.global_transform.to_np()
                ),
            )
        )

    def _stop_watching(self):
        """
        Stop the monitor and the joint trace of the trial that ran, if they are still
        watching.

        :return: The trace of the joints, or None where nothing was being watched.
        """
        if self.monitor is not None:
            self.monitor.stop()
            self.monitor = None
        if self.joints is None:
            return None
        self.joints.stop()
        traced = self.joints.trace
        self.joints = None
        return traced
