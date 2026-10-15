from __future__ import annotations

from abc import ABC

from typing_extensions import Any, Self

from krrood.patterns.exceptions import InterfaceInstantiationError

# %% interfaces


class Interface(ABC):
    """
    A class that only declares what its subclasses provide.

    An interface cannot be instantiated, but its subclasses can. Its annotations declare
    attributes for its subclasses to provide, so
    :class:`~krrood.patterns.subclass_safe_generic.SubClassSafeGeneric` never narrows
    them into fields.
    """

    def __new__(cls, *args: Any, **kwargs: Any) -> Self:
        if Interface.is_interface(cls):
            raise InterfaceInstantiationError(cls)
        return super().__new__(cls)

    @staticmethod
    def is_interface(class_: type) -> bool:
        """
        :param class_: The class to check.
        :return: Whether the class names :class:`Interface` among its own bases.
        """
        return Interface in class_.__bases__
