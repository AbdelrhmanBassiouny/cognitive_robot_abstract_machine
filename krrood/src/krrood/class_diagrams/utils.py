from __future__ import annotations
import inspect
import sys
from enum import Enum
from uuid import UUID
from copy import copy

from typing_extensions import List, Type, TYPE_CHECKING
from typing_extensions import TypeVar

if TYPE_CHECKING:
    pass


def classes_of_module(module) -> List[Type]:
    """
    Get all classes of a given module.

    :param module: The module to inspect.
    :return: All classes of the given module.
    """

    result = []
    for name, obj in inspect.getmembers(sys.modules[module.__name__]):
        if inspect.isclass(obj) and obj.__module__ == module.__name__:
            result.append(obj)
    return result


def behaves_like_a_built_in_class(
    clazz: Type,
) -> bool:
    return (
        is_builtin_class(clazz)
        or clazz == UUID
        or (inspect.isclass(clazz) and issubclass(clazz, Enum))
    )


def is_builtin_class(clazz: Type) -> bool:
    return clazz.__module__ == "builtins"


T = TypeVar("T")




def nearest_common_ancestor(classes):
    if not classes:
        return None

    # Get MROs as lists
    mros = [copy(cls.mro()) for cls in classes]

    # Iterate in MRO order of the first class
    for candidate in mros[0]:
        if all(candidate in mro for mro in mros[1:]):
            return candidate

    return None


