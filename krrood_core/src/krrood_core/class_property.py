from __future__ import annotations

from collections.abc import Callable


class classproperty[ValueType]:
    """
    A decorator that allows a class method to be accessed as a property.

    An accessor marked with :func:`abc.abstractmethod` stays abstract: reading it
    answers the descriptor itself, so a subclass that supplies no value is refused at
    instantiation like any other missing abstract member.
    """

    def __init__(self, fget: Callable[[type], ValueType]) -> None:
        """
        Stores the accessor function invoked when the property is read on the owning
        class.
        """
        self.fget = fget
        """
        The underlying accessor; receives the owning class and returns the property
        value.
        """
        self.__isabstractmethod__ = getattr(fget, "__isabstractmethod__", False)
        self.__doc__ = fget.__doc__

    def __get__(self, instance: object, owner: type | None = None) -> ValueType:
        """
        Returns the property value by invoking the accessor with the owning class.
        """
        if self.__isabstractmethod__:
            return self
        return self.fget(owner if owner is not None else type(instance))
