"""
An action stated partly over things nothing has found yet, mimicking the shape a plan
takes where one of its fields is a description rather than a thing.

Answering such a statement takes more than one backend: the thing has to be looked for,
and the option nothing has stated has to be enumerated.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from typing_extensions import List

from .backend_that_looks_at_the_world import Sighting


class Grip(Enum):
    """
    How something found is taken hold of.
    """

    FROM_ABOVE = "from_above"
    FROM_THE_SIDE = "from_the_side"


@dataclass(frozen=True)
class TakingHoldOfSomethingFound:
    """
    Taking hold of a thing a look has to find first, in a way nothing has stated.
    """

    thing: Sighting
    """
    What is taken hold of.
    """

    grip: Grip
    """
    How it is taken hold of.
    """


@dataclass
class TakingHoldOfSeveralThingsFound:
    """
    Taking hold of several things a look has to find, so that a statement handing a
    description over as one element of a collection is a case the tests can state.
    """

    things: List[Sighting]
    """
    What is taken hold of, in the order it is taken.
    """

    grip: Grip
    """
    How each of them is taken hold of.
    """
