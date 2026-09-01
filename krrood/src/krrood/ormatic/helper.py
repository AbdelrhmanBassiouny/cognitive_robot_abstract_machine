from __future__ import annotations

from inspect import isclass
from types import ModuleType
from typing import Tuple, List, Type, Dict

from sqlalchemy.orm import DeclarativeBase

from krrood.ormatic.data_access_objects.alternative_mappings import AlternativeMapping
from krrood.ormatic.data_access_objects.dao import DataAccessObject
from krrood.ormatic.utils import classes_of_module, is_direct_subclass


def get_classes_of_ormatic_interface(
    interface: ModuleType,
) -> Tuple[List[Type], List[Type[AlternativeMapping]], Dict, Dict[Type, Type]]:
    """
    Get all classes and alternative mappings of an existing ormatic interface.

    :param interface: The ormatic interface to extract the information from.
    :return: A list of classes, a list of alternative mappings, the type mappings used
        in the interface, and a mapping of every domain class already mapped in the
        interface to the :class:`DataAccessObject` subclass that maps it there. The
        latter lets a dependent interface import and reuse that DAO instead of
        regenerating it.
    """
    classes = []
    alternative_mappings = []
    classes_of_ormatic_interface = classes_of_module(interface)
    type_mappings = {}
    externally_mapped_classes: Dict[Type, Type] = {}

    for cls in filter(
        lambda x: issubclass(x, DataAccessObject) and isclass(x.original_class()),
        classes_of_ormatic_interface,
    ):
        original_class = cls.original_class()

        if issubclass(original_class, AlternativeMapping):
            alternative_mappings.append(original_class)
            domain_class = original_class.original_class()
            classes.append(domain_class)
        else:
            domain_class = original_class
            classes.append(original_class)

        externally_mapped_classes[domain_class] = cls

    # get the type mappings from the direct subclass of declarative base
    for cls in filter(
        lambda x: is_direct_subclass(x, DeclarativeBase), classes_of_ormatic_interface
    ):
        type_mappings.update(cls.type_mappings)

    return classes, alternative_mappings, type_mappings, externally_mapped_classes
