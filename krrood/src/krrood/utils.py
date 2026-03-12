from __future__ import annotations

import ast
import inspect
import os
import types
from ast import Module
from collections import defaultdict
from dataclasses import dataclass, field, fields, Field
from functools import lru_cache
from importlib.util import resolve_name
from inspect import isclass
from typing import Union, Type

from typing_extensions import TypeVar, Type, List, Optional, _SpecialForm

T = TypeVar("T")


def recursive_subclasses(cls: Type[T]) -> List[Type[T]]:
    """
    :param cls: The class.
    :return: A list of the classes subclasses without the class itself.
    """
    return cls.__subclasses__() + [
        g for s in cls.__subclasses__() for g in recursive_subclasses(s)
    ]


@dataclass
class DataclassException(Exception):
    """
    A base exception class for dataclass-based exceptions.
    The way this is used is by inheriting from it and setting the `message` field in the __post_init__ method,
    then calling the super().__post_init__() method.
    """

    message: str = field(kw_only=True, default=None)

    def __post_init__(self):
        super().__init__(self.message)


def get_full_class_name(cls):
    """
    Returns the full name of a class, including the module name.

    :param cls: The class.
    :return: The full name of the class
    """
    return cls.__module__ + "." + cls.__name__


@lru_cache
def inheritance_path_length(child_class: Type, parent_class: Type) -> Optional[int]:
    """
    Calculate the inheritance path length between two classes.
    Every inheritance level that lies between `child_class` and `parent_class` increases the length by one.
    In case of multiple inheritance, the path length is calculated for each branch and the minimum is returned.

    :param child_class: The child class.
    :param parent_class: The parent class.
    :return: The minimum path length between `child_class` and `parent_class` or None if no path exists.
    """
    if not (
        isclass(child_class)
        and isclass(parent_class)
        and issubclass(child_class, parent_class)
    ):
        return None

    return _inheritance_path_length(child_class, parent_class, 0)


def _inheritance_path_length(
    child_class: Type, parent_class: Type, current_length: int = 0
) -> int:
    """
    Helper function for :func:`inheritance_path_length`.

    :param child_class: The child class.
    :param parent_class: The parent class.
    :param current_length: The current length of the inheritance path.
    :return: The minimum path length between `child_class` and `parent_class`.
    """

    if child_class == parent_class:
        return current_length
    else:
        return min(
            _inheritance_path_length(base, parent_class, current_length + 1)
            for base in child_class.__bases__
            if issubclass(base, parent_class)
        )


def module_and_class_name(t: Union[Type, _SpecialForm]) -> str:
    return f"{t.__module__}.{t.__name__}"


def extract_imports(
    module: types.ModuleType,
    exclude_libraries: Optional[List[str]] = None,
    convert_relative_to_absolute: bool = False,
    strip_levels_by_dots: bool = False,
) -> List[str]:

    exclude_libraries = exclude_libraries or []

    source = inspect.getsource(module)
    tree = ast.parse(source)

    import_modules = set()
    from_imports = defaultdict(set)

    current_module = module.__name__

    for node in ast.walk(tree):

        # import x
        if isinstance(node, ast.Import):

            for alias in node.names:
                name = alias.name

                if name in exclude_libraries:
                    continue

                if alias.asname:
                    import_modules.add(f"{name} as {alias.asname}")
                else:
                    import_modules.add(name)

        # from x import y
        elif isinstance(node, ast.ImportFrom):

            prefix = "." * node.level
            module_name = node.module or ""
            full_module = f"{prefix}{module_name}"

            if convert_relative_to_absolute and node.level > 0:
                full_module = resolve_name(full_module, current_module)

                if strip_levels_by_dots:
                    parts = full_module.split(".")
                    full_module = ".".join(parts[node.level :])

            if node.module and node.module in exclude_libraries:
                continue

            for alias in node.names:
                if alias.asname:
                    from_imports[full_module].add(f"{alias.name} as {alias.asname}")
                else:
                    from_imports[full_module].add(alias.name)

    result = set()

    for mod in import_modules:
        result.add(f"import {mod}")

    for mod, names in from_imports.items():
        joined = ", ".join(sorted(names))
        result.add(f"from {mod} import {joined}")

    return sorted(result)


def generate_relative_import(
    from_module: str, target_module: str, symbol: str | None = None
) -> str:
    """
    Generate a relative import statement using Python's own resolver.

    :param from_module: The module where the import is being made.
    :param target_module: The module to import.
    :param symbol: The symbol (e.g., a class, a method, ..., etc.) to import (optional).
    """

    # Compute absolute module name as Python would resolve it
    absolute = resolve_name(target_module, from_module)

    from_pkg = from_module.rsplit(".", 1)[0]
    from_parts = from_pkg.split(".")
    target_parts = absolute.split(".")

    # find common prefix
    i = 0
    while (
        i < min(len(from_parts), len(target_parts)) and from_parts[i] == target_parts[i]
    ):
        i += 1

    up = len(from_parts) - i
    prefix = "." * (up + 1)

    remainder = ".".join(target_parts[i:])

    if symbol:
        if remainder:
            return f"from {prefix}{remainder} import {symbol}"
        return f"from {prefix} import {symbol}"
    else:
        return f"from {prefix} import {remainder}"


@lru_cache
def own_dataclass_fields(cls) -> List[Field]:
    """
    :return: The fields of the dataclass that are not inherited from a base class.
    """
    base_fields = set()
    for base in cls.__mro__[1:]:
        if hasattr(base, "__dataclass_fields__"):
            base_fields.update(base.__dataclass_fields__.keys())

    return [f for f in fields(cls) if f.name not in base_fields]
