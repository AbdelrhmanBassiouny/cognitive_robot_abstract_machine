"""
The supplementary video, cut from the framework demo the robot recorded and the
perturbation episodes, and written out within the conference's limits.

Usage:
    python -m experiments.video.icra_video --output <video.mp4> [--paper-id ####]
        [--preview]

Needs the results database and the episode artifacts the reproduction package restores
(``MONTESSORI_SORTING_DATABASE_URI``, ``EPISODE_ARTIFACTS_DIRECTORY``). What takes a
while to compute is kept under ``EXPERIMENTS_VIDEO_CACHE`` between runs.
"""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path

from typing_extensions import Dict, List, Optional, Sequence

from experiments.montessori.semantics import MontessoriShape, MontessoriShapeCategory
from experiments.video.attribution import (
    AttributionScene,
    MovedQuestions,
    TrialTimelines,
)
from experiments.video.canvas import Ink
from experiments.video.encoding import H264Encoder, SubmissionLimits, VideoFile
from experiments.video.figure import (
    FrameworkFigure,
    GraspChartBar,
    RunReadings,
    Slot,
)
from experiments.video.footage import CameraFilm, ExecutionFootage
from experiments.video.grasp import (
    ApproachPrior,
    GraspDistribution,
    GraspOptionsOnThePicture,
    GraspSampling,
)
from experiments.video.perception import NarrowingReel, PerceptionNarrowing
from experiments.video.perturbations import (
    GridLabels,
    PerturbationMatrix,
    PerturbationTile,
)
from experiments.video.rules import HoleOnThePicture, HoleRuleTrace, RuleTreeEvaluation
from experiments.video.script import VideoScript
from experiments.video.slides import ClosingSlide, TextSlide, TitleSlide
from experiments.video.sources import FRAMEWORK_DEMO_EPISODE, RecordedRun
from experiments.video.stages import FigureOnCanvas, FigureScene, OnCanvas, Spotlight
from experiments.video.timeline import Scene, Timeline
from experiments.video.twin import TwinPictures, WorkingMemoryCheck
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


ATTRIBUTION_RUNS = (
    AttributionRun("25f5161da5584bac9554b686711a01fe", "the robot sorts the pieces it saw", 24.0),
    AttributionRun("0a793ded6dd54da7b64171ab78638d38", "the scene stands still; a person pushes the cube", 3.0),
)
"""
The two trials the paper sets against each other: the robot moving the pieces itself,
and a person moving one while the robot stands idle.
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

EXECUTION_FROM_SECOND = 8.0
"""
Where in the framework demo's recording the film of the execution starts: once the
look has been answered and the arm sets off.
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
        )

    def figure(self, stage: int, focus: Optional[Slot], caption: str) -> FigureOnCanvas:
        return FigureOnCanvas(FrameworkFigure(stage=stage, focus=focus, readings=self.readings), caption=caption)

    def work_of(self, slot: Slot) -> Scene:
        """
        The close-up that plays while a backend answers its slot.
        """
        if slot is Slot.PERCEPTION:
            reel = NarrowingReel(self.demo, frame_indices=list(range(IDLE_FRAMES_READ)))
            scene = PerceptionNarrowing(reel)
            if self.preview:
                scene.tile_every, scene.run_for, scene.answer_for = 1.0, 2.0, 2.0
            return scene
        if slot is Slot.SIMULATION:
            scene = WorkingMemoryCheck(self.twin)
            if self.preview:
                scene.flight_for, scene.boxes_for = 2.0, 4.0
            return scene
        if slot is Slot.PROBABILISTIC:
            scene = GraspDistribution(self.sampling, GraspOptionsOnThePicture(self.demo, self.twin.cube_at + [0.0, 0.0, 0.01]))
            if self.preview:
                scene.sampling_for, scene.answer_for = 3.0, 2.0
            return scene
        scene = RuleTreeEvaluation(self.rule_trace, HoleOnThePicture(self.demo))
        if self.preview:
            scene.answer_for = 2.0
        return scene

    def backend_scenes(self, slot: Slot) -> List[Scene]:
        """
        The figure with the slot ringed, the backend's close-up, and the figure with the
        slot answered.
        """
        before = self.figure(slot.stage - 1, slot, CAPTIONS[slot])
        after = self.figure(slot.stage, None, CAPTIONS[slot])
        return [
            FigureScene(before, held_for=1.5),
            Spotlight(before, after, slot, self.work_of(slot), HUES[slot].rgb),
            FigureScene(after, held_for=1.0),
        ]

    def perturbation_matrix(self) -> PerturbationMatrix:
        # one recording kept no transforms; the camera stood the same way for every run that day
        tiles = [
            [
                PerturbationTile(RecordedRun(episode, camera_pose_from=self.demo.bag))
                for episode in row
            ]
            for row in PERTURBATION_EPISODES
        ]
        return PerturbationMatrix(tiles, GridLabels(), played_for=8.0 if self.preview else 30.0)

    def attribution_scenes(self) -> List[Scene]:
        """
        The questions about who moved what, answered in each of the two trials.
        """
        scenes: List[Scene] = []
        for run in ATTRIBUTION_RUNS:
            timelines = TrialTimelines(RecordedRun(run.episode))
            scene = AttributionScene(
                timelines,
                CameraFilm(timelines.run),
                MovedQuestions(timelines).both(),
                scenario=run.scenario,
                speed=run.speed * (3.0 if self.preview else 1.0),
                question_for=2.0 if self.preview else 4.0,
            )
            scenes.append(OnCanvas(scene))
        return scenes

    def scenes(self) -> List[Scene]:
        """
        Every scene, in order.
        """
        scenes: List[Scene] = [
            TitleSlide(self.script, held_for=6.0),
            FigureScene(self.figure(0, None, "The plan states what it wants and leaves four things open, each answered by a backend."), held_for=4.0),
        ]
        for slot in Slot:
            scenes.extend(self.backend_scenes(slot))
        scenes.append(FigureScene(self.figure(len(Slot), None, "Every open field answered: the resolved plan is carried out on the robot."), held_for=2.5))
        scenes.append(
            OnCanvas(
                ExecutionFootage(
                    CameraFilm(self.demo),
                    from_second=EXECUTION_FROM_SECOND,
                    speed=8.0 if self.preview else 4.0,
                    caption="the robot's own camera: the cube picked up and put through the square hole",
                )
            )
        )
        scenes.append(TextSlide(["Did you move it?", "The event segmentation reports what happened to each object;",
                                 "the plan history records which action ran when."], held_for=3.5))
        scenes.extend(self.attribution_scenes())
        scenes.append(TextSlide(["Perturbation experiments", "Six episodes on the robot: the scene standing still or the robot sorting,",
                                 "unperturbed, with a person shoving a piece, or moving the board."], held_for=3.5))
        scenes.append(OnCanvas(self.perturbation_matrix()))
        scenes.append(ClosingSlide(self.script, held_for=5.0))
        return scenes

    def timeline(self) -> Timeline:
        return Timeline(self.scenes(), frames_per_second=self.frames_per_second, dissolve=0.4)

    def written_to(self, path: Path) -> VideoFile:
        """
        Render and encode the video, checking it against the conference's limits.

        :param path: Where the mp4 goes.
        """
        limits = SubmissionLimits.icra_2027()
        timeline = self.timeline()
        logger.info("%.1f s of video in %d scenes", timeline.duration, len(timeline.scenes))
        budget = int(limits.largest * min(timeline.duration / limits.longest, 1.0))
        video = H264Encoder(size_budget=budget, preset="fast" if self.preview else "slow").encode(timeline, path)
        limits.check(video)
        logger.info("%s: %.1f s, %d bytes", video.path, video.duration, video.size)
        return video


# %% the command line


def parse_arguments(argument_list: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="where the mp4 is written")
    parser.add_argument("--paper-id", default=None, help="the paper's submission number for the title slide")
    parser.add_argument("--preview", action="store_true", help="render a short rough version for looking at")
    return parser.parse_args(argument_list)


def main(argument_list: Optional[Sequence[str]] = None) -> None:
    arguments = parse_arguments(argument_list)
    script = VideoScript() if arguments.paper_id is None else VideoScript(paper_id=arguments.paper_id)
    VideoAssembly(script=script, preview=arguments.preview).written_to(arguments.output)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s", force=True)
    main()
