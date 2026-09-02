from __future__ import annotations

from dataclasses import dataclass, field
from inspect import isclass
from types import ModuleType
from typing import List, Type, Dict

from sqlalchemy.orm import DeclarativeBase

from krrood.ormatic.data_access_objects.alternative_mappings import AlternativeMapping
from krrood.ormatic.data_access_objects.dao import DataAccessObject
from krrood.ormatic.utils import classes_of_module, is_direct_subclass


@dataclass
class OrmaticInterfaceInfo:
    """
    Classes, alternative mappings, type mappings, and externally-mapped classes read
    from an existing ormatic interface.
    """

    classes: List[Type] = field(default_factory=list)
    alternative_mappings: List[Type[AlternativeMapping]] = field(default_factory=list)
    type_mappings: Dict = field(default_factory=dict)
    externally_mapped_classes: Dict[Type, Type] = field(default_factory=dict)
    """
    Maps every domain class already mapped anywhere in this interface's dependency
    chain to the :class:`DataAccessObject` subclass that maps it, so a dependent
    interface can import and reuse that DAO instead of regenerating it.
    """


def get_classes_of_ormatic_interface(interface: ModuleType) -> OrmaticInterfaceInfo:
    """
    Get all classes and alternative mappings of an existing ormatic interface.

    :param interface: The ormatic interface to extract the information from.
    """
    from krrood.ormatic.ormatic import ORMatic

    result = OrmaticInterfaceInfo()
    classes_of_ormatic_interface = classes_of_module(interface)

    for cls in filter(
        lambda x: issubclass(x, DataAccessObject), classes_of_ormatic_interface
    ):
        original_class = cls.original_class()

        if not isclass(original_class):
            continue

        if issubclass(original_class, AlternativeMapping):
            result.alternative_mappings.append(original_class)
            result.classes.append(original_class.original_class())
        else:
            result.classes.append(original_class)

    # every interface in the chain shares one Base, so its registry already
    # transitively includes every DAO mapped anywhere upstream
    for mapper in interface.Base.registry.mappers:
        dao_class = mapper.class_
        if issubclass(dao_class, DataAccessObject):
            ORMatic.register_externally_mapped_class(
                dao_class, result.externally_mapped_classes
            )

    # get the type mappings from the direct subclass of declarative base
    for cls in filter(
        lambda x: is_direct_subclass(x, DeclarativeBase), classes_of_ormatic_interface
    ):
        result.type_mappings.update(cls.type_mappings)

    return result
