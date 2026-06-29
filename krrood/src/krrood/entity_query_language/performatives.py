"""
Performatives -- speech acts over EQL descriptions.

A *performative* applies an illocutionary force (Searle 1976; cf. the FIPA-ACL / KQML performatives) to a
propositional *content* expressed as an EQL :class:`~krrood.entity_query_language.core.base_expressions.SymbolicExpression`.
The force decides what is *done* with the description -- found, achieved, observed, explained, asserted,
warned -- while the description stays a reusable, verbalizable query.

Atomic acts (:class:`Performative`) and their compositions (:class:`Composition`: sequential / parallel /
try) share the :class:`Performable` interface, so a plan is a tree of speech acts that both executes
(:meth:`Performable.perform`) and verbalizes (:meth:`Performable.verbalize`).

..note:: This module owns the *specification* and *verbalization* of acts. Executing a motion act
    (:class:`Achieve`/:class:`Observe`) needs a solver/monitor backend, and executing a composition needs
    the plan layer; those ``perform`` methods raise :class:`NotImplementedError` here until a backend
    provides them.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from typing_extensions import Any, List, Protocol, runtime_checkable

from krrood.entity_query_language.core.base_expressions import SymbolicExpression
from krrood.entity_query_language.verbalization.pipeline import verbalize_expression
from krrood.exceptions import DataclassException


@runtime_checkable
class Performable(Protocol):
    """A speech act that can be performed and verbalized: an atomic act or a composition of them."""

    def perform(self) -> Any:
        """Carry out the act (evaluate / solve / monitor / compose) and return its result."""

    def verbalize(self) -> str:
        """:return: the act rendered as a natural-language utterance."""


@dataclass
class Performative(ABC):
    """An atomic speech act applied to an EQL description."""

    content: SymbolicExpression
    """The propositional content -- the EQL description the force is applied to."""

    @abstractmethod
    def perform(self) -> Any:
        """Carry out the act and return its result."""

    @abstractmethod
    def verbalize(self) -> str:
        """:return: the act as a natural-language utterance."""


@dataclass
class Find(Performative):
    """Search the world for the values matching the description -- the existing query speech act."""

    def perform(self) -> List[Any]:
        return list(self.content.evaluate())

    def verbalize(self) -> str:
        return verbalize_expression(self.content)


@dataclass
class Achieve(Performative):
    """Bring about the described state -- a motion goal compiled to a solver by a backend."""

    def perform(self) -> Any:
        raise NotImplementedError(
            "Achieve is executed by a motion/solver backend (see the giskard prototype)."
        )

    def verbalize(self) -> str:
        return f"Achieve that {verbalize_expression(self.content)}"


@dataclass
class Observe(Performative):
    """Monitor whether the described condition holds -- a monitor provided by a backend."""

    def perform(self) -> Any:
        raise NotImplementedError(
            "Observe is executed by a monitor backend (see the giskard prototype)."
        )

    def verbalize(self) -> str:
        return f"Observe whether {verbalize_expression(self.content)}"


@dataclass
class Inform(Performative):
    """Assert the described proposition to a listener."""

    def perform(self) -> str:
        return self.verbalize()

    def verbalize(self) -> str:
        return verbalize_expression(self.content)


@dataclass
class Explain(Performative):
    """Explain why the described proposition holds, or failed to."""

    def perform(self) -> Any:
        raise NotImplementedError(
            "Explain is provided by the EQL explanation machinery (future integration)."
        )

    def verbalize(self) -> str:
        return f"Explain why {verbalize_expression(self.content)}"


@dataclass
class Warn:
    """A warning: an assertion of an illegal state plus a suggested remedy.

    Conforms to :class:`Performable` without an EQL content: a warning's situation and remedy are the very
    things a :class:`~krrood.exceptions.DataclassException` already carries, so :meth:`of` lifts any such
    exception into the speech-act layer.
    """

    situation: str
    """A human-readable description of what is wrong."""

    suggestion: str = ""
    """Advice on how to fix it, or empty when there is none."""

    @classmethod
    def of(cls, exception: DataclassException) -> "Warn":
        """:return: the warning a :class:`~krrood.exceptions.DataclassException` expresses."""
        return cls(
            situation=exception.error_message(),
            suggestion=exception.suggest_correction(),
        )

    def perform(self) -> "Warn":
        return self

    def verbalize(self) -> str:
        if not self.suggestion:
            return f"Warning: {self.situation}"
        return f"Warning: {self.situation} Suggestion: {self.suggestion}"


@dataclass
class Composition(ABC):
    """A composite act: a control structure over child performables (a Searle commissive).

    ..note:: Verbalization is owned here; *executing* a composition (ordering, parallelism, failure
        fall-through) is the plan layer's responsibility, so :meth:`perform` raises here.
    """

    children: List[Performable]
    """The performables this composition coordinates."""

    @abstractmethod
    def verbalize(self) -> str:
        """:return: the composition as a natural-language utterance joining its children."""

    def perform(self) -> Any:
        raise NotImplementedError(
            "Executing a composition is provided by the coraplex plan layer."
        )


@dataclass
class Sequential(Composition):
    """Do the children one after another -- a temporal conjunction."""

    def verbalize(self) -> str:
        return ", then ".join(child.verbalize() for child in self.children)


@dataclass
class Parallel(Composition):
    """Do the children at the same time -- a conjunction with concurrency."""

    def verbalize(self) -> str:
        return f"{', and '.join(child.verbalize() for child in self.children)} simultaneously"


@dataclass
class TryInOrder(Composition):
    """Try the children in order, falling through on failure -- an ordered disjunction."""

    def verbalize(self) -> str:
        head, *rest = [child.verbalize() for child in self.children]
        return "; otherwise ".join([f"try {head}", *rest])


@dataclass
class TryAll(Composition):
    """Try the children at once, succeeding if any does -- a disjunction with concurrency."""

    def verbalize(self) -> str:
        attempts = ", ".join(child.verbalize() for child in self.children)
        return f"try {attempts} in parallel"
