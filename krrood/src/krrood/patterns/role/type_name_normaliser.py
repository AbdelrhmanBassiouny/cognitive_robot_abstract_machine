"""
Normaliser that converts Python type objects to consistent string representations.
"""

from __future__ import annotations

import dataclasses
import sys
from typing import Any, TypeVar, get_origin, get_args

from krrood.class_diagrams import ClassDiagram
from krrood.patterns.role.import_name_resolver import ImportNameResolver


@dataclasses.dataclass
class TypeNameNormaliser:
    """
    Normalises Python type objects to consistent string names for code generation.
    """

    resolver: ImportNameResolver
    class_diagram: ClassDiagram

    def normalise(self, type_obj: Any) -> str:
        """
        Return a consistent string representation of a type for use in generated code.

        :param type_obj: The type object to normalise.
        :return: A string type name suitable for inclusion in generated source code.
        """
        if isinstance(type_obj, str):
            return self._handle_string_type(type_obj)

        if isinstance(type_obj, TypeVar):
            return self._handle_type_var(type_obj)

        origin = get_origin(type_obj)
        if origin is not None:
            return self._handle_generic_type(type_obj, origin)

        if isinstance(type_obj, type):
            return self._handle_class_type(type_obj)

        return self._handle_fallback_type(type_obj)

    def _handle_string_type(self, type_str: str) -> str:
        """Resolve a forward-reference string type name."""
        # Avoid importing Role here to prevent circular imports — use duck typing.
        if type_str.startswith("T"):
            class_name = type_str[1:]
            for wrapped in self.class_diagram.wrapped_classes:
                if wrapped.clazz.__name__ == class_name:
                    from krrood.patterns.role.role import Role
                    if issubclass(wrapped.clazz, Role):
                        return type_str
                    else:
                        return class_name

        # Try to resolve module for the string type if not already known
        if type_str not in self.resolver.name_to_module_map:
            resolved_module = self.resolver.resolve(type_str)
            if resolved_module:
                self.resolver.name_to_module_map[type_str] = resolved_module
        return type_str

    def _handle_generic_type(self, type_obj: Any, origin: Any) -> str:
        """Normalise a generic type such as List[str] or Dict[str, Any]."""
        origin_name = self.normalise(origin)
        args = get_args(type_obj)

        if args:
            arg_names = [self.normalise(arg) for arg in args]
            res = f"{origin_name}[{', '.join(arg_names)}]"
        else:
            res = origin_name

        return res.replace("typing.", "").replace("typing_extensions.", "")

    def _handle_type_var(self, type_var: TypeVar) -> str:
        """Normalise a TypeVar to its name or bound type name."""
        if hasattr(type_var, "__module__"):
            self.resolver.name_to_module_map[type_var.__name__] = type_var.__module__

        if type_var.__bound__ is not None:
            # Recursively handle bound to record its module
            self.normalise(type_var.__bound__)
            from krrood.patterns.role.role import Role
            if issubclass(type_var.__bound__, Role):
                return type_var.__name__
            return type_var.__bound__.__name__
        return type_var.__name__

    def _handle_class_type(self, clazz: type) -> str:
        """Normalise a plain class type to its name."""
        if clazz is type(None):
            return "None"

        self.resolver.name_to_module_map[clazz.__name__] = clazz.__module__
        from krrood.patterns.role.role import Role
        if issubclass(clazz, Role):
            return self._get_type_name(clazz)
        return clazz.__name__

    def _handle_fallback_type(self, type_obj: Any) -> str:
        """Normalise an unrecognised type object using str() as a last resort."""
        if hasattr(type_obj, "__name__") and hasattr(type_obj, "__module__"):
            self.resolver.name_to_module_map[type_obj.__name__] = type_obj.__module__
        return str(type_obj)

    def _get_type_name(self, clazz: type) -> str:
        """Return the TypeVar name for a class if one exists, otherwise the plain class name."""
        type_var_name = f"T{clazz.__name__}"
        class_module = sys.modules[clazz.__module__]
        if type_var_name in class_module.__dict__:
            return type_var_name
        return clazz.__name__
