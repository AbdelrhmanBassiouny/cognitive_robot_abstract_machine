"""
Self-contained example domain for the EQL-RDR conclusion-asking documentation.

A small museum collection scenario: each ``Exhibit`` has observable features
(material, size, has_inscription) and must be classified into an ``ExhibitKind``
(Pottery / Jewelry / Tablet).  Nothing is imported from test/ — this module is
the single source of truth for the running example used in both docs.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass


class ExhibitKind(enum.Enum):
    """The allowable conclusions an expert may assign to an Exhibit."""

    pottery = "pottery"
    jewelry = "jewelry"
    tablet = "tablet"


@dataclass
class Exhibit:
    """A museum artefact whose kind has not yet been catalogued."""

    name: str
    material: str  # "clay", "gold", "stone", …
    size_cm: float
    has_inscription: bool
    kind: ExhibitKind = None  # the conclusion attribute the RDR predicts


# A small labelled collection — enough to grow a three-rule tree.
EXHIBITS = [
    Exhibit("Bowl-1", material="clay", size_cm=12.0, has_inscription=False),
    Exhibit("Ring-1", material="gold", size_cm=2.5, has_inscription=False),
    Exhibit("Stele-1", material="stone", size_cm=80.0, has_inscription=True),
    Exhibit("Jug-1", material="clay", size_cm=30.0, has_inscription=False),
    Exhibit("Amulet-1", material="gold", size_cm=4.0, has_inscription=True),
]

# Ground-truth labels (parallel to EXHIBITS) — used by the FunctionInterface expert.
LABELS = [
    ExhibitKind.pottery,
    ExhibitKind.jewelry,
    ExhibitKind.tablet,
    ExhibitKind.pottery,
    ExhibitKind.jewelry,
]
