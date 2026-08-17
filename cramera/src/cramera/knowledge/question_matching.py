"""
Recognizing which ready-made query a natural-language question is asking.

A spoken (or typed) question is free text, and the panel can only run the presets it
has. The matcher compares the text against each preset's wording — the verbalization of
its query and the label on its button — and either names the preset worth running or
says that nothing on offer answers the question.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from rapidfuzz import fuzz, utils
from typing_extensions import Any, Dict, List, Optional

from cramera.knowledge.presets import Preset
from cramera.payload import CrameraPayload

MINIMUM_SIMILARITY = 70.0
"""
Similarity (0–100) below which no preset counts as being what the question asked.

Calibrated against :func:`rapidfuzz.fuzz.token_set_ratio`: honest paraphrases of a
preset's wording score in the high 80s and above, while unrelated questions stay
around 60 and below.
"""

UNMATCHED_QUESTION_REPLY = "Sorry, I cannot answer that question."
"""
The reply shown for a question no ready-made query matches.
"""


@dataclass(kw_only=True)
class QuestionMatchResult(CrameraPayload):
    """
    The outcome of asking a natural-language question: the preset recognized as that
    question, or the reply that nothing on offer answers it.
    """

    preset: Optional[Preset]
    """
    The ready-made query recognized as the asked question, or None when none was
    similar enough.
    """

    similarity: float
    """
    Similarity (0–100) between the asked question and the closest preset's wording.
    """

    @property
    def matched(self) -> bool:
        """
        Whether a preset was recognized as the asked question.
        """
        return self.preset is not None

    def to_payload(self) -> Dict[str, Any]:
        """
        The JSON-serializable shape the panel's voice consumer reads.
        """
        if self.preset is None:
            return {
                "ok": self.ok,
                "matched": False,
                "similarity": self.similarity,
                "reply": UNMATCHED_QUESTION_REPLY,
            }
        return {
            "ok": self.ok,
            "matched": True,
            "similarity": self.similarity,
            "preset": asdict(self.preset),
        }


@dataclass
class QuestionMatcher:
    """
    Recognizes which of the presets on offer a natural-language question is asking.
    """

    presets: List[Preset]
    """
    The ready-made queries on offer, each worded as well as its source knows how.
    """

    minimum_similarity: float = MINIMUM_SIMILARITY
    """
    Similarity (0–100) below which a question counts as unanswerable.
    """

    def match(self, text: str) -> QuestionMatchResult:
        """
        The preset most similar to the asked question, or the no-match outcome.

        :param text: The question as asked, in natural language.
        """
        best: Optional[Preset] = None
        best_similarity = 0.0
        for preset in self.presets:
            similarity = self._similarity(text, preset)
            if similarity > best_similarity:
                best, best_similarity = preset, similarity
        if best is None or best_similarity < self.minimum_similarity:
            return QuestionMatchResult(preset=None, similarity=best_similarity)
        return QuestionMatchResult(preset=best, similarity=best_similarity)

    @staticmethod
    def _similarity(text: str, preset: Preset) -> float:
        """
        Similarity (0–100) between the asked question and one preset's wording.

        A preset is worded twice — its query's verbalization and the label on its
        button — and being recognized by either is being recognized.

        Scored by word overlap (:func:`rapidfuzz.fuzz.token_set_ratio`), so word
        order and polite framing around the words that matter do not count against a
        question.

        :param text: The question as asked, in natural language.
        :param preset: The preset whose wordings the question is compared against.
        """
        wordings = [preset.text]
        if preset.verbalization is not None:
            wordings.append(preset.verbalization.text)
        return max(
            fuzz.token_set_ratio(text, wording, processor=utils.default_process)
            for wording in wordings
        )
