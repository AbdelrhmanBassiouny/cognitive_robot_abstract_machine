"""
ORMatic-specific check that a many-to-many relationship declared as ``Sequence[X]``
(rather than as a concrete ``list[X]``, ``Set[X]`` or ``tuple[X, ...]``) can be mapped
and round-tripped.

``Sequence`` is abstract, so it can be neither named in the generated interface without
importing the module that defines it nor instrumented in place by SQLAlchemy. The
generated relationship therefore has to be held in a collection SQLAlchemy can build and
append to.
"""

from __future__ import annotations

import importlib.util
import sys

import pytest
from sqlalchemy import select
from sqlalchemy.orm import configure_mappers, sessionmaker

from krrood.class_diagrams.class_diagram import ClassDiagram
from krrood.ormatic.data_access_objects.helper import to_dao
from krrood.ormatic.helper import get_classes_of_ormatic_interface
from krrood.ormatic.ormatic import ORMatic
from krrood.ormatic.utils import create_engine
from ..dataset.sequence_collection_classes import (
    SequenceCollectionMember,
    SequenceCollectionOwner,
)


@pytest.fixture(scope="module")
def module(tmp_path_factory):
    """
    Generate and import an ORMatic SQLAlchemy interface for the sequence-collection
    classes, once, so the two tests below don't redeclare the same classes into the
    shared registry twice.
    """
    class_diagram = ClassDiagram([SequenceCollectionOwner, SequenceCollectionMember])
    instance = ORMatic(class_diagram)
    instance.make_all_tables()

    interface_file = (
        tmp_path_factory.mktemp("sequence_collection")
        / "sequence_collection_interface.py"
    )
    with open(interface_file, "w") as f:
        instance.to_sqlalchemy_file(f)

    spec = importlib.util.spec_from_file_location(
        "sequence_collection_interface", interface_file
    )
    generated_module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = generated_module
    spec.loader.exec_module(generated_module)
    return generated_module


def test_ormatic_configures_a_sequence_valued_many_to_many_relationship(module):
    """
    Configuring the mappers of a ``Sequence[X]``-valued relationship must not raise,
    since SQLAlchemy cannot instrument the abstract ``Sequence`` as a collection class.
    """
    get_classes_of_ormatic_interface(module)

    configure_mappers()


def test_ormatic_round_trips_a_sequence_valued_many_to_many_relationship(module):
    get_classes_of_ormatic_interface(module)
    configure_mappers()

    engine = create_engine("sqlite:///:memory:")
    module.Base.metadata.create_all(engine)
    session = sessionmaker(engine)()

    original = SequenceCollectionOwner(
        members=(
            SequenceCollectionMember(label="a"),
            SequenceCollectionMember(label="b"),
        )
    )

    dao = to_dao(original)
    session.add(dao)
    session.commit()

    reconstructed = session.scalars(select(type(dao))).one().from_dao()

    assert list(reconstructed.members) == list(original.members)
