"""
A sorting run watched while it happens: an event monitor ticks against the piece the
script acts on, the frozen working-memory question set is asked at the step the scene is
asked about, what a look made of the robot's own account of the scene is scored as the
look is taken, and every motion state chart a step runs is kept as it finishes.

All of it goes through the run's observer, so the trial the run records carries its
ticks, its scored queries and the motions it ran rather than only its outcome.
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass, field

from coraplex.datastructures.enums import ExecutionType
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.spatial_types.spatial_types import (
    HomogeneousTransformationMatrix,
    Point3,
)
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.world_entity import Body
from typing_extensions import Dict, Iterator, List, Optional, Sequence, Set

from experiments.episodes.observer import ObserverListener, ObserverMotionListener
from experiments.episodes.recording import EpisodeRecording
from experiments.episodes.trace import JointTraceRecorder
from experiments.montessori.event_monitoring import (
    MontessoriEventMonitor,
    build_shape_monitor_in_scene,
    build_translation_monitor_in_scene,
)
from experiments.montessori.exceptions import NoPieceNumbered, UnknownPieceNamed
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
)
from experiments.questions.question_set import QuestionSet
from experiments.questions.working_memory import BeliefAgreesWithPerception
from experiments.scenarios.scenario import Person, Perturbation, ScenarioStep

PIECES_ON_OFFER = tuple(MontessoriShapeCategory)
"""
The shapes the person at the table chooses among, numbered from one in this order.
"""

BETWEEN_THE_PIECES_THEY_NAME = ","
"""
What separates one piece from the next in what the person types, beside whitespace.
"""

WHICH_PIECES_WERE_PLACED = (
    "Which pieces did you put on the table when you set it up? "
    "Type their numbers, separated by commas:\n"
    + "\n".join(
        "  %d. %s" % (number, category)
        for number, category in enumerate(PIECES_ON_OFFER, start=1)
    )
    + "\n"
)
"""
What the person at the table is asked, so a run on the robot is scored on the scene they
set up rather than on the one the camera made of it: every shape of the set with its
number, since a number is easier to type right at the console than a spelling.
"""

# %% what the person at the table says they set up


@dataclass
class SceneThePersonSetUp:
    """
    The scene of a run on the robot as the person at the table can state it: which loose
    pieces they put there, named but not placed, and the rest of the scene as the twin
    was built.

    On the robot the twin is what the camera made of the table, so the person is the
    only account of the table that is not the camera's.
    """

    person: Person
    """
    The person at the table, who is asked which pieces they placed.
    """

    def pieces_placed(self) -> Optional[List[MontessoriShapeCategory]]:
        """
        The shapes the person at the table says they put on it, each picked by its
        number on the list they are offered, or named.

        :return: The shapes, or None where nobody at the table says.
        :raises NoPieceNumbered: If they pick a number no piece is listed under.
        :raises UnknownPieceNamed: If they name a shape no piece of the set is.
        """
        said = self.person.answer(WHICH_PIECES_WERE_PLACED)
        if said is None:
            return None
        return [
            self.piece_picked(typed)
            for typed in said.replace(BETWEEN_THE_PIECES_THEY_NAME, " ").split()
        ]

    @staticmethod
    def piece_picked(typed: str) -> MontessoriShapeCategory:
        """
        The shape one thing the person typed picks: a number off the list, or a shape's
        own name.

        :param typed: What they typed for one piece.
        :raises NoPieceNumbered: If it is a number no piece is listed under.
        :raises UnknownPieceNamed: If it is a name no shape of the set has.
        """
        if typed.isdigit():
            number = int(typed)
            if not 1 <= number <= len(PIECES_ON_OFFER):
                raise NoPieceNumbered(number=number, count=len(PIECES_ON_OFFER))
            return PIECES_ON_OFFER[number - 1]
        spellings = {str(category) for category in PIECES_ON_OFFER}
        if typed not in spellings:
            raise UnknownPieceNamed(named=typed, known=frozenset(spellings))
        return MontessoriShapeCategory(typed)

    def stated_over(self, scene: SortingScene) -> Optional[SceneAsSetUp]:
        """
        The scene as the person states it: the pieces they say they placed, named as the
        scene names them, among the rest of the scene as the twin holds it, with nothing
        in the robot's hand.

        :param scene: The scene, as the world the run is set in holds it.
        :return: The account, or None where nobody at the table says what was placed.
        """
        placed = self.pieces_placed()
        if placed is None:
            return None
        return scene.as_set_up([scene.piece_as_named(category) for category in placed])


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

    watched_piece: Optional[MontessoriShapeCategory] = field(init=False, default=None)
    """
    The piece the monitor watches in the trial that is running, or None between
    trials: the one the script acts on, else the one a perturbation acts on, else the
    first piece standing in the scene.
    """

    stated_scene: Optional[SceneAsSetUp] = field(init=False, default=None)
    """
    What the run knows it set up in the trial that is running, or None between trials
    and in a trial nobody can give an account of.

    Taken as the trial starts, before anything acts on the scene, so it is an account of
    what was set up rather than a second reading of what the questions are answered
    from.
    """

    def trial_started(
        self,
        scenario: MontessoriSortingScenario,
        world: World,
        perturbations: Sequence[Perturbation[World]],
    ) -> None:
        """
        Take down what the run knows it set up, start watching the piece something is
        going to happen to, tick the observer with every detection, trace where every
        joint of the world stands, and have the steps hand their motions to the observer
        as they finish.

        :param scenario: The scenario the trial runs.
        :param world: The world the trial is about to run in.
        :param perturbations: The changes due to be applied to this trial's world.
        """
        super().trial_started(scenario, world, perturbations)
        self._stop_watching()
        self.joints = JointTraceRecorder(
            _world=world, clock=lambda: self.observer.elapsed_seconds
        )
        # A still robot changes no joint, so where the joints stand is read once here,
        # as the trial's clock starts, or a trial that moves nothing would keep no trace.
        self.joints.trace.sample(world, self.observer.elapsed_seconds)
        self.pieces_acted_on = set()
        self.stated_scene = self.scene_as_set_up(scenario, world)
        scenario.motion_listener = ObserverMotionListener(observer=self.observer)
        scene = SortingScene(world)
        self.watched_piece = self.watched_category(scenario, perturbations)
        self.monitor = build_shape_monitor_in_scene(
            world,
            scene.shape_of(self.watched_piece),
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
        Keep the instruction the perturbation states with the trial, with what it moves
        and when, bring it about, note which pieces it acted on, and stop saying where
        anything it moved stands.

        The run is the only thing that sees both a perturbation and a look, so it is
        where what the robot ought to have been wrong about is known. What someone else
        moved is no longer where the run put it, and where it ended up is theirs rather
        than the run's to say.

        :param scenario: The scenario the trial runs.
        :param perturbation: The perturbation due at the step about to be performed.
        :param world: The world the trial is running in.
        """
        things_moved = perturbation.things_moved(SortingScene(world))
        self.observer.carried_out(
            perturbation.instruction_for_a_person(),
            self.observer.elapsed_seconds,
            things_moved,
        )
        with self.watching_translations_of(
            self.not_watched(things_moved, world), world
        ):
            super().apply_perturbation(scenario, perturbation, world)
        self.pieces_acted_on.update(perturbation.pieces_acted_on)
        if self.stated_scene is None:
            return
        for moved in things_moved:
            self.stated_scene.forget_where(moved)

    def not_watched(self, names: Sequence[PrefixedName], world: World) -> List[Body]:
        """
        The named things the trial's monitor does not already watch, such as the board.

        :param names: What is asked after, named as the scene names it.
        :param world: The world the trial is running in.
        """
        watched = SortingScene(world).body_of(self.watched_piece).name
        return [
            world.get_kinematic_structure_entity_by_name(name)
            for name in names
            if name != watched
        ]

    @contextlib.contextmanager
    def watching_translations_of(
        self, bodies: Sequence[Body], world: World
    ) -> Iterator[None]:
        """
        Watch the given bodies for the length of the block, seen where they rest before
        it and again after it, so what someone moves in it is kept as a translation of
        what they moved.

        :param bodies: The bodies watched.
        :param world: The world the trial is running in.
        """
        if not bodies:
            yield
            return
        monitor = build_translation_monitor_in_scene(
            world, bodies, listener=ObserverListener(observer=self.observer)
        )
        monitor.tick()
        yield
        monitor.tick()

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

    def piece_asked_about(
        self, scenario: MontessoriSortingScenario
    ) -> MontessoriShapeCategory:
        """
        The piece the questions single out: the one being watched, or, outside a trial,
        the one the script acts on or the first standing in the scene.

        :param scenario: The scenario whose scene is asked, which has built its scene.
        """
        if self.watched_piece is not None:
            return self.watched_piece
        return self.watched_category(scenario, ())

    @staticmethod
    def watched_category(
        scenario: MontessoriSortingScenario,
        perturbations: Sequence[Perturbation[World]],
    ) -> MontessoriShapeCategory:
        """
        The piece the monitor tracks: the one the script acts on, else the one a
        perturbation acts on, else the first piece standing in the scene.

        Something is going to happen to a piece someone acts on, which is what a monitor
        is there to see.

        :param scenario: The scenario whose piece is watched, which has built its scene.
        :param perturbations: The changes due to be applied to the trial's world.
        """
        if scenario.acted_on_category is not None:
            return scenario.acted_on_category
        for perturbation in perturbations:
            if not isinstance(perturbation, SortingPerturbation):
                continue
            if perturbation.pieces_acted_on:
                return perturbation.pieces_acted_on[0]
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
        acted_on = self.piece_asked_about(scenario)
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
    ) -> Optional[SceneAsSetUp]:
        """
        What this run knows it set up, said in the words its questions are scored in.

        Which pieces stand there and where comes from the layout the scenario stood them
        by, or from the person who placed them where the run is on the robot. A piece
        the script acts on is left without a place, since where the physics takes it is
        not the script's to say, and the piece the script leaves in the hand is no
        object of the scene at all. The rest of the scene -- the table, the board,
        whatever the script acts with -- is named and placed off the world as it was
        just built, since a run builds that rather than putting it there.

        :param scenario: The scenario whose scene it is, which has built that scene.
        :param world: The world the trial is about to run in.
        :return: The account, or None where nobody can give one, which is a trial on the
            robot that the person who set its scene up is not at.
        """
        scene = SortingScene(world)
        pieces = self.pieces_set_up(scenario, scene)
        if pieces is None:
            return None
        return scene.as_set_up(pieces, in_the_hand=scenario.category_in_the_hand)

    def pieces_set_up(
        self, scenario: MontessoriSortingScenario, scene: SortingScene
    ) -> Optional[List[PlacedObject]]:
        """
        The loose pieces standing in the scene as whoever set it up knows them, which is
        every piece put there but the one the script leaves in the hand.

        :param scenario: The scenario whose scene it is.
        :param scene: The scene, as the world it was built in holds it.
        :return: The pieces, or None where nobody can say which were put there.
        """
        placements = self.pieces_placed(scenario)
        if placements is None:
            return None
        return [
            self.piece_set_up(scenario, scene, category, placement)
            for category, placement in placements.items()
            if category is not scenario.category_in_the_hand
        ]

    def piece_set_up(
        self,
        scenario: MontessoriSortingScenario,
        scene: SortingScene,
        category: MontessoriShapeCategory,
        placement: Optional[PiecePlacement],
    ) -> PlacedObject:
        """
        One loose piece as whoever set the scene up knows it.

        A piece the script acts on is named and nothing more: it is somewhere the physics
        put it by the time the scene is asked about. A piece nobody says where they put
        stands on nothing the account names: only a run that stood the piece itself
        knows it stood it on the table.

        :param scenario: The scenario whose scene it is.
        :param scene: The scene, as the world it was built in holds it.
        :param category: The shape of the piece.
        :param placement: Where it was put, or None where whoever set the scene up did
            not say.
        """
        named = scene.piece_as_named(category)
        if category is scenario.acted_on_category or placement is None:
            return named
        return PlacedObject(
            name=named.name,
            place=Point3(
                placement.x,
                placement.y,
                scenario.world_builder.resting_height_of(scene.body_of(category)),
            ),
            standing_on=scene.table.root.name,
        )

    def pieces_placed(
        self, scenario: MontessoriSortingScenario
    ) -> Optional[Dict[MontessoriShapeCategory, Optional[PiecePlacement]]]:
        """
        Which pieces were put on the table and where, as whoever put them there knows
        it: the layout in simulation, and the person at the table on the robot, who says
        which pieces they placed but not where to the millimetre.

        :param scenario: The scenario whose scene it is.
        :return: The pieces, or None where the run is on the robot and nobody at the
            table says which are on it.
        """
        if scenario.execution_type is ExecutionType.REAL:
            placed = SceneThePersonSetUp(self.person).pieces_placed()
            if placed is None:
                return None
            return {category: None for category in placed}
        return {
            placement.piece.category: placement
            for placement in scenario.starting_layout.placements
        }

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
