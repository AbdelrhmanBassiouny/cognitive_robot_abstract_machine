"""
Class collection must be able to exclude a whole subclass hierarchy, not only named
classes.
"""

from krrood.entity_query_language.predicate import SymbolicCallable
from krrood.ormatic.ormatic import ORMatic

from ..dataset import semantic_world_like_classes
from ..dataset.semantic_world_like_classes import ContainsType


# %% subclass hierarchy exclusion


def test_subclasses_of_an_ignored_base_class_are_not_collected():
    """
    Naming a base class must drop every one of its subclasses from the collected
    classes.
    """
    ormatic = ORMatic.from_package(
        packages=[semantic_world_like_classes],
        ormatic_interface_dependencies=[],
        ignored_classes=set(),
        type_mappings={},
        ignored_base_classes={SymbolicCallable},
    )

    assert ContainsType not in ormatic.class_dependency_graph.classes


def test_a_predicate_is_collected_when_no_base_class_is_ignored():
    """
    Without an ignored base class the same predicate is collected, so its exclusion is
    attributable to :attr:`ignored_base_classes` alone.
    """
    ormatic = ORMatic.from_package(
        packages=[semantic_world_like_classes],
        ormatic_interface_dependencies=[],
        ignored_classes=set(),
        type_mappings={},
    )

    assert ContainsType in ormatic.class_dependency_graph.classes
