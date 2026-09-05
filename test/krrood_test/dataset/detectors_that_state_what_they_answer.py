"""
Detectors that state which looks they can answer, mimicking the shape a family of
perception detectors takes over a real sensor.

Each states its capability as an entity query language condition over the look it is
put, so rules choose among them by matching a look against what each one says. What a
condition may read is the whole situation a look is decided from: what is being sought,
what the world says about it, and what the sensor provides.
"""

from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import Optional

from krrood.entity_query_language.backends import PerceptionDetector
from krrood.entity_query_language.factories import ConditionType, not_

# %% the look a detector is put


@dataclass(frozen=True)
class PlaceToLookAt:
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
        return look.depth_is_returned


@dataclass(eq=False)
class ReadTheColors(PerceptionDetector[PlaceToLookAt]):
    """
    Reads colour alone, which is what is left when the sensor returns no depth.
    """

    def capability(self, look: PlaceToLookAt) -> ConditionType:
        return not_(look.depth_is_returned)
