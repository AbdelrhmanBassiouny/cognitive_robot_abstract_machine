"""
What is said over the video, and when.

A line of narration belongs to the scene it starts with and may run on into the scenes
that follow, as long as the next line has not started by then. A slide grows to hold
its line; a close-up keeps the length of what it shows, so a line that does not fit
one is refused rather than talked over.

The lines are synthesized once each and kept, so the soundtrack and the subtitles come
from the same speech and always agree with each other.
"""

from __future__ import annotations

import hashlib
import re
from itertools import product
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from krrood.exceptions import DataclassException
from typing_extensions import Callable, Iterator, List, Optional, Protocol, Sequence, Tuple

from experiments.video.cache import SceneCache
from experiments.video.canvas import Anchor, Ink, Typesetting
from experiments.video.timeline import Frame, Resolution, Scene, Timeline

SUBTITLE_ROW = 42
"""
The most characters a subtitle row takes, the width players show at a glance.
"""

SUBTITLE_ROWS = 1
"""
How many rows a subtitle takes: one, so that a player's own text size, which differs
from player to player, stays inside the band the scenes leave clear.
"""

LEAD = 0.3
"""
Seconds a line starts after its scene has, so it is not heard over the dissolve in.
"""

VOICE_DIRECTORY = Path.home() / ".cache" / "experiments" / "video" / "voice"
"""
Where the speech model and its voices lie.
"""

CLAUSE_END_WORD = re.compile(r"[.;:?!,—]$")
"""
A word a subtitle had better end after: one that ends a clause with its punctuation.
"""

SENTENCE_END = re.compile(r"(?<=[.?!])\s+")
"""
Where the written line falls into sentences.
"""


def _ends_a_clause(word: str) -> bool:
    """
    :param word: A word.
    :return: Whether a subtitle had better end after it.
    """
    return bool(CLAUSE_END_WORD.search(word))

# %% a line and its speech


@dataclass(frozen=True)
class Line:
    """
    One thing the narrator says.
    """

    written: str
    """
    The line as the subtitles show it.
    """

    spoken: str = ""
    """
    The line as the voice says it, where that differs from how it is written; numbers
    are said the way people say them. Empty when the two agree.
    """

    @property
    def said(self) -> str:
        """
        What the voice is given to say.
        """
        return self.spoken or self.written


@dataclass(frozen=True)
class Speech:
    """
    A line spoken, as sound.
    """

    samples: np.ndarray
    """
    The sound, one channel, from minus one to one.
    """

    rate: int
    """
    Samples per second.
    """

    @property
    def duration(self) -> float:
        """
        How long it lasts, in seconds.
        """
        return len(self.samples) / self.rate


class Voice(Protocol):
    """
    Whatever turns a line into speech.
    """

    def speaks(self, text: str) -> Speech:
        """
        :param text: What to say.
        :return: It, said.
        """


@dataclass
class KokoroVoice:
    """
    The Kokoro speech model, run on this machine, one of its voices chosen.

    Every line is kept on disk once said, so a video is rebuilt with the very same
    speech.
    """

    voice: str = "af_heart"
    """
    Which of the model's voices speaks.
    """

    speed: float = 1.15
    """
    How fast it speaks, one being the model's own pace.
    """

    language: str = "en-us"
    """
    The language the text is read in.
    """

    model: Path = VOICE_DIRECTORY / "kokoro-v1.0.onnx"
    """
    The model's weights.
    """

    voices: Path = VOICE_DIRECTORY / "voices-v1.0.bin"
    """
    The model's voices.
    """

    cache: SceneCache = field(default_factory=lambda: SceneCache("narration"))
    """
    Where the lines said are kept.
    """

    def speaks(self, text: str) -> Speech:
        import soundfile

        kept = self.cache.directory / f"{self._key(text)}.wav"
        if not kept.exists():
            speech = self._synthesize(text)
            soundfile.write(kept, speech.samples, speech.rate)
        samples, rate = soundfile.read(kept, dtype="float32")
        return Speech(samples, rate)

    def _key(self, text: str) -> str:
        said = f"{self.voice}|{self.speed}|{self.language}|{text}"
        return hashlib.sha1(said.encode()).hexdigest()

    def _synthesize(self, text: str) -> Speech:
        from kokoro_onnx import Kokoro

        model = Kokoro(str(self.model), str(self.voices))
        samples, rate = model.create(text, voice=self.voice, speed=self.speed, lang=self.language)
        return Speech(samples.astype(np.float32), rate)


# %% a line placed in time


@dataclass(frozen=True)
class SubtitleCue:
    """
    One subtitle: a piece of a line, shown for a while.
    """

    start: float
    """
    When it appears, in seconds from the video's start.
    """

    end: float
    """
    When it goes.
    """

    text: str
    """
    What it shows.
    """

    def rows(self, characters_per_row: int) -> List[str]:
        """
        The text on one row where it fits, else on two as even as the words allow.

        :param characters_per_row: The most characters a row takes.
        """
        if len(self.text) <= characters_per_row:
            return [self.text]
        words = self.text.split()
        for cuts in _even_cuts(words, 2, prefer=_ends_a_clause):
            halves = _cut(words, cuts)
            if all(len(half) <= characters_per_row for half in halves):
                return halves
        return _packed(words, characters_per_row)


@dataclass(frozen=True)
class SpokenLine:
    """
    A line, said, and placed where it is heard.
    """

    line: Line
    """
    The line.
    """

    starts: float
    """
    When it is heard, in seconds from the video's start.
    """

    speech: Speech
    """
    The line as sound.
    """

    @property
    def ends(self) -> float:
        """
        When it has been said.
        """
        return self.starts + self.speech.duration

    def cues(self, room: Optional[SubtitleRoom] = None) -> List[SubtitleCue]:
        """
        The line cut into subtitles, each short enough for the room, each shown for its
        share of the speech by its share of the letters.

        :param room: How much text one subtitle may show; a player's one row if not
            given.
        """
        fitting = room if room is not None else SubtitleRoom(SUBTITLE_ROW, SUBTITLE_ROWS)
        pieces = self._pieces(fitting)
        letters = sum(len(piece) for piece in pieces)
        cues: List[SubtitleCue] = []
        start = self.starts
        for piece in pieces:
            end = start + self.speech.duration * len(piece) / letters
            cues.append(SubtitleCue(start, end, piece))
            start = end
        return cues

    def _pieces(self, room: SubtitleRoom) -> List[str]:
        """
        The written line cut into pieces that each fit the room: sentence by sentence,
        each cut into the fewest even parts that fit, at clause ends where one lies
        near enough, and short sentences joined where they fit together.
        """
        pieces: List[str] = []
        for sentence in SENTENCE_END.split(self.line.written):
            for part in room.evenly(sentence):
                if pieces and room.holds(pieces[-1] + " " + part):
                    pieces[-1] += " " + part
                else:
                    pieces.append(part)
        return pieces


@dataclass(frozen=True)
class SubtitleRoom:
    """
    How much text one subtitle may show: so many rows of so many characters.
    """

    characters_per_row: int
    """
    The most characters a player shows on one row.
    """

    rows: int
    """
    How many rows a subtitle may take.
    """

    def holds(self, text: str) -> bool:
        """
        :param text: A piece of text.
        :return: Whether it fits in the rows, broken between words.
        """
        return len(_packed(text.split(), self.characters_per_row)) <= self.rows

    def evenly(self, text: str) -> List[str]:
        """
        :param text: A piece of text.
        :return: It, as it is if it fits, else cut between words into the fewest parts
            that each fit, as even in length as the words allow, each cut moved to a
            clause end where one lies near.
        """
        words = text.split()
        if self.holds(text):
            return [text]
        for parts in range(2, len(words) + 1):
            for cuts in _even_cuts(words, parts, prefer=_ends_a_clause):
                cut = _cut(words, cuts)
                if all(self.holds(part) for part in cut):
                    return cut
        return words


BURNED_IN_ROOM = SubtitleRoom(characters_per_row=58, rows=2)
"""
How much a subtitle burned into the picture shows: two rows of the band the scenes keep
clear, the letters' size being the video's own, so that a whole clause is read at a
time rather than pieces that switch faster than they are read.
"""

CUTS_TRIED = 3
"""
How many places near each even cut are tried, nearest first, before one more part.
"""


def _even_cuts(
    words: Sequence[str], parts: int, prefer: Callable[[str], bool]
) -> Iterator[Tuple[int, ...]]:
    """
    :param words: Words, in order.
    :param parts: How many parts to cut them into.
    :param prefer: Which words a cut had better come after; such a word within a fifth
        of a part's length of where the cut would fall comes before any other.
    :return: The words a cut may come after, one per cut, likeliest set first.
    """
    ends = [sum(len(word) + 1 for word in words[: index + 1]) for index in range(len(words))]
    share = ends[-1] / parts
    choices: List[List[int]] = []
    for number in range(1, parts):
        target = share * number
        candidates = sorted(
            range(number - 1, len(words) - (parts - number)),
            key=lambda index: (
                not (prefer(words[index]) and abs(ends[index] - target) <= share / 5),
                abs(ends[index] - target),
            ),
        )
        choices.append(candidates[:CUTS_TRIED])
    for cuts in product(*choices):
        if all(earlier < later for earlier, later in zip(cuts, cuts[1:])):
            yield cuts


def _cut(words: Sequence[str], cuts: Sequence[int]) -> List[str]:
    """
    :param words: Words, in order.
    :param cuts: The words the parts end after, in order.
    :return: The parts.
    """
    pieces: List[str] = []
    begin = 0
    for cut in cuts:
        pieces.append(" ".join(words[begin : cut + 1]))
        begin = cut + 1
    pieces.append(" ".join(words[begin:]))
    return pieces


def _packed(words: Sequence[str], longest: int) -> List[str]:
    """
    :param words: Words, in order.
    :param longest: The most characters a piece takes.
    :return: The words packed into pieces no longer than that, in order.
    """
    pieces: List[str] = []
    for word in words:
        if pieces and len(pieces[-1]) + 1 + len(word) <= longest:
            pieces[-1] += " " + word
        else:
            pieces.append(word)
    return pieces


# %% every line, one after the other


@dataclass
class NarrationOverrun(DataclassException):
    """
    Raised when a line is still being said when the next starts, or when the video ends.
    """

    line: Line
    """
    The line cut off.
    """

    by: float
    """
    By how many seconds.
    """

    def error_message(self) -> str:
        return f'"{self.line.written[:40]}…" runs {self.by:.1f} s past what follows it'

    def suggest_correction(self) -> str:
        return "Shorten the line, or give the scenes it plays over more time."


@dataclass(frozen=True)
class Soundtrack:
    """
    The whole narration as one stretch of sound, silent where nothing is said.
    """

    samples: np.ndarray
    """
    The sound, one channel.
    """

    rate: int
    """
    Samples per second.
    """

    def written_to(self, path: Path) -> Path:
        """
        :param path: Where the wave file goes.
        :return: The path.
        """
        import soundfile

        soundfile.write(path, self.samples, self.rate)
        return path


@dataclass
class Narration:
    """
    Every line of the video, placed in time.
    """

    lines: List[SpokenLine]
    """
    The lines, in order.
    """

    def check(self, runs_for: float) -> None:
        """
        Refuse a line that runs into the next, or past the video's end.

        :param runs_for: How long the video lasts.
        :raises NarrationOverrun: For the first line that does.
        """
        for line, following in zip(self.lines, self.lines[1:]):
            if line.ends > following.starts:
                raise NarrationOverrun(line.line, line.ends - following.starts)
        if self.lines and self.lines[-1].ends > runs_for:
            raise NarrationOverrun(self.lines[-1].line, self.lines[-1].ends - runs_for)

    def soundtrack(self, runs_for: float) -> Soundtrack:
        """
        :param runs_for: How long the video lasts.
        :return: The lines laid where they start, on silence.
        """
        rate = self.lines[0].speech.rate if self.lines else 24000
        track = np.zeros(int(round(runs_for * rate)), dtype=np.float32)
        for line in self.lines:
            first = int(round(line.starts * rate))
            last = min(first + len(line.speech.samples), len(track))
            track[first:last] = line.speech.samples[: last - first]
        return Soundtrack(track, rate)

    def report(self, runs_for: float) -> str:
        """
        One row per line: when it starts, how long it is said, and the silence before
        the next line or the video's end (negative where it runs over).

        :param runs_for: How long the video lasts.
        """
        rows = []
        for line, next_start in zip(self.lines, [each.starts for each in self.lines[1:]] + [runs_for]):
            rows.append(
                f"{line.starts:6.1f} s  {line.speech.duration:5.1f} s said  "
                f"{next_start - line.ends:+6.1f} s free   {line.line.written[:60]}"
            )
        return "\n".join(rows)

    def cues(self, room: Optional[SubtitleRoom] = None) -> List[SubtitleCue]:
        """
        Every subtitle, in order.

        :param room: How much text one subtitle may show; a player's one row if not
            given.
        """
        return [cue for line in self.lines for cue in line.cues(room)]

    def srt(self) -> str:
        """
        The subtitles in the SubRip format every player reads.
        """
        return "".join(
            f"{number}\n{_timestamp(cue.start)} --> {_timestamp(cue.end)}\n{rows}\n\n"
            for number, cue in enumerate(self.cues(), start=1)
            for rows in ["\n".join(cue.rows(SUBTITLE_ROW))]
        )

    def written_to(self, path: Path) -> Path:
        """
        :param path: Where the SubRip file goes.
        :return: The path.
        """
        path.write_text(self.srt(), encoding="utf-8")
        return path


SUBTITLE_SIZE = 27
"""
The height of the letters of a subtitle burned into the picture, in pixels.
"""


@dataclass
class Subtitled(Timeline):
    """
    A timeline with its subtitles drawn into the band every scene keeps clear at the
    bottom of the picture, so they are part of the video itself.
    """

    cues: List[SubtitleCue] = field(default_factory=list)
    """
    The subtitles, in order, each fitting the room.
    """

    room: SubtitleRoom = BURNED_IN_ROOM
    """
    How much text one subtitle shows: the rows a cue is written on.
    """

    @classmethod
    def over(cls, timeline: Timeline, narration: Narration, room: SubtitleRoom = BURNED_IN_ROOM) -> Subtitled:
        """
        :param timeline: The timeline as it stands.
        :param narration: What is said over it, cut into subtitles that fit the room.
        :param room: How much text one subtitle shows.
        """
        return cls(timeline.scenes, timeline.frames_per_second, timeline.dissolve, cues=narration.cues(room), room=room)

    def cue_at(self, seconds: float) -> Optional[SubtitleCue]:
        """
        The subtitle shown at a moment, if one is.
        """
        return next((cue for cue in self.cues if cue.start <= seconds < cue.end), None)

    def frame_at(self, seconds: float) -> Frame:
        frame = super().frame_at(seconds)
        cue = self.cue_at(seconds)
        if cue is None:
            return frame
        resolution = Resolution.of(frame)
        middle = (resolution.stage_height + resolution.height) / 2
        return Typesetting(size=SUBTITLE_SIZE, color=Ink.TEXT.rgb).written(
            frame, "\n".join(cue.rows(self.room.characters_per_row)), (resolution.width / 2, middle), Anchor.CENTRE_MIDDLE
        )


def _timestamp(seconds: float) -> str:
    """
    :param seconds: A moment.
    :return: It as SubRip writes it, ``HH:MM:SS,mmm``.
    """
    milliseconds = int(round(seconds * 1000))
    hours, rest = divmod(milliseconds, 3_600_000)
    minutes, rest = divmod(rest, 60_000)
    whole, milliseconds = divmod(rest, 1000)
    return f"{hours:02d}:{minutes:02d}:{whole:02d},{milliseconds:03d}"


# %% the scenes with their lines


@dataclass
class NarratedScene:
    """
    A scene and the line that starts with it, if one does.
    """

    scene: Scene
    """
    The scene.
    """

    lines: Tuple[Line, ...] = ()
    """
    The lines that start with it, said one after the other, if any do.
    """

    delay: float = 0.0
    """
    Seconds into the scene the line starts, beyond the lead every line has.
    """

    runs_on: bool = False
    """
    Whether the line may run on into the scenes that follow instead of the scene
    growing to hold it; a close-up never grows, whatever this says.
    """


def starts_of(voice: Voice, lines: Sequence[Line], pause: float) -> List[float]:
    """
    Seconds after the first of some lines starts that each of them starts, said one
    after the other with a pause between: for a scene to time itself to its lines.

    :param voice: What says the lines.
    :param lines: The lines, in order.
    :param pause: Seconds between one line and the next.
    """
    starts: List[float] = []
    at = 0.0
    for line in lines:
        starts.append(at)
        at += voice.speaks(line.said).duration + pause
    return starts


@dataclass
class Storyboard:
    """
    The scenes in order, each with the line that starts with it.
    """

    narrated: List[NarratedScene]
    """
    The scenes.
    """

    tail: float = 0.6
    """
    Seconds a slide is held after its line has ended.
    """

    pause: float = 0.5
    """
    Seconds between two lines said over the same scene.
    """

    @property
    def scenes(self) -> List[Scene]:
        """
        The scenes alone, in order.
        """
        return [each.scene for each in self.narrated]

    def fitted_to(self, voice: Voice) -> None:
        """
        Grow every slide to hold the line that starts with it.

        :param voice: What says the lines.
        """
        for each in self.narrated:
            if not each.lines or each.runs_on or not hasattr(each.scene, "held_for"):
                continue
            said = sum(voice.speaks(line.said).duration for line in each.lines)
            needed = LEAD + each.delay + said + self.pause * (len(each.lines) - 1) + self.tail
            each.scene.held_for = max(each.scene.held_for, needed)

    def narrated_by(self, voice: Voice, dissolve: float) -> Narration:
        """
        The lines said and placed where their scenes start, as the timeline puts them.

        :param voice: What says the lines.
        :param dissolve: How long the scenes dissolve into one another.
        """
        spoken: List[SpokenLine] = []
        for each, start in zip(self.narrated, Timeline(self.scenes, dissolve=dissolve).starts()):
            at = start + LEAD + each.delay
            for line in each.lines:
                spoken.append(SpokenLine(line, at, voice.speaks(line.said)))
                at = spoken[-1].ends + self.pause
        return Narration(spoken)
