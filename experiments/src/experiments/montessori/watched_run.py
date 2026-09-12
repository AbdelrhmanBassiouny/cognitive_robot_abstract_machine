"""
A sorting run watched while it happens: an event monitor ticks against the piece the
script acts on, the frozen working-memory question set is asked at the step the scene is
asked about, and every motion state chart a step runs is kept as it finishes.

All three go through the run's observer, so the trial the run records carries its ticks,
its scored queries and the motions it ran rather than only its outcome.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from semantic_digital_twin.spatial_types.spatial_types import (
    HomogeneousTransformationMatrix,
)
from semantic_digital_twin.world import World
from typing_extensions import Optional

from experiments.episodes.observer import ObserverListener, ObserverMotionListener
from experiments.episodes.recording import EpisodeRecording
from experiments.montessori.event_monitoring import (
    MontessoriEventMonitor,
    build_shape_monitor_in_scene,
)
from experiments.montessori.scenarios import (
    MontessoriSortingScenario,
    SortingScene,
    SortingStep,
)
from experiments.montessori.semantics import MontessoriShapeCategory
from experiments.questions.question import QuestionedThings
from experiments.questions.question_set import QuestionSet
from experiments.scenarios.scenario import ScenarioStep

# %% the run


@dataclass
class WatchedSortingRun(EpisodeRecording[MontessoriSortingScenario, World]):
    """
    A recorded run of a sorting scenario whose trials are watched by an event monitor
    and asked the working-memory question set when the scene is asked about.
    """

    monitor: Optional[MontessoriEventMonitor] = field(init=False, default=None)
    """
    The monitor watching the trial that is running, or None between trials.
    """

    def trial_started(self, scenario: MontessoriSortingScenario, world: World) -> None:
        """
        Start watching the piece the script acts on, ticking the observer with every
        detection, and have the steps hand their motions to the observer as they finish.

        :param scenario: The scenario the trial runs.
        :param world: The world the trial is about to run in.
        """
        super().trial_started(scenario, world)
        scenario.motion_listener = ObserverMotionListener(observer=self.observer)
        self._stop_watching()
        scene = SortingScene(world)
        self.monitor = build_shape_monitor_in_scene(
            world,
            scene.shape_of(self.watched_category(scenario)),
            listener=ObserverListener(observer=self.observer),
        )
        self.monitor.start()

    def perform_step(
        self,
        scenario: MontessoriSortingScenario,
        step: ScenarioStep[World],
        world: World,
    ) -> None:
        """
        Perform the step, take one tick of the monitor after it, and ask the question
        set once the scene is asked about.

        The monitor is also ticked from the control cycle of whatever motion the step
        runs; the tick here is what watches a step no motion runs in, such as the scene
        settling under gravity.

        :param scenario: The scenario the step belongs to.
        :param step: The step to perform.
        :param world: The world the trial is running in.
        """
        super().perform_step(scenario, step, world)
        self.monitor.tick()
        if step.name is not SortingStep.ANSWER:
            return
        self.observer.ask(
            self.question_set(scenario, world),
            SortingScene(world).robot,
            self.observer.elapsed_seconds,
        )

    def trial_finished(self, scenario: MontessoriSortingScenario, trial) -> None:
        """
        Stop watching, then record the trial with everything observed inside it.

        :param scenario: The scenario the trial ran.
        :param trial: The trial that has finished.
        """
        self._stop_watching()
        super().trial_finished(scenario, trial)

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

    def _stop_watching(self) -> None:
        """
        Stop the monitor of the trial that ran, if one is still watching.
        """
        if self.monitor is None:
            return
        self.monitor.stop()
        self.monitor = None
