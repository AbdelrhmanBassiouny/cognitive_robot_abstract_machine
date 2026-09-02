from __future__ import annotations

from inspect import isclass
from types import ModuleType
from typing import Tuple, List, Type, Dict

from sqlalchemy.orm import DeclarativeBase

from krrood.ormatic.data_access_objects.alternative_mappings import AlternativeMapping
from krrood.ormatic.data_access_objects.dao import DataAccessObject
from krrood.ormatic.utils import classes_of_module, is_direct_subclass


def _register_externally_mapped_class(
    dao_class: Type, externally_mapped_classes: Dict[Type, Type]
) -> None:
    """
    Register the domain class(es) ``dao_class`` maps as already-mapped, so a dependent
    interface imports and reuses ``dao_class`` instead of regenerating its own copy.

    An :class:`AlternativeMapping` subclass is registered under both its own type and
    its ultimate domain class: it gets its own node in the class diagram (see
    :meth:`ORMatic._add_alternative_mappings_to_class_diagram`), so both need to
    resolve to the same already-mapped DAO.
    """
    original_class = dao_class.original_class()

    if not isclass(original_class):
        # A specialized generic (e.g. DerivativeMap[float]) is a valid original_class
        # but isn't itself a class -- still register it as already-mapped so two
        # independent packages that both use the same specialized generic don't each
        # map it under their own name and collide once they share one declarative Base.
        externally_mapped_classes[original_class] = dao_class
        return

    if issubclass(original_class, AlternativeMapping):
        externally_mapped_classes[original_class] = dao_class
        externally_mapped_classes[original_class.original_class()] = dao_class
    else:
        externally_mapped_classes[original_class] = dao_class


def get_classes_of_ormatic_interface(
    interface: ModuleType,
) -> Tuple[List[Type], List[Type[AlternativeMapping]], Dict, Dict[Type, Type]]:
    """
    Get all classes and alternative mappings of an existing ormatic interface.

    :param interface: The ormatic interface to extract the information from.
    :return: A list of classes, a list of alternative mappings, the type mappings used
        in the interface, and a mapping of every domain class already mapped anywhere
        in this interface's dependency chain to the :class:`DataAccessObject` subclass
        that maps it. The latter lets a dependent interface import and reuse that DAO
        instead of regenerating it.
    """
    classes = []
    alternative_mappings = []
    classes_of_ormatic_interface = classes_of_module(interface)
    type_mappings = {}
    externally_mapped_classes: Dict[Type, Type] = {}

    for cls in filter(
        lambda x: issubclass(x, DataAccessObject), classes_of_ormatic_interface
    ):
        original_class = cls.original_class()

        if not isclass(original_class):
            continue

        if issubclass(original_class, AlternativeMapping):
            alternative_mappings.append(original_class)
            classes.append(original_class.original_class())
        else:
            classes.append(original_class)

    # `externally_mapped_classes` has to cover the *whole* transitive dependency
    # chain, not just DAOs classes_of_module() can see defined in `interface` itself.
    # A generated interface only references a dependency's DAO by name (and so shows
    # up as a module attribute classes_of_module() can find) when it actually needs
    # it -- e.g. for a foreign key or a local subclass. A DAO that's merely "passed
    # through" -- such as a framework-wide AlternativeMapping every package's own
    # unconditional recursive_subclasses() scan rediscovers -- can be invisible to
    # classes_of_module() on an intermediate package even though it was already
    # mapped further up the chain, which broke a >1-hop chain (e.g. package C
    # depending on B depending on A: C couldn't see a class only A, not B, mapped).
    # Every interface in the chain shares one declarative Base -- each dependent
    # module imports its dependency's Base instead of declaring its own -- so
    # `interface.Base.registry.mappers` already transitively includes every DAO
    # mapped anywhere upstream. Ask the registry directly instead of trying to
    # reconstruct that via module introspection.
    for mapper in interface.Base.registry.mappers:
        dao_class = mapper.class_
        if issubclass(dao_class, DataAccessObject):
            _register_externally_mapped_class(dao_class, externally_mapped_classes)

    # get the type mappings from the direct subclass of declarative base
    for cls in filter(
        lambda x: is_direct_subclass(x, DeclarativeBase), classes_of_ormatic_interface
    ):
        type_mappings.update(cls.type_mappings)

    return classes, alternative_mappings, type_mappings, externally_mapped_classes
