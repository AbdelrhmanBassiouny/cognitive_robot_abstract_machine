"""
The objects that rules infer, kept so that one rule answer always denotes one object.

For a class ``H``, an inference variable ``inference(H)(k1=t1, ..., kn=tn)`` stands for
the function term ``f_H(t1, ..., tn)``: for a given binding of its keyword arguments
there is at most one ``H`` object. This module keeps that object, so that
re-evaluating a rule, or evaluating another rule over the same class and binding,
returns it instead of constructing a duplicate.
"""

from __future__ import annotations

import weakref
from dataclasses import dataclass, field
from enum import Enum
from numbers import Number

from typing_extensions import Any, Callable, Dict, FrozenSet, Hashable, Optional, Type

from krrood.singleton import SingletonMeta

# %% argument keys

LITERAL_TYPES = (Number, str, bytes, Enum, type(None))
"""
The types whose values identify an inferred object by value rather than by identity.
"""


class ArgumentComparison(Enum):
    """
    How an argument value is compared when looking up an inferred object.
    """

    VALUE = "value"
    """
    The argument is a scalar literal and is compared by its value and type.
    """

    IDENTITY = "identity"
    """
    The argument is an object (hashable or not) and is compared by identity.
    """


@dataclass(frozen=True)
class ArgumentKey:
    """
    The part of an inferred object's key contributed by one keyword argument.
    """

    name: str
    """
    The keyword the argument is passed under.
    """

    comparison: ArgumentComparison
    """
    Whether :attr:`value` holds the literal itself or the identity of the object.
    """

    value_type: Type
    """
    The type of the argument value, so that equal values of different types (for
    example ``True`` and ``1``) stay apart.
    """

    value: Hashable
    """
    The literal value, or the identity of the argument object.
    """

    @classmethod
    def from_argument(cls, name: str, value: Any) -> ArgumentKey:
        """
        :param name: The keyword the argument is passed under.
        :param value: The argument value.
        :return: The key part of the argument: scalar literals by value, everything else
            by identity.
        """
        if isinstance(value, LITERAL_TYPES):
            return cls(name, ArgumentComparison.VALUE, type(value), value)
        return cls(name, ArgumentComparison.IDENTITY, type(value), id(value))


@dataclass(frozen=True)
class InferredObjectKey:
    """
    The identity of an inferred object: its class and the binding of its arguments.
    """

    inferred_type: Type
    """
    The class of the inferred object.
    """

    arguments: FrozenSet[ArgumentKey]
    """
    The key parts of the keyword arguments the object is constructed from.
    """

    @classmethod
    def from_arguments(
        cls, inferred_type: Type, arguments: Dict[str, Any]
    ) -> InferredObjectKey:
        """
        :param inferred_type: The class of the inferred object.
        :param arguments: The keyword arguments the object is constructed from.
        :return: The key identifying the object.
        """
        return cls(
            inferred_type,
            frozenset(
                ArgumentKey.from_argument(name, value)
                for name, value in arguments.items()
            ),
        )


# %% registry entries


@dataclass(frozen=True)
class StrongReference:
    """
    A reference with the call interface of :class:`weakref.ref` for objects that
    cannot be referenced weakly.
    """

    referent: Any
    """
    The referenced object.
    """

    def __call__(self) -> Any:
        """
        :return: The referenced object.
        """
        return self.referent

    @staticmethod
    def weak_where_possible(
        referent: Any, on_death: Optional[Callable[[weakref.ref], None]] = None
    ) -> Callable[[], Any]:
        """
        :param referent: The object to reference.
        :param on_death: Called with the weak reference once *referent* is gone.
        :return: A weak reference to *referent*, or a :class:`StrongReference` if
            *referent* cannot be referenced weakly.
        """
        if type(referent).__weakrefoffset__ == 0:
            return StrongReference(referent)
        return weakref.ref(referent, on_death)


@dataclass
class InferredObjectEntry:
    """
    One inferred object together with the arguments compared by identity that it was
    constructed from.
    """

    reference: Callable[[], Any]
    """
    A weak reference to the inferred object, or a :class:`StrongReference` when the
    object cannot be referenced weakly. A weak reference returns ``None`` once the object
    is gone.
    """

    argument_references: Dict[str, Callable[[], Any]]
    """
    References to the arguments compared by identity, weak where the argument supports
    it. They tell a live argument apart from a later object that reuses the identity of
    an argument that is gone.
    """

    @property
    def inferred_object(self) -> Any:
        """
        :return: The inferred object, or ``None`` if it no longer exists.
        """
        return self.reference()

    def was_inferred_from(self, arguments: Dict[str, Any]) -> bool:
        """
        :param arguments: Arguments whose key equals the key of this entry.
        :return: Whether every argument compared by identity is the very object this
            entry was inferred from.
        """
        return all(
            reference() is arguments[name]
            for name, reference in self.argument_references.items()
        )


# %% registry


@dataclass
class InferredObjectRegistry(metaclass=SingletonMeta):
    """
    The objects inferred by rules, at most one per class and argument binding.

    Scalar literal arguments (numbers, strings, bytes, ``None`` and enumeration members)
    are compared by value and type; every other argument, including unhashable values
    such as lists and sets, is compared by identity. Inferred objects are held weakly
    where they support it: once nothing else references an inferred object, its entry
    is dropped and a later evaluation constructs a new one. Arguments compared by
    identity are referenced weakly too, so the registry keeps neither an inferred object
    nor its arguments alive. Objects and arguments that cannot be referenced weakly,
    such as lists, are held until the entry is dropped or :meth:`clear` is called.
    """

    _entries: Dict[InferredObjectKey, InferredObjectEntry] = field(
        default_factory=dict, init=False, repr=False
    )
    """
    The live inferred objects by their key.
    """

    def object_for(self, inferred_type: Type, arguments: Dict[str, Any]) -> Any:
        """
        Return the object of *inferred_type* inferred from *arguments*, constructing and
        recording it if no live one exists.

        :param inferred_type: The class of the object.
        :param arguments: The keyword arguments to construct the object from.
        :return: The single object of *inferred_type* for *arguments*.
        """
        key = InferredObjectKey.from_arguments(inferred_type, arguments)
        entry = self._entries.get(key)
        inferred_object = None if entry is None else entry.inferred_object
        if inferred_object is not None and entry.was_inferred_from(arguments):
            return inferred_object
        inferred_object = inferred_type(**arguments)
        self._entries[key] = self._entry_for(inferred_object, key, arguments)
        return inferred_object

    def _entry_for(
        self, inferred_object: Any, key: InferredObjectKey, arguments: Dict[str, Any]
    ) -> InferredObjectEntry:
        """
        :param inferred_object: The object just inferred.
        :param key: The key the object is recorded under.
        :param arguments: The arguments the object was constructed from.
        :return: The entry recording *inferred_object*, which drops itself from the
            registry once the object is gone.
        """
        return InferredObjectEntry(
            StrongReference.weak_where_possible(
                inferred_object,
                lambda dead_reference: self._forget(key, dead_reference),
            ),
            {
                argument_key.name: StrongReference.weak_where_possible(
                    arguments[argument_key.name]
                )
                for argument_key in key.arguments
                if argument_key.comparison is ArgumentComparison.IDENTITY
            },
        )

    def _forget(self, key: InferredObjectKey, dead_reference: weakref.ref) -> None:
        """
        Drop the entry under *key* if it still refers to the object that is gone.

        :param key: The key of the entry.
        :param dead_reference: The weak reference to the object that is gone.
        """
        entry = self._entries.get(key)
        if entry is not None and entry.reference is dead_reference:
            del self._entries[key]

    @classmethod
    def clear(cls) -> None:
        """
        Forget every inferred object, so the next evaluation constructs new ones.
        """
        cls.clear_instance()
