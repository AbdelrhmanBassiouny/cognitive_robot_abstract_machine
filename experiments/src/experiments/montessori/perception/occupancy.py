"""
One physical thing, one detection.

A look at the scene rectifies the same camera frame onto every surface in turn, so one
thing standing on the upper of two surfaces is read twice: once at its own footprint on
the surface it rests on, and once on the surface below, in the patch of it the thing
stands in front of. The second reading is what the lower surface's own pass reports, and
nothing in a per-surface search rules it out -- the parallax that displaces it is
exactly what carries its centre clear of the outline that would have caught it.

Both readings are one thing said twice about one place, so this is where a place is
decided. A place is the space something takes up rather than the point at its centre,
and a raised thing takes up the stretch of the surface below it that it keeps the camera
from seeing as well as the space it physically stands in.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np
from typing_extensions import List, Self

from experiments.montessori.perception.detections import (
    MontessoriDetection,
    DetectedMontessoriShape,
)
from experiments.montessori.perception.exceptions import NothingIsHiddenFromBelow
from experiments.montessori.perception.explanations import CompetingExplanations

# %% the space one thing takes up

OUTLINE_UNIT = 0.001
"""
The unit, in metres, an outline is measured in to be laid over another.

OpenCV's convex intersection holds to a tolerance of its own rather than to one taken
from what it is handed, and answers that two outlines share no ground at all once the
step from one of their corners to the next falls below about four thousandths of a unit.
A cylinder's rectified outline is read at scores of points around a fourteen millimetre
radius, so in metres its steps are that small and two readings of one cylinder a
millimetre apart are measured to stand in different places. In millimetres they are
measured to share what they plainly share.
"""


@dataclass(frozen=True)
class OccupiedVolume:
    """
    The space one thing takes up: the outline it covers, and how far it reaches above
    the surface it rests on.
    """

    outline: np.ndarray
    """
    The outline itself, as ``(n, 2)`` world-frame ``(x, y)`` points.
    """

    bottom: float
    """
    Height of the surface it rests on, in metres.
    """

    top: float
    """
    Height of its own topmost surface, in metres.
    """

    @classmethod
    def of(cls, detection: MontessoriDetection) -> Self:
        """
        The space a detection takes up.

        :param detection: The detection to measure.
        """
        return cls(
            outline=detection.outline,
            bottom=detection.surface_height,
            top=detection.top_height,
        )

    @property
    def area(self) -> float:
        """
        Area the outline encloses, in square metres.
        """
        return float(cv2.contourArea(self._polygon)) * OUTLINE_UNIT**2

    def shared_area(self, other: OccupiedVolume) -> float:
        """
        Area the two outlines both cover, in square metres.

        :param other: The volume to measure against.
        """
        shared, _ = cv2.intersectConvexConvex(self._polygon, other._polygon)
        return float(shared) * OUTLINE_UNIT**2

    def overlaps(self, other: OccupiedVolume) -> bool:
        """
        Whether the two are one place rather than two.

        Two solid things cannot stand in one another, so any shared ground at heights
        that meet is one thing read twice. Heights that do not meet are one thing above
        another, which is what a piece resting on a surface does to that surface.

        :param other: The volume to measure against.
        """
        if self.bottom >= other.top or other.bottom >= self.top:
            return False
        return self.shared_area(other) > 0.0

    def hides(self, plane_height: float, seen_from: np.ndarray) -> Self:
        """
        The space below this one that this thing keeps a camera from seeing, together
        with the space it stands in itself.

        A camera looking down at a raised thing sees it against the surface below, and a
        rectification onto that lower surface therefore places it there. Where it lands
        is this outline pushed away from the camera onto the lower plane, so that is the
        stretch of the lower surface no detection may claim to be resting on.

        :param plane_height: Height of the surface being hidden, in metres.
        :param seen_from: Where the camera stands, as world-frame ``(x, y, z)``.
        :raises NothingIsHiddenFromBelow: If the camera does not stand above this thing.
        """
        if seen_from[2] <= self.top:
            raise NothingIsHiddenFromBelow(
                camera_height=float(seen_from[2]), top_height=self.top
            )
        reach = (plane_height - seen_from[2]) / (self.top - seen_from[2])
        against_the_lower_plane = seen_from[:2] + (self.outline - seen_from[:2]) * reach
        outline = cv2.convexHull(
            np.vstack([self.outline, against_the_lower_plane]).astype(np.float32)
        )
        return type(self)(
            outline=outline.reshape(-1, 2).astype(float),
            bottom=plane_height,
            top=self.bottom,
        )

    @property
    def _polygon(self) -> np.ndarray:
        """
        The outline in the shape OpenCV's polygon operations take, and in the unit they
        are answered reliably in.
        """
        return (
            (np.asarray(self.outline, dtype=float) / OUTLINE_UNIT)
            .astype(np.float32)
            .reshape(-1, 1, 2)
        )


# %% who holds which place


@dataclass
class Occupancy:
    """
    The places one look has already given away, and the rule that gives them.
    """

    taken: List[OccupiedVolume] = field(default_factory=list)
    """
    The places already held, in the order they were claimed.
    """

    explanations: CompetingExplanations = field(default_factory=CompetingExplanations)
    """
    How much better one account of a place must be than the next before it is reported.

    The same rule that decides whether a fit is reported at all decides which of two
    fits claiming one place is kept, so a place and a report are settled by one
    comparison rather than by two filters run in sequence on two different quantities.
    """

    def claim(self, volume: OccupiedVolume) -> bool:
        """
        Give a place to whatever asks for it, unless something already holds it.

        :param volume: The space asked for.
        :return: Whether the place was free, and is now held.
        """
        if any(volume.overlaps(held) for held in self.taken):
            return False
        self.taken.append(volume)
        return True

    def keep_one_detection_per_place(
        self, detections: List[DetectedMontessoriShape]
    ) -> List[DetectedMontessoriShape]:
        """
        The detections that each stand somewhere nothing else does.

        Places go to the account that explains its own place best, and one is given away
        only where the reading claiming it names something else and explains it as well:
        two readings that disagree about what stands somewhere, neither of which the
        picture prefers, leave that place unexplained, so neither is reported. Two that
        name the same thing are that thing read twice, and the second confirms the first
        rather than contesting it.

        :param detections: Everything the look found, in the order it found it.
        :return: Those of them left, in the order they were offered.
        """
        kept: List[DetectedMontessoriShape] = []
        volumes: List[OccupiedVolume] = []
        for detection in sorted(
            detections,
            key=lambda found: found.explanation.strength,
            reverse=True,
        ):
            volume = OccupiedVolume.of(detection)
            if any(volume.overlaps(held) for held in self.taken):
                continue
            claimants = [
                index for index, held in enumerate(volumes) if volume.overlaps(held)
            ]
            if claimants:
                self._settle_a_contested_place(detection, claimants, kept, volumes)
                continue
            kept.append(detection)
            volumes.append(volume)
        return [detection for detection in detections if detection in kept]

    def _settle_a_contested_place(
        self,
        detection: DetectedMontessoriShape,
        claimants: List[int],
        kept: List[DetectedMontessoriShape],
        volumes: List[OccupiedVolume],
    ) -> None:
        """
        Give up a place already held where the reading now claiming it names something
        else and the holder does not clearly explain the place better.

        The claimant is never reported either way: it was offered the place second
        because it explains it less well, so the question is only whether the holder
        keeps it. It keeps it against a reading that names what it names, because a
        second reading of one thing is that thing read again -- which is what two ways
        of looking do on a picture clear enough for both to be right, and there is
        nothing there for a lead to settle. What costs the holder its place is a reading
        that says something else stands there and explains the place as well as it does.

        :param detection: The reading now claiming the place.
        :param claimants: Where in *kept* the readings already holding it stand.
        :param kept: The readings holding a place, which this may shorten.
        :param volumes: The places they hold, kept alongside them.
        """
        for index in reversed(claimants):
            if kept[index].category is detection.category:
                continue
            if not self.explanations.leads(
                kept[index].explanation, detection.explanation
            ):
                kept.pop(index)
                volumes.pop(index)
