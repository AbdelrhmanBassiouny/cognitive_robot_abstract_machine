"""
Loading the CTU Mutagenesis dataset (https://relational.fel.cvut.cz/dataset/Mutagenesis)
into :class:`~experiments.causal_reasoning.mutagenesis.domain.MutagenesisMolecule`
instances, plus a synthetic generator with the same shape for the CI-safe pairing
:mod:`test.causal_reasoning_test.test_mutagenesis_pipeline` needs alongside its
live-dataset tests.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from krrood.exceptions import DataclassException
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from typing_extensions import List

from experiments.causal_reasoning.mutagenesis.domain import (
    MutagenesisAtom,
    MutagenesisBondType,
    MutagenesisElement,
    MutagenesisMolecule,
)


@dataclass
class MutagenesisDatasetUnavailableError(DataclassException):
    """
    Raised when the CTU relational-dataset repository cannot be reached.
    """

    reason: str
    """
    The underlying database error's message.
    """

    def error_message(self) -> str:
        return f"Could not reach the CTU Mutagenesis database: {self.reason}"

    def suggest_correction(self) -> str:
        return (
            "Check network access to relational.fel.cvut.cz, or skip tests that "
            "require it."
        )


@dataclass(frozen=True)
class MutagenesisDatabaseConnection:
    """
    Connection details for the CTU relational-dataset repository's Mutagenesis database.
    """

    host: str = "relational.fel.cvut.cz"
    """
    Hostname of the MariaDB server.
    """

    port: int = 3306
    """
    Port of the MariaDB server.
    """

    user: str = "guest"
    """
    Username for the read-only guest account.
    """

    password: str = "ctu-relational"
    """
    Password for the read-only guest account.
    """

    database: str = "mutagenesis_188"
    """
    Database name; ``mutagenesis_188`` is the 188-molecule "regression friendly" set.
    """

    @property
    def url(self) -> str:
        """
        The SQLAlchemy connection URL for this connection.
        """
        return (
            f"mysql+pymysql://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.database}"
        )


def is_mutagenesis_dataset_reachable(
    connection: MutagenesisDatabaseConnection = MutagenesisDatabaseConnection(),
) -> bool:
    """
    Check whether the CTU Mutagenesis database can be connected to right now.

    :param connection: Connection details to check.
    :return:``True`` if a connection could be established, ``False`` otherwise.
    """
    engine = create_engine(connection.url, connect_args={"connect_timeout": 5})
    try:
        with engine.connect():
            return True
    except OperationalError:
        return False
    finally:
        engine.dispose()


def fetch_mutagenesis_molecules(
    connection: MutagenesisDatabaseConnection = MutagenesisDatabaseConnection(),
) -> List[MutagenesisMolecule]:
    """
    Download the Mutagenesis dataset and convert it into domain objects.

    Pulls the ``drugs``, ``atoms`` and ``bonds`` tables, derives
    :attr:`~experiments.causal_reasoning.mutagenesis.domain.MutagenesisMolecule.double_bond_count`
    and
    :attr:`~experiments.causal_reasoning.mutagenesis.domain.MutagenesisMolecule.aromatic_bond_count`
    from the bond table, and groups atoms by their owning molecule.

    :param connection: Connection details for the database.
    :return: One :class:`~experiments.causal_reasoning.mutagenesis.domain.MutagenesisMolecule`
        per row of ``drugs``.
    :raises MutagenesisDatasetUnavailableError: If the database cannot be reached.
    """
    engine = create_engine(connection.url, connect_args={"connect_timeout": 5})
    try:
        drugs = pd.read_sql_table("drugs", engine)
        atoms = pd.read_sql_table("atoms", engine)
        bonds = pd.read_sql_table("bonds", engine)
    except OperationalError as error:
        raise MutagenesisDatasetUnavailableError(str(error)) from error
    finally:
        engine.dispose()

    double_bond_counts = (
        bonds[bonds["bond_type"] == MutagenesisBondType.DOUBLE]
        .groupby("drug_id")
        .size()
    )
    aromatic_bond_counts = (
        bonds[bonds["bond_type"] == MutagenesisBondType.AROMATIC]
        .groupby("drug_id")
        .size()
    )
    atoms_by_drug = {
        drug_id: [
            MutagenesisAtom(
                element=MutagenesisElement(row.element),
                atom_type=int(row.atom_type),
                charge=float(row.charge),
            )
            for row in group.itertuples()
        ]
        for drug_id, group in atoms.groupby("drug_id")
    }

    return [
        MutagenesisMolecule(
            indicator_1=bool(drug.ind1),
            logp=float(drug.logp),
            lumo=float(drug.lumo),
            double_bond_count=int(double_bond_counts.get(drug.id, 0)),
            aromatic_bond_count=int(aromatic_bond_counts.get(drug.id, 0)),
            mutagenic=bool(drug.active),
            atoms=atoms_by_drug[drug.id],
        )
        for drug in drugs.itertuples()
    ]


def synthetic_mutagenesis_molecules(
    random_state: np.random.Generator,
    molecule_count: int = 20,
    atom_count: int = 2,
) -> List[MutagenesisMolecule]:
    """
    Generate a small, network-free dataset with the same shape as
    :func:`fetch_mutagenesis_molecules`, for tests that must run without live network
    access.

    Each molecule's chlorine count is drawn to be either 0 or ``atom_count`` (all
    chlorine, none hydrogen), and ``mutagenic`` is set to match, baking in a real
    chlorine-count/mutagenicity correlation so a fitted circuit has something genuine to
    pick up, mirroring ``_room_with_chair_count`` in ``test_rspns.py``.

    :param random_state: Source of randomness for the non-causal fields.
    :param molecule_count: How many molecules to generate.
    :param atom_count: How many atoms each molecule has.
    :return: The generated molecules.
    """
    molecules = []
    for index in range(molecule_count):
        all_chlorine = index % 2 == 0
        element = (
            MutagenesisElement.CHLORINE if all_chlorine else MutagenesisElement.HYDROGEN
        )
        atoms = [
            MutagenesisAtom(
                element=element,
                atom_type=int(random_state.integers(1, 10)),
                charge=float(random_state.uniform(-0.5, 0.5)),
            )
            for _ in range(atom_count)
        ]
        molecules.append(
            MutagenesisMolecule(
                indicator_1=bool(random_state.integers(0, 2)),
                logp=float(random_state.uniform(0, 5)),
                lumo=float(random_state.uniform(-3, 0)),
                double_bond_count=int(random_state.integers(0, 3)),
                aromatic_bond_count=int(random_state.integers(0, 5)),
                mutagenic=all_chlorine,
                atoms=atoms,
            )
        )
    return molecules
