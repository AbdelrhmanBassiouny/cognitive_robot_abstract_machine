from __future__ import annotations

import weakref
from _weakref import ref as weakref_ref
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from line_profiler import profile
from typing_extensions import (
    Optional,
    Union,
    Dict,
    Type,
    Generic,
    TYPE_CHECKING,
    TypeVar,
)

from ...class_diagrams.utils import (
    sort_classes_by_role_aware_inheritance_path_length,
)
from ...class_diagrams.utils import Role
from ...entity_query_language.predicate import Symbol

if TYPE_CHECKING:
    from .property_descriptor import PropertyDescriptor


monitored_type_map: Dict[Type, Type[MonitoredContainer]] = {}
"""
A mapping of container types to their monitored container types.
"""

T = TypeVar("T", bound=Symbol)


@dataclass(init=False)
class MonitoredContainer(Generic[T], ABC):
    """
    A container abstract class to be inherited from for specific container types to invoke the on-add
    callback of the descriptor. This is used by the
    :py:class:`krrood.ontomatic.property_descriptor.PropertyDescriptor` to apply
    implicit inferences.

    For example like here, the Set[Person] will be internally replaced with a MonitoredSet[Person] by the
    descriptor, this allows for catching additions/insertions/removals to the Set and applying implicit inferences:
    >>> from dataclasses import dataclass, field
    >>> from typing_extensions import Set
    >>> from krrood.ontomatic.property_descriptor.property_descriptor import PropertyDescriptor
    >>> from krrood.entity_query_language.predicate import Symbol
    ...
    >>> @dataclass
    >>> class Person(Symbol):
    >>>     name: str
    ...
    >>> @dataclass
    >>> class Company(Symbol):
    >>>     name: str
    >>>     members: Set[Person] = field(default_factory=set)
    ...
    >>> @dataclass
    >>> class Member(PropertyDescriptor):
    >>>     pass
    ...
    >>> Company.members = Member(Company, "members")
    >>> company = Company("Company")
    >>> person = Person("Person")
    >>> company.members.add(person)
    >>> assert isinstance(company.members, MonitoredSet)
    """

    def __init_subclass__(cls, **kwargs):
        """
        Hook to update the monitored_type_map with the monitored type of the subclass.
        """
        super().__init_subclass__(**kwargs)
        monitored_type_map[cls._get_monitored_type()] = cls

    def __init__(
        self, *args, descriptor: Optional[PropertyDescriptor] = None, **kwargs
    ):
        self._descriptor: PropertyDescriptor = descriptor
        self._owner_ref: Optional[weakref.ref[Symbol]] = None
        super().__init__(*args, **kwargs)

    def _bind_owner(self, owner) -> MonitoredContainer:
        """
        Bind the owning instance via a weak reference and return self.
        """
        self._owner_ref = weakref_ref(owner)
        return self

    @property
    def _owner(self):
        """
        Get the owner instance via the weak reference.
        """
        return self._owner_ref() if self._owner_ref is not None else None

    def _on_add(
        self,
        value: Symbol,
        inferred: bool = False,
        add_relation_to_the_graph: bool = True,
    ) -> Union[Symbol, weakref.ref[Symbol]]:
        """Call the descriptor on_add with the concrete owner instance

        :param value: The value to be added to the container
        :param inferred: Whether the value is inferred or not
        :param add_relation_to_the_graph: Whether to add the relation to the graph or not.
        :return: The value with a weakref if inferred is True, otherwise the value itself
        """
        owner = self._owner
        if owner is not None and add_relation_to_the_graph:
            value_owner = value
            while isinstance(value_owner, Role):
                value_owner = value_owner.role_taker
            while isinstance(owner, Role):
                owner = owner.role_taker
            self._descriptor.add_relation_to_the_graph_and_apply_implications(
                owner, value_owner, inferred=inferred
            )
        return value

    def _update(
        self,
        value: Symbol,
        inferred: bool = False,
        add_relation_to_the_graph: bool = False,
    ) -> bool:
        """
        Only add the value if it is not already in the container.

        :param value: The value to be added to the container
        :param inferred: If the value is inferred or not
        :param add_relation_to_the_graph: Whether to add the relation to the graph or not
        :return: Whether the value was added or not
        """
        if value in self:
            return False
        self._add_item(
            value,
            inferred=inferred,
            add_relation_to_the_graph=add_relation_to_the_graph,
        )
        return True

    @abstractmethod
    def _remove_item(self, item):
        """
        This method is called when an item is removed from the container. It should be implemented by subclasses.

        :param item: The item to be removed
        """
        ...

    @abstractmethod
    def _add_item(
        self,
        item: Symbol,
        inferred: bool = False,
        add_relation_to_the_graph: bool = True,
    ):
        """
        This method is called when an item is added to the container. It should be implemented by subclasses.
        In addition, this method should call the descriptor on_add method.

        :param item: The item to be added
        :param inferred: Whether the value is inferred or not
        :param add_relation_to_the_graph: Whether to call the descriptor on_add or not
        """
        ...

    @classmethod
    @abstractmethod
    def _get_monitored_type(cls) -> Type:
        """
        Get the monitored container type (i.e., the original container type)
        """
        ...

    @abstractmethod
    def _clear(self) -> None:
        """
        Clear the container.
        """
        ...


@dataclass(init=False)
class MonitoredList(MonitoredContainer, list):
    """
    A list that invokes the descriptor on_add for further implicit inferences.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._known_uris: set[str] = set()

    @classmethod
    def _get_monitored_type(cls):
        return list

    def extend(self, items):
        for item in items:
            self._add_item(item)

    def append(self, item):
        self._add_item(item)

    def add(self, value):
        self.append(value)

    def _add_item(
        self, value, inferred: bool = False, add_relation_to_the_graph: bool = True
    ):
        if value in self:
            return
        self._on_add(
            value,
            inferred=inferred,
            add_relation_to_the_graph=add_relation_to_the_graph,
        )
        # if str(value.uri) in [str(v.uri) for v in self]:
        #     raise ValueError(f"Duplicate URI detected: {value.uri}")
        # self._known_uris.add(value.uri)
        super().append(value)
        if isinstance(self._owner, Role) and hasattr(
            self._owner.role_taker, self._descriptor.field_name
        ):
            role_taker_attr = getattr(
                self._owner.role_taker, self._descriptor.field_name
            )
            role_taker_attr._add_item(
                value, inferred=inferred, add_relation_to_the_graph=False
            )

    def __setitem__(self, idx, value):
        value = self._on_add(value)
        super().__setitem__(idx, value)

    def insert(self, idx, item):
        item = self._on_add(item)
        super().insert(idx, item)

    def _remove_item(self, item):
        self.remove(item)

    def _clear(self):
        self.clear()


@dataclass(init=False)
class MonitoredSet(MonitoredContainer, set):
    """
    A set that invokes the descriptor on_add for further implicit inferences.
    """

    @classmethod
    def _get_monitored_type(cls):
        return set

    def add(self, value):
        self._add_item(value)

    def update(self, values):
        for value in values:
            self._add_item(value)

    @profile
    def _add_item(
        self, value, inferred: bool = False, add_relation_to_the_graph: bool = True
    ):
        if value in self:
            return
        # value_owner = value
        range_ = self._descriptor.range
        most_upper_range = sort_classes_by_role_aware_inheritance_path_length(
            self._descriptor.all_ranges[self._descriptor.__class__]
        )[-1]
        found = False
        if not isinstance(value, most_upper_range):
            for role in Role._role_taker_roles[value]:
                if isinstance(role, most_upper_range):
                    value = role
                    found = True
                    break
            if not found:
                for role_taker in Role._role_role_takers[value]:
                    if isinstance(role_taker, most_upper_range):
                        value = role_taker
                        break
        if (
            self._descriptor.__class__.__name__ == "HasHead"
            and value.__class__.__name__ == "Chair"
        ):
            import pdbpp

            pdbpp.set_trace()
        self._on_add(
            value,
            inferred=inferred,
            add_relation_to_the_graph=add_relation_to_the_graph,
        )
        # while isinstance(value_owner, Role):
        #     value_owner = value_owner.role_taker

        super().add(value)
        if isinstance(self._owner, Role) and hasattr(
            self._owner.role_taker, self._descriptor.field_name
        ):
            role_taker_attr = getattr(
                self._owner.role_taker, self._descriptor.field_name
            )
            role_taker_attr._add_item(
                value, inferred=inferred, add_relation_to_the_graph=False
            )

    def _remove_item(self, item):
        self.remove(item)

    def _clear(self):
        self.clear()
