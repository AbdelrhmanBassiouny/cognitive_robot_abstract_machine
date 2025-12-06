from __future__ import annotations

from dataclasses import dataclass, field

from typing_extensions import (
    Generic,
    Optional,
    Iterable,
    Dict,
    Any,
    Callable,
    List,
)
from typing_extensions import TypeVar, ClassVar

from .utils import make_list, ALL

T = TypeVar("T")


@dataclass
class HashedValue(Generic[T]):
    """
    Value wrapper carrying a stable hash identifier.
    """

    value: T
    """
    The wrapped value.
    """
    id_: Optional[int] = field(default=None)
    """
    Optional explicit identifier; if omitted, derived from value.
    """

    def __post_init__(self) -> None:
        """
        Initialize the identifier from the wrapped value when not provided.
        """
        if self.id_ is not None:
            return
        if isinstance(self.value, HashedValue):
            # General nested HashedValue: unwrap
            self.id_ = self.value.id_
            self.value = self.value.value
            return
        if hasattr(self.value, "_id_"):
            self.id_ = self.value._id_
        else:
            self.id_ = id(self.value)

    def __hash__(self) -> int:
        """Hash of the identifier."""
        return hash(self.id_)

    def __eq__(self, other: object) -> bool:
        """
        Equality based on identifier, with ALL sentinel matching any value.
        """
        if isinstance(other, ALL):
            return True
        if not isinstance(other, HashedValue):
            return False
        return self.id_ == other.id_

    def __bool__(self) -> bool:
        return bool(self.value)


@dataclass
class HashedIterable(Generic[T]):
    """
    A wrapper for an iterable that hashes its items.
    This is useful for ensuring that the items in the iterable are unique and can be used as keys in a dictionary.
    """

    iterable: Iterable[HashedValue[T]] = field(default_factory=list)
    values: Dict[int, HashedValue[T]] = field(default_factory=dict)

    def __post_init__(self):
        if self.iterable and not isinstance(self.iterable, HashedIterable):
            self.iterable = (
                HashedValue(v) if not isinstance(v, HashedValue) else v
                for v in self.iterable
            )

    def set_iterable(self, iterable):
        if iterable and not isinstance(iterable, HashedIterable):
            self.iterable = (
                HashedValue(v) if not isinstance(v, HashedValue) else v
                for v in iterable
            )

    def __iter__(self):
        """
        Iterate over the hashed values.

        :return: An iterator over the hashed values.
        """
        yield from self.values.values()
        for v in self.iterable:
            self.values[v.id_] = v
            yield v

    def __bool__(self):
        return bool(self.values) or bool(self.iterable)
