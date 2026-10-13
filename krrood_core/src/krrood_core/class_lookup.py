from __future__ import annotations

import importlib

from typing_extensions import List, Type, TypeVar

T = TypeVar("T")


# %% class names


def get_full_class_name(cls):
    """
    Return the full name of a class, including the module name.

    :param cls: The class.
    :return: The full name of the class
    """
    return cls.__module__ + "." + cls.__name__


def resolve_class_from_full_name(fully_qualified_class_name: str) -> Type:
    """
    Import and return the class named by a fully qualified name of the form
    ``"module.submodule.ClassName"``, as written by :func:`get_full_class_name`.

    :param fully_qualified_class_name: The fully qualified class name.
    :return: The resolved class.
    """
    module_name, class_name = fully_qualified_class_name.rsplit(".", 1)
    module = importlib.import_module(module_name)
    return getattr(module, class_name)


# %% class hierarchy


def recursive_subclasses(cls: Type[T]) -> List[Type[T]]:
    """
    :param cls: The class.
    :return: A list of the classes subclasses without the class itself.
    """
    return cls.__subclasses__() + [
        g for s in cls.__subclasses__() for g in recursive_subclasses(s)
    ]
