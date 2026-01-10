from __future__ import annotations

from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from typing_extensions import TYPE_CHECKING, Type, List, Any, Dict


if TYPE_CHECKING:
    from .property_descriptor import PropertyDescriptor
    from ...entity_query_language.predicate import Symbol


@dataclass
class TransitiveProperty:
    """
    A mixin for descriptors that are transitive.
    """

    ...


@dataclass
class HasInverseProperty(ABC):
    """
    A mixin for descriptors that have an inverse property.
    """

    @classmethod
    @abstractmethod
    def get_inverse(cls) -> Optional[Type[PropertyDescriptor]]:
        """
        The inverse of this property.
        """
        ...


@dataclass
class HasEquivalentProperties(ABC):

    @classmethod
    @abstractmethod
    def get_equivalent_properties(cls) -> List[Type[PropertyDescriptor]]:
        """
        The equivalent properties of this property.
        """
        ...


@dataclass
class HasDisjointProperties(ABC):

    @classmethod
    @abstractmethod
    def get_disjoint_properties(self) -> List[Type[PropertyDescriptor]]:
        """
        The disjoint properties of this property.
        """
        ...


@dataclass
class SymmetricProperty(ABC):
    """
    Means that the property is symmetric, it can interchange the subject and object of a statement.
    """

    ...


@dataclass
class ASymmetricProperty(ABC):
    """
    Means that the property is anti-symmetric, it cannot interchange the subject and object of a statement.
    """

    ...


@dataclass
class ReflexiveProperty(ABC):
    """
    Means that the property is reflexive, it relates every individual to itself.
    """

    ...


@dataclass
class IrreflexiveProperty(ABC):
    """
    Means that the property is irreflexive, it does not relate any individual to itself.
    """

    ...


@dataclass
class IsBaseClass(ABC):
    """
    Means that the class is the base class.
    """

    ...


@dataclass
class RoleForMixin(ABC):
    """A mixin for property descriptors that represent a role-for relationship."""

    ...


@dataclass
class HasChainAxioms(ABC):
    """
    A mixin for descriptors that have property chain axioms.
    """

    @classmethod
    @abstractmethod
    def get_chain_axioms(
        cls,
    ) -> Dict[Type[PropertyDescriptor], List[Tuple[Type[PropertyDescriptor], ...]]]:
        """
        Returns a mapping where the key is the target property (the implication)
        and the value is a list of chains (tuples of property descriptors) that imply it.
        """
        ...


@dataclass
class PersistentEntityMixin(ABC):
    """A mixin for classes that are persistent entities."""

    property_range_subject_map: Dict[PropertyDescriptor, Dict[Type, Symbol]] = field(
        init=False, default_factory=lambda: defaultdict(dict)
    )
    """
    A mapping from property descriptors to a mapping of ranges to the subject instance
    """
