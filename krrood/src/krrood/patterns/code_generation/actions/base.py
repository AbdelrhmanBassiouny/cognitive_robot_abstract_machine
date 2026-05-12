"""
Abstract base classes for atomic, reversible code-modification actions.

Actions are the "Command" in the Command pattern.  Each action knows how to
apply itself to a :class:`libcst.Module` and how to reverse that application.
Actions are composed into :class:`ActionPlan` objects for execution.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import libcst


class Action(ABC):
    """An atomic, reversible code modification.

    Each action operates on a :class:`libcst.Module`.  Actions are designed to
    be composed into :class:`ActionPlan` instances.  Reversal follows LIFO
    order: reversing an :class:`ActionPlan` calls :meth:`reverse` on each
    sub-action in reverse sequence.

    Subclasses must implement :meth:`apply`, :meth:`reverse`, and
    :meth:`description`.  They may override :meth:`precondition` to enable
    per-action undo validation in a future planner.
    """

    @abstractmethod
    def apply(self, module: libcst.Module) -> libcst.Module:
        """Apply this action to *module* and return the modified module.

        The returned module is typically a new :class:`libcst.Module` instance
        (libcst nodes are immutable).  Callers should use the return value, not
        the original reference.
        """

    @abstractmethod
    def reverse(self, module: libcst.Module) -> libcst.Module:
        """Reverse this action on *module* and return the restored module.

        The default implementation assumes the action stores enough state to
        undo itself.  For example, :class:`AddBaseClass` records the base it
        added so it can remove that base on reversal.
        """

    @property
    @abstractmethod
    def description(self) -> str:
        """A human-readable description of what this action does.

        Used for audit trails and debugging.  Examples:

        * ``"Add HasRoles base to Professor"``
        * ``"Create DelegatorForPerson class"``
        * ``"Add import of typing.List"``
        """

    def precondition(self, module: libcst.Module) -> bool:
        """Check whether this action can be applied to *module*.

        The default implementation always returns ``True``.  Override in
        subclasses to enable per-action undo validation.  When a planner
        supports preconditions, it calls this method before :meth:`apply`.
        """
        return True


class TransformationAction(Action, ABC):
    """An action that modifies an existing :class:`libcst.Module` in-place.

    Transformation actions alter the content of a module: adding or removing
    base classes, methods, properties, imports, decorators, etc.

    Subclasses include :class:`AddBaseClass`, :class:`AddMethod`,
    :class:`AddProperty`, :class:`AddImport`, and similar.
    """


class GenerationAction(Action, ABC):
    """An action that creates new code artifacts.

    Generation actions add new top-level constructs to a module (like new
    class definitions) or write files to disk.

    Subclasses include :class:`CreateClass`, :class:`CreateModule`, and
    :class:`WriteModule`.
    """
