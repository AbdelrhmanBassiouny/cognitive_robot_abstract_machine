from __future__ import annotations

import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, fields, is_dataclass
from functools import lru_cache, cached_property

from typing_extensions import Type, get_origin, Any, Dict, List, TypeVar, Iterator

from krrood.class_diagrams.exceptions import ClassIsUnMappedInClassDiagram
from krrood.class_diagrams.utils import (
    T,
    all_nearest_common_ancestors,
)
from krrood.class_diagrams.wrapped_field import WrappedField
from krrood.entity_query_language.core.mapped_variable import Attribute
from krrood.patterns.subclass_safe_generic import SubClassSafeGeneric
from krrood.symbol_graph.symbol_graph import Symbol, PredicateClassRelation, SymbolGraph
from krrood.utils import get_generic_type_param


@dataclass(eq=False)
class HasRoles:
    """Mixin that gives a role taker a registry of its active roles."""

    roles: Dict[type, Any] = field(default_factory=dict, init=False)


@dataclass
class Role(HasRoles, SubClassSafeGeneric[T], Symbol, ABC):
    """
    Represents a role with generic typing. This is used in Role Design Pattern in OOP.

    Roles are extensions of the role taker's behaviour and data in different contexts.
    Roles live side-by-side with the role taker: they never overwrite the role taker's
    data or behaviour, only extend it.

    Role-native attributes are accessed directly from the role instance.  Attributes that
    belong to the role taker are exposed on the role through the generated ``RoleFor<Taker>``
    mixin properties (produced by :class:`RoleTransformer`).

    Role takers that inherit from :class:`HasRoles` automatically receive a ``roles`` dict
    keyed by role type, populated when each role is instantiated.

    Roles and role takers are considered the same entity (same hash, equal):
    >>> student = Student(person=person)
    >>> person == student
    True
    >>> hash(person) == hash(student)
    True
    """

    def __post_init__(self):
        # Subclasses that define __post_init__ must call super().__post_init__().
        role_taker = self.role_taker
        if isinstance(role_taker, HasRoles):
            role_taker.roles[type(self)] = self
        self._update_mapping_between_roles_and_role_takers(role_taker)

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Make fields from common bases (shared between the role class and its role-taker
        # type) init=False so the dataclass constructor does not require them.  Delegation
        # of those fields is handled by the generated RoleFor<Taker> mixin properties.
        for common_base in all_nearest_common_ancestors(
            (cls.get_role_taker_type(), cls)
        ):
            if common_base in [ABC, object, Role]:
                continue
            if not is_dataclass(common_base):
                continue
            for field_ in fields(common_base):
                if not field_.init:
                    continue
                if field_.name == cls.role_taker_attribute_name():
                    continue
                if (
                    issubclass(common_base, Role)
                    and field_.name in Role.__annotations__
                ):
                    continue
                type_ = field_.type
                if isinstance(field_.type, str):
                    try:
                        type_ = eval(
                            field_.type, sys.modules[common_base.__module__].__dict__
                        )
                    except NameError:
                        pass
                cls._update_field_kwargs(field_.name, {"init": False}, type_=type_)

    @classmethod
    def has_role(cls, role_taker: T, role_type: Type[Role]) -> bool:
        """:return: Whether the role taker has the given role type."""
        return any(cls.yield_taker_roles_of_type(role_taker, role_type))

    @property
    def role_taker_roles(self) -> List[Role]:
        """:return: All roles of the role taker instance."""
        return self.get_taker_roles_of_type(self.role_taker, Role)

    @classmethod
    def get_taker_roles_of_type(
        cls, role_taker: T, role_type: Type[Role[T]]
    ) -> List[Role[T]]:
        """:return: All roles of the given type for the role taker instance."""
        return list(cls.yield_taker_roles_of_type(role_taker, role_type))

    @classmethod
    def yield_taker_roles_of_type(
        cls, role_taker: T, role_type: Type[Role[T]]
    ) -> Iterator[Role[T]]:
        """:return: All roles of the given type for the role taker instance."""
        wrapped_taker = SymbolGraph().get_wrapped_instance(role_taker)
        yield from (
            relation.source.instance
            for relation in SymbolGraph().get_incoming_relations_with_type(
                wrapped_taker, HasRoleTaker
            )
            if isinstance(relation.source.instance, role_type)
        )

    @property
    def all_role_takers(self) -> List[Any]:
        """:return: All role takers of the role instance."""
        return list(self.yield_takers_of_role(self))

    @classmethod
    def yield_takers_of_role(cls, role: Role) -> Iterator[Any]:
        """:return: All role takers of the given role."""
        wrapped_role = SymbolGraph().get_wrapped_instance(role)
        yield from (
            relation.target.instance
            for relation in SymbolGraph().get_outgoing_relations_with_type(
                wrapped_role, HasRoleTaker
            )
        )

    @classmethod
    @lru_cache
    def get_root_role_taker_type(cls) -> Type[T]:
        """:return: The root (non-Role) type of the role taker chain."""
        current_cls = cls
        while issubclass(current_cls, Role):
            current_cls = current_cls.get_role_taker_type()
        return current_cls

    @classmethod
    @lru_cache
    def get_role_generic_type(cls) -> Type[T] | TypeVar:
        """:return: The generic type parameter of this role class."""
        if cls is Role:
            return T
        res = get_generic_type_param(cls, Role)
        return res[0] if res else T

    @classmethod
    def get_role_taker_type(cls) -> Type[T]:
        """:return: The type of the role taker."""
        try:
            type_ = next(
                f.type for f in fields(cls) if f.name == cls.role_taker_attribute_name()
            )
        except StopIteration:
            type_ = get_generic_type_param(cls, Role)[0]
        if isinstance(type_, str):
            try:
                type_ = sys.modules[cls.__module__].__dict__[type_]
            except KeyError:
                type_ = eval(type_, sys.modules[cls.__module__].__dict__)
        if isinstance(type_, TypeVar):
            if type_.__bound__ is not None:
                type_ = type_.__bound__
            else:
                raise ValueError(f"TypeVar {type_} has no bound")
        return type_

    @classmethod
    @lru_cache
    def updates_role_taker_type(cls) -> bool:
        """:return: True if this role narrows its parent role's taker type."""
        if Role in cls.__bases__:
            return False
        role_taker_type = cls.get_role_taker_type()
        for parent in cls.__bases__:
            if not issubclass(parent, Role):
                continue
            parent_origin_type = get_origin(parent) or parent
            parent_role_taker_type = parent_origin_type.get_role_taker_type()
            if parent_role_taker_type is not role_taker_type:
                return True
        return False

    @classmethod
    @abstractmethod
    def role_taker_attribute(cls) -> Attribute:
        """:return: The symbolic representation of the role-taker field."""
        ...

    @classmethod
    def role_taker_attribute_name(cls) -> str:
        """:return: The name of the field that holds the role taker instance."""
        return cls.role_taker_attribute()._attribute_name_

    @cached_property
    def role_taker(self) -> T:
        """Retrieves the role taker instance."""
        return getattr(self, self.role_taker_attribute_name())

    @property
    def root_persistent_entity(self):
        """:return: The root persistent entity in the role hierarchy."""
        curr = self
        while isinstance(curr, Role):
            rt = getattr(curr, curr.role_taker_attribute_name())
            if rt is not None:
                curr = rt
            else:
                curr = curr.role_taker
        return curr

    def _update_mapping_between_roles_and_role_takers(self, role_taker: T):
        """
        Update the SymbolGraph mapping between this role and its role taker.

        Silently skips if this class is not registered in the SymbolGraph class
        diagram (e.g. test-only or dynamically created classes).

        :param role_taker: The role taker instance to link.
        """
        try:
            wrapped_self = SymbolGraph().get_wrapped_instance(self)
            wrapped_role_taker = SymbolGraph().ensure_wrapped_instance(role_taker)
            SymbolGraph().add_relation(
                HasRoleTaker(
                    wrapped_self, wrapped_role_taker, self.role_taker_wrapped_field
                )
            )
            if isinstance(role_taker, Role):
                for relation in SymbolGraph().get_outgoing_relations_with_type(
                    wrapped_role_taker, HasRoleTaker
                ):
                    SymbolGraph().add_relation(
                        HasRoleTaker(wrapped_self, relation.target, relation.wrapped_field)
                    )
        except ClassIsUnMappedInClassDiagram:
            pass

    @cached_property
    def role_taker_wrapped_field(self) -> WrappedField:
        """:return: The wrapped field of this class pointing to the role taker."""
        return next(
            wf
            for wf in SymbolGraph()
            .class_diagram.get_wrapped_class(self.__class__)
            .fields
            if wf.name == self.role_taker_attribute_name()
        )

    def __hash__(self):
        """Roles and their taker share an identity — hash via the root persistent entity."""
        return hash(self.root_persistent_entity)

    def __eq__(self, other):
        return hash(self) == hash(other)


class HasRoleTaker(PredicateClassRelation[Role]): ...
