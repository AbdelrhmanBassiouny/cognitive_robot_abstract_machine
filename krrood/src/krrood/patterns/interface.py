from __future__ import annotations

import inspect
from abc import ABC
from functools import lru_cache

from typing_extensions import Any, Self

from krrood.patterns.exceptions import (
    InterfaceInstantiationError,
    MissingInterfaceAttributesError,
)

# %% interfaces


class Interface(ABC):
    """
    A class that only declares the typed attributes and methods its subclasses provide,
    as fields or properties. It cannot be instantiated, and neither can a class that
    does not provide every attribute its interfaces declare.

    .. note::
        Never make an interface a dataclass, which turns its declarations into fields.
        A base class with fields or behaviour of its own subclasses :class:`abc.ABC`.
        Only a class naming :class:`Interface` among its own bases is an interface.
    """

    def __new__(cls, *args: Any, **kwargs: Any) -> Self:
        if Interface.is_interface(cls):
            raise InterfaceInstantiationError(cls)
        missing_attributes = Interface.missing_attributes(cls)
        if missing_attributes:
            raise MissingInterfaceAttributesError(cls, missing_attributes)
        return super().__new__(cls)

    @staticmethod
    def is_interface(class_: type) -> bool:
        """
        :param class_: The class to check.
        :return: Whether the class names :class:`Interface` among its own bases.
        """
        return Interface in class_.__bases__

    @staticmethod
    @lru_cache(maxsize=None)
    def missing_attributes(class_: type) -> tuple[str, ...]:
        """
        :param class_: A class implementing interfaces.
        :return: The attributes the interfaces of the class declare that neither the
            class nor any of its other bases declares or defines, in name order.
        """
        implementations = [
            base for base in class_.__mro__ if not Interface.is_interface(base)
        ]
        declared_attributes = {
            name
            for base in class_.__mro__
            if Interface.is_interface(base)
            for name in inspect.get_annotations(base)
        }
        return tuple(
            sorted(
                name
                for name in declared_attributes
                if not any(
                    name in vars(base) or name in inspect.get_annotations(base)
                    for base in implementations
                )
            )
        )
