from __future__ import annotations

import inspect
import sys
from abc import ABC, abstractmethod
from collections import defaultdict
from copy import copy
from dataclasses import dataclass, Field
from enum import Enum
from functools import lru_cache
from uuid import UUID

from typing_extensions import List, Type, Optional
from typing_extensions import TypeVar, get_origin, get_args
from typing_extensions import (
    Union,
    Generic,
    Dict,
    Tuple,
    ClassVar,
    Any,
)


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


def get_generic_type_param(cls, generic_base_name: str) -> Optional[List[Type[T]]]:
    """
    Given a subclass and its generic base, return the concrete type parameter(s).

    Example:
        get_generic_type_param(Employee, Role) -> (<class '__main__.Person'>,)
    """
    for base in getattr(cls, "__orig_bases__", []):
        base_origin = get_origin(base)
        if base_origin is None:
            continue
        if get_origin(base).__name__ == generic_base_name:
            args = get_args(base)
            return list(args) if args else None
    return None


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


def sort_classes_by_role_aware_inheritance_path_length(
        classes: Tuple[Type, ...],
        common_ancestor: Optional[Type] = None,
        classes_to_remove_from_common_ancestor: Optional[Tuple[Type, ...]] = None,
        with_levels: bool = False,
) -> List[Type]:
    classes_to_remove_from_common_ancestor = (
        list(classes_to_remove_from_common_ancestor)
        if classes_to_remove_from_common_ancestor
        else []
    )
    classes_to_remove_from_common_ancestor.append(None)
    if not common_ancestor:
        common_ancestor = role_aware_nearest_common_ancestor(tuple(classes))
        if common_ancestor in classes_to_remove_from_common_ancestor:
            return classes
    class_lengths = [
        (clazz, role_aware_inheritance_path_length(clazz, common_ancestor))
        for clazz in classes
    ]
    sorted_ = list(sorted(class_lengths, key=lambda x: x[1]))
    # if any consecutive lengths are equal, make non role first
    for i in range(len(sorted_) - 1):
        if sorted_[i][1] != sorted_[i + 1][1]:
            continue
        if (
                issubclass(sorted_[i][0], Role) and not issubclass(sorted_[i + 1][0], Role)
        ) or (
                issubclass(sorted_[i][0], Role)
                and issubclass(sorted_[i + 1][0], Role)
                and len(sorted_[i][0].all_role_taker_types())
                > len(sorted_[i + 1][0].all_role_taker_types())
        ):
            # keep swapping until we find a different length
            for j in range(i + 1, 0, -1):
                if sorted_[j][1] != sorted_[j - 1][1]:
                    break
                # swap
                sorted_[j], sorted_[j - 1] = sorted_[j - 1], sorted_[j]

    if with_levels:
        return sorted_
    return [clazz for clazz, _ in sorted_]


@lru_cache
def role_aware_nearest_common_ancestor(classes):
    if not classes:
        return None

    # Get MROs as lists
    mros = [copy(cls.mro()) for cls in classes]
    for mro in mros:
        if Role not in mro:
            continue
        rol_idx = mro.index(Role)
        role_cls = mro[rol_idx - 1]
        role_taker_cls = role_cls.get_role_taker_type()
        mro[rol_idx] = role_taker_cls

    # Iterate in MRO order of the first class
    for candidate in mros[0]:
        if all(candidate in mro for mro in mros[1:]):
            return candidate

    return None


@lru_cache
def role_aware_inheritance_path_length(
        child_class: Type,
        parent_class: Type,
) -> Union[float, int]:
    """
    Calculate the inheritance path length between two classes taking roles into account.
    Every inheritance level that lies between `child_class` and `parent_class` increases the length by one.
    In case of multiple inheritance, the path length is calculated for each branch and the minimum is returned.

    :param child_class: The child class.
    :param parent_class: The parent class.
    :return: The minimum path length between `child_class` and `parent_class` or None if no path exists.
    """
    if not issubclass_or_role(child_class, parent_class):
        return float("inf")

    return _role_aware_inheritance_path_length(child_class, parent_class, 0)


def _role_aware_inheritance_path_length(
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
        child_bases = set(child_class.__bases__)
        if Role in child_bases and child_class is not Role:
            role_taker_type = child_class.get_role_taker_type()
            if role_taker_type is not None:
                child_bases.add(role_taker_type)
        return min(
            _role_aware_inheritance_path_length(base, parent_class, current_length + 1)
            for base in child_bases
            if issubclass_or_role(base, parent_class)
        )


@lru_cache
def issubclass_or_role(child: Type, parent: Type | Tuple[Type, ...]) -> bool:
    """
    Check if `child` is a subclass of `parent` or if `child` is a Role whose role taker is a subclass of `parent`.

    :param child: The child class.
    :param parent: The parent class.
    :return: True if `child` is a subclass of `parent` or if `child` is a Role for `parent`, False otherwise.
    """
    if issubclass(child, parent):
        return True
    if issubclass(child, Role) and child is not Role:
        role_taker_type = child.get_role_taker_type()
        if issubclass_or_role(role_taker_type, parent):
            return True
    return False


@dataclass
class Role(Generic[T], ABC):
    """
    Represents a role with generic typing. This is used in Role Design Pattern in OOP.

    This class serves as a container for defining roles with associated generic
    types, enabling flexibility and type safety when modeling role-specific
    behavior and data.
    """

    _role_taker_roles: ClassVar[Dict[Any, List[Role]]] = defaultdict(list)
    _role_role_takers: ClassVar[Dict[Role, List[Any]]] = defaultdict(list)

    @classmethod
    @lru_cache(maxsize=None)
    def get_role_taker_type(cls) -> Type[T]:
        """
        :return: The type of the role taker.
        """
        return get_generic_type_param(cls, Role.__name__)[0]

    @classmethod
    @abstractmethod
    def role_taker_field(cls) -> Field:
        """
        :return: the field that holds the role taker instance.
        """
        ...

    @property
    def role_taker(self) -> T:
        """
        :return: The role taker instance.
        """
        return getattr(self, self.role_taker_field().name)

    @classmethod
    @lru_cache
    def all_role_taker_types(cls) -> Tuple[Type, ...]:
        role_taker_type = cls.get_role_taker_type()
        all_role_taker_types = [role_taker_type]
        while issubclass(role_taker_type, Role):
            role_taker_type = role_taker_type.get_role_taker_type()
            all_role_taker_types.append(role_taker_type)
        return tuple(all_role_taker_types)

    def __getattr__(self, item):
        """
        Get an attribute from the role taker when not found on the class.

        :param item: The attribute name to retrieve.
        :return: The attribute value if found in the role taker, otherwise raises AttributeError.
        """
        if hasattr(self.role_taker, item):
            return getattr(self.role_taker, item)
        # for role in self.role_taker_roles:
        #     if role is self:
        #         continue
        #     if hasattr(role, item):
        #         return getattr(role, item)
        raise AttributeError(
            f"'{self.__class__.__name__}' object has no attribute '{item}'"
        )

    @property
    def role_taker_roles(self) -> List[Role]:
        """
        :return: All roles of the role taker instance.
        """
        return Role._role_taker_roles[self.role_taker]

    def __setattr__(self, key, value):
        """
        Set an attribute on the role taker instance if the role taker has this attribute,
         otherwise set on this instance directly.
        """
        if key == self.role_taker_field().name:
            object.__setattr__(self, "_direct_role_taker", value)

        if key != self.role_taker_field().name and hasattr(self.role_taker, key):
            setattr(self.role_taker, key, value)
        if key == self.role_taker_field().name or hasattr(self, key):
            super().__setattr__(key, value)
        if key == self.role_taker_field().name:
            role_taker = value
            Role._role_taker_roles[role_taker].append(self)
            Role._role_role_takers[self].append(role_taker)
            if isinstance(role_taker, Role):
                rt = role_taker.role_taker
                Role._role_taker_roles[rt].append(self)
                Role._role_role_takers[self].append(rt)

    def __hash__(self):
        curr = self
        while isinstance(curr, Role):
            rt = getattr(curr, "_direct_role_taker", None)
            if rt is not None:
                curr = rt
            else:
                curr = curr.role_taker
        return hash(id(curr))

    def __eq__(self, other):
        # if not isinstance(other, self.__class__):
        #     return False
        return hash(self) == hash(other)


def make_tuple(obj: Any) -> Tuple:
    """
    Ensure the given object is a tuple.

    :param obj: The object to convert.
    :return: A tuple containing the object or the object itself if it's already a tuple.
    """
    if hasattr(obj, "__iter__") and not isinstance(obj, (str, bytes)):
        return tuple(obj)
    else:
        return (obj,)
