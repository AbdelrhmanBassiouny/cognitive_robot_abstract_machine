import inspect
import sys
from enum import Enum
from uuid import UUID

from typing_extensions import List, Type, Optional
from typing_extensions import TypeVar, get_origin, get_args


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


def get_generic_type_param(cls, generic_base: Type[T]) -> Optional[List[Type[T]]]:
    """
    Given a subclass and its generic base, return the concrete type parameter(s).

    Example:
        get_generic_type_param(Employee, Role) -> (<class '__main__.Person'>,)
    """
    for base in getattr(cls, "__orig_bases__", []):
        base_origin = get_origin(base)
        if base_origin is None:
            continue
        if issubclass(get_origin(base), generic_base):
            args = get_args(base)
            return list(args) if args else None
    return None
