from __future__ import annotations

from krrood.adapters.object_reference import IdentifiedObject
from krrood.patterns.interface import Interface

# %% what coordinates are given in


class Space(IdentifiedObject, Interface):
    """
    A coordinate system that the coordinates of a point are given in.

    Coordinates given in one space mean nothing in another, so values of two spaces are
    combined only after mapping one into the other.
    """


class ImageSpace(Space, Interface):
    """
    The coordinate system of an image: in pixels, from its top left corner, with ``x``
    along the columns and ``y`` down the rows.
    """
