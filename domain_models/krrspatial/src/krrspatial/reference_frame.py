from __future__ import annotations

from krrood.patterns.interface import Interface

# %% frames that positions and directions are expressed in


class ReferenceFrame(Interface):
    """
    A frame that positions and directions are expressed in, such as a body of a robot or
    an image.
    """
