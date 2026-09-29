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

    def speaks(self, text: str) -> Speech:
        seconds = self.seconds_per_word * len(text.split())
        return Speech(
            np.full(int(seconds * self.rate), self.level, dtype=np.float32), self.rate
        )
