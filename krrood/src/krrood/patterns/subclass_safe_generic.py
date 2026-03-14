from __future__ import annotations

import inspect
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import lru_cache

from typing_extensions import (
    Generic,
    TypeVar,
    Type,
    List,
    TYPE_CHECKING,
    get_type_hints,
    Optional,
)

from krrood.class_diagrams.exceptions import CouldNotResolveType
from krrood.class_diagrams.utils import (
    get_type_hints_of_object,
    get_and_resolve_generic_type_hints_of_object_using_substitutions,
    resolve_type,
)
from krrood.utils import (
    get_generic_type_param,
    T,
    get_type_checking_imports,
    extract_imports_from,
    get_scope_from_imports,
)

if TYPE_CHECKING:
    from krrood.entity_query_language.core.mapped_variable import Attribute


@dataclass
class SubClassSafeGeneric(Generic[T], ABC):
    """
    A generic class that can be subclassed safely because it automatically updates the field types that use the generic
     type with the new specified type.
     Example:
         >>> T = TypeVar("T")
         >>> @dataclass
         >>> class MyClass(SubClassSafeGeneric[T]):
         >>>     my_attribute: T
         >>>     @classmethod
         >>>     def get_attributes_using_generic_type(cls) -> List[Attribute]:
         >>>         return [variable(cls, None).my_attribute]
         >>>
         >>> @dataclass
         >>> class MyClass2(SubClassSafeGeneric[int]): ...
         >>> assert next(f for f in fields(MyClass2) if f.name == "my_attribute").type == int)
    """

    def __init_subclass__(cls, **kwargs):
        """
        Automatically updates the field types that use the generic type with the new specified type, before the class is
        initialized.
        """
        old_generic_type = cls._get_old_generic_type()
        if not old_generic_type:
            return
        resolved_types = (
            get_and_resolve_generic_type_hints_of_object_using_substitutions(
                cls, {old_generic_type: cls.get_generic_type()}
            )
        )
        for name in cls.get_names_of_attributes_using_generic_type():
            cls.__annotations__[name] = resolved_types[name]

    @classmethod
    def _get_old_generic_type(cls) -> Optional[Type[T]]:
        """
        :return: The type of the generic type that was used in the parent class if it was changed in this class.
        """
        current_generic_type = cls.get_generic_type()
        if current_generic_type is None:
            return None
        for base in cls.__bases__:
            if not issubclass(base, SubClassSafeGeneric):
                continue
            base_generic_type = base.get_generic_type()
            if base_generic_type is None:
                continue
            if base_generic_type is not current_generic_type:
                return base_generic_type
        return None

    @classmethod
    @lru_cache
    def get_generic_type(cls) -> Optional[Type[T]]:
        """
        :return: The type of the role taker.
        """
        generic_types = get_generic_type_param(cls, SubClassSafeGeneric)
        if generic_types:
            return generic_types[0]
        return None

    @classmethod
    def get_names_of_attributes_using_generic_type(cls) -> List[str]:
        """
        :return: The names of the attributes that use the generic type.
        """
        return [
            attribute._attribute_name_
            for attribute in cls.get_attributes_using_generic_type()
        ]

    @classmethod
    @abstractmethod
    def get_attributes_using_generic_type(cls) -> List[Attribute]:
        """
        :return: The symbolic representation of the attributes that use the generic type.
        """
        return []
