"""
What is said over the video, and when.

A line of narration belongs to the scene it starts with and may run on into the scenes
that follow, as long as the next line has not started by then. A slide grows to hold its
line; a close-up keeps the length of what it shows, so a line that does not fit one is
refused rather than talked over.

The lines are synthesized once each and kept, so the soundtrack and the subtitles come
from the same speech and always agree with each other.
"""

from __future__ import annotations

import hashlib
import re
import wave
from abc import ABC, abstractmethod
from itertools import product
from dataclasses import dataclass, field, replace
from pathlib import Path

import numpy as np
from krrood.exceptions import DataclassException
from typing_extensions import (
    Callable,
    Iterator,
    List,
    Optional,
    Protocol,
    Sequence,
    Tuple,
)

from experiments.video.cache import SceneCache, configured_cache_directory
from experiments.video.canvas import (
    BODY_SIZE,
    FOOTAGE_TEXT,
    NEUTRAL_THEME,
    Anchor,
    Area,
    VideoTheme,
    Typesetting,
    darkened,
    shaded,
)
from experiments.video.timeline import Frame, HeldScene, Resolution, Scene, Timeline

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

VOICE_DIRECTORY_NAME = "voice"
"""
The folder of the cache the speech model and its voices lie in.
"""

SILENT_RATE = 24_000
"""
Samples per second of a soundtrack nothing is said over: the rate the Kokoro model
speaks at.
"""

SAMPLE_WIDTH = 2
"""
Bytes a sample of a wave file takes: sixteen-bit sound, which every player reads.
"""

LOUDEST_SAMPLE = 2 ** (8 * SAMPLE_WIDTH - 1) - 1
"""
The largest value a sixteen-bit sample holds, which a sound at full scale is written as.
"""

SILENCE_LEVEL = 0.01
"""
The loudest a sample may be and still count as silence around a spoken line.
"""

BREATH_BEFORE = 0.03
"""
Seconds of quiet kept before the first sound of a line, so its first word is not cut.
"""

BREATH_AFTER = 0.12
"""
Seconds of quiet kept after the last sound of a line: the natural tail of its last word.
"""

SPEECH_PEAK = 0.89
"""
The loudest sample of every spoken line, so every line is said at one loudness and none
clips.
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
    are said the way people say them.

    Empty when the two agree.
    """

    pace: float = 1.0
    """
    How fast the line is said, as a share of the voice's own speed: below one for a line
    the viewer needs time to follow.
    """

    @property
    def said(self) -> str:
        """
        What the voice is given to say.
        """
        return self.spoken or self.written

    def spoken_by(self, voice: Voice) -> Speech:
        """
        :param voice: What says the line.
        :return: The line, said at its pace.
        """
        return voice.speaks(self.said, self.pace)


@dataclass(frozen=True)
class Sound:
    """
    One channel of sound, kept as samples.
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

    def written_to(self, path: Path) -> Path:
        """
        :param path: Where the wave file goes.
        :return: The path.
        """
        scaled = np.clip(self.samples, -1.0, 1.0) * LOUDEST_SAMPLE
        with wave.open(str(path), "wb") as written:
            written.setnchannels(1)
            written.setsampwidth(SAMPLE_WIDTH)
            written.setframerate(self.rate)
            written.writeframes(np.round(scaled).astype("<i2").tobytes())
        return path

    @classmethod
    def read_from(cls, path: Path) -> Sound:
        """
        :param path: A wave file of one channel of sixteen-bit sound.
        :return: The sound it holds.
        """
        with wave.open(str(path), "rb") as read:
            rate = read.getframerate()
            frames = read.readframes(read.getnframes())
        samples = np.frombuffer(frames, dtype="<i2").astype(np.float32) / LOUDEST_SAMPLE
        return cls(samples, rate)


@dataclass(frozen=True)
class Speech(Sound):
    """
    A line spoken, as sound.
    """

    def trimmed(self) -> Speech:
        """
        :return: The speech without the silence around it, keeping a breath before its
            first sound and after its last; all of it where it holds no sound.
        """
        loud = np.flatnonzero(np.abs(self.samples) > SILENCE_LEVEL)
        if loud.size == 0:
            return self
        first = max(0, loud[0] - int(BREATH_BEFORE * self.rate))
        after_last = min(
            len(self.samples), loud[-1] + 1 + int(BREATH_AFTER * self.rate)
        )
        return replace(self, samples=self.samples[first:after_last])

    def levelled(self) -> Speech:
        """
        :return: The speech scaled so its loudest sample reaches :data:`SPEECH_PEAK`;
            silence as it is.
        """
        loudest = float(np.abs(self.samples).max(initial=0.0))
        if loudest == 0.0:
            return self
        return replace(self, samples=self.samples * (SPEECH_PEAK / loudest))


class Voice(Protocol):
    """
    Whatever turns a line into speech.
    """

    def speaks(self, text: str, pace: float = 1.0) -> Speech:
        """
        :param text: What to say.
        :param pace: How fast, as a share of the voice's own speed.
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

    model: Path = field(
        default_factory=lambda: configured_cache_directory()
        / VOICE_DIRECTORY_NAME
        / "kokoro-v1.0.onnx"
    )
    """
    The model's weights.
    """

    voices: Path = field(
        default_factory=lambda: configured_cache_directory()
        / VOICE_DIRECTORY_NAME
        / "voices-v1.0.bin"
    )
    """
    The model's voices.
    """

    cache: SceneCache = field(default_factory=lambda: SceneCache("narration"))
    """
    Where the lines said are kept.
    """

    def speaks(self, text: str, pace: float = 1.0) -> Speech:
        speed = self.speed * pace
        kept = self.cache.directory / f"{self._key(text, speed)}.wav"
        if not kept.exists():
            self._synthesize(text, speed).written_to(kept)
        return Speech.read_from(kept)

    def _key(self, text: str, speed: float) -> str:
        # what the speech is trimmed and levelled to is part of the key, so changing it
        # says every line again rather than reusing speech cut the old way
        said = (
            f"{self.voice}|{speed}|{self.language}|"
            f"{BREATH_BEFORE}|{BREATH_AFTER}|{SPEECH_PEAK}|{text}"
        )
        return hashlib.sha1(said.encode()).hexdigest()

    def _synthesize(self, text: str, speed: float) -> Speech:
        # the speech model is an optional dependency, the ``video`` extra
        from kokoro_onnx import Kokoro

        model = Kokoro(str(self.model), str(self.voices))
        samples, rate = model.create(
            text, voice=self.voice, speed=speed, lang=self.language
        )
        return Speech(samples.astype(np.float32), rate).trimmed().levelled()


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
        fitting = (
            room if room is not None else SubtitleRoom(SUBTITLE_ROW, SUBTITLE_ROWS)
        )
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
        each cut into the fewest even parts that fit, at clause ends where one lies near
        enough, and short sentences joined where they fit together.
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


BURNED_IN_ROOM = SubtitleRoom(characters_per_row=72, rows=2)
"""
How much a subtitle burned into the picture shows: two rows of the band the scenes keep
clear, the letters' size being the video's own, so that a whole clause is read at a time
rather than pieces that switch faster than they are read; the rows are as wide as the
longest sentence said whole needs.
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
    ends = [
        sum(len(word) + 1 for word in words[: index + 1]) for index in range(len(words))
    ]
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
class Soundtrack(Sound):
    """
    The whole narration as one stretch of sound, silent where nothing is said.
    """


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
        rate = self.lines[0].speech.rate if self.lines else SILENT_RATE
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
        for line, next_start in zip(
            self.lines, [each.starts for each in self.lines[1:]] + [runs_for]
        ):
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


CAPTION_TOP = 12
"""
Pixels under the stage the first row of a caption hangs from: the rows keep one baseline
whether one or two are written.
"""

CAPTION_ROW = 38
"""
Pixels from one caption row to the next.
"""

PAGE_LIKENESS = 20
"""
How far the band's mean colour may lie from the page's, per channel, for the band to be
the page rather than footage.
"""

BAND_SHADE = 0.72
"""
How dark the band over footage is shaded at its bottom.
"""

BOX_SHADE = 0.66
"""
How dark the box behind a boxed caption is shaded.
"""

BOX_PADDING = 25
"""
Pixels between a boxed caption's rows and the sides of its box.
"""

BOX_PADDING_ABOVE_AND_BELOW = 14
"""
Pixels between a boxed caption's rows and the top and bottom of its box.
"""

BOX_CORNER_RADIUS = 11
"""
Pixels the corners of a caption's box are rounded by.
"""

BOX_MARGIN = 20
"""
Pixels between a caption's box and the bottom of the frame.
"""


@dataclass
class CaptionStyle(ABC):
    """
    How the rows of a subtitle are drawn into a frame.
    """

    @abstractmethod
    def captioned(self, frame: Frame, rows: Sequence[str]) -> Frame:
        """
        :param frame: The frame.
        :param rows: The rows of the subtitle, at most two.
        :return: A copy of the frame with the rows written in.
        """


@dataclass
class BandCaption(CaptionStyle):
    """
    Rows written in the band every scene keeps clear at the bottom of the picture, from
    one fixed baseline: in the theme's text colour on its page, and white on a band
    shaded towards black wherever footage fills the frame.
    """

    theme: VideoTheme = NEUTRAL_THEME
    """
    The page the band is told apart from footage by, and the colour written on it.
    """

    def captioned(self, frame: Frame, rows: Sequence[str]) -> Frame:
        resolution = Resolution.of(frame)
        band = Area(
            0,
            resolution.stage_height,
            resolution.width,
            resolution.height - resolution.stage_height,
        )
        on_page = self.is_page(frame[int(band.y) :])
        if not on_page:
            frame = darkened(
                frame,
                Area(
                    0,
                    band.y - CAPTION_TOP * 2,
                    resolution.width,
                    band.height + CAPTION_TOP * 2,
                ),
                BAND_SHADE,
            )
        lettering = Typesetting(
            size=BODY_SIZE,
            color=self.theme.text if on_page else FOOTAGE_TEXT,
            typeface=self.theme.typeface,
        )
        for number, row in enumerate(rows):
            frame = lettering.written(
                frame,
                row,
                (resolution.width / 2, band.y + CAPTION_TOP + number * CAPTION_ROW),
                Anchor.CENTRE_TOP,
            )
        return frame

    def is_page(self, band: Frame) -> bool:
        """
        :param band: The band of a frame.
        :return: Whether it is the theme's page rather than footage.
        """
        mean = band.reshape(-1, 3).mean(axis=0)
        return bool(np.abs(mean - np.array(self.theme.page)).max() <= PAGE_LIKENESS)


@dataclass
class BoxedCaption(CaptionStyle):
    """
    Rows written in white on a box shaded towards black, centred over the bottom of the
    picture, so they read on any scene alike.
    """

    def captioned(self, frame: Frame, rows: Sequence[str]) -> Frame:
        resolution = Resolution.of(frame)
        lettering = Typesetting(size=BODY_SIZE, color=FOOTAGE_TEXT)
        width = max(lettering.width_of(row) for row in rows) + 2 * BOX_PADDING
        height = (
            BODY_SIZE + (len(rows) - 1) * CAPTION_ROW + 2 * BOX_PADDING_ABOVE_AND_BELOW
        )
        box = Area(
            (resolution.width - width) / 2,
            resolution.height - BOX_MARGIN - height,
            width,
            height,
        )
        frame = shaded(frame, box, BOX_SHADE, BOX_CORNER_RADIUS)
        for number, row in enumerate(rows):
            frame = lettering.written(
                frame,
                row,
                (
                    resolution.width / 2,
                    box.y + BOX_PADDING_ABOVE_AND_BELOW + number * CAPTION_ROW,
                ),
                Anchor.CENTRE_TOP,
            )
        return frame


@dataclass
class Subtitled(Timeline):
    """
    A timeline with its captions drawn into the picture, so they are part of the video
    itself.
    """

    cues: List[SubtitleCue] = field(default_factory=list)
    """
    The subtitles, in order, each fitting the room.
    """

    room: SubtitleRoom = BURNED_IN_ROOM
    """
    How much text one subtitle shows: the rows a cue is written on.
    """

    style: CaptionStyle = field(default_factory=BandCaption)
    """
    How a cue's rows are drawn.
    """

    @classmethod
    def over(
        cls,
        timeline: Timeline,
        narration: Narration,
        room: SubtitleRoom = BURNED_IN_ROOM,
        style: Optional[CaptionStyle] = None,
    ) -> Subtitled:
        """
        :param timeline: The timeline as it stands, its overlays kept.
        :param narration: What is said over it, cut into subtitles that fit the room.
        :param room: How much text one subtitle shows.
        :param style: How a cue's rows are drawn; in the band if not given.
        """
        return cls(
            timeline.scenes,
            timeline.frames_per_second,
            timeline.dissolve,
            timeline.overlays,
            cues=narration.cues(room),
            room=room,
            style=style if style is not None else BandCaption(),
        )

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
        return self.style.captioned(frame, cue.rows(self.room.characters_per_row))


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

    waits: Tuple[float, ...] = ()
    """
    Seconds each line after the first waits beyond the pause, for what it speaks of to
    come up; nothing for every line to follow the one before at once.
    """

    runs_on: bool = False
    """
    Whether the line may run on into the scenes that follow instead of the scene growing
    to hold it; a close-up never grows, whatever this says.
    """

    def wait_before(self, number: int) -> float:
        """
        :param number: Which of the lines, from zero.
        :return: Seconds it waits beyond the pause after the line before it.
        """
        return self.waits[number - 1] if 0 < number <= len(self.waits) else 0.0


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
        at += line.spoken_by(voice).duration + pause
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
        Grow every held scene to hold the lines that start with it.

        :param voice: What says the lines.
        """
        for each in self.narrated:
            if not each.lines or each.runs_on or not isinstance(each.scene, HeldScene):
                continue
            said = sum(line.spoken_by(voice).duration for line in each.lines)
            needed = (
                LEAD
                + each.delay
                + said
                + self.pause * (len(each.lines) - 1)
                + sum(each.waits)
                + self.tail
            )
            each.scene.held_for = max(each.scene.held_for, needed)

    def narrated_by(self, voice: Voice, dissolve: float) -> Narration:
        """
        The lines said and placed where their scenes start, as the timeline puts them.

        :param voice: What says the lines.
        :param dissolve: How long the scenes dissolve into one another.
        """
        spoken: List[SpokenLine] = []
        for each, start in zip(
            self.narrated, Timeline(self.scenes, dissolve=dissolve).starts()
        ):
            at = start + LEAD + each.delay
            for number, line in enumerate(each.lines):
                spoken.append(
                    SpokenLine(
                        line, at + each.wait_before(number), line.spoken_by(voice)
                    )
                )
                at = spoken[-1].ends + self.pause
        return Narration(spoken)
