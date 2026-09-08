"""
Domain classes mirroring the CTU relational-learning repository's Mutagenesis
dataset (https://relational.fel.cvut.cz/dataset/Mutagenesis), used to validate the
RSPN grounding and causal-query pipeline against a real, external, standard
relational-learning benchmark rather than only the ``SceneRoom``/``SceneObject`` toy
fixture.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, IntEnum
from typing_extensions import List

from krrood.entity_query_language.factories import entity, count_range, variable
from krrood.parametrization.feature_extraction.aggregations import (
    AggregationStatistic,
    aggregation_statistic,
)


class MutagenesisElement(Enum):
    """
    Chemical element of an atom, as recorded in the CTU Mutagenesis dataset.
    """

    CARBON = "c"
    HYDROGEN = "h"
    OXYGEN = "o"
    NITROGEN = "n"
    CHLORINE = "cl"
    BROMINE = "br"
    FLUORINE = "f"
    IODINE = "i"


class MutagenesisBondType(IntEnum):
    """
    ``bonds.bond_type`` value, as recorded in the CTU Mutagenesis dataset.

    1, 2, 3 and 7 follow the encoding documented in the dataset's own ILP literature
    (single, double, triple, aromatic). 4 and 5 also occur in the live table, in a
    handful of bonds, but their chemical meaning is not documented anywhere the schema
    exposes, so they are kept under their raw codes rather than guessed at.
    """

    SINGLE = 1
    DOUBLE = 2
    TRIPLE = 3
    UNDOCUMENTED_TYPE_4 = 4
    UNDOCUMENTED_TYPE_5 = 5
    AROMATIC = 7


@dataclass
class MutagenesisAtom:
    """
    One atom of a :class:`MutagenesisMolecule`.
    """

    element: MutagenesisElement
    """
    The atom's chemical element.
    """

    atom_type: int
    """
    The dataset's ILP atom-type code, a finer-grained classification than
    :attr:`element` alone.
    """

    charge: float
    """
    The atom's partial charge.
    """


@dataclass
class MutagenesisMolecule:
    """
    One molecule of the CTU Mutagenesis dataset, with its atoms as an exchangeable part.

    ``double_bond_count`` and ``aromatic_bond_count`` stay class-level scalars rather
    than a retained ``bonds`` exchangeable part alongside ``atoms``: grounding a second
    exchangeable part together with an aggregation-derived cause variable currently
    breaks ``CausalCircuit``'s region extraction (a separate, pre-existing bug in the
    relational-grounding/causal-circuit pipeline, not specific to bonds).
    """

    indicator_1: bool
    """
    The dataset's ``ind1`` structural indicator, a strong known predictor of
    mutagenicity in this benchmark.
    """

    logp: float
    """
    Octanol-water partition coefficient, a measure of the molecule's hydrophobicity.
    """

    lumo: float
    """
    Energy of the molecule's lowest unoccupied molecular orbital.
    """

    double_bond_count: int
    """
    Count of the molecule's double bonds, derived from its bond table at load time.
    """

    aromatic_bond_count: int
    """
    Count of the molecule's aromatic bonds, derived from its bond table at load time.
    """

    mutagenic: bool
    """
    Whether the molecule is mutagenic; the dataset's prediction target.
    """

    atoms: List[MutagenesisAtom]
    """
    The molecule's atoms.
    """


@dataclass
class MutagenesisMoleculeAggregations(AggregationStatistic[MutagenesisMolecule]):
    """
    Aggregation statistics for :class:`MutagenesisMolecule` over its ``atoms`` field.
    """

    @aggregation_statistic("atoms")
    def chlorine_count(self) -> int:
        """
        Count of chlorine atoms.
        """
        element_variable = variable(MutagenesisAtom, self.instance.atoms).element
        [result] = (
            entity(count_range(element_variable))
            .where(element_variable == MutagenesisElement.CHLORINE)
            .tolist()
        )
        return result
