"""
A voice for tests: it says every word in the same time, so a test knows how long any
line lasts without a speech model.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from experiments.video.narration import Speech


@dataclass
class EvenlyPacedVoice:
    """
    A voice whose every word lasts the same, sounding one steady level throughout.
    """

    seconds_per_word: float = 0.5
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
        seconds = self.seconds_per_word * len(text.split()) / pace
        return Speech(
            np.full(int(seconds * self.rate), self.level, dtype=np.float32), self.rate
        )


@dataclass
class ToneSpeechModel:
    """
    Stands in for the Kokoro speech model: it says every word as one steady tone lasting
    :data:`TONE_SECONDS_PER_WORD` at its own speed, with the silence before and after
    that a speech model leaves.
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
        tone = np.full(
            int(TONE_SECONDS_PER_WORD * len(text.split()) / speed * TONE_RATE),
            TONE_LEVEL,
            dtype=np.float32,
        )
        before = np.zeros(int(SILENCE_BEFORE * TONE_RATE), dtype=np.float32)
        after = np.zeros(int(SILENCE_AFTER * TONE_RATE), dtype=np.float32)
        return np.concatenate([before, tone, after]), TONE_RATE


TONE_RATE = 1000
"""
Samples per second the tone model speaks at.
"""

TONE_SECONDS_PER_WORD = 0.5
"""
How long the tone model says each word at its own speed.
"""

TONE_LEVEL = 0.3
"""
The value every sample of its tone holds.
"""

SILENCE_BEFORE = 0.2
"""
Seconds of silence before the tone.
"""

SILENCE_AFTER = 0.3
"""
Seconds of silence after the tone.
"""
