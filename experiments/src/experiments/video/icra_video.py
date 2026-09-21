"""
The supplementary video, cut from the framework demo the robot recorded and the
perturbation episodes, and written out within the conference's limits.

Usage:
    python -m experiments.video.icra_video --output <video.mp4> [--paper-id 3889]
        [--voice af_heart] [--speech-speed 1.15] [--subtitles burned-in|soft] [--preview]

The narration is spoken by the Kokoro model on this machine (``--voice`` picks any of
its voices) and goes into the mp4 with its subtitles burned into the picture; with
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

from typing_extensions import Callable, Dict, List, Optional, Sequence, Tuple

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
from experiments.video.figure import (
    FigureBox,
    FigureGeometry,
    FrameworkFigure,
    GraspChartBar,
    PlanAction,
    RunReadings,
    Slot,
)
from experiments.video.footage import (
    CameraFilm,
    ExecutionFootage,
    Framing,
    HandHeldFilm,
    SideBySide,
    ViewOfTheRun,
)
from experiments.video.grasp import (
    ApproachPrior,
    GraspDistribution,
    GraspOptionsOnThePicture,
    GraspSampling,
)
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
    GridLabels,
    PerturbationMatrix,
    PerturbationTile,
)
from experiments.video.rules import HoleOnThePicture, HoleRuleTrace, RuleTreeEvaluation
from experiments.video.script import NarrationLines, VideoScript
from experiments.video.slides import ClosingSlide, TextSlide, TitleSlide
from experiments.video.sources import FRAMEWORK_DEMO_EPISODE, RecordedRun
from experiments.video.query_slide import QuerySlide, SlideMoments
from experiments.video.stages import (
    Answering,
    FigureOnCanvas,
    FigureScene,
    Magnified,
    Mark,
    OnCanvas,
    Pointer,
)
from experiments.video.timeline import Scene, Timeline
from experiments.video.twin import TwinPictures, WorkingMemoryCheck
from experiments.episodes.long_term_memory import LongTermMemory
from krrood.entity_query_language.backends import ProbabilisticBackend

logger = logging.getLogger(__name__)

PERTURBATION_EPISODES = (
    ("508e367a6fd04cc2ba657f991e3f4bd9", "0a793ded6dd54da7b64171ab78638d38", "57bbcbb2c919404e9cd729d7e766bf66"),
    ("25f5161da5584bac9554b686711a01fe", "e9b1eef3d2f34a57a95e2b897ec63cdd", "25ccb55ba8ab4d90aabe54c5800cedb8"),
)
"""
The perturbation episodes, row by row as the grid shows them: the scene standing still
and the robot sorting, each unperturbed, with a piece shoved and with the board moved.
"""

ATTRIBUTION_QUESTION_FOR = 5.0
"""
Seconds each question about who moved what takes: long enough to read the query, see
the asking ruled onto the timelines, and the events lit.
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

    scenario: str
    """
    What was going on, as written under the film.
    """

    speed: float
    """
    How many recorded seconds pass per second played while the film runs.
    """

    told_while_watched: bool = False
    """
    Whether the trial's line is said while its film plays, so that it tells what is
    about to be seen, rather than as its questions come up.
    """

    question_for: float = ATTRIBUTION_QUESTION_FOR
    """
    Seconds each question about the trial takes.
    """


ATTRIBUTION_RUNS = (
    AttributionRun("25f5161da5584bac9554b686711a01fe", "the robot sorts the pieces it saw", 50.0),
    # at this pace the hand reaches in as the line reaches "a person pushes the cube";
    # its answers are one object and none, read in less time than the sorting's four
    AttributionRun(
        "0a793ded6dd54da7b64171ab78638d38",
        "the scene stands still; a person pushes the cube",
        4.0,
        told_while_watched=True,
        question_for=3.0,
    ),
)
"""
The two trials the paper sets against each other: the robot moving the pieces itself,
and a person moving one while the robot stands idle.
"""

DISSOLVE = 0.4
"""
Seconds each scene dissolves into the next.
"""

PAUSE = 0.5
"""
Seconds between two lines said over one scene.
"""

ASKED_BY: Dict[Slot, Callable[[NarrationLines], Line]] = {
    Slot.PERCEPTION: lambda lines: lines.perception_query,
    Slot.SIMULATION: lambda lines: lines.working_memory_query,
    Slot.PROBABILISTIC: lambda lines: lines.probabilistic_query,
    Slot.RULES: lambda lines: lines.rules_query,
}
"""
The line said over each slot's sub-query, magnified out of the plan.
"""

NARRATED_BY: Dict[Slot, Callable[[NarrationLines], Tuple[Line, ...]]] = {
    Slot.PERCEPTION: lambda lines: lines.perception_views,
    Slot.SIMULATION: lambda lines: (lines.working_memory,),
    Slot.PROBABILISTIC: lambda lines: (lines.probabilistic,),
    Slot.RULES: lambda lines: (lines.rules,),
}
"""
The lines said over each backend's close-up.
"""

GRID_SPEED = 6.0
"""
How many recorded seconds pass per second played in the perturbation grid: slow enough
for the perturbations to be seen; the recordings need not end before the questions.
"""

GRID_QUESTION_FOR = 3.5
"""
Seconds each question put to long-term memory over the grid takes.
"""

QUESTIONS_INTO_THE_LINE = 0.55
"""
How far into the line about long-term memory its questions are reached: the first
question comes up on the grid then.
"""

QUERY_HELD_AT_LEAST = 0.5
"""
Seconds a sub-query is held alone at the least, however short the line over it.
"""

PLAN_CAPTION = ""
"""
What is written under the figure while the plan is read: nothing, the plan magnified
to the stage's height covering the caption's place.
"""

PLAN_SHARE = 0.96
"""
How much of the stage the whole plan takes while it is read: as tall as the stage
allows, so that all of it is in view while its parts are pointed to in turn.
"""

PICK_UP_NAMED_AT = 3.75
"""
Seconds into the line about the pick-up that "pick up" is said, after the pause that
follows "meaning:" — measured on the spoken line; the pick-up action is pointed to
then. The insertion action is pointed to as the line about it starts.
"""

OPEN_PART_NAMED_AT: Dict[Slot, float] = {Slot.PERCEPTION: 1.8, Slot.PROBABILISTIC: 2.55, Slot.RULES: 3.45}
"""
Seconds into the line about the insertion that what each slot leaves open is named —
"The cube", "the approach direction", "and the hole" — measured on the spoken line;
the part is pointed to and highlighted then.
"""

OPEN_FIELD_HUE = Ink.ASKED.rgb
"""
What a part of the plan is ringed in when it is pointed to.
"""

QUERY_PARTS_NAMED_AT = (1.1, 3.4, 4.2, 5.5)
"""
Seconds into the line defining a query that each part of the template is named —
"under-specified", "its type", "the fields already known", "further conditions" —
measured on the spoken line.
"""

EXAMPLE_LINES_NAMED_AT = (0.6, 3.1, 2.3, 1.7)
"""
Seconds into the line about the example that each of its lines is named, in the
example's order — "a grasp description", "the approach direction", "from the top",
"left hand" — measured on the spoken line.
"""

OPEN_FIELD_WRITTEN_AT = 5.0
"""
Seconds into the line about the example that "three dots" is said, when its open field
is marked.
"""

GROUNDING_NAMED_AT = 3.5
"""
Seconds into the line about what the example means that "its grounding" is said; its
intended meaning is named as the line starts.
"""

COMPUTATION_NAMED_AT = 8.5
"""
Seconds into that line that "computed" is said.
"""

GRASP_PRIOR_SHARE = 0.55
"""
The probability the prior over the approach gives the direction the run took; the
rest is split evenly among the other three.
"""

IDLE_FRAMES_READ = 24
"""
How many of the recording's first frames, taken while the robot stood still, the look
is watched over.
"""

EXECUTION_STRETCH = (19.5, 47.5)
"""
The seconds of the framework demo's recording shown while the robot acts: from the arm
setting off for the cube to its withdrawing from the hole.
"""

EXECUTION_SPEED = 7.0
"""
How many recorded seconds pass per second played while the robot acts.
"""

EXECUTION_CAPTION = "the cube picked up and put through the square hole"
"""
What is written under the film of the robot acting.
"""

HAND_HELD_OFFSET = 15.5
"""
Seconds after the robot's own recording started that the hand-held film of the
framework demo started: read off both films at the moment the gripper is lowered
into the square hole.
"""

HAND_HELD_FRAMING = Framing(top=450, bottom=570)
"""
What of the hand-held film is shown: it stands upright, and the arm and the board take
its middle.
"""

@dataclass(frozen=True)
class BackendName:
    """
    What a backend is called on screen while it answers its slot.
    """

    name: str
    """
    The backend's class name.
    """

    role: str = ""
    """
    What kind of reasoning it does, where the name alone does not say.
    """

    @property
    def tab(self) -> str:
        """
        The name and the role, as the tab over the close-up carries them.
        """
        return f"{self.name}  ·  {self.role}" if self.role else self.name


BACKENDS: Dict[Slot, BackendName] = {
    Slot.PERCEPTION: BackendName("PerceptionBackend"),
    Slot.SIMULATION: BackendName("WorkingMemory (default)"),
    Slot.PROBABILISTIC: BackendName("ProbabilisticBackend"),
    Slot.RULES: BackendName("RippleDownRulesBackend", "rule-based reasoning / logical inference"),
}
"""
What each slot's backend is called: on the figure's panel and on the tab over its
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

CAPTIONS: Dict[Slot, str] = {
    Slot.PERCEPTION: "The innermost description first: the perception backend looks for a cyan cube resting on the lid.",
    Slot.SIMULATION: "Working memory checks the stated relation on the spawned cube: SupportedBy(cube, lid).",
    Slot.PROBABILISTIC: "The probabilistic backend samples the approach direction the plan left open.",
    Slot.RULES: "Ripple-down rules conclude which hole the cube belongs in.",
}
"""
What is written under the figure while each backend answers.
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
        The backend's sampling, under a prior that favours the direction the run took.

        The run itself sampled under the backend's uniform default, where every
        direction is as likely as the next and the first sample wins; the video shows
        the same machinery with a prior stated, so the direction handed to the plan is
        the one the model favours rather than the luck of the draw.
        """
        taken = self.demo.recorded_grasp().approach_direction
        prior = ApproachPrior.favouring(taken, share=GRASP_PRIOR_SHARE)
        return GraspSampling(answered=taken, backend=ProbabilisticBackend(prior))

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

    def figure(self, stage: int, focus: Optional[Slot], caption: str) -> FigureOnCanvas:
        titles = {slot: backend.name for slot, backend in BACKENDS.items()}
        figure = FrameworkFigure(stage=stage, focus=focus, readings=self.readings, panel_titles=titles)
        return FigureOnCanvas(figure, caption=caption)

    def starts_of(self, lines: Sequence[Line]) -> List[float]:
        """
        Seconds after the first of some lines starts that each starts, said in turn.
        """
        return starts_of(self.voice, lines, PAUSE)

    def work_of(self, slot: Slot) -> Scene:
        """
        The close-up that plays while a backend answers its slot.
        """
        if slot is Slot.PERCEPTION:
            reel = NarrowingReel(self.demo, frame_indices=list(range(IDLE_FRAMES_READ)))
            # each view comes up as its line starts
            scene = PerceptionNarrowing(reel, appears_at=tuple(self.starts_of(self.lines.perception_views)), run_for=1.0)
            if self.preview:
                scene.appears_at, scene.run_for = (0.0, 1.0, 2.0, 3.0), 2.0
            return scene
        if slot is Slot.SIMULATION:
            # the band where the boxes interfere is drawn as the line reaches "the board's
            # top", and the verdict as it reaches "confirms"
            scene = WorkingMemoryCheck(
                self.twin, spawn_at=0.3, flight_from=1.2, flight_for=2.0, boxes_for=3.0, boxes_at=(0.2, 0.6), band_at=1.0, verdict_at=1.8
            )
            if self.preview:
                scene.flight_for, scene.boxes_for = 2.0, 4.0
            return scene
        if slot is Slot.PROBABILISTIC:
            scene = GraspDistribution(
                self.sampling,
                GraspOptionsOnThePicture(self.demo, self.twin.cube_at + [0.0, 0.0, 0.01]),
                statement_for=1.5,
                sampling_for=3.5,
                answer_for=1.5,
            )
            if self.preview:
                scene.sampling_for, scene.answer_for = 3.0, 2.0
            return scene
        scene = RuleTreeEvaluation(self.rule_trace, HoleOnThePicture(self.demo), tree_for=2.0, answer_for=2.7)
        if self.preview:
            scene.answer_for = 2.0
        return scene

    def plan_reading(self) -> NarratedScene:
        """
        The whole plan magnified out of the figure and read with an arrow: the pick-up
        and then the insertion pointed to as the lines describe them, then each part
        left open as it is named, highlighted as the arrow moves on.
        """
        shown = self.figure(0, None, PLAN_CAPTION)
        geometry = shown.figure.geometry
        pick_up, insertion = geometry.actions[PlanAction.PICK_UP], geometry.actions[PlanAction.INSERTION]
        whole = FigureBox(geometry.plan.x, pick_up.y, geometry.plan.width, insertion.y + insertion.height - pick_up.y)
        lines = (self.lines.plan_pick_up, self.lines.plan_insertion)
        pick_up_from, insertion_from = (LEAD + start for start in self.starts_of(lines))
        open_parts = {slot: insertion_from + named_at for slot, named_at in OPEN_PART_NAMED_AT.items()}
        magnified = Magnified(shown, whole, Ink.TEXT.rgb, share=PLAN_SHARE)
        magnified.pointers = (
            Pointer(pick_up, OPEN_FIELD_HUE, from_second=pick_up_from + PICK_UP_NAMED_AT),
            Pointer(insertion, OPEN_FIELD_HUE, from_second=insertion_from),
            *(Pointer(self.left_open(geometry, slot), OPEN_FIELD_HUE, from_second=named_at, framed=False) for slot, named_at in open_parts.items()),
        )
        magnified.marks = tuple(Mark(self.left_open(geometry, slot), OPEN_FIELD_HUE, from_second=named_at) for slot, named_at in open_parts.items())
        return NarratedScene(magnified, lines)

    @staticmethod
    def left_open(geometry: FigureGeometry, slot: Slot) -> FigureBox:
        """
        What the plan leaves open for a slot: the field written as ``...`` where there
        is one, else the whole description the slot answers.
        """
        return geometry.open_fields.get(slot, geometry.slots[slot])

    def backend_scene(self, slot: Slot) -> NarratedScene:
        """
        The backend answering its slot: the sub-query held beside the close-up of the
        backend's work, the answer written into it. The line about what is asked is
        said over the sub-query alone; the lines about how the backend answers start as
        its work does.
        """
        before = self.figure(slot.stage - 1, slot, CAPTIONS[slot])
        after = self.figure(slot.stage, None, CAPTIONS[slot])
        asked = ASKED_BY[slot](self.lines)
        geometry = before.figure.geometry
        marks = (Mark(geometry.open_fields[slot], OPEN_FIELD_HUE),) if slot in geometry.open_fields else ()
        scene = Answering(before, after, slot, self.work_of(slot), HUES[slot].rgb, title=BACKENDS[slot].tab, marks=marks)
        scene.query_for = self.query_hold(asked, scene)
        return NarratedScene(scene, (asked, *NARRATED_BY[slot](self.lines)))

    def query_hold(self, asked: Line, scene: Answering) -> float:
        """
        Seconds the sub-query is held alone so that the work starts as the first line
        over it does: once the line about what is asked and the pause after it are over.

        :param asked: The line said over the sub-query.
        :param scene: The backend answering it.
        """
        said = self.voice.speaks(asked.said).duration
        return max(LEAD + said + PAUSE - scene.grow - scene.close_up_grow, QUERY_HELD_AT_LEAST)

    def execution(self) -> Scene:
        """
        The robot carrying out the resolved plan: from its own camera and, where someone
        filmed the run by hand, from beside the table in step with it.
        """
        start, end = EXECUTION_STRETCH
        speed = 16.0 if self.preview else EXECUTION_SPEED
        by_hand = HandHeldFilm.beside(self.demo)
        if by_hand is None:
            return ExecutionFootage(CameraFilm(self.demo), from_second=start, to_second=end, speed=speed, caption=EXECUTION_CAPTION)
        views = (
            # the gripper reaches the cube at the very top of the robot's picture, so none is cut off
            ViewOfTheRun(CameraFilm(self.demo), start, Framing(), "the robot's own camera"),
            ViewOfTheRun(by_hand, start - HAND_HELD_OFFSET, HAND_HELD_FRAMING, "a camera held by hand beside the table"),
        )
        return SideBySide(views, length=end - start, speed=speed, caption=EXECUTION_CAPTION)

    def perturbation_matrix(self) -> PerturbationMatrix:
        """
        The six episodes playing out, then long-term memory asked about them.
        """
        # one recording kept no transforms; the camera stood the same way for every run that day
        tiles = [
            [
                PerturbationTile(RecordedRun(episode, camera_pose_from=self.demo.bag))
                for episode in row
            ]
            for row in PERTURBATION_EPISODES
        ]
        remembered = RememberedPiece(LongTermMemory(self.demo.database)).both()
        lines = (self.lines.episodic_memory, self.lines.long_term_memory)
        # the first question comes up as the line reaches its questions
        asked_from = LEAD + self.grid_lines_delay() + self.starts_of(lines)[1] + QUESTIONS_INTO_THE_LINE * self.voice.speaks(lines[1].said).duration
        return PerturbationMatrix(
            tiles,
            GridLabels(),
            questions=remembered,
            speed=GRID_SPEED * (4.0 if self.preview else 1.0),
            question_for=2.0 if self.preview else GRID_QUESTION_FOR,
            asked_from=asked_from,
        )

    def perturbations_slide(self) -> TextSlide:
        return TextSlide(
            ["Perturbation experiments & Long-term memory", "Six episodes on the robot: the scene standing still or the robot sorting,",
             "unperturbed, with a person shoving a piece, or moving the board."],
            held_for=3.5,
        )

    def grid_lines_delay(self) -> float:
        """
        Seconds the grid's lines wait, beyond the lead, for the slide's line before it
        to end: that line runs on over the grid's beginning.
        """
        said = self.voice.speaks(self.lines.perturbations.said).duration
        return max(said + PAUSE - (self.perturbations_slide().held_for - DISSOLVE), 0.0)

    def attribution_scenes(self) -> List[NarratedScene]:
        """
        The questions about who moved what, answered in each of the two trials; each
        trial's line starts as its questions do.
        """
        scenes: List[NarratedScene] = []
        lines = (self.lines.attribution_sorting, self.lines.attribution_pushed)
        for run, line in zip(ATTRIBUTION_RUNS, lines):
            timelines = TrialTimelines(RecordedRun(run.episode))
            scene = AttributionScene(
                timelines,
                CameraFilm(timelines.run),
                MovedQuestions(timelines).both(),
                scenario=run.scenario,
                speed=run.speed * (3.0 if self.preview else 1.0),
                question_for=2.0 if self.preview else run.question_for,
            )
            delay = 0.0 if run.told_while_watched else max(scene.watching_for - LEAD, 0.0)
            scenes.append(NarratedScene(OnCanvas(scene), (line,), delay=delay))
        return scenes

    def storyboard(self) -> Storyboard:
        """
        Every scene, in order, with the line that starts with it.
        """
        lines = self.lines
        introduction = (lines.definition, lines.example, lines.meaning, lines.taxonomy, lines.backend_choice)
        opening = (lines.title, lines.summary)
        narrated: List[NarratedScene] = [
            # the summary comes up under the title as its line starts
            NarratedScene(TitleSlide(self.script, held_for=5.5, summary_at=LEAD + self.starts_of(opening)[1]), opening),
            NarratedScene(QuerySlide(moments=self.query_slide_moments(introduction), held_for=8.0), introduction),
        ]
        narrated.append(self.plan_reading())
        for slot in Slot:
            narrated.append(self.backend_scene(slot))
        narrated.append(
            NarratedScene(
                FigureScene(self.figure(len(Slot), None, "Every open field answered: the resolved plan is carried out on the robot."), held_for=1.5),
                (lines.resolved,),
                runs_on=True,
            )
        )
        narrated.append(NarratedScene(OnCanvas(self.execution())))
        narrated.append(
            NarratedScene(
                TextSlide(["Temporal & Attribution Queries", "The event segmentation reports what happened to each object;",
                           "the plan history records which action ran when."], held_for=4.0),
                (lines.attribution,),
                runs_on=True,
            )
        )
        narrated.extend(self.attribution_scenes())
        narrated.append(NarratedScene(self.perturbations_slide(), (lines.perturbations,), runs_on=True))
        narrated.append(
            NarratedScene(
                OnCanvas(self.perturbation_matrix()),
                (lines.episodic_memory, lines.long_term_memory),
                delay=self.grid_lines_delay(),
            )
        )
        narrated.append(NarratedScene(ClosingSlide(self.script, held_for=2.0), (lines.closing,)))
        return Storyboard(narrated, pause=PAUSE)

    def query_slide_moments(self, introduction: Sequence[Line]) -> SlideMoments:
        """
        When each part of the query slide comes up: as the words naming it are said.

        :param introduction: The lines said over the slide, in order: the definition,
            the example, its meaning, the kinds of backend, the choice.
        """
        definition, example, meaning, taxonomy, choice = (LEAD + start for start in self.starts_of(introduction))
        return SlideMoments(
            template=0.0,
            parts=tuple(definition + named_at for named_at in QUERY_PARTS_NAMED_AT),
            lines=tuple(example + named_at for named_at in EXAMPLE_LINES_NAMED_AT),
            open_field=example + OPEN_FIELD_WRITTEN_AT,
            meaning=meaning,
            grounding=meaning + GROUNDING_NAMED_AT,
            computation=meaning + COMPUTATION_NAMED_AT,
            tree=taxonomy,
            choice=choice,
        )

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


# %% the command line


def parse_arguments(argument_list: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="where the mp4 is written")
    parser.add_argument("--paper-id", default=None, help="the paper's submission number for the title slide")
    parser.add_argument("--voice", default=KokoroVoice.voice, help="which of the speech model's voices narrates")
    parser.add_argument("--speech-speed", type=float, default=KokoroVoice.speed, help="how fast it speaks, 1 being its own pace")
    parser.add_argument("--preview", action="store_true", help="render a short rough version for looking at")
    parser.add_argument("--subtitles", type=Subtitling, choices=list(Subtitling), default=Subtitling.BURNED_IN, help="burned into the picture, or a track the viewer can switch off")
    return parser.parse_args(argument_list)


def main(argument_list: Optional[Sequence[str]] = None) -> None:
    arguments = parse_arguments(argument_list)
    script = VideoScript() if arguments.paper_id is None else VideoScript(paper_id=arguments.paper_id)
    voice = KokoroVoice(voice=arguments.voice, speed=arguments.speech_speed)
    VideoAssembly(script=script, preview=arguments.preview, voice=voice, subtitling=arguments.subtitles).written_to(arguments.output)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s", force=True)
    main()
