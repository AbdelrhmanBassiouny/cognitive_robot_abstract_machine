from __future__ import annotations

from krrood.patterns.interface import Interface

# %% sets of points and their geometry


class Space(Interface):
    """
    A set of points with a geometry, charted by any number of coordinate systems.

    Coordinates in two coordinate systems of one space convert into each other; points
    of two spaces relate only through a map between the spaces, such as a camera.
    """


class EuclideanSpace(Space, Interface):
    """
    Physical space, in metres; its coordinate systems are reference frames, related by
    rigid transforms, which keep distances and angles.
    """
