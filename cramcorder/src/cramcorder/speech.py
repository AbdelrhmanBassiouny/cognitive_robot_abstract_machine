"""
Speech as sound, and the voices that make it.

The lines are said once each and kept, so the soundtrack and the subtitles come from the
same speech and always agree with each other.
"""

from __future__ import annotations

import hashlib
import wave
from dataclasses import dataclass, field, replace
from datetime import timedelta
from pathlib import Path

import numpy as np
from typing_extensions import ClassVar, Protocol

from cramcorder.cache import SceneCache

# %% sound


@dataclass(frozen=True)
class Sound:
    """
    One channel of sound, kept as samples.
    """

    SAMPLE_WIDTH: ClassVar[int] = 2
    """
    Bytes a sample of a wave file takes: sixteen-bit sound, which every player reads.
    """

    samples: np.ndarray
    """
    The sound, one channel, from minus one to one.
    """

    rate: int
    """
    Samples per second.
    """

    @classmethod
    def loudest_sample(cls) -> int:
        """
        :return: The largest value a sixteen-bit sample holds, which a sound at full scale
            is written as.
        """
        return 2 ** (8 * cls.SAMPLE_WIDTH - 1) - 1

    @property
    def duration(self) -> timedelta:
        """
        How long it lasts.
        """
        return timedelta(seconds=len(self.samples) / self.rate)

    def written_to(self, path: Path) -> Path:
        """
        :param path: Where the wave file goes.
        :return: The path.
        """
        scaled = np.clip(self.samples, -1.0, 1.0) * self.loudest_sample()
        with wave.open(str(path), "wb") as written:
            written.setnchannels(1)
            written.setsampwidth(self.SAMPLE_WIDTH)
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
        samples = (
            np.frombuffer(frames, dtype="<i2").astype(np.float32) / cls.loudest_sample()
        )
        return cls(samples, rate)


@dataclass(frozen=True)
class Speech(Sound):
    """
    A line spoken, as sound.
    """

    def trimmed(
        self, silence_level: float, breath_before: timedelta, breath_after: timedelta
    ) -> Speech:
        """
        :param silence_level: The loudest a sample may be and still count as silence.
        :param breath_before: The quiet kept before the first sound, so its first word
            is not cut.
        :param breath_after: The quiet kept after the last sound: the natural tail of
            its last word.
        :return: The speech without the silence around it; all of it where it holds no
            sound.
        """
        loud = np.flatnonzero(np.abs(self.samples) > silence_level)
        if loud.size == 0:
            return self
        first = max(0, loud[0] - int(breath_before.total_seconds() * self.rate))
        after_last = min(
            len(self.samples),
            loud[-1] + 1 + int(breath_after.total_seconds() * self.rate),
        )
        return replace(self, samples=self.samples[first:after_last])

    def levelled(self, peak: float) -> Speech:
        """
        :param peak: The loudest sample the speech is scaled to, from zero to one.
        :return: The speech scaled so its loudest sample reaches the peak; silence as it
            is.
        """
        loudest = float(np.abs(self.samples).max(initial=0.0))
        if loudest == 0.0:
            return self
        return replace(self, samples=self.samples * (peak / loudest))


# %% voices


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
        default_factory=lambda: SceneCache.configured_root()
        / "voice"
        / "kokoro-v1.0.onnx"
    )
    """
    The model's weights.
    """

    voices: Path = field(
        default_factory=lambda: SceneCache.configured_root()
        / "voice"
        / "voices-v1.0.bin"
    )
    """
    The model's voices.
    """

    cache: SceneCache = field(default_factory=lambda: SceneCache("narration"))
    """
    Where the lines said are kept.
    """

    silence_level: float = 0.01
    """
    The loudest a sample may be and still count as silence around a spoken line.
    """

    breath_before: timedelta = timedelta(seconds=0.03)
    """
    The quiet kept before the first sound of a line, so its first word is not cut.
    """

    breath_after: timedelta = timedelta(seconds=0.12)
    """
    The quiet kept after the last sound of a line: the natural tail of its last word.
    """

    peak: float = 0.89
    """
    The loudest sample of every spoken line, so every line is said at one loudness and
    none clips.
    """

    def speaks(self, text: str, pace: float = 1.0) -> Speech:
        """
        :param text: What to say.
        :param pace: How fast, as a share of the voice's own speed.
        :return: It, said by the model the first time and read back from the cache
            after.
        """
        speed = self.speed * pace
        kept = self.cache.directory / f"{self._key(text, speed)}.wav"
        if not kept.exists():
            self._synthesize(text, speed).written_to(kept)
        return Speech.read_from(kept)

    def _key(self, text: str, speed: float) -> str:
        """
        :param text: What is said.
        :param speed: The model's speed it is said at.
        :return: What a line said at a speed is kept as; how the speech is trimmed and
            levelled is part of it, so changing that says every line again rather than
            reusing speech cut the old way.
        """
        said = (
            f"{self.voice}|{speed}|{self.language}|{self.silence_level}|"
            f"{self.breath_before.total_seconds()}|"
            f"{self.breath_after.total_seconds()}|{self.peak}|{text}"
        )
        return hashlib.sha1(said.encode()).hexdigest()

    def _synthesize(self, text: str, speed: float) -> Speech:
        """
        :param text: What to say.
        :param speed: The model's speed to say it at.
        :return: The line said by the model, trimmed and levelled.
        """
        # the speech model is an optional dependency, the ``video`` extra
        from kokoro_onnx import Kokoro

        model = Kokoro(str(self.model), str(self.voices))
        samples, rate = model.create(
            text, voice=self.voice, speed=speed, lang=self.language
        )
        return (
            Speech(samples.astype(np.float32), rate)
            .trimmed(self.silence_level, self.breath_before, self.breath_after)
            .levelled(self.peak)
        )
