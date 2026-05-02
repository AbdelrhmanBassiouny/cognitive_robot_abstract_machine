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
        """Return a consistent string representation of a type for use in generated code.

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
        """Return a normalised name for a forward-reference string type.

        :param type_str: The forward-reference string to normalise.
        :return: The resolved or unchanged type name string.
        """
        if type_str.startswith("T"):
            class_name = type_str[1:]
            for wrapped in self.class_diagram.wrapped_classes:
                if wrapped.clazz.__name__ == class_name:
                    # Register the bound class for imports
                    self.resolver.name_to_module_map.setdefault(
                        class_name, wrapped.clazz.__module__
                    )
                    # Register the TypeVar itself if it exists in the defining module
                    module = sys.modules.get(wrapped.clazz.__module__)
                    if module is not None:
                        candidate = vars(module).get(type_str)
                        if isinstance(candidate, TypeVar) and hasattr(candidate, "__module__"):
                            self.resolver.name_to_module_map[type_str] = candidate.__module__
                    return type_str

        if type_str not in self.resolver.name_to_module_map:
            resolved_module = self.resolver.resolve(type_str)
            if resolved_module:
                self.resolver.name_to_module_map[type_str] = resolved_module
        return type_str

    def _handle_generic_type(self, type_obj: Any, origin: Any) -> str:
        """Return a normalised name for a generic type such as ``List[str]``.

        :param type_obj: The generic type object.
        :param origin: The origin type returned by ``get_origin``.
        :return: A normalised string representation of the generic type.
        """
        alias_name = type_obj._name if hasattr(type_obj, "_name") else None
        alias_module = type_obj.__module__ if hasattr(type_obj, "__module__") else None
        if alias_name and alias_module and alias_module != "builtins":
            self.resolver.name_to_module_map.setdefault(alias_name, alias_module)
        origin_name = self.normalise(origin)
        args = get_args(type_obj)

        if args:
            arg_names = [self.normalise(arg) for arg in args]
            result = f"{origin_name}[{', '.join(arg_names)}]"
        else:
            result = origin_name

        return result.replace("typing.", "").replace("typing_extensions.", "")

    def _handle_type_var(self, type_var: TypeVar) -> str:
        """Return a normalised name for a TypeVar.

        :param type_var: The TypeVar to normalise.
        :return: The TypeVar name.
        """
        if hasattr(type_var, "__module__"):
            self.resolver.name_to_module_map[type_var.__name__] = type_var.__module__

        if type_var.__bound__ is not None:
            self.normalise(type_var.__bound__)

        return type_var.__name__

    def _handle_class_type(self, clazz: type) -> str:
        """Return a normalised name for a plain class type.

        :param clazz: The class to normalise.
        :return: The class name string.
        """
        if clazz is type(None):
            return "None"

        self.resolver.name_to_module_map[clazz.__name__] = clazz.__module__
        from krrood.patterns.role.role import Role
        if issubclass(clazz, Role):
            return self.get_type_name(clazz)
        return clazz.__name__

    def _handle_fallback_type(self, type_obj: Any) -> str:
        """Return a normalised name for an unrecognised type object.

        :param type_obj: The unrecognised type to normalise.
        :return: A string representation of the type.
        """
        if hasattr(type_obj, "__name__") and hasattr(type_obj, "__module__"):
            self.resolver.name_to_module_map[type_obj.__name__] = type_obj.__module__
        return str(type_obj)

    def get_type_name(self, clazz: type) -> str:
        """Return the TypeVar name for a class if one exists, otherwise the plain class name.

        :param clazz: The class whose name to retrieve.
        :return: The TypeVar name or the plain class name.
        """
        type_var_name = f"T{clazz.__name__}"
        class_module = sys.modules[clazz.__module__]
        if type_var_name in class_module.__dict__:
            return type_var_name
        return clazz.__name__
