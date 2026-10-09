"""
An animated scene paced by the narration said over it.

A drawn scene plays its steps against beats, one beat per line of narration: a beat
lasts as long as its line plus the pause that follows it, its steps are scaled down to
fit that and never stretched to fill it, and whatever time is left over is waited out.
The scene therefore keeps step with the voice without any timings being written down.

Nothing here draws. :class:`AnimatedScene` asks an :class:`AnimationRenderer` for its
frames, so this module stays free of the drawing library and the beats can be measured
without it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from krrood.exceptions import DataclassException
from typing_extensions import Any, List, Protocol, Sequence, Tuple

from experiments.video.canvas import VIDEO_RESOLUTION
from experiments.video.narration import Line, Voice
from experiments.video.timeline import Frame, Resolution, Scene

# %% one step of a beat


@dataclass(frozen=True)
class AnimationStep:
    """
    One step of a beat: whatever plays together, and how long it takes beside the other
    steps of the same beat.
    """

    weight: float = 1.0
    """
    How long the step takes next to the other steps of its beat, as a bare ratio.
    """

    drawn: Tuple[Any, ...] = ()
    """
    What the drawing library plays for the step, each either something it can play or
    something returning one once the steps before have run; a step with none waits.
    """


# %% one beat


@dataclass(frozen=True)
class NarrationBeat:
    """
    The time one line of narration gives a scene to play its steps in.
    """

    line: Line
    """
    The line said over the beat.
    """

    said_for: float
    """
    Seconds the voice takes to say the line.
    """

    pause: float
    """
    Seconds of silence after the line, before the next begins.
    """

    shortest_step: float = 1.0 / 15.0
    """
    Seconds the shortest step runs for, so a beat of many steps still shows each.
    """

    headroom: float = 0.1
    """
    Seconds kept free at the end of a beat, so its last step ends before the next
    line begins.
    """

    @property
    def duration(self) -> float:
        """
        Seconds the beat lasts.
        """
        return self.said_for + self.pause

    def lengths_of(self, steps: Sequence[AnimationStep]) -> List[float]:
        """
        Seconds each step runs for: its weight fitted into the beat, scaled down where
        the steps together ask for more time than the beat has and left alone where they
        ask for less.

        :param steps: The steps of this beat, in order.
        """
        asked = sum(step.weight for step in steps)
        if not asked:
            return []
        scale = min(1.0, max(self.duration - self.headroom, 0.0) / asked)
        return [max(step.weight * scale, self.shortest_step) for step in steps]

    def waits_after(self, steps: Sequence[AnimationStep]) -> float:
        """
        Seconds of the beat left once its steps have played, waited out so the next beat
        starts with its line.

        :param steps: The steps of this beat, in order.
        """
        return max(self.duration - sum(self.lengths_of(steps)), 0.0)


# %% a wrong number of beats


@dataclass
class BeatMiscount(DataclassException):
    """
    Raised when a scene plays a different number of beats than it has lines of
    narration, which leaves its steps and the voice out of step.
    """

    played: int
    """
    Beats the scene played.
    """

    lines: int
    """
    Lines of narration said over it.
    """

    def error_message(self) -> str:
        return f"a scene played {self.played} beats over {self.lines} lines"

    def suggest_correction(self) -> str:
        return "Play one beat per line, or write one line per beat."


# %% the beats of one scene


@dataclass(frozen=True)
class BeatSchedule:
    """
    The beats one scene plays against, in order.
    """

    beats: Tuple[NarrationBeat, ...]
    """
    One beat per line of narration said over the scene.
    """

    @classmethod
    def of(cls, lines: Sequence[Line], voice: Voice, pause: float) -> BeatSchedule:
        """
        :param lines: The lines said over the scene, in order.
        :param voice: What says them, measured for how long each takes.
        :param pause: Seconds between one line and the next.
        """
        return cls(
            tuple(
                NarrationBeat(
                    line=line, said_for=line.spoken_by(voice).duration, pause=pause
                )
                for line in lines
            )
        )

    @property
    def duration(self) -> float:
        """
        Seconds every beat together lasts.
        """
        return sum(beat.duration for beat in self.beats)

    @property
    def starts(self) -> List[float]:
        """
        Seconds after the first beat that each beat starts.
        """
        starts: List[float] = []
        start = 0.0
        for beat in self.beats:
            starts.append(start)
            start += beat.duration
        return starts

    @property
    def lengths(self) -> Tuple[float, ...]:
        """
        Seconds each beat lasts, which a rendering of the scene is keyed by.
        """
        return tuple(beat.duration for beat in self.beats)

    def check_played(self, played: int) -> None:
        """
        :param played: Beats the scene played.
        :raises BeatMiscount: If that is not one beat per line.
        """
        if played != len(self.beats):
            raise BeatMiscount(played=played, lines=len(self.beats))


# %% how an animated scene comes in


class SceneEntry(StrEnum):
    """
    How a scene follows the one before it.
    """

    DISSOLVE = "dissolve"
    """
    The scene before fades into this one.
    """

    CUT = "cut"
    """
    This one replaces the scene before at once, for where the two would write different
    text in the same place.
    """


# %% what draws the frames


class AnimationRenderer(Protocol):
    """
    Whatever turns a scene's beats into the frames it plays.
    """

    def frames_of(
        self, schedule: BeatSchedule, resolution: Resolution, frames_per_second: int
    ) -> List[Frame]:
        """
        :param schedule: The beats the scene plays against.
        :param resolution: The size every frame has.
        :param frames_per_second: The rate the frames are drawn at.
        :return: Every frame of the scene, in order.
        """


# %% the scene


@dataclass
class AnimatedScene(Scene):
    """
    A drawn scene played on the timeline, its steps paced by the lines said over it.

    It is drawn once and keeps its frames, reading them back for every moment asked of
    it, so the picture is compressed only where the video is encoded.
    """

    renderer: AnimationRenderer
    """
    What draws the frames.
    """

    lines: Tuple[Line, ...]
    """
    The lines said over the scene, one beat each.
    """

    voice: Voice
    """
    What says them, measured for how long each takes.
    """

    pause: float
    """
    Seconds between one line and the next, as the storyboard leaves them.
    """

    resolution: Resolution = VIDEO_RESOLUTION
    """
    The size every frame has.
    """

    frames_per_second: int = 25
    """
    The rate the scene is drawn at, which a production sets to its own.
    """

    entry: SceneEntry = SceneEntry.DISSOLVE
    """
    How the scene before it comes into this one.
    """

    drawn: List[Frame] = field(default_factory=list, init=False)
    """
    The frames, once they have been drawn.
    """

    @property
    def schedule(self) -> BeatSchedule:
        """
        The beats this scene plays against.
        """
        return BeatSchedule.of(self.lines, self.voice, pause=self.pause)

    @property
    def frames(self) -> List[Frame]:
        """
        Every frame of the scene, drawn on the first reading and kept after it.
        """
        if not self.drawn:
            self.drawn = self.renderer.frames_of(
                self.schedule, self.resolution, self.frames_per_second
            )
        return self.drawn

    @property
    def duration(self) -> float:
        """
        Seconds the drawn scene lasts.
        """
        return len(self.frames) / self.frames_per_second

    @property
    def dissolves_in(self) -> bool:
        return self.entry is SceneEntry.DISSOLVE

    def picture_at(self, seconds: float) -> Frame:
        frames = self.frames
        return frames[min(int(seconds * self.frames_per_second), len(frames) - 1)]
