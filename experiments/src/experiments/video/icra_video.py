"""
The supplementary video, cut from the framework demo the robot recorded and the
perturbation episodes, and written out within the conference's limits.

Usage:

    python -m experiments.video.icra_video --output <video.mp4>
        [--voice af_heart] [--speech-speed 1.15] [--subtitles burned-in|soft] [--preview]

The narration is spoken by the Kokoro model on this machine (``--voice`` picks any of
its voices) and goes into the mp4 with its captions burned into the picture; with
``--subtitles soft`` they go in as a track the viewer can switch off instead, and are
written next to the mp4 as a SubRip file too.

Needs the results database and the episode artifacts the reproduction package restores
(``MONTESSORI_SORTING_DATABASE_URI``, ``EPISODE_ARTIFACTS_DIRECTORY``). What takes a
while to compute is kept under ``EXPERIMENTS_VIDEO_CACHE`` between runs.
"""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass, field, replace
from enum import StrEnum
from functools import cached_property
from pathlib import Path

from typing_extensions import Dict, List, Optional, Sequence, Tuple

from experiments.montessori.semantics import MontessoriShape, MontessoriShapeCategory
from experiments.video.attribution import (
    AttributionScene,
    MovedQuestions,
    TrialTimelines,
)
from experiments.video.canvas import Ink
from experiments.video.encoding import (
    H264Encoder,
    Muxer,
    SubmissionLimits,
    VideoFile,
    bytes_for_sound,
)
from experiments.video.figure import FigureBox, FigureGeometry, FrameworkFigure, GraspChartBar, PlanAction, RunReadings, Slot
from experiments.video.footage import (
    FULL_BLEED_FRAMING,
    TABLE_FRAMING,
    CameraFilm,
    FullBleedFootage,
    HandHeldFilm,
    HeldInset,
    TitleOverFootage,
    ViewOfTheRun,
)
from experiments.video.grasp import GraspDistribution, GraspSampling
from experiments.video.long_term import RememberedPiece
from experiments.video.narration import (
    LEAD,
    KokoroVoice,
    Line,
    NarratedScene,
    Narration,
    Storyboard,
    Subtitled,
    Voice,
    starts_of,
)
from experiments.video.perception import NarrowingReel, PerceptionNarrowing
from experiments.video.perturbations import (
    ZOOM,
    DetectionsOnTheFilm,
    GridLabels,
    GridSequence,
    IdleStretches,
    PerturbationTile,
    Zoom,
)
from experiments.video.rules import HoleOnThePicture, HoleRuleTrace, RuleTreeEvaluation
from experiments.video.script import NarrationLines, VideoScript
from experiments.video.slides import EndCard, ResultsTable
from experiments.video.sources import FRAMEWORK_DEMO_EPISODE, RecordedRun
from experiments.video.stages import Answering, FigureOnCanvas, Magnified, Mark, Pointer
from experiments.video.timeline import Scene, Timeline
from experiments.video.twin import TwinPictures, WorkingMemoryCheck
from experiments.episodes.long_term_memory import LongTermMemory

logger = logging.getLogger(__name__)

PERTURBATION_EPISODES = (
    ("508e367a6fd04cc2ba657f991e3f4bd9", "0a793ded6dd54da7b64171ab78638d38", "57bbcbb2c919404e9cd729d7e766bf66"),
    ("25f5161da5584bac9554b686711a01fe", "e9b1eef3d2f34a57a95e2b897ec63cdd", "25ccb55ba8ab4d90aabe54c5800cedb8"),
)
"""
The perturbation episodes, row by row as the grid shows them: the scene standing still
and the robot sorting, each unperturbed, with a piece shoved and with the board moved.
"""

PAPER_EPISODES = frozenset(episode for row in PERTURBATION_EPISODES for episode in row) | {FRAMEWORK_DEMO_EPISODE}
"""
The seven episodes recorded on the real robot that the paper's results are over: the
six of the grid, three of them holding three trials each, and the framework demo --
thirteen trials in seven episodes.
"""

ZOOMS = (
    # the scene stands still while the board is moved: from just before the person
    # takes hold of the board
    Zoom(row=0, column=2, replay_from=20.0, held_for=5.0),
    # the robot sorts after a piece is shoved: the shove, the robot looking again, and
    # the robot acting on what it then found
    Zoom(row=1, column=1, replay_from=8.0, held_for=6.5),
)
"""
The two tiles brought to the front of the grid, in order; each is held for as long as
the line said over it, at the least for this.
"""


@dataclass(frozen=True)
class AttributionRun:
    """
    One episode the questions about who moved what are shown being answered in.
    """

    episode: str
    """
    The episode's identifier.
    """

    speed: Optional[float]
    """
    How many recorded seconds pass per second played while the film runs; None for as
    slow as the lines said over the film before its questions need.
    """

    question_for: Optional[Tuple[float, ...]]
    """
    Seconds each question about the trial takes, one per question; None for as long
    as the line said over each needs.
    """


ATTRIBUTION_RUNS = (
    # the robot sorts the pieces it saw; the section's line is said over the film, and
    # the questions come up as it ends, each held for the line said over it
    AttributionRun("25f5161da5584bac9554b686711a01fe", None, None),
    # the scene stands still while a person pushes the cube; at this pace the hand
    # reaches in as the line reaches "a person pushes the cube"
    AttributionRun("0a793ded6dd54da7b64171ab78638d38", 5.0, (2.0, 2.5)),
)
"""
The two trials the paper sets against each other: the robot moving the pieces itself,
and a person moving one while the robot stands idle.
"""

DISSOLVE = 0.25
"""
Seconds each scene dissolves into the next, where it does not cut in.
"""

PAUSE = 0.25
"""
Seconds between two lines said over one scene.
"""

TAIL = 0.3
"""
Seconds a slide is held after its last line has ended.
"""

TITLE_FOR = 2.6
"""
Seconds the title stands over the footage before the summary is said under it.
"""

TITLE_FOOTAGE_FROM = 20.5
"""
Seconds into the hand-held film the title's footage starts: the gripper carrying the
cube over the board and putting it through the square hole.
"""

PLAN_SHARE = 0.96
"""
How much of the stage the whole plan takes while it is read: as tall as the stage
allows, so that all of it is in view while its parts are pointed to in turn.
"""

RESOLVED_SHARE = 0.96
"""
How much of the room the resolved plan takes, over its footnote.
"""

PICK_UP_NAMED_AT = 6.0
"""
Seconds into the line about the pick-up that "pick up" is said, after the pause that
follows "domain language:" -- measured on the spoken line; the pick-up action is
pointed to then. The insertion action is pointed to as the line about it starts.
"""

OPEN_PART_NAMED_AT: Dict[Slot, float] = {Slot.PERCEPTION: 1.8, Slot.PROBABILISTIC: 2.55, Slot.RULES: 3.45}
"""
Seconds into the line about the insertion that what each slot leaves open is named --
"The cube", "the approach direction", "and the hole" -- measured on the spoken line;
the part is pointed to and highlighted then.
"""

QUERY_HELD_AT_LEAST = 0.5
"""
Seconds a sub-query is held alone at the least, however short the line over it.
"""

PERCEIVED_FOR = 0.3
"""
Seconds the last view of the look stands before the perception backend's answer is
written in.
"""

BOXES_DRAWN_AT = (3.2, 4.0)
"""
Seconds into the line about the geometric check that "the cube's bottom" and "the
board's top" are said, when each box is drawn -- measured on the spoken line.
"""

BAND_DRAWN_AT = 4.35
"""
Seconds into that line that "confirms" starts, when the band where the boxes interfere
is drawn.
"""

VERDICT_AT = 4.9
"""
Seconds into that line that "confirms" has been said, when the result is given.
"""

SAMPLES_FROM = 3.8
"""
Seconds into the line about the model that "and samples from it" starts, when the
samples start arriving -- measured on the spoken line.
"""

SAMPLING_FOR = 1.0
"""
Seconds the probabilistic backend's samples take to arrive.
"""

ANSWER_SHOWN_FOR = 0.6
"""
Seconds a backend's answer stands out in its close-up at the least before it is
written into the sub-query.
"""

SELECTS_AT = 4.1
"""
Seconds into the line about the rules that "and selects the one" starts, when the rule
that fired is highlighted -- measured on the spoken line.
"""

ANSWER_SETTLE = 0.1
"""
Seconds a backend's close-up is held after its last line before the answer is written
into the sub-query.
"""

EXECUTION_STRETCH = (0.5, 30.5)
"""
The seconds of the hand-held film shown while the robot acts: from the arm setting off
for the cube to its withdrawing from the hole. Whoever stands at the back of the room
in the film's first seconds lies above the window the framing keeps.
"""

EXECUTION_SPEED = 1.5
"""
How many recorded seconds pass per second played while the robot acts: slow enough for
the grasp and the insertion to be seen as motion.
"""

EXECUTION_LINES_AT = (0.0, 8.25, 14.1, 18.3, 24.75)
"""
Seconds into the stretch of the film shown while the robot acts, as recorded, at which
each line said over it starts: as the robot sets off, as it closes on the cube, as it
lifts it, as the gripper reaches the hole, and as it withdraws.
"""

PERCEIVED_INSET_FOR = 3.0
"""
Seconds the robot's own view in the corner holds what the look found before it runs:
the look ran before the hand-held film starts.
"""

HAND_HELD_OFFSET = 15.5
"""
Seconds after the robot's own recording started that the hand-held film of the
framework demo started: read off both films at the moment the gripper is lowered
into the square hole.
"""

PUSHED_ANSWER_AT = 5.5
"""
Seconds into the second trial's scene, beyond the lead, that the line answering it
starts: as the first question's answer comes up; the first question is held for less
than the second so that "no action of the robot" falls with the second's answer.
"""

QUERY_NAMED_AT = 2.4
"""
Seconds into the line about long term memory that "the same kind of query" starts,
when its card comes up over the grid -- measured on the spoken line.
"""

ANSWER_READ_FOR = 1.5
"""
Seconds the answer to long term memory stands after its line ends.
"""

GRID_SPEED = 6.0
"""
How many recorded seconds pass per second played in the perturbation grid.
"""


IDLE_FRAMES_READ = 24
"""
How many of the recording's first frames, taken while the robot stood still, the look
is watched over.
"""

RESULTS_FOR = 4.0
"""
Seconds the results table is held at the least.
"""

END_CARD_FOR = 3.5
"""
Seconds the end card is held at the least.
"""

BACKENDS: Dict[Slot, str] = {
    Slot.PERCEPTION: "PerceptionBackend",
    Slot.SIMULATION: "WorkingMemory",
    Slot.PROBABILISTIC: "ProbabilisticBackend",
    Slot.RULES: "RippleDownRulesBackend",
}
"""
What each slot's backend is called, on its panel of the figure and on the tab over its
close-up.
"""

HUES: Dict[Slot, Ink] = {
    Slot.PERCEPTION: Ink.PERCEPTION,
    Slot.SIMULATION: Ink.SIMULATION,
    Slot.PROBABILISTIC: Ink.PROBABILISTIC,
    Slot.RULES: Ink.RULES,
}
"""
The colour each backend's close-up is framed in, the figure's own.
"""

ACCENT = Ink.ANSWER.rgb
"""
What a part of the plan is ringed in when it is pointed to, and what an answer written
into it is ringed in: the video's one accent.
"""


class Subtitling(StrEnum):
    """
    How the subtitles go into the video.
    """

    BURNED_IN = "burned-in"
    """
    Drawn into the picture, in the band every scene keeps clear: part of the video.
    """

    SOFT = "soft"
    """
    A text track the viewer can switch off, with the same cues as a SubRip file next to
    the mp4 for players that take one.
    """


# %% the video


@dataclass
class VideoAssembly:
    """
    Every scene of the video, built from the recorded runs, laid on one timeline.
    """

    script: VideoScript = field(default_factory=VideoScript)
    """
    The words the slides carry.
    """

    demo: RecordedRun = field(default_factory=lambda: RecordedRun(FRAMEWORK_DEMO_EPISODE))
    """
    The framework demo the robot recorded.
    """

    frames_per_second: int = 25
    """
    The rate the video plays at.
    """

    preview: bool = False
    """
    Whether to render a short rough version for looking at, with the close-ups cut
    down.
    """

    voice: Voice = field(default_factory=KokoroVoice)
    """
    What says the narration.
    """

    lines: NarrationLines = field(default_factory=NarrationLines)
    """
    What the narration says.
    """

    subtitling: Subtitling = Subtitling.BURNED_IN
    """
    How the subtitles go in.
    """

    @cached_property
    def cube(self) -> MontessoriShape:
        """
        The cube the look found, as the run's world holds it.
        """
        return next(
            shape
            for shape in self.demo.world.semantic_annotations
            if isinstance(shape, MontessoriShape)
            and shape.shape_category is MontessoriShapeCategory.CUBE
        )

    @cached_property
    def twin(self) -> TwinPictures:
        return TwinPictures(self.demo)

    @cached_property
    def sampling(self) -> GraspSampling:
        """
        The backend's sampling, under the registry the run used: every direction as
        likely as the next, and the direction the run went with as recorded.
        """
        return GraspSampling(answered=self.demo.recorded_grasp().approach_direction)

    @cached_property
    def rule_trace(self) -> HoleRuleTrace:
        return HoleRuleTrace(self.cube)

    @cached_property
    def readings(self) -> RunReadings:
        """
        What the run read, for the figure to show in place of its stand-ins.
        """
        at = self.twin.cube_at
        grasp = self.demo.recorded_grasp()
        return RunReadings(
            resolved_lines={
                Slot.PERCEPTION: ["cube_1  # CYAN, CUBE", f"  at ({at[0]:.2f}, {at[1]:.2f}, {at[2]:.2f}) m,"],
                Slot.PROBABILISTIC: [
                    "grasp_1 = GraspDescription(",
                    f"  {grasp.approach_direction.name}, {grasp.vertical_alignment.name},",
                    "  LEFT_HAND)",
                ],
                Slot.RULES: ["ShapeSortingHole(", f"  shape_category={self.rule_trace.concluded.name})"],
            },
            grasps=[
                GraspChartBar(direction.name, grasp.vertical_alignment.name, probability, chosen=direction is grasp.approach_direction)
                for direction, probability in self.sampling.probabilities.items()
            ],
            support_reading=self.twin.reading.reading_line,
            support_verdict=f"SupportedBy(cube_1, lid) → {self.twin.reading.holds}",
            # the plan as written, with each `...` replaced by what was read; a description
            # left open as a whole is replaced by what was found, and a relation checked
            # is ticked
            filled_values={
                Slot.PROBABILISTIC: grasp.approach_direction.name,
                Slot.RULES: self.rule_trace.concluded.name,
            },
            filled_lines={
                Slot.PERCEPTION: ["cube_1  # CYAN, CUBE", f"  at ({at[0]:.2f}, {at[1]:.2f}, {at[2]:.2f}) m,"],
                Slot.SIMULATION: [f"SupportedBy(shape, lid)),  {'✓' if self.twin.reading.holds else '✗'}"],
            },
        )

    # %% the backends completing the plan

    def figure(self, stage: int, focus: Optional[Slot] = None) -> FigureOnCanvas:
        """
        The framework figure at a stage, its panels named after the backends.

        :param stage: How many backends have answered.
        :param focus: The slot being answered, ringed, if any.
        """
        figure = FrameworkFigure(stage=stage, focus=focus, readings=self.readings, panel_titles=dict(BACKENDS))
        return FigureOnCanvas(figure)

    def title(self) -> NarratedScene:
        """
        The title over the footage of the insertion, unspoken; what the video shows is
        said over it.
        """
        by_hand = HandHeldFilm.beside(self.demo)
        summary_for = self.said_for(self.lines.summary) + TAIL
        footage = FullBleedFootage(
            ViewOfTheRun(by_hand, TITLE_FOOTAGE_FROM, FULL_BLEED_FRAMING),
            length=TITLE_FOR + summary_for,
            speed=1.0,
        )
        line = f"{self.script.kind}  ·  {self.script.conference}"
        titled = TitleOverFootage(footage, self.script.title, line, title_for=TITLE_FOR + summary_for)
        return NarratedScene(titled, (self.lines.summary,), delay=TITLE_FOR - LEAD)

    def plan_reading(self) -> NarratedScene:
        """
        The whole plan magnified out of the figure and read with an arrow: the pick-up
        and then the insertion pointed to as the lines describe them, then each part
        left open as it is named, highlighted as the arrow moves on.
        """
        shown = self.figure(0)
        geometry = shown.figure.geometry
        pick_up, insertion = geometry.actions[PlanAction.PICK_UP], geometry.actions[PlanAction.INSERTION]
        lines = (self.lines.plan_pick_up, self.lines.plan_insertion)
        pick_up_from, insertion_from = (LEAD + start for start in self.starts_of(lines))
        open_parts = {slot: insertion_from + named_at for slot, named_at in OPEN_PART_NAMED_AT.items()}
        # the storyboard grows the hold to the lines; the growing out is the settle after them
        magnified = Magnified(shown, self.whole_plan(geometry), Ink.TEXT.rgb, grow=0.6, shrink=0.4, share=PLAN_SHARE)
        magnified.pointers = (
            Pointer(pick_up, ACCENT, from_second=pick_up_from + PICK_UP_NAMED_AT),
            Pointer(insertion, ACCENT, from_second=insertion_from),
            *(Pointer(self.left_open(geometry, slot), ACCENT, from_second=named_at, framed=False) for slot, named_at in open_parts.items()),
        )
        magnified.marks = tuple(Mark(self.left_open(geometry, slot), ACCENT, from_second=named_at) for slot, named_at in open_parts.items())
        return NarratedScene(magnified, lines)

    def plan_resolved(self) -> NarratedScene:
        """
        The plan with every field answered, magnified out of the finished figure over
        the footnote on where its values come from.
        """
        shown = self.figure(len(Slot))
        magnified = Magnified(
            shown, self.whole_plan(shown.figure.geometry), Ink.TEXT.rgb, grow=0.6, shrink=0.0,
            share=RESOLVED_SHARE, footnote=self.script.run_values_note,
        )
        return NarratedScene(magnified, (self.lines.resolved,))

    @staticmethod
    def whole_plan(geometry: FigureGeometry) -> FigureBox:
        """
        The plan from the pick-up's first line to the insertion's last, in the figure's
        centimetres.
        """
        pick_up, insertion = geometry.actions[PlanAction.PICK_UP], geometry.actions[PlanAction.INSERTION]
        return FigureBox(geometry.plan.x, pick_up.y, geometry.plan.width, insertion.y + insertion.height - pick_up.y)

    @staticmethod
    def left_open(geometry: FigureGeometry, slot: Slot) -> FigureBox:
        """
        What the plan leaves open for a slot: the field written as ``...`` where there
        is one, else the whole description the slot answers.
        """
        return geometry.open_fields.get(slot, geometry.slots[slot])

    def backend_scenes(self) -> List[NarratedScene]:
        """
        Each backend answering its slot, in the order the plan is resolved.
        """
        return [self.backend_scene(slot) for slot in Slot]

    def backend_scene(self, slot: Slot) -> NarratedScene:
        """
        The backend answering its slot: the sub-query held beside the close-up of the
        backend's work, the answer written into it. The line about what is asked is
        said over the sub-query alone; the lines about how the backend answers start as
        its work does.
        """
        before, after = self.figure(slot.stage - 1, slot), self.figure(slot.stage)
        asked, told, work = self.work_of(slot)
        geometry = before.figure.geometry
        marks = (Mark(geometry.open_fields[slot], ACCENT),) if slot in geometry.open_fields else ()
        scene = Answering(before, after, slot, work, HUES[slot].rgb, title=BACKENDS[slot], marks=marks)
        scene.query_for = self.query_hold(asked, scene)
        return NarratedScene(scene, (asked, *told))

    def query_hold(self, asked: Line, scene: Answering) -> float:
        """
        Seconds the sub-query is held alone so that the work starts as the first line
        over it does: once the line about what is asked and the pause after it are over.

        :param asked: The line said over the sub-query.
        :param scene: The backend answering it.
        """
        said = self.said_for(asked)
        return max(LEAD + said + PAUSE - scene.grow - scene.close_up_grow, QUERY_HELD_AT_LEAST)

    def work_of(self, slot: Slot) -> Tuple[Line, Tuple[Line, ...], Scene]:
        """
        The line asking a backend's sub-query, the lines said over its work, and the
        work: what plays in the close-up, from the moment the first of those lines
        starts, and long enough to hold them.
        """
        lines = self.lines
        if slot is Slot.PERCEPTION:
            told = lines.perception_views
            reel = NarrowingReel(self.demo, frame_indices=list(range(IDLE_FRAMES_READ)))
            # each view comes up as its line starts
            starts = self.starts_of(told)
            scene = PerceptionNarrowing(reel, appears_at=tuple(starts), run_for=self.said_for(told[-1]) + PERCEIVED_FOR)
            return lines.perception_query, told, scene
        if slot is Slot.SIMULATION:
            told = (lines.working_memory,)
            scene = WorkingMemoryCheck(
                self.twin, held_for=self.said_for(told[0]) + ANSWER_SETTLE, boxes_at=BOXES_DRAWN_AT, band_at=BAND_DRAWN_AT, verdict_at=VERDICT_AT
            )
            return lines.working_memory_query, told, scene
        if slot is Slot.PROBABILISTIC:
            told = (lines.probabilistic,)
            answer_for = max(self.said_for(told[0]) + ANSWER_SETTLE - SAMPLES_FROM - SAMPLING_FOR, ANSWER_SHOWN_FOR)
            scene = GraspDistribution(self.sampling, statement_for=SAMPLES_FROM, sampling_for=SAMPLING_FOR, answer_for=answer_for)
            return lines.probabilistic_query, told, scene
        told = (lines.rules,)
        answer_for = max(self.said_for(told[0]) + ANSWER_SETTLE - SELECTS_AT, ANSWER_SHOWN_FOR)
        scene = RuleTreeEvaluation(self.rule_trace, HoleOnThePicture(self.demo), tree_for=SELECTS_AT, checking_for=0.0, answer_for=answer_for)
        return lines.rules_query, told, scene

    def perceived_picture(self):
        """
        What the robot's camera saw when the look found the cube, with the findings
        drawn on it: what the inset holds while the robot sets off.
        """
        detections = DetectionsOnTheFilm(self.demo, IdleStretches(self.demo))
        return TABLE_FRAMING.of(detections.picture_at(detections.drawn_at[0]))

    def execution(self) -> NarratedScene:
        """
        The robot carrying out the resolved plan, filmed by hand from beside the table
        and filling the frame, with its own camera in the corner; the lines said over
        it as what they name is seen.
        """
        start, end = EXECUTION_STRETCH
        speed = 8.0 if self.preview else EXECUTION_SPEED
        by_hand = HandHeldFilm.beside(self.demo)
        beside = ViewOfTheRun(by_hand, start, FULL_BLEED_FRAMING)
        own = ViewOfTheRun(CameraFilm(self.demo), start + HAND_HELD_OFFSET, TABLE_FRAMING)
        footage = FullBleedFootage(beside, length=end - start, speed=speed, inset=own, inset_held=HeldInset(self.perceived_picture(), PERCEIVED_INSET_FOR))
        lines = (
            self.lines.execution_perceived,
            self.lines.execution_grasp,
            self.lines.execution_carry,
            self.lines.execution_insertion,
            self.lines.execution_outcome,
        )
        played_at = tuple(recorded / speed for recorded in EXECUTION_LINES_AT)
        return NarratedScene(footage, lines, waits=self.waits_for(lines, played_at))

    def waits_for(self, lines: Sequence[Line], starts_at: Sequence[float]) -> Tuple[float, ...]:
        """
        The waits that start each line of a scene at a given moment beyond the lead,
        the lines said in turn with the pause between them.

        :param lines: The lines.
        :param starts_at: When each is to start, beyond the lead, the first's being
            when it starts anyway; a line whose moment the line before it runs past
            follows that one at once.
        """
        waits = []
        ends = starts_at[0] + self.said_for(lines[0])
        for line, wanted in zip(lines[1:], starts_at[1:]):
            start = max(wanted, ends + PAUSE)
            waits.append(start - (ends + PAUSE))
            ends = start + self.said_for(line)
        return tuple(waits)

    # %% the queries over events

    def attribution_scenes(self) -> List[NarratedScene]:
        """
        The questions about who moved what, answered in each of the two trials. The
        section's line is said over the first trial's film; the line on the event
        classes over its first question and the line on the answers over its second.
        The second trial's line is said while its film plays, and the line answering
        it as its first answer comes up.
        """
        sorting, pushed = ATTRIBUTION_RUNS
        lines = self.lines
        first_lines = (lines.attribution, lines.event_classes, lines.attribution_sorting)
        first = self.attribution_scene(sorting, *first_lines)
        second = self.attribution_scene(pushed, lines.attribution_pushed)
        first_at = (0.0, first.watching_for - LEAD, first.question_starts(1) - LEAD)
        second_lines = (lines.attribution_pushed, lines.attribution_pushed_answer)
        return [
            NarratedScene(first, first_lines, waits=self.waits_for(first_lines, first_at)),
            NarratedScene(second, second_lines, waits=self.waits_for(second_lines, (0.0, PUSHED_ANSWER_AT))),
        ]

    def attribution_scene(self, run: AttributionRun, watched: Line, *asked: Line) -> AttributionScene:
        """
        One trial's scene, its film played so that its questions come up as the line
        said over the film ends, where the run leaves the pace open, and each question
        held for the line said over it, where the run leaves that open.

        :param run: The trial.
        :param watched: The line said over the film before its questions.
        :param asked: The lines said over the questions, one each, where the run
            leaves how long they are held open.
        """
        timelines = TrialTimelines(RecordedRun(run.episode))
        questions = MovedQuestions(timelines).both()
        question_for = run.question_for
        if question_for is None:
            question_for = tuple(self.said_for(line) + PAUSE for line in asked)
        scene = AttributionScene(
            timelines,
            CameraFilm(timelines.run),
            questions,
            speed=1.0,
            question_for=tuple(2.0 for _ in questions) if self.preview else question_for,
        )
        speed = run.speed
        if speed is None:
            watched_for = LEAD + self.said_for(watched) + PAUSE
            speed = round(scene.horizon / watched_for)
        scene.speed = speed * (3.0 if self.preview else 1.0)
        return scene

    # %% the real robot

    def grid(self) -> NarratedScene:
        """
        The six episodes playing out, two brought to the front in turn, then long term
        memory asked which the robot picked the cube up in. The lines set the pace:
        each tile comes to the front as its line starts and goes back as the next
        starts, the grid plays on as the last line starts, the question comes up as
        that line names the query, and the answer as it ends.
        """
        # one recording kept no transforms; the camera stood the same way for every run that day
        tiles = [
            [PerturbationTile(RecordedRun(episode, camera_pose_from=self.demo.bag)) for episode in row]
            for row in PERTURBATION_EPISODES
        ]
        memory = LongTermMemory(self.demo.database)
        question = RememberedPiece(memory, over=PAPER_EPISODES).where_the_robot_picked_it_up()
        labels = GridLabels(header=self.script.grid_header, long_term_header=self.script.long_term_header)
        lines = (self.lines.grid, self.lines.stands_still, self.lines.shoved, self.lines.long_term_memory)
        plays, first, second, resumes = (LEAD + start for start in self.starts_of(lines))
        zooms = tuple(
            replace(zoom, held_for=max(zoom.held_for, next_at - at - 2 * ZOOM))
            for zoom, at, next_at in zip(ZOOMS, (first, second), (second, resumes))
        )
        said = self.said_for(self.lines.long_term_memory)
        scene = GridSequence(
            tiles,
            labels,
            zooms,
            question,
            speed=GRID_SPEED * (4.0 if self.preview else 1.0),
            play_for=first,
            asked_after=QUERY_NAMED_AT,
            question_for=said - QUERY_NAMED_AT + ANSWER_READ_FOR,
            answered_after=said - QUERY_NAMED_AT,
        )
        return NarratedScene(scene, lines)

    def results(self) -> NarratedScene:
        table = ResultsTable(self.script.results_title, self.script.results, held_for=RESULTS_FOR)
        return NarratedScene(table, (self.lines.results,))

    def end_card(self) -> NarratedScene:
        return NarratedScene(EndCard(self.script, held_for=END_CARD_FOR), (self.lines.closing,))

    # %% the storyboard

    def storyboard(self) -> Storyboard:
        """
        Every scene, in order, with the lines said over it.
        """
        narrated = [
            self.title(),
            self.plan_reading(),
            *self.backend_scenes(),
            self.plan_resolved(),
            self.execution(),
            *self.attribution_scenes(),
            self.grid(),
            self.results(),
            self.end_card(),
        ]
        return Storyboard(narrated, tail=TAIL, pause=PAUSE)

    def scenes(self) -> List[Scene]:
        """
        Every scene, in order.
        """
        return self.storyboard().scenes

    def timeline(self) -> Timeline:
        return Timeline(self.scenes(), frames_per_second=self.frames_per_second, dissolve=DISSOLVE)

    def narrated_timeline(self) -> Tuple[Timeline, Narration]:
        """
        The timeline with its slides grown to hold their lines, and the narration
        placed on it, checked to run clear of itself and of the video's end.
        """
        board = self.storyboard()
        board.fitted_to(self.voice)
        timeline = Timeline(board.scenes, frames_per_second=self.frames_per_second, dissolve=DISSOLVE)
        narration = board.narrated_by(self.voice, dissolve=DISSOLVE)
        narration.check(runs_for=timeline.duration)
        return timeline, narration

    def written_to(self, path: Path) -> VideoFile:
        """
        Render and encode the video, checking it against the conference's limits.

        :param path: Where the mp4 goes.
        """
        limits = SubmissionLimits.icra_2027()
        timeline, narration = self.narrated_timeline()
        logger.info("%.1f s of video in %d scenes", timeline.duration, len(timeline.scenes))
        budget = int(limits.largest * min(timeline.duration / limits.longest, 1.0)) - bytes_for_sound(timeline.duration)
        burned_in = self.subtitling is Subtitling.BURNED_IN
        picture = Subtitled.over(timeline, narration) if burned_in else timeline
        silent = H264Encoder(size_budget=budget, preset="fast" if self.preview else "slow").encode(
            picture, path.with_name(path.stem + "_silent.mp4")
        )
        soundtrack = narration.soundtrack(runs_for=timeline.duration).written_to(path.with_suffix(".wav"))
        subtitles = None if burned_in else narration.written_to(path.with_suffix(".srt"))
        video = Muxer().joined(silent, soundtrack, path, subtitles=subtitles)
        silent.path.unlink()
        soundtrack.unlink()
        limits.check(video)
        logger.info("%s: %.1f s, %d bytes; subtitles %s", video.path, video.duration, video.size, "burned in" if burned_in else f"in {subtitles}")
        return video

    def starts_of(self, lines: Sequence[Line]) -> List[float]:
        """
        Seconds after the first of some lines starts that each starts, said in turn.
        """
        return starts_of(self.voice, lines, PAUSE)

    def said_for(self, line: Line) -> float:
        """
        Seconds a line takes to say.
        """
        return self.voice.speaks(line.said).duration

    def delay_after(self, lines: Sequence[Line], held_for: float) -> float:
        """
        Seconds the lines of a scene wait, beyond the lead, for the lines of the scene
        before it to end: those run on over this scene's beginning.

        :param lines: The lines said over the scene before, from its lead.
        :param held_for: How long that scene is held.
        """
        said = sum(self.said_for(line) for line in lines) + PAUSE * len(lines)
        return max(said - (held_for - DISSOLVE), 0.0)


# %% the command line



# %% the command line


def parse_arguments(argument_list: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="where the mp4 is written")
    parser.add_argument("--voice", default=KokoroVoice.voice, help="which of the speech model's voices narrates")
    parser.add_argument("--speech-speed", type=float, default=KokoroVoice.speed, help="how fast it speaks, 1 being its own pace")
    parser.add_argument("--preview", action="store_true", help="render a short rough version for looking at")
    parser.add_argument("--subtitles", type=Subtitling, choices=list(Subtitling), default=Subtitling.BURNED_IN, help="burned into the picture, or a track the viewer can switch off")
    return parser.parse_args(argument_list)


def main(argument_list: Optional[Sequence[str]] = None) -> None:
    arguments = parse_arguments(argument_list)
    voice = KokoroVoice(voice=arguments.voice, speed=arguments.speech_speed)
    VideoAssembly(preview=arguments.preview, voice=voice, subtitling=arguments.subtitles).written_to(arguments.output)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s", force=True)
    main()
