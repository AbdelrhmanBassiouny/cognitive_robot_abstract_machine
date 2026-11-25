"""
The kinds of collections krrood recognises, for values and for field annotations alike.
"""

from __future__ import annotations

import collections.abc
from enum import Enum, auto
from inspect import isclass

from sortedcontainers import SortedSet
from typing_extensions import Any, get_args, get_origin

from krrood.class_diagrams.utils import common_base_class

# %% collection kinds


class CollectionKind(Enum):
    """
    A kind of collection, each member holding the classes of that kind.

    The classes serve both :func:`isinstance` on values and the origin of a generic
    annotation, since ``get_origin(list[int])`` is :class:`list`.
    """

    ELEMENT_SEQUENCE = (list, tuple, set, frozenset, SortedSet)
    """
    Unkeyed collections of elements, each rebuilt from its elements by calling its class
    on them.
    """

    MAPPING = (dict,)
    """
    Collections of key-value pairs.
    """

    @classmethod
    def declared_element_type(cls, *, annotation: Any) -> Any:
        """
        :param annotation: The annotation of a value whose elements are read.
        :return: The type of the elements of a parameterized collection: the key type of
            a mapping, the lowest common base class of a tuple's positions, else the
            parameter. Any other annotation is returned unchanged.
        """
        element_types = cls.declared_element_types(annotation=annotation)
        if len(element_types) == 1:
            return element_types[0]
        return common_base_class(list(element_types))

    @staticmethod
    def declared_element_types(*, annotation: Any) -> tuple[Any, ...]:
        """
        :param annotation: The annotation of a value whose elements are read.
        :return: The distinct types the elements of a parameterized collection are
            declared as: the key type of a mapping, each position of a tuple, else the
            parameter. Any other annotation is returned alone.
        """
        collection_class = get_origin(annotation)
        element_types = get_args(annotation)
        if not (
            isclass(collection_class)
            and issubclass(collection_class, collections.abc.Iterable)
            and element_types
        ):
            return (annotation,)
        if issubclass(collection_class, collections.abc.Mapping):
            return element_types[:1]
        return tuple(
            element_type
            for element_type in dict.fromkeys(element_types)
            if element_type is not Ellipsis
        )

    @classmethod
    def all_classes(cls) -> tuple[type, ...]:
        """
        :return: The classes of every kind of collection.
        """
        return tuple(
            collection_class
            for collection_kind in cls
            for collection_class in collection_kind.value
        )


# %% declared value kinds


class DeclaredValueKind(Enum):
    """
    What an annotation declares a value to be, regardless of whether the value can be
    iterated at runtime.
    """

    COLLECTION = auto()
    """
    A collection of elements, such as ``list[X]`` or ``Sequence[X]``.
    """

    SINGLE_VALUE = auto()
    """
    One value, such as an instance of a class, even when that class can be iterated.
    """

    UNDECLARED = auto()
    """
    Nothing the kind of the value can be read from, such as ``Any`` or a type variable.
    """

    @classmethod
    def from_annotation(cls, *, annotation: Any) -> DeclaredValueKind:
        """
        :param annotation: An annotation that is not a union.
        :return: The kind of value the annotation declares: a collection for the classes
            of a :class:`CollectionKind` and for the abstract collections of
            :mod:`collections.abc`, one value for any other class.
        """
        annotated_class = get_origin(annotation) or annotation
        if not isclass(annotated_class):
            return cls.UNDECLARED
        if issubclass(annotated_class, CollectionKind.all_classes()):
            return cls.COLLECTION
        if annotated_class.__module__ == collections.abc.__name__:
            return cls.COLLECTION
        return cls.SINGLE_VALUE
