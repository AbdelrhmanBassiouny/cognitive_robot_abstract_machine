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

from coraplex.datastructures.enums import ExecutionType
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.spatial_types.spatial_types import (
    HomogeneousTransformationMatrix,
    Point3,
)
from semantic_digital_twin.world import World
from typing_extensions import Dict, List, Optional, Set

from experiments.episodes.observer import ObserverListener, ObserverMotionListener
from experiments.episodes.recording import EpisodeRecording
from experiments.episodes.trace import JointTraceRecorder
from experiments.montessori.event_monitoring import (
    MontessoriEventMonitor,
    build_shape_monitor_in_scene,
)
from experiments.montessori.exceptions import UnknownPieceNamed
from experiments.montessori.scenarios import (
    LookAtTheScene,
    MontessoriSortingScenario,
    HaveTheRobotAct,
    PiecePlacement,
    SortingPerturbation,
    SortingScene,
    SortingStep,
)
from experiments.montessori.semantics import MontessoriShapeCategory
from experiments.questions.question import (
    PlacedObject,
    QuestionedThings,
    SceneAsSetUp,
    objects_of_the_scene,
    placeless,
)
from experiments.questions.question_set import QuestionSet
from experiments.questions.working_memory import BeliefAgreesWithPerception
from experiments.scenarios.scenario import ScenarioStep

WHICH_PIECES_WERE_PLACED = (
    "Which pieces did you put on the table when you set it up? "
    "Name their shapes, separated by commas:"
)
"""
What the person at the table is asked, so a run on the robot is scored on the scene they
set up rather than on the one the camera made of it.
"""

BETWEEN_THE_PIECES_THEY_NAME = ","
"""
What separates one shape from the next in what the person types.
"""

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

    stated_scene: Optional[SceneAsSetUp] = field(init=False, default=None)
    """
    What the run knows it set up in the trial that is running, or None between trials.

    Taken as the trial starts, before anything acts on the scene, so it is an account of
    what was set up rather than a second reading of what the questions are answered
    from.
    """

    def trial_started(self, scenario: MontessoriSortingScenario, world: World) -> None:
        """
        Take down what the run knows it set up, start watching the piece the script acts
        on, tick the observer with every detection, trace where every joint of the world
        stands, and have the steps hand their motions to the observer as they finish.

        :param scenario: The scenario the trial runs.
        :param world: The world the trial is about to run in.
        """
        super().trial_started(scenario, world)
        self.pieces_acted_on = set()
        self.stated_scene = self.scene_as_set_up(scenario, world)
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
        Bring the perturbation about, note which pieces it acted on, keep the
        instruction it states with the trial, and stop saying where anything it moved
        stands.

        The run is the only thing that sees both a perturbation and a look, so it is
        where what the robot ought to have been wrong about is known. What someone else
        moved is no longer where the run put it, and where it ended up is theirs rather
        than the run's to say.

        :param scenario: The scenario the trial runs.
        :param perturbation: The perturbation due at the step about to be performed.
        :param world: The world the trial is running in.
        """
        super().apply_perturbation(scenario, perturbation, world)
        self.pieces_acted_on.update(perturbation.pieces_acted_on)
        self.observer.carried_out(perturbation.instruction_for_a_person())
        for moved in perturbation.things_moved(SortingScene(world)):
            self.stated_scene.forget_where(moved)

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

    def question_set(
        self, scenario: MontessoriSortingScenario, world: World
    ) -> QuestionSet:
        """
        The working-memory question set, with the pieces of this scene filled in for the
        questions that single one out and the run's own account of the scene for the
        ones scored against it.

        The piece the script acts on is what is asked about and what the robot is asked
        whether it holds; the next piece standing in the scene is what it is placed
        against, and the board stands in when the scene holds one piece only.

        :param scenario: The scenario whose scene is asked, which has built its scene.
        :param world: The world the trial is running in.
        """
        scene = SortingScene(world)
        acted_on = self.watched_category(scenario)
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
                scene=self.stated_scene,
            )
        )

    def scene_as_set_up(
        self, scenario: MontessoriSortingScenario, world: World
    ) -> SceneAsSetUp:
        """
        What this run knows it set up, said in the words its questions are scored in.

        Which pieces stand there and where comes from the layout the scenario stood them
        by, or from the person who placed them where the run is on the robot. A piece the
        script acts on is left without a place, since where the physics takes it is not
        the script's to say, and the piece the script leaves in the hand is no object of
        the scene at all. The rest of the scene -- the table, the board, whatever the
        script acts with -- is named and placed off the world as it was just built, since
        a run builds that rather than putting it there.

        :param scenario: The scenario whose scene it is, which has built that scene.
        :param world: The world the trial is about to run in.
        """
        scene = SortingScene(world)
        pieces = self.pieces_set_up(scenario, scene)
        piece_names = {scene.body_of(category).name for category in scene.categories}
        in_the_hand = scenario.category_in_the_hand
        return SceneAsSetUp(
            objects=pieces
            + [
                PlacedObject(name=body.name, place=placeless(body.global_pose))
                for body in objects_of_the_scene(scene.robot)
                if body.name not in piece_names
            ],
            object_in_the_hand=(
                None if in_the_hand is None else scene.body_of(in_the_hand).name
            ),
        )

    def pieces_set_up(
        self, scenario: MontessoriSortingScenario, scene: SortingScene
    ) -> List[PlacedObject]:
        """
        The loose pieces standing in the scene as whoever set it up knows them, which is
        every piece put there but the one the script leaves in the hand.

        :param scenario: The scenario whose scene it is.
        :param scene: The scene, as the world it was built in holds it.
        """
        resting_on = scene.table.root.name
        return [
            self.piece_set_up(scenario, scene, category, placement, resting_on)
            for category, placement in self.pieces_placed(scenario).items()
            if category is not scenario.category_in_the_hand
        ]

    def piece_set_up(
        self,
        scenario: MontessoriSortingScenario,
        scene: SortingScene,
        category: MontessoriShapeCategory,
        placement: Optional[PiecePlacement],
        resting_on: PrefixedName,
    ) -> PlacedObject:
        """
        One loose piece as whoever set the scene up knows it.

        A piece the script acts on is named and nothing more: it is somewhere the physics
        put it by the time the scene is asked about. A piece the twin holds none of --
        one placed but never found -- is named by its own shape, since the twin has no
        name for what it does not hold.

        :param scenario: The scenario whose scene it is.
        :param scene: The scene, as the world it was built in holds it.
        :param category: The shape of the piece.
        :param placement: Where it was put, or None where whoever set the scene up did
            not say.
        :param resting_on: What the pieces were put on.
        """
        name = (
            scene.body_of(category).name
            if category in scene.categories
            else PrefixedName(str(category))
        )
        if category is scenario.acted_on_category or placement is None:
            return PlacedObject(name=name)
        return PlacedObject(
            name=name,
            place=Point3(
                placement.x,
                placement.y,
                scenario.world_builder.resting_height_of(scene.body_of(category)),
            ),
            standing_on=resting_on,
        )

    def pieces_placed(
        self, scenario: MontessoriSortingScenario
    ) -> Dict[MontessoriShapeCategory, Optional[PiecePlacement]]:
        """
        Which pieces were put on the table and where, as whoever put them there knows
        it: the layout in simulation, and the person at the table on the robot, who says
        which pieces they placed but not where to the millimetre.

        :param scenario: The scenario whose scene it is.
        """
        if scenario.execution_type is ExecutionType.REAL:
            return {category: None for category in self.pieces_the_person_placed()}
        return {
            placement.piece.category: placement
            for placement in scenario.starting_layout.placements
        }

    def pieces_the_person_placed(self) -> List[MontessoriShapeCategory]:
        """
        The shapes the person at the table says they put on it.

        :raises UnknownPieceNamed: If they name a shape no piece of the set is.
        """
        said = self.person.answer(WHICH_PIECES_WERE_PLACED)
        named = [
            spelled.strip()
            for spelled in said.split(BETWEEN_THE_PIECES_THEY_NAME)
            if spelled.strip()
        ]
        spellings = {str(category) for category in MontessoriShapeCategory}
        unknown = [spelled for spelled in named if spelled not in spellings]
        if unknown:
            raise UnknownPieceNamed(named=unknown[0], known=frozenset(spellings))
        return [MontessoriShapeCategory(spelled) for spelled in named]

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
