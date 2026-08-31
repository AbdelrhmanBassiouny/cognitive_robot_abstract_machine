"""
Where a belief came from.
"""

from __future__ import annotations

from abc import ABC


class BeliefSource(ABC):
    """
    Something whose say-so is a reason to expect a thing to be somewhere.

    A belief that records the source itself rather than a label for it can be asked what
    else that source says: how sure it is, when it last said so, and what has happened
    to the thing since. Anything able to give a reason inherits this - the world model
    that places a body, a detector that saw something in a picture, or a person telling
    the robot what to look for - so a new kind of source needs no change to whatever
    reads the belief.
    """
