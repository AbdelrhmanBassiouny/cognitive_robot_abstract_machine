"""
What perception expects to find, and where it believes it to be.

A detector that only ever fits what colour segmentation isolated can only find what
colour separates. So a look is described instead by the things it expects and the places
it believes them to be in, and finding one is evaluating that expectation against the
picture. Colour is then one of the things that suggests a place, and evidence for what
stands there, rather than the gate everything has to pass to be looked at at all.

Where an expectation comes from is what makes a look knowledge-directed: the picture
suggests some, the world the robot already keeps suggests others, and whatever asked for
the look supplies the rest.
"""

from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import List, Optional, Self, Tuple

from experiments.montessori.pieces import (
    HUE_TOLERANCE,
    KNOWN_PIECES,
    KnownPiece,
    hue_distance,
)
from experiments.montessori.planar_geometry import PlanarPoint
from krrood.patterns.belief_source import BeliefSource
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName

# %% how sure a belief is when it says nothing about how sure it is

SEED_REACH = 0.024
"""
How far, in metres, a thing may be found from a place believed with no measure of how
sure that belief is.

A piece seen together with its own reflection is believed to be at the middle of the
two, which on this table is up to fifteen millimetres from the piece itself, and a piece
the world places has drifted about as far from where the world puts it. A belief that
carries its own measure of how sure it is states its own reach instead.
"""

# %% which way a thing is believed to be turned


@dataclass(frozen=True)
class YawInterval:
    """
    The turns about the world frame's z-axis a thing is believed to be within.
    """

    center: float
    """
    The turn believed most likely, in radians.
    """

    spread: float
    """
    How far either side of :attr:`center` the belief reaches, in radians.
    """

    def holds(self, yaw: float) -> bool:
        """
        Whether a turn is one this belief allows.

        :param yaw: The turn to check, in radians.
        """
        return abs(yaw - self.center) <= self.spread

    def turns(self, step: float) -> List[float]:
        """
        The turns worth trying inside this interval, which always includes its own
        centre.

        :param step: How finely to turn, in radians.
        """
        steps = int(self.spread / step)
        return [self.center + turn * step for turn in range(-steps, steps + 1)]


# %% where a thing is believed to be


@dataclass(frozen=True)
class BelievedPlace:
    """
    A stretch of one named surface, and the turns a thing standing in it may be at.

    This is what a search is aimed at rather than a bare position: how far it reaches
    and which turns it holds are what decide how widely to look, so a place known
    closely is searched finely and one known loosely is searched the way an unguided
    pass would be.
    """

    surface: PrefixedName
    """
    What the world calls the surface the thing is believed to be resting on.
    """

    center: PlanarPoint
    """
    Where on the surface's own plane it is believed to be.
    """

    radius: float = SEED_REACH
    """
    How far, in metres, from :attr:`center` it may actually be.
    """

    yaw: Optional[YawInterval] = None
    """
    Which way it is believed to be turned, or None where nothing is believed about it
    and every turn it can be told apart at is worth trying.
    """


# %% one thing expected at one place


@dataclass(frozen=True)
class PieceHypothesis:
    """
    That one of a set of known pieces stands at a believed place, and what suggested it.

    A look reports the hypothesis each detection came from, so a result says not only
    what was recognised but why it was looked for there.
    """

    place: BelievedPlace
    """
    Where the piece is believed to be.
    """

    source: BeliefSource
    """
    What suggested it: the detector that saw a colour, the world that places the piece,
    or whoever asked for the look.
    """

    candidates: Tuple[KnownPiece, ...] = KNOWN_PIECES
    """
    The pieces it may turn out to be, narrowest first where the belief names one.
    """

    hue: Optional[int] = None
    """
    The colour measured where the belief came from, as OpenCV reports hue, or None where
    there was none to read.

    Evidence for the hypothesis rather than a condition on it: it is what narrowed
    :attr:`candidates` when a colour is what suggested the place, and it is kept so a
    reader can see that.
    """

    @classmethod
    def of_color(
        cls,
        place: BelievedPlace,
        hue: Optional[int],
        source: BeliefSource,
        candidates: Tuple[KnownPiece, ...] = KNOWN_PIECES,
        hue_tolerance: int = HUE_TOLERANCE,
    ) -> Self:
        """
        The hypothesis a colour seen at a place suggests, expecting the pieces that wear
        that colour.

        :param place: Where the colour was seen.
        :param hue: The colour measured there, or None where there was none to read, in
            which case every candidate stands.
        :param source: What read the colour.
        :param candidates: The pieces that may be found at all.
        :param hue_tolerance: How far a measured colour may sit from a piece's own
            before that piece is ruled out.
        """
        return cls(
            place=place,
            source=source,
            candidates=tuple(
                candidate
                for candidate in candidates
                if hue is None or hue_distance(hue, candidate.hue) <= hue_tolerance
            ),
            hue=hue,
        )

    def turns_of(self, piece: KnownPiece, step: float) -> List[float]:
        """
        The turns worth trying for one piece believed to be here.

        A believed interval is the whole of what is tried; with nothing believed, one of
        the piece's own rotation periods about zero is, which holds every orientation it
        can be told apart in.

        :param piece: The piece to turn.
        :param step: How finely to turn it, in radians.
        """
        if self.place.yaw is not None:
            return self.place.yaw.turns(step)
        if piece.rotation_period is None:
            return [0.0]
        return YawInterval(center=0.0, spread=piece.rotation_period / 2).turns(step)
