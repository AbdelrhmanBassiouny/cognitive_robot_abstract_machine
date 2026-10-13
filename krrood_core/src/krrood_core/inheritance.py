from __future__ import annotations

from functools import lru_cache
from inspect import isclass

from typing_extensions import Type


@lru_cache(maxsize=None)
def inheritance_path_length(child_class: Type, parent_class: Type) -> int | None:
    """
    The number of inheritance levels between two classes.

    For multiple inheritance the length is computed per branch and the minimum is
    returned.

    :param child_class: The child class.
    :param parent_class: The parent class.
    :return: The minimum path length, or ``None`` when ``child_class`` does not derive
        from ``parent_class``.
    """
    if not (
        isclass(child_class)
        and isclass(parent_class)
        and issubclass(child_class, parent_class)
    ):
        return None
    return _path_length_from(child_class, parent_class, 0)


def _path_length_from(
    child_class: Type, parent_class: Type, current_length: int
) -> int:
    """
    :param child_class: A class deriving from ``parent_class``.
    :param parent_class: The parent class.
    :param current_length: The length of the path walked so far.
    :return: The minimum path length between ``child_class`` and ``parent_class``.
    """
    if child_class == parent_class:
        return current_length
    return min(
        _path_length_from(base, parent_class, current_length + 1)
        for base in child_class.__bases__
        if issubclass(base, parent_class)
    )
