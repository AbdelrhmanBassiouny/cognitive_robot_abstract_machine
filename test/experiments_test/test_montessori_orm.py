"""
Tests that the Montessori package's own classes reach the ORM.

The package is mapped only if the generator's package walk reports it, and only if no
two classes it maps share a name, so both are asserted here beside the DAO lookup they
exist to make succeed.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import is_dataclass
from types import ModuleType

import experiments
import experiments.montessori
import semantic_digital_twin
from krrood.ormatic.utils import classes_of_package
from typing_extensions import Dict, Set, Type

from experiments.montessori.semantics import (
    CubeShape,
    MontessoriShape,
    ShapeSortingBoard,
    ShapeSortingHole,
)


def mapped_classes_of(package: ModuleType) -> Set[Type]:
    """
    The classes of a package the ORM generator would map, which are the dataclasses its
    package walk reports.

    :param package: The package to walk.
    """
    return {clazz for clazz in classes_of_package(package) if is_dataclass(clazz)}


# %% what the generator is offered


def test_the_package_walk_offers_the_montessori_classes_to_the_generator():
    """
    Without an ``__init__.py`` the walk does not report ``experiments.montessori`` as a
    subpackage at all, so none of its classes is ever offered.
    """
    offered = mapped_classes_of(experiments)

    assert {MontessoriShape, CubeShape, ShapeSortingHole, ShapeSortingBoard} <= offered


# %% one name per mapped class


def test_no_montessori_class_shares_its_name_with_one_the_upstream_interface_maps():
    """
    A DAO is named after the class it maps, so two mapped classes of one name become two
    data access objects claiming a single table.
    """
    montessori_names = {
        clazz.__name__ for clazz in mapped_classes_of(experiments.montessori)
    }
    upstream_names = {
        clazz.__name__ for clazz in mapped_classes_of(semantic_digital_twin)
    }

    assert montessori_names & upstream_names == set()


def test_no_two_montessori_classes_share_their_name_with_each_other():
    """
    Two mapped classes of one name collide the same way whether the second is upstream's
    or the package's own, and a package walking two modules is where it happens
    unnoticed.
    """
    modules_declaring: Dict[str, Set[str]] = defaultdict(set)
    for clazz in mapped_classes_of(experiments.montessori):
        modules_declaring[clazz.__name__].add(clazz.__module__)

    assert {
        name: modules for name, modules in modules_declaring.items() if len(modules) > 1
    } == {}


# %% the lookup a persisted shape goes through


def test_the_generated_interface_resolves_a_data_access_object_for_a_montessori_shape():
    """
    ``get_dao_class`` returning nothing is what raises ``NoDAOFoundError`` when an
    action holding a Montessori shape is persisted.
    """
    import experiments.orm.ormatic_interface  # noqa: F401  registers the DAOs
    from krrood.ormatic.data_access_objects.helper import get_dao_class

    assert get_dao_class(CubeShape) is not None
