#!/usr/bin/env python3
"""
The base every error this tooling raises is built on.

Each failure carries the values that explain it as typed fields and composes its own
message from them, so a caller can read the cause without parsing a sentence. Mirrors
``krrood``'s dataclass-exception idiom without importing it: these scripts run headless
in an Action with only their own requirements installed.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class PlanDashboardError(Exception, ABC):
    """
    Something the dashboards depended on and did not get.

    Subclasses declare the context as fields and implement :meth:`error_message`; the
    message is composed once at construction, so raising and logging read alike.
    """

    def __post_init__(self) -> None:
        """
        Compose the message from the subclass's own fields.

        ``BaseException.__new__`` bypasses the usual abstract-class check, so an
        incomplete subclass is rejected here instead of constructing silently.
        """
        if type(self).__abstractmethods__:
            missing = ", ".join(sorted(type(self).__abstractmethods__))
            raise TypeError(
                f"{type(self).__name__} is abstract without an implementation of "
                f"{missing}."
            )
        super().__init__(self.error_message())

    @abstractmethod
    def error_message(self) -> str:
        """:return: What went wrong, composed from this error's own fields."""

    def __str__(self) -> str:
        """:return: The composed message.

        Stated here because stdlib mixins such as ``LookupError`` render their args
        rather than the message ``__post_init__`` built.
        """
        return Exception.__str__(self)
