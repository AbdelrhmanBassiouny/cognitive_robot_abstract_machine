"""
Mimic entities the query-runner and live-query tests range over.

Deliberately none of cramera's own knowledge entities: a query runner must serve
whatever dataclass a source declares, without that dataclass subclassing anything
cramera owns.
"""

from __future__ import annotations

from dataclasses import dataclass

from semantic_digital_twin.spatial_types import Point3, Pose


@dataclass
class NamedRecord:
    """
    A record carrying the ``name`` field the row renderer titles a row with.
    """

    name: str
    """
    What the rendered row is titled with.
    """

    category: str
    """
    A field to group and filter rows by.
    """

    score: float
    """
    A numeric field to order and compare rows by.
    """

    position: Point3
    """
    A spatial field, so rendering of non-JSON-native values is exercised.
    """


@dataclass
class PosedRecord:
    """
    A record whose payload is a full pose rather than a bare position.
    """

    name: str
    """
    What the rendered row is titled with.
    """

    target: Pose
    """
    The pose the row reports.
    """


@dataclass
class UnnamedRecord:
    """
    A record with no ``name`` field, which must not be rendered as a named entity.
    """

    identifier: str
    """
    This record's identity, deliberately not called ``name``.
    """
