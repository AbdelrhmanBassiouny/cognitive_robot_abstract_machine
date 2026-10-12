"""
Voices for tests: they say every word in the same time, so a test knows how long any
line lasts without a speech model.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

import numpy as np
from typing_extensions import ClassVar

from cramcorder.speech import Speech


@dataclass
class EvenlyPacedVoice:
    """
    A voice whose every word lasts the same, sounding one steady level throughout.
    """

    time_per_word: timedelta = timedelta(seconds=0.5)
    """
    How long each word takes.
    """

    rate: int = 100
    """
    Samples per second of the speech.
    """

    level: float = 1.0
    """
    The value every sample holds.
    """

    def speaks(self, text: str, pace: float = 1.0) -> Speech:
        duration = self.time_per_word * len(text.split()) / pace
        return Speech(
            np.full(
                int(duration.total_seconds() * self.rate), self.level, dtype=np.float32
            ),
            self.rate,
        )


@dataclass
class ToneSpeechModel:
    """
    Stands in for the Kokoro speech model: it says every word as one steady tone lasting
    :attr:`TIME_PER_WORD` at its own speed, with the silence before and after that a
    speech model leaves.
    """

    RATE: ClassVar[int] = 1000
    """
    Samples per second the tone model speaks at.
    """

    TIME_PER_WORD: ClassVar[timedelta] = timedelta(seconds=0.5)
    """
    How long the tone model says each word at its own speed.
    """

    LEVEL: ClassVar[float] = 0.3
    """
    The value every sample of its tone holds.
    """

    SILENCE_BEFORE: ClassVar[timedelta] = timedelta(seconds=0.2)
    """
    The silence before the tone.
    """

    SILENCE_AFTER: ClassVar[timedelta] = timedelta(seconds=0.3)
    """
    The silence after the tone.
    """

    model: str
    """
    The weights it was given, unread.
    """

    voices: str
    """
    The voices it was given, unread.
    """

    def create(
        self, text: str, voice: str, speed: float, lang: str
    ) -> tuple[np.ndarray, int]:
        words = len(text.split())
        tone = np.full(
            int(self.TIME_PER_WORD.total_seconds() * words / speed * self.RATE),
            self.LEVEL,
            dtype=np.float32,
        )
        before = np.zeros(
            int(self.SILENCE_BEFORE.total_seconds() * self.RATE), dtype=np.float32
        )
        after = np.zeros(
            int(self.SILENCE_AFTER.total_seconds() * self.RATE), dtype=np.float32
        )
        return np.concatenate([before, tone, after]), self.RATE
