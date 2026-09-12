"""
One query of the paper shown beside a picture of what its answer means.

The counterpart of :mod:`~experiments.paper.figure`: a table says how often the queries
were answered correctly, a card says what one of those answers *is* -- the bodies it
names picked out of the twin, when in the run it was asked, and, for a run on the robot,
what the camera was looking at while it was.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from krrood.exceptions import DataclassException
from segmind.datastructures.events import (
    AgentInteractionEvent,
    DetectionEvent,
    MotionEvent,
    PickUpEvent,
)
import numpy as np
from typing_extensions import ClassVar, Dict, List, Optional, Sequence, Tuple, Type

from experiments.episodes.artifacts import ArtifactDirectory, EpisodeArtifacts
from experiments.episodes.episode import RecordedQuery, RecordedTrial
from experiments.experiment_definitions import TypstRenderer
from experiments.episodes.trace import JointPositions, JointTrace
from experiments.montessori.same_piece import SamePiece
from experiments.montessori.semantics import MontessoriShape, ShapeSortingBoard
from experiments.paper.camera_frame import (
    EITHER_SIDE,
    BagFrameAt,
    BagFramesAround,
    RecordedFramesAround,
)
from experiments.paper.figure import FigureFile
from experiments.paper.layered import Layer, LayeredFigure
from experiments.paper.panel import CardPanel, PanelKind
from experiments.paper.plan_timeline import PlanTimeline
from experiments.paper.pose_change import (
    WAYPOINTS,
    PoseChange,
    PoseChangeRender,
    can_be_stood_somewhere_else,
    standing_pose,
)
from experiments.paper.run_timeline import RunTimeline
from experiments.paper.scene import PointOfView, SceneRender
from experiments.paper.run_plan import ObjectIdentity, SameName, plans_of
from experiments.paper.timeline import EventTimeline
from experiments.questions.question import Question
from experiments.questions.working_memory import (
    NumberOfOwnDegreesOfFreedom,
    ObjectsSeen,
    PickedUpRecently,
    SideOfAnotherObject,
)
from semantic_digital_twin.adapters.multi_sim import MujocoCamera
from semantic_digital_twin.robots.robot_parts import AbstractRobot
from semantic_digital_twin.world import World
from semantic_digital_twin.spatial_types.spatial_types import (
    HomogeneousTransformationMatrix,
)
from semantic_digital_twin.world_description.world_entity import (
    Body,
    KinematicStructureEntity,
)

# %% which card of the paper a card is


class QueryCardName(StrEnum):
    """
    Every query the paper shows a picture of, named by the question it asks.

    A member's value is the stem of the files the card is written to, so the paper and
    the script that regenerates it name a card once.
    """

    OBJECTS_SEEN = "objects_seen"
    SIDE_OF_ANOTHER_OBJECT = "side_of_another_object"
    PICKED_UP_RECENTLY = "picked_up_recently"
    OWN_DEGREES_OF_FREEDOM = "own_degrees_of_freedom"
    EVENT_AGAINST_THE_PLAN = "event_against_the_plan"


class CardFile(StrEnum):
    """
    What a card leaves beside its own panels, named as the file is called after the
    card.
    """

    LAYERED = "layered"
    """
    The card's levels drawn one above another as a single picture.
    """


EPISODE_IDENTIFIER_SHOWN = 8
"""
How many characters of an episode's identifier a figure names it by: enough to find it
in the database, short enough for a line.
"""

TRIAL_DIRECTORY = "trial_%02d"
"""
What one trial's own directory of cards is called inside its episode's.

A trial asks the same questions as every other trial of its episode, so the cards of two
of them would otherwise write over each other.
"""


@dataclass(frozen=True)
class WrittenQueryCard:
    """
    Where one card's markup, and every picture it names, were left.
    """

    card: QueryCardName
    """
    The card that was written.
    """

    query: RecordedQuery
    """
    The query it shows, so a card in the paper is traceable to the run that asked it.
    """

    markup_path: Path
    """
    The Typst markup the paper includes, which names every picture below.
    """

    panel_paths: Dict[PanelKind, Path]
    """
    Where each of the card's pictures was left, in the order they were drawn.
    """

    layered_path: Optional[Path] = None
    """
    Where the card's levels were left stacked as one picture, or None for a card that
    shows each of its pictures as a figure of its own.
    """


# %% asking for a card that cannot be drawn


@dataclass
class UnknownQueryCardError(DataclassException):
    """
    Raised when a card is asked for that the set does not hold.
    """

    card: QueryCardName
    """
    The card nothing was found for.
    """

    def error_message(self) -> str:
        return "The set holds no card showing %s." % self.card.value

    def suggest_correction(self) -> str:
        return (
            "Add a QueryCard for it to QueryCardSet.for_the_paper, which is where the "
            "queries the paper shows are listed."
        )


@dataclass
class EpisodeKeptNoWorldError(DataclassException):
    """
    Raised when a card is asked to draw a scene of an episode that kept no world.
    """

    episode_identifier: str
    """
    The episode that was asked.
    """

    def error_message(self) -> str:
        return "Episode %s kept no world, so its scene cannot be drawn." % (
            self.episode_identifier
        )

    def suggest_correction(self) -> str:
        return (
            "A run keeps its world as it records, so an episode recorded before the run "
            "was asked for one has rows but nothing to draw. Record the episode again, "
            "or write only the cards whose panels do not show the twin."
        )


@dataclass
class RobotNotFoundInTheWorldError(DataclassException):
    """
    Raised when a card asks a world which robot ran in it and it holds other than one.
    """

    found: int
    """
    How many robots it holds.
    """

    def error_message(self) -> str:
        return "The world holds %d robots, not one." % self.found

    def suggest_correction(self) -> str:
        return (
            "A question about the robot's own body is about one robot, so the world it "
            "is asked of has to say which. Record the episode with the robot its "
            "scenario builds."
        )


# %% one card


@dataclass
class QueryCard(ABC):
    """
    One query of the paper, drawn as the panels that say what its answer means.

    A card is a question rather than one asking of it: a trial asks the same question as
    often as its scenario says, and each asking is drawn as a card of its own.
    """

    name: ClassVar[QueryCardName]
    """
    Which card of the paper this is.
    """

    question: ClassVar[Type[Question]]
    """
    The question of the frozen set this card shows the answer to.
    """

    panels: ClassVar[Tuple[PanelKind, ...]]
    """
    The pictures this card is made of, in the order they are shown.
    """

    caption: ClassVar[str]
    """
    What the card shows, as the paper's reader is told it.
    """

    layered: ClassVar[bool] = False
    """
    Whether this card's pictures are shown as one stacked figure rather than as one
    figure each.

    A card whose pictures are read *against* each other -- an event over the plan that
    was running when it happened -- only reads that way if they are one picture, since
    separate figures float apart on a page. A card whose pictures each stand on their own
    is better off as separate figures the layout can place where they fit.
    """

    labels_the_answers: ClassVar[bool] = True
    """
    Whether each thing picked out of the scene is written over with its own name.

    A card whose answer is a handful of named objects reads better for it; one whose
    answer is a whole robot does not, since the names of a dozen links written over each
    other say less than the shape they are drawn on.
    """

    identity: ClassVar[ObjectIdentity] = SameName()
    """
    How a body an item of the plan acts on is told to be the body an event is about.
    """

    title: ClassVar[str] = "%s  %s"
    """
    What is written across the head of this card's stacked figure, given the query as
    it was asked and what it answered.
    """

    subtitle: ClassVar[str] = "%s, trial %d of episode %s"
    """
    What is written under the head naming the run, given the scenario, the trial's
    number and the episode.
    """

    perturbed: ClassVar[str] = "%s, perturbed by %s"
    """
    What the run's line says instead where the run was perturbed, given the line and
    the perturbations' names.
    """

    @abstractmethod
    def answers(self, asked: Question, world: World) -> List[KinematicStructureEntity]:
        """
        The things in the twin this question's answer points at, which the scene picks
        out.

        :param asked: The question as it was asked, which is what names the things a
            question about particular objects is about.
        :param world: The twin the run happened in.
        """

    def emphasise(self, asked: Question, trial: RecordedTrial) -> List[DetectionEvent]:
        """
        The events of the trial this question's answer is about, whose rows the timeline
        picks out. None, for a question that is not about anything that happened.

        :param asked: The question as it was asked.
        :param trial: The trial it was asked during.
        """
        return []

    def point_of_view(self, asked: Question, world: World) -> Optional[MujocoCamera]:
        """
        The camera this card's scene is drawn through, or None to frame the whole scene
        from the overview viewpoint.

        :param asked: The question as it was asked.
        :param world: The twin the run happened in.
        """
        return None

    # %% what a card reaches for in the trial it is given

    def queries_in(self, trial: RecordedTrial) -> List[RecordedQuery]:
        """
        Every query of the trial this card shows, in the order they were asked.

        :param trial: The trial to read.
        """
        return [
            query
            for query in trial.queries
            if isinstance(query.question, self.question)
        ]

    @staticmethod
    def robot_of(world: World) -> AbstractRobot:
        """
        The robot the run's world holds.

        :param world: The twin the run happened in.
        :raises RobotNotFoundInTheWorldError: If it holds other than one robot.
        """
        robots = world.get_semantic_annotations_by_type(AbstractRobot)
        if len(robots) != 1:
            raise RobotNotFoundInTheWorldError(found=len(robots))
        return robots[0]

    @staticmethod
    def world_of(trial: RecordedTrial) -> World:
        """
        The twin the run happened in.

        :param trial: The trial whose episode's world is read.
        :raises EpisodeKeptNoWorldError: If the episode kept no world.
        """
        if trial.episode.world is None:
            raise EpisodeKeptNoWorldError(episode_identifier=trial.episode.identifier)
        return trial.episode.world

    # %% what this card's files are called

    def stem(self, number: int) -> str:
        """
        What one asking of this card's question has its files named after.

        :param number: Which asking of it this is, counting from one.
        """
        return "%s_%02d" % (self.name.value, number)

    def panel_file_name(self, number: int, panel: PanelKind) -> str:
        """
        What one picture of this card is called.

        :param number: Which asking of this card's question it belongs to.
        :param panel: Which picture of the card it is.
        """
        return "%s_%s%s" % (self.stem(number), panel.value, FigureFile.IMAGE.value)

    def layered_file_name(self, number: int) -> str:
        """
        What this card's stacked picture is called.

        :param number: Which asking of this card's question it shows.
        """
        return "%s_%s%s" % (
            self.stem(number),
            CardFile.LAYERED.value,
            FigureFile.IMAGE.value,
        )

    def markup_file_name(self, number: int) -> str:
        """
        What this card's markup is called.

        :param number: Which asking of this card's question it shows.
        """
        return "%s%s" % (self.stem(number), FigureFile.TYPST_TABLE.value)

    # %% writing it out

    def write(
        self,
        trial: RecordedTrial,
        output_directory: Path,
        artifacts: Optional[EpisodeArtifacts] = None,
    ) -> List[WrittenQueryCard]:
        """
        Leave one card per asking of this card's question in the given directory.

        :param trial: The trial the queries were asked during.
        :param output_directory: Where the files go, created if it is not there.
        :param artifacts: The episode's own files, where a run on the robot kept the
            recording its camera panel is read from. Without them the card is drawn
            without that panel.
        :return: Where each card was left, in the order they were written.
        """
        output_directory.mkdir(parents=True, exist_ok=True)
        return [
            self._written(trial, query, number, output_directory, artifacts)
            for number, query in enumerate(self.queries_in(trial), start=1)
        ]

    def _written(
        self,
        trial: RecordedTrial,
        query: RecordedQuery,
        number: int,
        output_directory: Path,
        artifacts: Optional[EpisodeArtifacts],
    ) -> WrittenQueryCard:
        """
        Draw and leave one card, for one asking of this card's question.

        :param trial: The trial the query was asked during.
        :param query: The query this card shows.
        :param number: Which asking of this card's question it is, counting from one.
        :param output_directory: Where the files go.
        :param artifacts: The episode's own files, or None.
        """
        panel_paths = {
            panel: drawn.write(output_directory / self.panel_file_name(number, panel))
            for panel, drawn in self._panels(trial, query, artifacts).items()
        }
        layered_path = self._layered(
            number, output_directory, panel_paths, query, trial
        )
        markup_path = output_directory / self.markup_file_name(number)
        markup_path.write_text(
            self._markup(query, self._figures(panel_paths, layered_path))
        )
        return WrittenQueryCard(
            card=self.name,
            query=query,
            markup_path=markup_path,
            panel_paths=panel_paths,
            layered_path=layered_path,
        )

    def _layered(
        self,
        number: int,
        output_directory: Path,
        panel_paths: Dict[PanelKind, Path],
        query: RecordedQuery,
        trial: RecordedTrial,
    ) -> Optional[Path]:
        """
        This card's pictures stacked into one under the query and its answer, or None
        for a card that shows each of them as a figure of its own.

        Every picture the card declares keeps its place, drawn or not: a reader shown
        two of three levels cannot tell whether the third was left out or never
        existed.

        :param number: Which asking of this card's question it shows.
        :param output_directory: Where the file goes.
        :param panel_paths: Where each of the card's pictures was left.
        :param query: The query the figure shows, written across its head.
        :param trial: The trial it is drawn from, named under the head.
        """
        if not self.layered:
            return None
        return LayeredFigure().write(
            [
                Layer(
                    name=panel.level,
                    picture=panel_paths.get(panel),
                    note=panel.when_missing,
                )
                for panel in self.panels
            ],
            output_directory / self.layered_file_name(number),
            title=self.title % (query.text, query.answer),
            subtitle=self.run_line(trial),
        )

    def run_line(self, trial: RecordedTrial) -> str:
        """
        The line naming the run a card is drawn from: its scenario, its trial and its
        episode, and what perturbed it if anything did.

        :param trial: The trial the card is drawn from.
        """
        line = self.subtitle % (
            trial.episode.scenario_name,
            trial.number,
            trial.episode.identifier[:EPISODE_IDENTIFIER_SHOWN],
        )
        if not trial.episode.perturbation_names:
            return line
        return self.perturbed % (line, ", ".join(trial.episode.perturbation_names))

    def _figures(
        self, panel_paths: Dict[PanelKind, Path], layered_path: Optional[Path]
    ) -> List[Tuple[str, Path]]:
        """
        What the paper is given for this card: one figure of the levels stacked, or one
        figure per picture.

        :param panel_paths: Where each of the card's pictures was left.
        :param layered_path: Where its stacked picture was left, or None.
        """
        if layered_path is not None:
            return [(self.caption, layered_path)]
        return [
            ("%s %s" % (self.caption, panel.caption), path)
            for panel, path in panel_paths.items()
        ]

    def _panels(
        self,
        trial: RecordedTrial,
        query: RecordedQuery,
        artifacts: Optional[EpisodeArtifacts],
    ) -> Dict[PanelKind, CardPanel]:
        """
        Draw every picture of this card that there is something to draw it from.

        :param trial: The trial the query was asked during.
        :param query: The query this card shows.
        :param artifacts: The episode's own files, or None.
        """
        drawn = {
            panel: self._drawn(panel, trial, query, artifacts) for panel in self.panels
        }
        return {
            panel: picture for panel, picture in drawn.items() if picture is not None
        }

    def _drawn(
        self,
        panel: PanelKind,
        trial: RecordedTrial,
        query: RecordedQuery,
        artifacts: Optional[EpisodeArtifacts],
    ) -> Optional[CardPanel]:
        """
        One picture of this card, or None where the run left nothing to draw it from.

        :param panel: Which picture of the card to draw.
        :param trial: The trial the query was asked during.
        :param query: The query this card shows.
        :param artifacts: The episode's own files, or None.
        """
        if panel is PanelKind.SCENE:
            return self._scene(query.question, trial)
        if panel is PanelKind.TIMELINE:
            return self._event_chart(trial, query)
        if panel is PanelKind.PLAN_TIMELINE:
            return self._plan_chart(trial, query)
        if panel is PanelKind.RUN_TIMELINE:
            return self._run_timeline(trial, query)
        if panel is PanelKind.POSE_CHANGE:
            return self._pose_change(trial, query, artifacts)
        if panel is PanelKind.CAMERA_FRAME:
            return self._camera_frame(trial, query, artifacts)
        return self._camera_frames_around(trial, query, artifacts)

    def _event_chart(self, trial: RecordedTrial, query: RecordedQuery) -> CardPanel:
        """
        When each kind of event was reported, with this query's own moment marked.

        :param trial: The trial the query was asked during.
        :param query: The query this card shows.
        """
        return EventTimeline().of(
            trial,
            mark=query.moment,
            emphasise=self.emphasise(query.question, trial),
        )

    def _plan_chart(
        self, trial: RecordedTrial, query: RecordedQuery
    ) -> Optional[CardPanel]:
        """
        What the robot was running, with the item accounting for the answered event
        picked out. None where the run recorded no plan.

        :param trial: The trial the query was asked during.
        :param query: The query this card shows.
        """
        if not plans_of(trial):
            return None
        return PlanTimeline().of(
            trial,
            mark=query.moment,
            emphasise=self.emphasise(query.question, trial),
            identity=self.identity,
        )

    def _run_timeline(
        self, trial: RecordedTrial, query: RecordedQuery
    ) -> Optional[CardPanel]:
        """
        What the monitor reported over what the robot was running, on one axis, with
        the answered event and the query's own moment marked. None where the run
        reported nothing and recorded no plan.

        :param trial: The trial the query was asked during.
        :param query: The query this card shows.
        """
        if not trial.ticks and not plans_of(trial):
            return None
        answered = self.emphasise(query.question, trial)
        happened_at = (
            self.reported_at(answered[0], trial, query.moment) if answered else None
        )
        return RunTimeline().of(
            trial,
            asked_at=query.moment,
            emphasise=answered,
            happened_at=happened_at,
            pictured_at=() if happened_at is None else self.pictured_at(happened_at),
            identity=self.identity,
        )

    @staticmethod
    def pictured_at(happened_at: float) -> Tuple[float, float]:
        """
        The instants the levels under the charts show, either side of the event: the
        camera frames, and the object's earlier and later pose.

        :param happened_at: Seconds into the trial the event was reported.
        """
        return (happened_at - EITHER_SIDE, happened_at + EITHER_SIDE)

    def _pose_change(
        self,
        trial: RecordedTrial,
        query: RecordedQuery,
        artifacts: Optional[EpisodeArtifacts],
    ) -> Optional[CardPanel]:
        """
        The object drawn where it was and where it ended up, with the robot as it stood
        when the event was reported wherever the run traced its joints. None where the
        run saw the object move at no point, or where the twin holds it fixed.

        :param trial: The trial the query was asked during.
        :param query: The query this card shows.
        :param artifacts: The episode's own files, or None.
        """
        answered = self.emphasise(query.question, trial)
        if not answered:
            return None
        change = PoseChange.around(answered[0], trial)
        if change is None:
            return None
        world = self.world_of(trial)
        subject = world.get_body_by_name(change.subject.name.name)
        if not can_be_stood_somewhere_else(subject.parent_connection):
            return None
        happened_at = self.reported_at(answered[0], trial, query.moment)
        trace = self._trace_of(trial, artifacts)
        change = PoseChange(subject=subject, before=change.before, after=change.after)
        if trace is not None:
            change = change.with_the_way(
                self._way_of(subject, world, trace, self.pictured_at(happened_at))
            )
        return PoseChangeRender(world=world).of(
            change,
            robot_at=None if trace is None else trace.at(happened_at),
            among=self.scene_around(subject, world),
        )

    @staticmethod
    def _trace_of(
        trial: RecordedTrial, artifacts: Optional[EpisodeArtifacts]
    ) -> Optional[JointTrace]:
        """
        The trace of where every joint stood along the trial, or None where the run
        kept none.

        :param trial: The trial to read.
        :param artifacts: The episode's own files, or None.
        """
        if artifacts is None:
            return None
        kept = artifacts.trial(trial.number)
        if not kept.kept_a_joint_trace:
            return None
        return kept.joint_trace

    @staticmethod
    def _way_of(
        subject: Body,
        world: World,
        trace: JointTrace,
        between: Tuple[float, float],
        dots: int = WAYPOINTS,
    ) -> List[HomogeneousTransformationMatrix]:
        """
        Where the object stood along its way, read off the trace between two instants.

        The world is stood at each sample and read, then put back as it was. An object
        the trace does not hold -- one the world holds fixed -- gives an empty way, and
        the picture falls back on the straight line.

        :param subject: The object.
        :param world: The twin it stands in.
        :param trace: Where every joint stood along the trial.
        :param between: The instants the way runs between, in seconds into the trial.
        :param dots: How many places along the way at most.
        """
        held_by = str(subject.parent_connection.name)
        if not any(name.startswith(held_by) for name in trace.names):
            return []
        stood = JointPositions(
            moment=0.0,
            positions={
                str(name): position
                for name, position in world.state.to_position_dict().items()
            },
        )
        way = []
        try:
            for moment in np.linspace(between[0], between[1], dots + 2)[1:-1]:
                trace.at(float(moment)).restore_into(world)
                way.append(standing_pose(world, subject))
        finally:
            stood.restore_into(world)
        return way

    @staticmethod
    def scene_around(
        subject: Body, world: World
    ) -> Tuple[KinematicStructureEntity, ...]:
        """
        What the picture of an object's move is framed on besides the object: the
        boards and every other piece of the scene, so the move is seen with the table
        it happened on rather than alone.

        :param subject: The object that moved.
        :param world: The twin it stands in.
        """
        boards = [
            board.root
            for board in world.get_semantic_annotations_by_type(ShapeSortingBoard)
        ]
        pieces = [
            shape.root
            for shape in world.get_semantic_annotations_by_type(MontessoriShape)
            if shape.root is not subject
        ]
        return tuple(boards + pieces)

    def _camera_frame(
        self,
        trial: RecordedTrial,
        query: RecordedQuery,
        artifacts: Optional[EpisodeArtifacts],
    ) -> Optional[CardPanel]:
        """
        What the robot's camera saw at the moment the query was asked. None where the run
        recorded none.

        :param trial: The trial the query was asked during.
        :param query: The query this card shows.
        :param artifacts: The episode's own files, or None.
        """
        if artifacts is None:
            return None
        frame = BagFrameAt(
            artifacts=artifacts, moment=query.moment, trial_duration=trial.duration
        )
        return frame if frame.was_recorded else None

    def _camera_frames_around(
        self,
        trial: RecordedTrial,
        query: RecordedQuery,
        artifacts: Optional[EpisodeArtifacts],
    ) -> Optional[CardPanel]:
        """
        What the robot's camera saw either side of the answered event.

        A run on the robot kept a bag, so the two frames are read back out of it; a run
        that kept what its camera saw along the trial, with the moments, is read the
        same way. None where the run answered no event to take the frames around, or
        kept no camera at all.

        :param trial: The trial the query was asked during.
        :param query: The query this card shows.
        :param artifacts: The episode's own files, or None.
        """
        answered = self.emphasise(query.question, trial)
        if not answered or artifacts is None:
            return None
        moment = self.reported_at(answered[0], trial, query.moment)
        bagged = BagFramesAround(
            artifacts=artifacts, moment=moment, trial_duration=trial.duration
        )
        if bagged.was_recorded:
            return bagged
        kept = artifacts.trial(trial.number)
        if not kept.kept_a_camera:
            return None
        return RecordedFramesAround(frames=kept.camera, moment=moment)

    @staticmethod
    def reported_at(
        event: DetectionEvent, trial: RecordedTrial, otherwise: float
    ) -> float:
        """
        How far into the trial the monitor first reported the given event.

        :param event: The event to place.
        :param trial: The trial it was reported in.
        :param otherwise: What to answer where no tick reported it.
        """
        for tick in trial.ticks:
            if any(reported is event for reported in tick.events):
                return tick.moment
        return otherwise

    def _scene(self, asked: Question, trial: RecordedTrial) -> CardPanel:
        """
        The twin with the things this question's answer names picked out of it.

        :param asked: The question as it was asked.
        :param trial: The trial it was asked during.
        :raises EpisodeKeptNoWorldError: If the episode kept no world.
        """
        world = self.world_of(trial)
        camera = self.point_of_view(asked, world)
        try:
            return SceneRender(
                world=world, camera=camera, label_answers=self.labels_the_answers
            ).of(self.answers(asked, world))
        finally:
            if camera is not None:
                camera.body.simulator_additional_properties.remove(camera)

    @staticmethod
    def _markup(query: RecordedQuery, figures: List[Tuple[str, Path]]) -> str:
        """
        This card as the Typst the paper includes: what was asked, what was answered, and
        every figure of it.

        :param query: The query this card shows.
        :param figures: What each figure shows and where it was left.
        """
        lines = ["== %s" % query.text, "", "#emph[%s]" % query.answer, ""]
        for caption, path in figures:
            lines.append(TypstRenderer.render_image_figure(caption, path.name))
            lines.append("")
        return "\n".join(lines)


# %% the cards the paper shows


@dataclass
class ObjectsSeenCard(QueryCard):
    """
    What the robot answers it can see, drawn as those objects picked out of the scene.
    """

    name: ClassVar[QueryCardName] = QueryCardName.OBJECTS_SEEN
    question: ClassVar[Type[Question]] = ObjectsSeen
    panels: ClassVar[Tuple[PanelKind, ...]] = (
        PanelKind.SCENE,
        PanelKind.TIMELINE,
        PanelKind.CAMERA_FRAME,
    )
    caption: ClassVar[str] = "The objects the robot answers it sees:"

    def answers(self, asked: Question, world: World) -> List[KinematicStructureEntity]:
        """
        Every object of the scene, read off the twin the same way the question's own
        ground truth is.

        :param asked: The question as it was asked.
        :param world: The twin the run happened in.
        """
        return list(asked.ground_truth(self.robot_of(world)))


@dataclass
class SideOfAnotherObjectCard(QueryCard):
    """
    Whether one object is to a side of another, drawn from the place it was asked from.
    """

    name: ClassVar[QueryCardName] = QueryCardName.SIDE_OF_ANOTHER_OBJECT
    question: ClassVar[Type[Question]] = SideOfAnotherObject
    panels: ClassVar[Tuple[PanelKind, ...]] = (
        PanelKind.SCENE,
        PanelKind.CAMERA_FRAME,
    )
    caption: ClassVar[str] = "The two objects a spatial question relates:"

    def answers(
        self, asked: SideOfAnotherObject, world: World
    ) -> List[KinematicStructureEntity]:
        """
        The two objects the question relates, since what its yes or no means is where
        they stand relative to each other.

        :param asked: The question as it was asked.
        :param world: The twin the run happened in.
        """
        return [asked.subject, asked.other]

    def point_of_view(
        self, asked: SideOfAnotherObject, world: World
    ) -> Optional[MujocoCamera]:
        """
        The place the question was asked from, which is what makes its left and right
        mean anything.

        :param asked: The question as it was asked.
        :param world: The twin the run happened in.
        """
        return PointOfView(body=world.root, pose=asked.point_of_view).camera()


@dataclass
class PickedUpRecentlyCard(QueryCard):
    """
    Whether an object was picked up, drawn beside the pick-ups the monitor reported.
    """

    name: ClassVar[QueryCardName] = QueryCardName.PICKED_UP_RECENTLY
    question: ClassVar[Type[Question]] = PickedUpRecently
    panels: ClassVar[Tuple[PanelKind, ...]] = (
        PanelKind.SCENE,
        PanelKind.TIMELINE,
        PanelKind.CAMERA_FRAME,
    )
    caption: ClassVar[str] = "The object a question about what happened is about:"

    def answers(
        self, asked: PickedUpRecently, world: World
    ) -> List[KinematicStructureEntity]:
        """
        The object the question is about.

        :param asked: The question as it was asked.
        :param world: The twin the run happened in.
        """
        return [asked.subject]

    def emphasise(
        self, asked: PickedUpRecently, trial: RecordedTrial
    ) -> List[DetectionEvent]:
        """
        The pick-ups of that object the monitor reported.

        Matched by the name the twin gives the object rather than by identity, because a
        recalled episode's question and its events are read back as separate objects.

        :param asked: The question as it was asked.
        :param trial: The trial it was asked during.
        """
        return [
            event
            for tick in trial.ticks
            for event in tick.events
            if isinstance(event, PickUpEvent)
            and event.tracked_object.name == asked.subject.name
        ]


@dataclass
class OwnDegreesOfFreedomCard(QueryCard):
    """
    How many joints the robot answers it has, drawn as its own body picked out of the
    scene.
    """

    name: ClassVar[QueryCardName] = QueryCardName.OWN_DEGREES_OF_FREEDOM
    question: ClassVar[Type[Question]] = NumberOfOwnDegreesOfFreedom
    panels: ClassVar[Tuple[PanelKind, ...]] = (PanelKind.SCENE,)
    caption: ClassVar[str] = "The body a question about the robot itself counts:"
    labels_the_answers: ClassVar[bool] = False

    def answers(self, asked: Question, world: World) -> List[KinematicStructureEntity]:
        """
        Every link the robot is made of, since the joints it counts are what hold them
        together.

        :param asked: The question as it was asked.
        :param world: The twin the run happened in.
        """
        return list(self.robot_of(world).bodies)


@dataclass
class EventAgainstThePlanCard(QueryCard):
    """
    What the robot saw happen to an object, set against what it was running at the time.

    The card that says why the answer is what it is rather than only what it is. The
    levels read one under the other: the event the monitor reported over the item of
    the plan that accounts for it, on one time axis; what the camera saw either side of
    it; and where the object went, with the robot as it stood at the time. A pick-up the
    robot performed has an item of the plan standing under it and the piece ends up in
    the gripper; a piece a person shoved has a translation under an empty stretch of
    plan, which is the picture of an answer of no.
    """

    name: ClassVar[QueryCardName] = QueryCardName.EVENT_AGAINST_THE_PLAN
    question: ClassVar[Type[Question]] = PickedUpRecently
    panels: ClassVar[Tuple[PanelKind, ...]] = (
        PanelKind.RUN_TIMELINE,
        PanelKind.CAMERA_BEFORE_AND_AFTER,
        PanelKind.POSE_CHANGE,
    )
    caption: ClassVar[str] = "What the run saw happen to the object:"
    layered: ClassVar[bool] = True
    identity: ClassVar[ObjectIdentity] = SamePiece()

    def answers(
        self, asked: PickedUpRecently, world: World
    ) -> List[KinematicStructureEntity]:
        """
        The object the question is about.

        :param asked: The question as it was asked.
        :param world: The twin the run happened in.
        """
        return [asked.subject]

    def emphasise(
        self, asked: PickedUpRecently, trial: RecordedTrial
    ) -> List[DetectionEvent]:
        """
        What the run saw happen to that object, which is what the four levels are read
        against.

        An agency question is about what was done to the object, so what the robot did to
        it is what the card shows where the run saw any of it. Where it saw none, what is
        left is the object moving on its own -- which is exactly the case the answer is no
        in, and the case the card has to show for that answer to mean anything.

        Matched by the name the twin gives the object rather than by identity, because a
        recalled episode's question and its events are read back as separate objects.

        :param asked: The question as it was asked.
        :param trial: The trial it was asked during.
        """
        acted_on = self._reported_about(asked.subject, trial, AgentInteractionEvent)
        return (
            acted_on
            if acted_on
            else self._reported_about(asked.subject, trial, MotionEvent)
        )

    @staticmethod
    def _reported_about(
        subject: KinematicStructureEntity,
        trial: RecordedTrial,
        kind: Type[DetectionEvent],
    ) -> List[DetectionEvent]:
        """
        Every event of the given kind the run reported about the given object, in the
        order they were reported.

        :param subject: The object the events are about.
        :param trial: The trial to read.
        :param kind: The kind of event wanted.
        """
        return [
            event
            for tick in trial.ticks
            for event in tick.events
            if isinstance(event, kind) and event.tracked_object.name == subject.name
        ]


# %% every card the paper shows


@dataclass
class QueryCardSet:
    """
    Every query the paper shows a picture of, drawn together from one recorded trial.
    """

    cards: List[QueryCard] = field(default_factory=list)
    """
    The cards, in the order the script writes them.
    """

    @classmethod
    def for_the_paper(cls) -> QueryCardSet:
        """
        The set the paper's own figures are drawn from.
        """
        return cls(
            cards=[
                ObjectsSeenCard(),
                SideOfAnotherObjectCard(),
                PickedUpRecentlyCard(),
                OwnDegreesOfFreedomCard(),
                EventAgainstThePlanCard(),
            ]
        )

    def card_named(self, card: QueryCardName) -> QueryCard:
        """
        The one card of this set showing the given query.

        :param card: The card wanted.
        :raises UnknownQueryCardError: If the set holds no card showing it.
        """
        for held in self.cards:
            if held.name is card:
                return held
        raise UnknownQueryCardError(card=card)

    def write(
        self,
        trial: RecordedTrial,
        output_directory: Path,
        artifacts: Optional[EpisodeArtifacts] = None,
    ) -> List[WrittenQueryCard]:
        """
        Leave every card of the paper the given trial asked a query for.

        :param trial: The trial the queries were asked during.
        :param output_directory: Where the files go, created if it is not there.
        :param artifacts: The episode's own files, where a run on the robot kept the
            recording its camera panels are read from.
        :return: Where each card was left, in the order they were written.
        """
        return [
            written
            for card in self.cards
            for written in card.write(trial, output_directory, artifacts)
        ]

    def write_every_episode(
        self,
        trials: Sequence[RecordedTrial],
        output_directory: Path,
        artifacts: Optional[ArtifactDirectory] = None,
    ) -> List[WrittenQueryCard]:
        """
        Leave the cards of every episode the given trials belong to.

        Each episode is given a directory named after its identifier and each of its
        trials one inside that, so a corpus of runs is written in one pass without any of
        them writing over another.

        :param trials: The trials to draw, of however many episodes.
        :param output_directory: Where the episodes' directories go, created if they are
            not there.
        :param artifacts: Where every episode's own files are kept, which is where a run
            on the robot left the recording its camera panels are read from.
        :return: Where each card was left, in the order they were written.
        """
        written: List[WrittenQueryCard] = []
        for recorded in self._by_episode(trials):
            episode = recorded[0].episode
            episode_directory = output_directory / episode.identifier
            for trial in recorded:
                written.extend(
                    self.write(
                        trial,
                        episode_directory / (TRIAL_DIRECTORY % trial.number),
                        None if artifacts is None else artifacts.open_for(episode),
                    )
                )
        return written

    @staticmethod
    def _by_episode(
        trials: Sequence[RecordedTrial],
    ) -> List[List[RecordedTrial]]:
        """
        The given trials gathered into the episode each belongs to, in the order the
        episodes were first seen and each episode's trials in the order they were given.

        :param trials: The trials to gather.
        """
        episodes: Dict[str, List[RecordedTrial]] = {}
        for trial in trials:
            episodes.setdefault(trial.episode.identifier, []).append(trial)
        return list(episodes.values())
