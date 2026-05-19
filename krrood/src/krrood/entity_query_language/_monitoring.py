"""
Isolated monitoring infrastructure for EQL object creation tracking.

This module intentionally has no intra-package EQL imports so that it can be
safely imported by modules (variable.py, query.py) that are themselves
dependencies of the main explanation module, without triggering circular
imports.
"""
from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, List, Optional, Type, Callable, Union


def filter_stack(
        stack: List[inspect.FrameInfo], internal_package: Optional[str] = None
) -> List[inspect.FrameInfo]:
    """
    Filter the stack to remove external libraries and optionally keep only a specific package.

    :param stack: The stack to filter.
    :param internal_package: The name of the package to focus on.
    :return: The filtered stack.
    """
    filtered = []
    for frame in stack:
        path = frame.filename
        if "site-packages" in path or "dist-packages" in path:
            continue
        if internal_package and internal_package not in path:
            continue
        filtered.append(frame)
    return filtered


@dataclass
class MonitoredRegistry:
    """
    Registry for monitoring EQL object creation stacks.
    Acts as a class decorator and provides lookup methods.
    """
    _monitored: set[type] = field(default_factory=set)

    def __call__(self, cls: Type) -> Type:
        """Decorate a class to automatically record its creation stack."""
        cls._is_monitored_ = True
        self._monitored.add(cls)

        original_post_init = getattr(cls, "__post_init__", lambda self: None)

        @wraps(original_post_init)
        def new_post_init(self, *args, **kwargs):
            raw_stack = inspect.stack()[1:]
            self._creation_stack = filter_stack(raw_stack)
            original_post_init(self, *args, **kwargs)

        cls.__post_init__ = new_post_init
        return cls

    def get_stack(self, instance: Any) -> Optional[List[inspect.FrameInfo]]:
        """Retrieve the creation stack for a monitored instance."""
        if not self.is_monitored(type(instance)):
            return None
        return instance._creation_stack

    def is_monitored(self, target: Union[Type, Callable]) -> bool:
        """Check whether a class or callable is monitored."""
        return target in self._monitored or bool(getattr(target, "_is_monitored_", False))

    def unregister(self, cls: Type) -> None:
        """Remove a class from monitoring."""
        self._monitored.discard(cls)
        if hasattr(cls, "_is_monitored_"):
            del cls._is_monitored_

    @property
    def monitored_classes(self) -> tuple[type, ...]:
        """Return an immutable snapshot of all monitored classes."""
        return tuple(self._monitored)


# Singleton — import this wherever @monitored decoration is needed.
monitored = MonitoredRegistry()
