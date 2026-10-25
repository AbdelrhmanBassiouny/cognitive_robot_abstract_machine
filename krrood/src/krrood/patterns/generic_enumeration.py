from __future__ import annotations

from enum import Enum, EnumMeta

from typing_extensions import Any, Generic

from krrood.patterns.exceptions import InvalidEnumerationKey

# %% enumeration that can be generic


class GenericEnumerationType(EnumMeta):
    """
    The type of a :class:`GenericEnumeration`, whose subscription takes a member's name
    or the types its parameters are bound to.
    """

    def __getitem__(cls, key: Any) -> Any:
        """
        :param key: The name of a member, or the types the enumeration's type parameters
            are bound to.
        :return: The member of that name, or the enumeration with its parameters bound
            to those types.
        :raises InvalidEnumerationKey: If the key is not a name and the enumeration has
            no unbound type parameter.
        """
        if isinstance(key, str):
            return super().__getitem__(key)
        if not issubclass(cls, Generic) or not cls.__parameters__:
            raise InvalidEnumerationKey(cls, key)
        return cls.__class_getitem__(key)


class GenericEnumeration(Enum, metaclass=GenericEnumerationType):
    """
    An enumeration that can be generic.

    Subscripting one that inherits :class:`~typing_extensions.Generic` with types binds
    its parameters, as in ``class Starters(NestedEnumeration[Menu])``, while
    subscripting any one with a member's name still looks up that member.

    .. note:: Only an enumeration without members can be subclassed, so the generic
        base binding its parameters declares no members.
    """
