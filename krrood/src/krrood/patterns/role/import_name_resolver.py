"""
Resolver that maps Python identifier names to their source modules.
"""

from __future__ import annotations

import dataclasses
from types import ModuleType
from typing import Any, TypeVar, get_origin, get_args, Callable

from krrood.class_diagrams import ClassDiagram
from krrood.class_diagrams.utils import (
    get_type_hints_of_object,
    resolve_name_in_hierarchy,
)


@dataclasses.dataclass
class ImportNameResolver:
    """
    Resolves Python names to their source modules for import generation.
    """

    source_module: ModuleType
    taker_modules: list[ModuleType]
    class_diagram: ClassDiagram
    name_to_module_map: dict[str, str] = dataclasses.field(default_factory=dict)

    def __post_init__(self) -> None:
        """Pre-populate the name-to-module map from runtime state and type hints."""
        self._initialise_map()

    def _initialise_map(self) -> None:
        """Populate name_to_module_map from runtime dicts and diagram type hints."""
        # 1. Scan runtime dicts of the source module and all taker modules.
        for module in [self.source_module] + list(self.taker_modules):
            for name, obj in module.__dict__.items():
                if name.startswith("_"):
                    continue
                if hasattr(obj, "__module__") and obj.__module__:
                    self.name_to_module_map.setdefault(name, obj.__module__)

        # 2. Walk type hints of all classes in the diagram.
        for wrapped in self.class_diagram.wrapped_classes:
            try:
                hints = get_type_hints_of_object(wrapped.clazz)
                for hint_type in hints.values():
                    self.register_from_type(hint_type)
            except Exception:
                pass

        # 3. Ensure every class in the diagram maps to its own module.
        for wrapped in self.class_diagram.wrapped_classes:
            self.name_to_module_map.setdefault(
                wrapped.clazz.__name__, wrapped.clazz.__module__
            )

    def register_from_type(self, type_obj: Any) -> None:
        """
        Recursively register name->module for a type and all its components.

        :param type_obj: The type object to register, including generic args and TypeVar bounds.
        """
        if type_obj is None or isinstance(type_obj, str):
            return
        if isinstance(type_obj, TypeVar):
            if hasattr(type_obj, "__module__") and type_obj.__module__:
                self.name_to_module_map.setdefault(type_obj.__name__, type_obj.__module__)
            if type_obj.__bound__ is not None:
                self.register_from_type(type_obj.__bound__)
            return
        origin = get_origin(type_obj)
        if origin is not None:
            alias_name = type_obj._name if hasattr(type_obj, "_name") else None
            alias_module = type_obj.__module__ if hasattr(type_obj, "__module__") else None
            if alias_name and alias_module and alias_module != "builtins":
                self.name_to_module_map.setdefault(alias_name, alias_module)
            self.register_from_type(origin)
            for arg in get_args(type_obj):
                self.register_from_type(arg)
            return
        if isinstance(type_obj, type) and hasattr(type_obj, "__module__"):
            self.name_to_module_map.setdefault(type_obj.__name__, type_obj.__module__)

    def register_from_callable_globals(self, method: Callable) -> None:
        """
        Register annotation identifiers from the method's own globals namespace.

        :param method: The method whose annotation strings should be scanned.
        """
        import re

        annotations = method.__annotations__ if hasattr(method, "__annotations__") else {}
        globals_ = method.__globals__ if hasattr(method, "__globals__") else {}
        for annotation in annotations.values():
            if not isinstance(annotation, str):
                continue
            for name in re.findall(r"\b[A-Za-z_]\w*\b", annotation):
                if name not in self.name_to_module_map and name in globals_:
                    obj = globals_[name]
                    if hasattr(obj, "__module__") and obj.__module__:
                        self.name_to_module_map[name] = obj.__module__

    def resolve(self, name: str, current_class: type | None = None) -> str | None:
        """
        Return the fully-qualified module name for the given identifier, or None.

        :param name: The identifier to resolve.
        :param current_class: Optional class context used to search the class hierarchy.
        :return: The fully-qualified module name, or None if unresolvable.
        """
        # 0. Check our recorded map
        if name in self.name_to_module_map:
            return self.name_to_module_map[name]

        # 1. Check if it's in original module globals
        if name in self.source_module.__dict__:
            obj = self.source_module.__dict__[name]
            if hasattr(obj, "__module__"):
                return obj.__module__
            return self.source_module.__name__

        # 2. Check context class hierarchy
        if current_class:
            try:
                obj = resolve_name_in_hierarchy(name, current_class)
                if hasattr(obj, "__module__"):
                    # Record it for future use
                    self.name_to_module_map[name] = obj.__module__
                    return obj.__module__
            except Exception:
                pass

        # 3. Check ClassDiagram
        for wrapped in self.class_diagram.wrapped_classes:
            if wrapped.clazz.__name__ == name:
                return wrapped.clazz.__module__

        return None
