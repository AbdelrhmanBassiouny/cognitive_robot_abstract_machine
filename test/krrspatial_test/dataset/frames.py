from __future__ import annotations

from dataclasses import dataclass

from krrspatial.reference_frame import ReferenceFrame

# %% frames told apart by name


@dataclass
class NamedFrame(ReferenceFrame):
    """
    A reference frame that only has a name.
    """

    name: str
    """
    What the frame is called.
    """
