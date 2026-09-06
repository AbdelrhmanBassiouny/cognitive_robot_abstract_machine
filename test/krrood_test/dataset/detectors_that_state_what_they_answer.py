"""
Detectors that state which looks they can answer, mimicking the shape a family of
perception detectors takes over a real sensor.

Each states its capability as an entity query language condition over the look it is
put, so rules choose among them by matching a look against what each one says. What a
condition may read is the whole situation a look is decided from: what is being sought,
what the world says about it, and what the sensor provides.

Two families of rules choose among them: one whose detectors already tell themselves
apart, and one whose detectors do not, so the rules have to say where each is worth
running.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from typing_extensions import List, Optional

from krrood.entity_query_language.backends import (
    DetectorChoice,
    Look,
    PerceptionDetector,
)
from krrood.entity_query_language.factories import ConditionType, a, not_
from krrood.entity_query_language.query.match import Match
from krrood.entity_query_language.rdr.rule_tree import StatedRule
from krrood.exceptions import DataclassException

# %% the look a detector is put


@dataclass(frozen=True)
class PlaceToLookAt(Look):
    """
    One place a look could be taken at, and what the sensor offers there.
    """

    place: str
    """
    What the world calls the place being looked at.
    """

    depth_is_returned: bool = True
    """
    Whether the sensor answers with a depth image as well as a colour one.
    """

    detector: Optional[PerceptionDetector] = None
    """
    Which detector answers a look here, left open for rules to work out.
    """


# %% two detectors, telling themselves apart by what the sensor provides


@dataclass(eq=False)
class MeasureTheDepth(PerceptionDetector[PlaceToLookAt]):
    """
    Reads how far away things stand, so it answers a look only where the sensor returns
    depth.
    """

    def capability(self, look: PlaceToLookAt) -> ConditionType:
        return look.depth_is_returned == True  # noqa: E712 - a stated condition


@dataclass(eq=False)
class ReadTheColors(PerceptionDetector[PlaceToLookAt]):
    """
    Reads colour alone, which is what is left when the sensor returns no depth.
    """

    def capability(self, look: PlaceToLookAt) -> ConditionType:
        return not_(look.depth_is_returned == True)  # noqa: E712 - a stated condition


@dataclass(eq=False)
class CountTheEdges(PerceptionDetector[PlaceToLookAt]):
    """
    Reads outlines, which every picture carries, so it answers a look anywhere the world
    has a name for -- including the places the depth measurement also answers.
    """

    def capability(self, look: PlaceToLookAt) -> ConditionType:
        return look.place != ""


# %% what no detector answers


@dataclass
class NoDetectorAnswersThePlace(DataclassException):
    """
    Raised when no rule reaches a look, so nothing would be run for it.
    """

    place: str
    """
    What the world calls the place that was looked at.
    """

    def error_message(self) -> str:
        return f"No detector answers a look at {self.place}."

    def suggest_correction(self) -> str:
        return "State the detector that answers a look there."


# %% rules choosing among them


@dataclass
class WhereToLookRules(DetectorChoice[PlaceToLookAt]):
    """
    Rules whose detectors already tell themselves apart, so each rule is the detector's
    own capability and nothing is added to it.
    """

    depth: MeasureTheDepth = field(default_factory=MeasureTheDepth)
    """
    Answers a look where the sensor returns depth.
    """

    colors: ReadTheColors = field(default_factory=ReadTheColors)
    """
    Answers a look where it does not.
    """

    def underspecified_look(self) -> Match:
        return a(PlaceToLookAt)(detector=...)

    def rules_stated_at_the_start(self) -> List[StatedRule]:
        return [
            StatedRule(detector.capability(self.look), detector)
            for detector in (self.depth, self.colors)
        ]

    def nothing_answers(self, look: PlaceToLookAt) -> Exception:
        return NoDetectorAnswersThePlace(look.place)


@dataclass
class WhereEachDetectorIsWorthItsCostRules(DetectorChoice[PlaceToLookAt]):
    """
    Rules whose two detectors both answer a look at a named place with depth, so a
    capability leaves the choice open and the rules' own knowledge of where each is
    worth running is what settles it.
    """

    edges: CountTheEdges = field(default_factory=CountTheEdges)
    """
    The general answer, which needs no situation of its own.
    """

    depth: MeasureTheDepth = field(default_factory=MeasureTheDepth)
    """
    Preferred wherever a rule was stated for the place being looked at.
    """

    def underspecified_look(self) -> Match:
        return a(PlaceToLookAt)(detector=...)

    def rules_stated_at_the_start(self) -> List[StatedRule]:
        return [StatedRule(self.edges.capability(self.look), self.edges)]

    def nothing_answers(self, look: PlaceToLookAt) -> Exception:
        return NoDetectorAnswersThePlace(look.place)

    def situation_answered_by(
        self,
        detector: PerceptionDetector[PlaceToLookAt],
        look: PlaceToLookAt,
        example: PlaceToLookAt,
    ) -> Optional[ConditionType]:
        if detector is self.edges:
            return None
        return look.place == example.place
