"""
Mimics of a blocksworld whose blocks rest on each other or on a table, for evaluating
queries against a planning state.
"""

from __future__ import annotations

from dataclasses import dataclass

# %% blocks and the table


@dataclass
class Table:
    """
    The surface every tower stands on.
    """

    name: str
    """
    The name of the table.
    """


@dataclass
class Block:
    """
    A block resting on another block or on the table.

    Compared by value, so two blocks with the same name and support are equal but remain
    distinct objects.
    """

    name: str
    """
    The name of the block.
    """

    support: Block | Table
    """
    What the block rests on.
    """
