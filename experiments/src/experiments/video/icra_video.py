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
from dataclasses import dataclass, field
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
from experiments.video.chapters import ChapterMark, InChapter, chaptered
from experiments.video.encoding import (
    H264Encoder,
    Muxer,
    SubmissionLimits,
    VideoFile,
    bytes_for_sound,
)
from experiments.video.figure import GraspChartBar, RunReadings, Slot
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
from experiments.video.query_slide import IntroductionMoments, IntroductionSlide
from experiments.video.plan import resolved_plan, stated_plan
from experiments.video.stages import BackendAtWork, PlanOverview
from experiments.video.statements import statements_of
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
    Zoom(row=1, column=1, replay_from=8.0, held_for=7.0),
)
"""
The two tiles brought to the front of the grid, in order.
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

    question_for: float
    """
    Seconds each question about the trial takes.
    """


ATTRIBUTION_RUNS = (
    # the robot sorts the pieces it saw; the section's line is said over the film, and
    # the questions come up as it ends, each held for the line said over it
    AttributionRun("25f5161da5584bac9554b686711a01fe", None, 9.0),
    # the scene stands still while a person pushes the cube; at this pace the hand
    # reaches in as the line reaches "a person pushes the cube"
    AttributionRun("0a793ded6dd54da7b64171ab78638d38", 5.0, 3.0),
)
"""
The two trials the paper sets against each other: the robot moving the pieces itself,
and a person moving one while the robot stands idle.
"""

DISSOLVE = 0.25
"""
Seconds each scene dissolves into the next, where it does not cut in.
"""

PAUSE = 0.5
"""
Seconds between two lines said over one scene.
"""

TAIL = 0.4
"""
Seconds a slide is held after its last line has ended.
"""

TITLE_FOR = 4.0
"""
Seconds the title stands over the footage; the first chapter's claim follows it there.
"""

CLAIM_FOR = 2.0
"""
Seconds a chapter's claim is shown large.
"""

TITLE_FOOTAGE_FROM = 20.5
"""
Seconds into the hand-held film the title's footage starts: the gripper carrying the
cube over the board and putting it through the square hole.
"""

OPEN_FIELD_NAMED_AT = 4.9
"""
Seconds into the line about the query that "three dots" is said, when its open field
is marked -- measured on the spoken line.
"""

GLOSSED_AFTER = 0.9
"""
Seconds after the open field is marked that what the query says in words comes up.
"""

LEFT_OPEN_NAMED_AT = 6.1
"""
Seconds into the line about the plan that "Cube, approach direction and hole are left
open" starts -- measured on the spoken line; the open parts are emphasised then.
"""

PLAN_FOR = 4.0
"""
Seconds the plan is held at the least, as stated and resolved; the stated one grows to
hold its line.
"""

PERCEIVED_FOR = 0.5
"""
Seconds the last view of the look stands before the perception backend's answer chip
comes up.
"""

BAND_DRAWN_AT = 2.2
"""
Seconds into the line about working memory that "in simulation" is said, when the band
where the boxes interfere is drawn -- measured on the spoken line.
"""

VERDICT_AT = 3.7
"""
Seconds into that line that "rests on the lid" is said, when the result is given.
"""

SAMPLING_FOR = 4.0
"""
Seconds the probabilistic backend's samples take to arrive, from the line about the
sampling starting.
"""

CHECKING_FOR = 1.5
"""
Seconds the rule that fired is checked before it is highlighted, from the line about
the matching starting.
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

EXECUTION_LINES_AT = (0.0, 5.5, 9.4, 12.2, 16.5)
"""
Seconds into the film of the robot acting, beyond the lead, that each line said over
it starts: as the robot sets off, as it closes on the cube, as it lifts it, as the
gripper reaches the hole, and as it withdraws.
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

PUSHED_ANSWER_AT = 6.0
"""
Seconds into the second trial's scene, beyond the lead, that the line answering it
starts: as the first question's answer comes up.
"""

GRID_SPEED = 6.0
"""
How many recorded seconds pass per second played in the perturbation grid.
"""

GRID_PLAY_FOR = 4.0
"""
Seconds the grid plays before the first tile is brought to the front.
"""

GRID_LINES_AT = (0.0, 4.6, 10.5, 18.1)
"""
Seconds into the grid, beyond the lead, that each line said over it starts: as it
plays, as the first tile is at the front, as the second is, and as the grid plays on
with the question up.
"""

GRID_ASKED_AFTER = 0.3
"""
Seconds the grid plays on after the last zoom before the question comes up.
"""

IDLE_FRAMES_READ = 24
"""
How many of the recording's first frames, taken while the robot stood still, the look
is watched over.
"""

ANSWER_SETTLE = 0.6
"""
Seconds a backend's scene is held at the least after its sub-query reads answered.
"""

RESULTS_FOR = 4.0
"""
Seconds the results table is held at the least.
"""

END_CARD_FOR = 4.0
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
What each slot's backend is called, on the title bar of its panel.
"""

HUES: Dict[Slot, Ink] = {
    Slot.PERCEPTION: Ink.PERCEPTION,
    Slot.SIMULATION: Ink.SIMULATION,
    Slot.PROBABILISTIC: Ink.PROBABILISTIC,
    Slot.RULES: Ink.RULES,
}
"""
The colour each backend's panel carries, the figure's own.
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

    @cached_property
    def marks(self) -> Tuple[ChapterMark, ...]:
        chapters = self.script.chapters
        return tuple(ChapterMark(chapter, len(chapters)) for chapter in chapters)

    # %% chapter one: the backends completing the plan

    def title(self) -> NarratedScene:
        """
        The title over the footage of the insertion, then the first chapter's claim
        there; the opening line is said over both and runs on.
        """
        by_hand = HandHeldFilm.beside(self.demo)
        footage = FullBleedFootage(
            ViewOfTheRun(by_hand, TITLE_FOOTAGE_FROM, FULL_BLEED_FRAMING),
            length=TITLE_FOR + CLAIM_FOR,
            speed=1.0,
        )
        line = f"{self.script.kind}  ·  {self.script.conference}"
        titled = TitleOverFootage(footage, self.script.title, line, title_for=TITLE_FOR)
        opened = InChapter(titled, self.marks[0], opens=True, claim_from=TITLE_FOR, claim_for=CLAIM_FOR)
        return NarratedScene(opened, (self.lines.opening,), runs_on=True)

    def introduction(self) -> NarratedScene:
        """
        The three beats of the introduction, each coming up as its line starts.
        """
        lines = (self.lines.query, self.lines.backends, self.lines.principle)
        delay = self.delay_after((self.lines.opening,), TITLE_FOR + CLAIM_FOR)
        query, backends, hero = (LEAD + delay + start for start in self.starts_of(lines))
        open_field = query + OPEN_FIELD_NAMED_AT
        # the query is up from the slide's start, while the opening line still runs
        moments = IntroductionMoments(example=0.0, open_field=open_field, gloss=open_field + GLOSSED_AFTER, backends=backends, hero=hero)
        slide = IntroductionSlide(
            self.script.backend_choice, self.script.principle, self.script.statement_label, self.script.backends_label, moments=moments
        )
        return NarratedScene(slide, lines, delay=delay)

    def plan_stated(self) -> NarratedScene:
        """
        The plan as stated, its three open parts emphasised as the line names them.
        """
        overview = PlanOverview(stated_plan(), held_for=PLAN_FOR, emphasis_from=LEAD + LEFT_OPEN_NAMED_AT)
        return NarratedScene(overview, (self.lines.plan,))

    def plan_resolved(self) -> NarratedScene:
        """
        The plan resolved, with the footnote on where its values come from.
        """
        overview = PlanOverview(resolved_plan(self.readings), held_for=PLAN_FOR, footnote=self.script.run_values_note)
        return NarratedScene(overview, (self.lines.resolved,))

    def backend_scenes(self) -> List[NarratedScene]:
        """
        Each backend at work on its sub-query, in the order the plan is resolved.
        """
        statements = statements_of(self.readings)
        scenes = []
        for slot in Slot:
            work, answered_at, lines = self.work_of(slot)
            scene = BackendAtWork(statements[slot], BACKENDS[slot], HUES[slot].rgb, work, answered_at)
            scene.held_for = scene.answered_read_at + ANSWER_SETTLE
            scenes.append(NarratedScene(scene, lines))
        return scenes

    def work_of(self, slot: Slot) -> Tuple[Scene, float, Tuple[Line, ...]]:
        """
        The visual that plays on a backend's panel, the moment its answer is known, and
        the lines said over it.
        """
        lines = self.lines
        if slot is Slot.PERCEPTION:
            said = (lines.perception_query, *lines.perception_views)
            starts = [LEAD + start for start in self.starts_of(said)]
            reel = NarrowingReel(self.demo, frame_indices=list(range(IDLE_FRAMES_READ)))
            # the rectified table is up from the start; the other views come up as their lines do
            scene = PerceptionNarrowing(reel, appears_at=(0.0, *starts[2:]), run_for=8.0)
            return scene, starts[-1] + PERCEIVED_FOR, said
        if slot is Slot.SIMULATION:
            scene = WorkingMemoryCheck(self.twin, held_for=12.0, boxes_at=(LEAD + 0.4, LEAD + 1.1), band_at=LEAD + BAND_DRAWN_AT, verdict_at=LEAD + VERDICT_AT)
            return scene, scene.verdict_at + 0.3, (lines.working_memory,)
        if slot is Slot.PROBABILISTIC:
            said = (lines.probabilistic_query, lines.probabilistic)
            sampling_from = LEAD + self.starts_of(said)[1]
            scene = GraspDistribution(self.sampling, statement_for=sampling_from, sampling_for=SAMPLING_FOR, answer_for=8.0)
            return scene, scene.answers_at + 0.3, said
        said = (lines.rules_query, lines.rules)
        matching_from = LEAD + self.starts_of(said)[1]
        scene = RuleTreeEvaluation(self.rule_trace, HoleOnThePicture(self.demo), tree_for=matching_from, checking_for=CHECKING_FOR, answer_for=8.0)
        return scene, scene.answers_at + 0.3, said

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
        return NarratedScene(footage, lines, waits=self.waits_for(lines, EXECUTION_LINES_AT))

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

    # %% chapter two: the queries over events

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
        first = self.attribution_scene(sorting, lines.attribution)
        second = self.attribution_scene(pushed, lines.attribution_pushed)
        first_lines = (lines.attribution, lines.event_classes, lines.attribution_sorting)
        first_at = (0.0, first.watching_for - LEAD, first.watching_for - LEAD + first.question_for)
        second_lines = (lines.attribution_pushed, lines.attribution_pushed_answer)
        return [
            NarratedScene(first, first_lines, waits=self.waits_for(first_lines, first_at)),
            NarratedScene(second, second_lines, waits=self.waits_for(second_lines, (0.0, PUSHED_ANSWER_AT))),
        ]

    def attribution_scene(self, run: AttributionRun, *before_questions: Line) -> AttributionScene:
        """
        One trial's scene, its film played so that its questions come up as the last of
        the lines said before them ends, where the run leaves the pace open.

        :param run: The trial.
        :param before_questions: The lines said over the film before its questions.
        """
        timelines = TrialTimelines(RecordedRun(run.episode))
        scene = AttributionScene(
            timelines,
            CameraFilm(timelines.run),
            MovedQuestions(timelines).both(),
            speed=1.0,
            question_for=2.0 if self.preview else run.question_for,
        )
        speed = run.speed
        if speed is None:
            watched_for = LEAD + sum(self.said_for(line) + PAUSE for line in before_questions)
            speed = round(scene.horizon / watched_for)
        scene.speed = speed * (3.0 if self.preview else 1.0)
        return scene

    # %% chapter three: the real robot

    def grid(self) -> NarratedScene:
        """
        The six episodes playing out, two brought to the front in turn, then long term
        memory asked which the robot picked the cube up in.
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
        scene = GridSequence(
            tiles,
            labels,
            ZOOMS,
            question,
            speed=GRID_SPEED * (4.0 if self.preview else 1.0),
            play_for=GRID_PLAY_FOR,
            asked_after=GRID_ASKED_AFTER,
            question_for=self.said_for(self.lines.long_term_memory) + TAIL,
        )
        return NarratedScene(scene, lines, waits=self.waits_for(lines, GRID_LINES_AT))

    def results(self) -> NarratedScene:
        table = ResultsTable(self.script.results_title, self.script.results, held_for=RESULTS_FOR)
        return NarratedScene(table, (self.lines.results,))

    def end_card(self) -> NarratedScene:
        return NarratedScene(EndCard(self.script, held_for=END_CARD_FOR), (self.lines.closing,))

    # %% the storyboard

    def storyboard(self) -> Storyboard:
        """
        Every scene, in order, with the lines said over it, in three chapters.
        """
        one = [self.introduction(), self.plan_stated(), *self.backend_scenes(), self.plan_resolved(), self.execution()]
        two = self.attribution_scenes()
        three = [self.grid(), self.results(), self.end_card()]
        narrated = [self.title()]
        for chapter, scenes in zip(self.marks, (one, two, three)):
            for number, each in enumerate(scenes):
                # the first chapter opens over the title, so its own first scene does not
                each.scene = InChapter(each.scene, chapter, opens=number == 0 and chapter is not self.marks[0], claim_for=CLAIM_FOR)
                narrated.append(each)
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
