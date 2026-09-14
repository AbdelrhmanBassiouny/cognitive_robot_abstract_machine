"""
Tests for :mod:`experiments.tracy_experiments.pickup.pickup_demo_real`: a perceived
piece is grasped with the target lifted back to where the pick aimed before the spawn
was lowered, and while a piece is carried the gripper is re-closed and watched for the
piece slipping out.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

import numpy as np
import pytest
from coraplex.datastructures.dataclasses import Context
from coraplex.datastructures.enums import Arms, ExecutionType
from giskardpy.motion_statechart.motion_statechart import MotionStatechart
from segmind.datastructures.events import PickUpEvent, TranslationEvent

from experiments.episodes.artifacts import (
    ARTIFACT_DIRECTORY_ENVIRONMENT_VARIABLE,
    ArtifactDirectory,
    RunFile,
    Transcript,
)
from experiments.episodes.trace import JointTrace
from experiments.montessori.record_episode import PerturbationChoice
from experiments.montessori.results_database import (
    IN_MEMORY_DATABASE_URI,
    InMemoryDatabaseRefused,
    ResultsDatabase,
)
from experiments.montessori.scenarios import SortingScene
from experiments.montessori.semantics import CubeShape, MontessoriShapeCategory
from experiments.montessori.watched_run import WHICH_PIECES_WERE_PLACED
from experiments.orm.ormatic_interface import RecordedTrialDAO
from experiments.paper.run_plan import TrialClock
from experiments.questions.question import ScoredAgainstTheSceneAsSetUp
from experiments.scenarios.scenario import AbsentPerson
from experiments.scenarios.trial import TrialOutcome
from experiments.tracy_experiments.montessori.gripper_feedback import (
    FULLY_CLOSED_KNUCKLE_POSITION,
    RECLOSE_MARGIN,
    GripperClosure,
    GripperSlipEvent,
)
from experiments.tracy_experiments.montessori.grasp_widths import (
    RECTANGULAR_PRISM_CLOSE_SETPOINT,
)
from experiments.tracy_experiments.pickup.pickup_demo_real import (
    GRASP_HEIGHT_OFFSET,
    PERTURBATION_STEP,
    PERTURBATIONS_A_PERSON_BRINGS_ABOUT,
    PICK_ARM,
    SCENARIO_NAME,
    DemoOption,
    PickupDemo,
    PieceNotSeenError,
    SortingTrial,
    _grasp_target_pose,
    _parse_arguments,
    _reach_action_for,
    _SortingRig,
    database_asked_for,
    keep_the_episode,
    main,
    outcome_of,
    perturbation_asked_for,
    piece_asked_about,
)
from experiments.tracy_experiments.robotiq_gripper import GripperCommandRejected
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.spatial_types.spatial_types import (
    HomogeneousTransformationMatrix,
    Pose,
)
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.connections import FixedConnection
from semantic_digital_twin.world_description.world_entity import Body

from .test_episode_artifacts import a_bag
from .test_episode_recording import (
    UNREACHABLE_URI,
    finished_trial,
    recorded_count,
    sorting_episode,
)
from .test_working_memory_ground_truth import (
    ATableTheCameraFound,
    PersonWhoSaysWhatTheyPlaced,
)

# %% the grasp offset


def _world_with_root() -> World:
    """
    :return: A world holding only its root body.
    """
    world = World()
    with world.modify_world():
        world.add_kinematic_structure_entity(Body(name=PrefixedName("root")))
    return world


def _body_at(world: World, name: str, x: float, y: float, z: float, yaw: float) -> Body:
    """
    A body stood in ``world`` at a position and turned about the world's z-axis, so a
    grasp target computed from it can be checked against a body that is not resting flat
    with no yaw.
    """
    body = Body(name=PrefixedName(name))
    with world.modify_world():
        world.add_connection(
            FixedConnection(
                parent=world.root,
                child=body,
                parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                    x=x, y=y, z=z, yaw=yaw, reference_frame=world.root
                ),
            )
        )
    return body


def test_grasp_target_pose_sits_the_offset_above_the_bodys_position():
    world = _world_with_root()
    body = _body_at(world, "shape", x=0.3, y=-0.1, z=0.05, yaw=1.0)

    pose = _grasp_target_pose(body, GRASP_HEIGHT_OFFSET, world)

    translation = [
        float(component) for component in pose.to_homogeneous_matrix()[:3, 3]
    ]
    assert translation == pytest.approx([0.3, -0.1, 0.05 + GRASP_HEIGHT_OFFSET])
    assert pose.reference_frame is world.root


def test_grasp_target_pose_uses_the_same_orientation_for_every_body():
    """
    A perceived piece can land turned any way it happens to rest; the reach is aimed at
    it the same way round whatever that turn was, so the target's own orientation does
    not depend on the body's.
    """
    world = _world_with_root()
    turned_one_way = _body_at(world, "first", x=0.3, y=-0.1, z=0.05, yaw=1.0)
    turned_another_way = _body_at(world, "second", x=0.1, y=0.2, z=0.05, yaw=-2.0)

    first_pose = _grasp_target_pose(turned_one_way, GRASP_HEIGHT_OFFSET, world)
    second_pose = _grasp_target_pose(turned_another_way, GRASP_HEIGHT_OFFSET, world)

    identity = np.eye(3)
    assert first_pose.to_homogeneous_matrix().to_np()[:3, :3] == pytest.approx(identity)
    assert second_pose.to_homogeneous_matrix().to_np()[:3, :3] == pytest.approx(
        identity
    )


# %% the reach that is built to grasp a piece


def test_the_reach_is_aimed_at_the_piece_not_its_body():
    """
    ``ReachAction.object_designator`` needs a semantic annotation to read its own
    ``.root`` from, not the piece's bare body, which has no ``root`` of its own.
    """
    piece = CubeShape(root=Body(name=PrefixedName("cube")))
    target_pose = Pose(reference_frame=piece.root)

    reach = _reach_action_for(piece, target_pose, grasp_description=None)

    assert reach.object_designator is piece
    assert reach.target_pose is target_pose
    assert reach.arm is PICK_ARM


# %% slip watch while carrying


@dataclass
class RecordingGripper:
    """
    Records every re-close instead of driving the real action server.
    """

    close_to_setpoints: list[float] = field(default_factory=list)
    """
    Setpoint of every :meth:`close_to` call, in order.
    """

    def close_to(self, arm: Arms, setpoint: float) -> None:
        self.close_to_setpoints.append(setpoint)


@dataclass
class RejectingOnceGripper:
    """
    Records every re-close like :class:`RecordingGripper`, but raises
    :class:`~experiments.tracy_experiments.robotiq_gripper.GripperCommandRejected` on
    one chosen call -- reproducing a Robotiq controller that answers a repeated,
    already-satisfied re-close with neither ``reached_goal`` nor ``stalled`` set.
    """

    close_to_setpoints: list[float] = field(default_factory=list)
    """
    Setpoint of every :meth:`close_to` call, in order, rejected calls included.
    """

    reject_on_call_index: int = 1
    """
    Zero-based index, among all :meth:`close_to` calls, that raises.
    """

    def close_to(self, arm: Arms, setpoint: float) -> None:
        index = len(self.close_to_setpoints)
        self.close_to_setpoints.append(setpoint)
        if index == self.reject_on_call_index:
            raise GripperCommandRejected(arm, reached_goal=False, stalled=False)


@dataclass
class SequencedClosureListener:
    """
    Serves a fixed sequence of knuckle readings, holding the last one.
    """

    readings: list[GripperClosure]
    """
    Readings handed out on successive accesses.
    """

    _next: int = 0
    """
    Index of the next reading to serve.
    """

    @property
    def latest_closure(self) -> GripperClosure:
        reading = self.readings[min(self._next, len(self.readings) - 1)]
        self._next += 1
        return reading


@dataclass
class PublishedEvent:
    """
    One event handed to the dashboard feed.
    """

    shape_name: str
    """
    Name the event was published under.
    """

    event: object
    """
    The event object.
    """


@dataclass
class RecordingFeed:
    """
    Records what the slip watch streams to the dashboard.
    """

    published: list[PublishedEvent] = field(default_factory=list)
    """
    Every :meth:`publish` call, in order.
    """

    def publish(self, shape_name: str, event: object) -> None:
        self.published.append(PublishedEvent(shape_name=shape_name, event=event))


def _slip_watch_rig(
    gripper: RecordingGripper,
    listener: SequencedClosureListener,
    feed: RecordingFeed | None = None,
) -> _SortingRig:
    """
    A rig with only the fields :meth:`_SortingRig._carry_watching_for_slip` reads.
    """
    return _SortingRig(
        context=Context(world=None, robot=None),
        world=None,
        robot=None,
        feed=feed,
        gripper=gripper,
        gripper_listener=listener,
        grasp_description=None,
        tool_frame=None,
        slip_watch_interval=0.01,
    )


def _held(*extra: float) -> SequencedClosureListener:
    """
    A listener whose grasp confirms as held, then serves ``extra`` poll readings.
    """
    return SequencedClosureListener(
        [GripperClosure(knuckle_position=position) for position in (0.45, *extra)]
    )


def _no_slip_watch_thread_left_running() -> bool:
    return not any(
        thread.name.startswith("slip-watch") and thread.is_alive()
        for thread in threading.enumerate()
    )


def _wait_until(predicate) -> None:
    deadline = time.monotonic() + 2.0
    while not predicate() and time.monotonic() < deadline:
        time.sleep(0.005)


def test_a_missed_grasp_skips_the_slip_watch_but_still_carries():
    gripper = RecordingGripper()
    listener = SequencedClosureListener(
        [GripperClosure(knuckle_position=FULLY_CLOSED_KNUCKLE_POSITION)]
    )
    rig = _slip_watch_rig(gripper, listener)
    carried: list[bool] = []

    rig._carry_watching_for_slip(
        Body(name=PrefixedName("cube")), 0.5, lambda: carried.append(True)
    )

    assert carried == [True]
    assert gripper.close_to_setpoints == []
    assert _no_slip_watch_thread_left_running()


def test_a_held_grasp_re_closes_past_fully_closed_while_the_shape_is_carried():
    gripper = RecordingGripper()
    rig = _slip_watch_rig(gripper, _held())

    rig._carry_watching_for_slip(
        Body(name=PrefixedName("cube")),
        0.5,
        lambda: _wait_until(lambda: len(gripper.close_to_setpoints) > 0),
    )

    assert gripper.close_to_setpoints
    assert all(
        setpoint == 0.5 + RECLOSE_MARGIN for setpoint in gripper.close_to_setpoints
    )
    assert _no_slip_watch_thread_left_running()


def test_the_slip_watch_re_closes_past_a_shapes_own_firmer_close_setpoint():
    """
    A shape closed to more than ``FingerSetpoint.CLOSED`` must be re-closed past *its*
    setpoint, not past ``CLOSED``.

    The rectangular prism grasps at ``0.6``. Re-commanding the ``CLOSED``-derived
    ``0.55`` would ease the fingers open on every poll and drop the piece.
    """
    gripper = RecordingGripper()
    rig = _slip_watch_rig(gripper, _held())

    rig._carry_watching_for_slip(
        Body(name=PrefixedName("rectangular_prism")),
        RECTANGULAR_PRISM_CLOSE_SETPOINT,
        lambda: _wait_until(lambda: len(gripper.close_to_setpoints) > 0),
    )

    re_closes = gripper.close_to_setpoints
    assert re_closes
    assert all(
        setpoint == RECTANGULAR_PRISM_CLOSE_SETPOINT + RECLOSE_MARGIN
        for setpoint in re_closes
    )
    assert all(setpoint > RECTANGULAR_PRISM_CLOSE_SETPOINT for setpoint in re_closes)
    assert _no_slip_watch_thread_left_running()


def test_a_rejected_reclose_does_not_end_the_slip_watch():
    """
    A re-close that repeats the previous poll's setpoint asks the fingers for no further
    travel once they have already settled there, and a real run against the rectangular
    prism had exactly that rejected with neither ``reached_goal`` nor ``stalled`` set --
    which used to raise out of the watch thread's target and kill it silently (a bare
    traceback on stderr, and nobody watching the piece for the rest of the carry).

    The watch must keep polling through a rejected re-close instead: the
    knuckle position :class:`SlipDetector` reads comes from the joint-state topic, not
    from the re-close action's own result.
    """
    gripper = RejectingOnceGripper()
    rig = _slip_watch_rig(gripper, _held(0.46))

    rig._carry_watching_for_slip(
        Body(name=PrefixedName("rectangular_prism")),
        0.5,
        lambda: _wait_until(lambda: len(gripper.close_to_setpoints) > 3),
    )

    assert len(gripper.close_to_setpoints) > 3
    assert _no_slip_watch_thread_left_running()


def test_a_slip_streams_a_gripper_slip_event_to_the_feed():
    gripper = RecordingGripper()
    feed = RecordingFeed()
    rig = _slip_watch_rig(gripper, _held(0.5), feed)
    body = Body(name=PrefixedName("cube"))

    rig._carry_watching_for_slip(
        body, 0.5, lambda: _wait_until(lambda: bool(feed.published))
    )

    assert feed.published
    assert all(entry.shape_name == "cube" for entry in feed.published)
    first_event = feed.published[0].event
    assert isinstance(first_event, GripperSlipEvent)
    assert first_event.tracked_object is body
    assert _no_slip_watch_thread_left_running()


# %% what the run records of itself


def test_an_event_a_monitor_reports_reaches_the_dashboard_and_the_episode():
    """
    An event goes to the live dashboard as before, and is kept as a tick of the trial
    the run records, stamped with the moment it arrived.
    """
    feed = RecordingFeed()
    rig = _slip_watch_rig(RecordingGripper(), _held(), feed)
    piece = Body(name=PrefixedName("shape"))
    picked_up = PickUpEvent(tracked_object=piece)

    rig.note_event(piece.name.name, picked_up)

    assert [published.event for published in feed.published] == [picked_up]
    [tick] = rig.observer.ticks
    assert tick.events == [picked_up]
    assert 0.0 <= tick.moment <= rig.observer.elapsed_seconds


def test_a_plan_the_rig_performed_is_kept_for_the_episode():
    rig = _slip_watch_rig(RecordingGripper(), _held())
    plan = PerformedNothing()

    rig.perform_and_record(plan)

    assert plan.performed
    assert [performed.plan for performed in rig.observer.plans] == [plan]


@dataclass
class PerformedNothing:
    """
    Stands in for a plan, remembering that it was performed.
    """

    performed: bool = False
    """
    Whether :meth:`perform` was called.
    """

    def perform(self) -> None:
        self.performed = True


HOW_LONG_THE_CHART_RAN = 0.5
"""
Seconds the mimic plan's one chart ran for.
"""


@dataclass
class PlanWhoseExecutableHandsOverItsChart:
    """
    Stands in for a plan whose one executable, as coraplex's does once it has run its
    chart, hands that chart to whoever the context says listens.
    """

    context: Context
    """
    The context the plan runs under.
    """

    motion_statechart: MotionStatechart
    """
    The chart the plan runs.
    """

    def perform(self) -> None:
        self.context.motion_listener.receive(
            self.motion_statechart, HOW_LONG_THE_CHART_RAN
        )


def test_every_chart_a_plan_of_the_rig_runs_is_kept_as_a_motion_of_the_trial():
    """
    The rig's plans run under its own context, so what that context is told about the
    charts they run reaches the trial as its motions -- which is what a question about
    the control program reads.
    """
    rig = _slip_watch_rig(RecordingGripper(), _held())
    chart = MotionStatechart()

    rig.perform_and_record(PlanWhoseExecutableHandsOverItsChart(rig.context, chart))
    trial = rig.observer.into(finished_trial(sorting_episode()))

    [motion] = trial.motions
    assert motion.motion_statechart is chart
    assert motion.end_moment - motion.start_moment == pytest.approx(
        HOW_LONG_THE_CHART_RAN
    )


def test_the_run_succeeded_when_its_monitors_saw_the_asked_piece_picked_up():
    piece = Body(name=PrefixedName("shape"))
    another = Body(name=PrefixedName("another"))

    assert outcome_of([PickUpEvent(tracked_object=piece)], piece) is (
        TrialOutcome.SUCCEEDED
    )
    assert outcome_of([PickUpEvent(tracked_object=another)], piece) is (
        TrialOutcome.FAILED
    )


def test_asking_about_a_piece_the_look_did_not_find_says_so():
    with pytest.raises(PieceNotSeenError) as raised:
        piece_asked_about(LookedAndFound(pieces=[]), MontessoriShapeCategory.CUBE)
    assert raised.value.category is MontessoriShapeCategory.CUBE


@dataclass
class LookedAndFound:
    """
    Stands in for a run that has looked, holding the pieces the look found, and counting
    how often it is asked to look again and whether it sorted.
    """

    pieces: list
    """
    The pieces, as the world holds them.
    """

    board: object = None
    """
    The board, as the world holds it.
    """

    looks_taken: int = 0
    """
    How many times :meth:`perceive` has been called.
    """

    sorted: bool = False
    """
    Whether :meth:`sort_every_piece` was called.
    """

    def perceive(self) -> None:
        self.looks_taken += 1

    def sort_every_piece(self) -> None:
        self.sorted = True


# %% the database the sorting is recorded to


def test_the_demo_refuses_a_database_that_dies_with_the_run():
    """
    A sorting run against a stopped database used to be sorted anyway and recorded to
    memory, so the episode was lost without anyone being told.
    """
    with pytest.raises(InMemoryDatabaseRefused):
        main([DemoOption.DATABASE_URI, UNREACHABLE_URI])


def test_the_demo_refuses_an_in_memory_database_asked_for_by_name():
    with pytest.raises(InMemoryDatabaseRefused):
        main([DemoOption.DATABASE_URI, IN_MEMORY_DATABASE_URI])


def test_the_episode_is_kept_in_the_database_the_run_was_checked_against(
    tmp_path, monkeypatch
):
    monkeypatch.setenv(ARTIFACT_DIRECTORY_ENVIRONMENT_VARIABLE, str(tmp_path))
    database = ResultsDatabase(uri="sqlite:///%s" % (tmp_path / "episodes.db"))
    trial = finished_trial(sorting_episode())

    artifacts = keep_the_episode(trial, JointTrace(), None, database)

    assert recorded_count(database, RecordedTrialDAO) == 1
    assert (
        Transcript(episode=trial.episode, trials=[trial]).render()
        == artifacts.transcript.read_text()
    )


def test_the_bag_is_kept_where_a_reader_of_the_episode_looks_for_it(
    tmp_path, monkeypatch
):
    """
    The bag is named after the demo and the moment it started, which nothing reading the
    episode back knows; kept as the episode's camera recording, a card finds it from the
    episode alone.
    """
    monkeypatch.setenv(ARTIFACT_DIRECTORY_ENVIRONMENT_VARIABLE, str(tmp_path))
    database = ResultsDatabase(uri="sqlite:///%s" % (tmp_path / "episodes.db"))
    bag = a_bag(tmp_path)

    artifacts = keep_the_episode(
        finished_trial(sorting_episode()), JointTrace(), bag, database
    )

    assert artifacts.camera_recording == artifacts.run_file(RunFile.CAMERA_RECORDING)
    assert sorted(path.name for path in artifacts.camera_recording.iterdir()) == sorted(
        path.name for path in bag.iterdir()
    )


# %% a run that keeps no episode


def test_a_run_keeps_its_episode_unless_told_not_to():
    assert _parse_arguments([]).no_episode is False
    assert _parse_arguments([DemoOption.NO_EPISODE]).no_episode is True


def test_a_run_that_keeps_no_episode_needs_no_database():
    """
    A database is checked before the robot moves only because the episode is recorded to
    it, so a run keeping none is not refused for one it cannot reach.
    """
    arguments = _parse_arguments(
        [DemoOption.NO_EPISODE, DemoOption.DATABASE_URI, UNREACHABLE_URI]
    )

    assert database_asked_for(arguments) is None


def test_a_run_that_keeps_no_episode_writes_nothing(tmp_path):
    artifact_directory = ArtifactDirectory(path=tmp_path / "artifacts")
    demo = PickupDemo(
        tracy=None,
        person=AbsentPerson(),
        database=None,
        artifact_directory=artifact_directory,
    )

    kept = demo.keep(finished_trial(sorting_episode()), JointTrace(), a_bag(tmp_path))

    assert kept is None
    assert not artifact_directory.path.exists()


# %% the perturbation the command line asks for


def test_the_two_perturbations_a_person_can_bring_about_are_offered():
    for choice in PERTURBATIONS_A_PERSON_BRINGS_ABOUT:
        arguments = _parse_arguments(
            [
                DemoOption.PERTURBATION,
                choice.value,
                DemoOption.PIECE,
                MontessoriShapeCategory.CYLINDER.value,
            ]
        )
        assert arguments.perturbation is choice
        assert arguments.piece is MontessoriShapeCategory.CYLINDER


def test_a_perturbation_of_what_is_seen_is_not_offered():
    """
    A person at the table can push a piece or slide the board, but cannot make the
    camera misread one; those perturbations are the recorder's, in simulation.
    """
    not_offered = set(PerturbationChoice) - set(PERTURBATIONS_A_PERSON_BRINGS_ABOUT)
    assert not_offered
    for choice in not_offered:
        with pytest.raises(SystemExit):
            _parse_arguments([DemoOption.PERTURBATION, choice.value])


def test_the_perturbation_asked_for_is_aimed_at_the_piece_and_due_before_the_sort():
    perturbation = perturbation_asked_for(
        PerturbationChoice.PIECE_SHOVED, MontessoriShapeCategory.CYLINDER
    )

    assert perturbation == PerturbationChoice.PIECE_SHOVED.aimed_at(
        MontessoriShapeCategory.CYLINDER, PERTURBATION_STEP
    )
    assert perturbation_asked_for(None, MontessoriShapeCategory.CYLINDER) is None


# %% the trial the demo records


def rig_over(world) -> _SortingRig:
    """
    A rig over the given world, with the parts a trial reads: its world, its robot, its
    observer and the context its plans run under.
    """
    scene = SortingScene(world)
    return _SortingRig(
        context=Context(world=world, robot=scene.robot),
        world=world,
        robot=scene.robot,
        feed=RecordingFeed(),
        gripper=RecordingGripper(),
        gripper_listener=_held(),
        grasp_description=None,
        tool_frame=None,
    )


def sorting_over(world) -> LookedAndFound:
    """
    A sorting that has looked at the given world, holding every piece standing in it.
    """
    scene = SortingScene(world)
    return LookedAndFound(
        pieces=[
            scene.shape_of(category)
            for category in MontessoriShapeCategory
            if category in scene.categories
        ],
        board=scene.board,
    )


def trial_over(found: ATableTheCameraFound, person, perturbation=None) -> SortingTrial:
    """
    The demo's trial over a table the camera found, with the given person at it.
    """
    return SortingTrial(
        rig=rig_over(found.world),
        sorting=sorting_over(found.world),
        person=person,
        asked_about=found.pieces_standing[0],
        perturbation=perturbation,
    )


def test_the_questions_are_scored_against_what_the_person_says_they_placed():
    """
    The twin is what the camera made of the table, which is the very thing an answer
    could be wrong about; the person at the table is the only other account of it.
    """
    found = ATableTheCameraFound.looked_at()
    scene = SortingScene(found.world)
    placed, not_placed = found.pieces_standing[:2], found.pieces_standing[2:]
    person = PersonWhoSaysWhatTheyPlaced.who_placed(placed)
    trial = trial_over(found, person)

    trial.state_the_scene()
    question_set = trial.question_set()

    assert person.asked == [WHICH_PIECES_WERE_PLACED]
    scored = [
        question
        for question in question_set.questions
        if isinstance(question, ScoredAgainstTheSceneAsSetUp)
    ]
    assert scored
    assert all(question.scene is trial.stated_scene for question in scored)
    names = trial.stated_scene.names
    assert all(scene.body_of(category).name in names for category in placed)
    assert not any(scene.body_of(category).name in names for category in not_placed)


def test_a_trial_nobody_is_at_asks_only_what_it_can_score():
    found = ATableTheCameraFound.looked_at()
    trial = trial_over(found, AbsentPerson())

    trial.state_the_scene()

    assert trial.stated_scene is None
    assert not any(
        isinstance(question, ScoredAgainstTheSceneAsSetUp)
        for question in trial.question_set().questions
    )


def test_the_episode_names_the_perturbation_the_trial_ran_under():
    found = ATableTheCameraFound.looked_at()
    perturbation = perturbation_asked_for(
        PerturbationChoice.PIECE_SHOVED, found.pieces_standing[0]
    )

    episode = trial_over(found, AbsentPerson(), perturbation).episode()

    assert episode.perturbation_names == [type(perturbation).__name__]
    assert episode.scenario_name == SCENARIO_NAME
    assert episode.execution_type is ExecutionType.REAL
    assert episode.world is found.world


def test_an_unperturbed_episode_names_no_perturbation():
    found = ATableTheCameraFound.looked_at()
    assert trial_over(found, AbsentPerson()).episode().perturbation_names == []


def test_the_person_brings_the_perturbation_about_and_the_trial_records_it():
    """
    A perturbation on the robot is something the person at the table does: they are told
    what to do before the sort, the run looks at the table again once they have done it,
    and what they were told is kept with the trial.
    """
    found = ATableTheCameraFound.looked_at()
    person = AbsentPerson()
    perturbation = perturbation_asked_for(
        PerturbationChoice.PIECE_SHOVED, found.pieces_standing[0]
    )
    trial = trial_over(found, person, perturbation)
    instruction = perturbation.instruction_for_a_person()

    trial.begin()
    trial.perform()
    recorded = trial.finish(trial.episode())

    assert person.asked == [instruction]
    assert recorded.instructions_carried_out == [instruction]
    assert trial.sorting.looks_taken == 1
    assert trial.sorting.sorted


@dataclass
class LookedAndFoundWhatWasShoved(LookedAndFound):
    """
    Stands in for a run whose second look finds what the person at the table moved where
    they moved it.
    """

    world: World = None
    """
    The world the look stands what it found in.
    """

    shove: object = None
    """
    What the person did, which the look finds done.
    """

    def perceive(self) -> None:
        super().perceive()
        self.shove.apply(self.world)


def test_the_piece_the_person_shoves_is_watched_and_recorded_as_moved_by_them():
    """
    Nothing of the robot moves while the person acts, so the piece they were told to
    move is watched from before they act until the camera has found it again, and the
    trial keeps what they moved and when.
    """
    found = ATableTheCameraFound.looked_at()
    shoved = found.pieces_standing[0]
    perturbation = perturbation_asked_for(PerturbationChoice.PIECE_SHOVED, shoved)
    piece = SortingScene(found.world).body_of(shoved)
    sorting = sorting_over(found.world)
    trial = SortingTrial(
        rig=rig_over(found.world),
        sorting=LookedAndFoundWhatWasShoved(
            pieces=sorting.pieces,
            board=sorting.board,
            world=found.world,
            shove=perturbation,
        ),
        person=AbsentPerson(),
        asked_about=shoved,
        perturbation=perturbation,
    )

    trial.begin()
    trial.perform()
    recorded = trial.finish(trial.episode())

    [moved] = recorded.moved_by_someone_else
    assert moved.things_moved == [piece.name]
    assert any(
        isinstance(event, TranslationEvent) and event.tracked_object is piece
        for tick in recorded.ticks
        if tick.moment >= moved.moment
        for event in tick.events
    )


def test_an_unperturbed_trial_tells_the_person_nothing_and_looks_no_further():
    found = ATableTheCameraFound.looked_at()
    person = AbsentPerson()
    trial = trial_over(found, person)

    trial.begin()
    trial.perform()
    recorded = trial.finish(trial.episode())

    assert person.asked == []
    assert recorded.instructions_carried_out == []
    assert trial.sorting.looks_taken == 0


def test_what_the_perturbation_moved_is_no_longer_placed_in_the_persons_account():
    """
    The board the person slid is not where the run had it any more, so the account stops
    saying where it stands.
    """
    found = ATableTheCameraFound.looked_at()
    scene = SortingScene(found.world)
    trial = trial_over(
        found,
        PersonWhoSaysWhatTheyPlaced.who_placed(found.pieces_standing),
        perturbation_asked_for(
            PerturbationChoice.TARGET_HOLE_MOVED, found.pieces_standing[0]
        ),
    )

    trial.state_the_scene()
    assert trial.stated_scene.place_of(scene.board.root.name) is not None
    trial.bring_about_the_perturbation()

    assert trial.stated_scene.place_of(scene.board.root.name) is None


def test_the_trial_asks_the_question_set_once_the_sorting_is_done():
    found = ATableTheCameraFound.looked_at()
    trial = trial_over(
        found, PersonWhoSaysWhatTheyPlaced.who_placed(found.pieces_standing)
    )

    trial.begin()
    trial.perform()
    recorded = trial.finish(trial.episode())

    assert recorded.queries
    assert all(
        query.question.scene is trial.stated_scene
        for query in recorded.queries
        if isinstance(query.question, ScoredAgainstTheSceneAsSetUp)
    )


# %% the clock the trial's rows, its joint trace and its bag share


def test_the_joint_trace_and_the_rows_count_their_seconds_from_when_the_trial_began():
    """
    The bag is stamped on the wall clock, the rows say when the trial began on it, and
    every moment of the trial -- a tick, a query, a joint sample -- is seconds from that
    instant, so all of them are read against one another through the trial's clock.
    """
    found = ATableTheCameraFound.looked_at()
    trial = trial_over(found, AbsentPerson())

    trial.begin()
    began_at = trial.rig.observer.began_at
    found.world.notify_state_change()
    assert trial.joints.clock() == pytest.approx(
        trial.rig.observer.elapsed_seconds, abs=0.01
    )
    trial.perform()
    recorded = trial.finish(trial.episode())

    assert TrialClock.of(recorded).origin == began_at
    assert trial.joints.trace.moments
    assert all(
        0.0 <= moment <= recorded.duration for moment in trial.joints.trace.moments
    )
    assert all(0.0 <= query.moment <= recorded.duration for query in recorded.queries)
