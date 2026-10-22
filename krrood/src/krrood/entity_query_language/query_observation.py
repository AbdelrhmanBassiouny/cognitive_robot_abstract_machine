"""
Observing the queries a program asks while it runs, and what they are answered with.

An observer is told about every query evaluated where it observes, as the query is asked
and once its answering has ended, together with the query whose answering asked it.
"""

from __future__ import annotations

import sys
from abc import ABC, abstractmethod
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from enum import Enum, StrEnum
from types import FrameType

from typing_extensions import Any, Iterable, Iterator, List, Optional, TYPE_CHECKING

from krrood.entity_query_language._stack import CallStack, StackFrame
from krrood.singleton import SingletonMeta

if TYPE_CHECKING:
    from krrood.entity_query_language.backends import QueryBackend
    from krrood.entity_query_language.evaluable import Evaluable

# %% an asked query


class QueryLanguagePackage(StrEnum):
    """
    The package of the query language, whose own evaluations are not asked queries.
    """

    NAME = "krrood.entity_query_language"
    """
    The dotted name its modules start with.
    """


class EvaluationEntry(StrEnum):
    """
    The methods a query is evaluated through by whoever asks it.
    """

    EVALUATE = "evaluate"
    """
    Evaluating to an iterator of answers.
    """

    TO_LIST = "tolist"
    """
    Evaluating to a list of answers.
    """

    FIRST = "first"
    """
    Evaluating to the first answer.
    """


class AnsweringEnd(Enum):
    """
    Marks that a query has no answer left.
    """

    EXHAUSTED = "exhausted"
    """
    The query's answers ran out.
    """


@dataclass(eq=False)
class AskedQuery:
    """
    One evaluation of a query, from the moment it is asked until its answering ends.
    """

    query: Evaluable
    """
    The query that was asked.
    """

    backend: QueryBackend
    """
    What answers the query.
    """

    asking_stack: CallStack
    """
    The calls that asked the query, innermost first.
    """

    asker: Optional[AskedQuery] = None
    """
    The query whose answering asked this one, if it was asked while another was being
    answered.
    """

    answers: List[Any] = field(default_factory=list)
    """
    The answers given so far, in the order they were given.
    """

    is_answered: bool = False
    """
    Whether the answering has ended, because the answers ran out or the asker stopped
    taking them.
    """

    @property
    def asking_frame(self) -> Optional[StackFrame]:
        """
        The innermost call outside the query language that asked the query, if any.
        """
        return next(
            (
                frame
                for frame in self.asking_stack
                if not (frame.module_name or "").startswith(QueryLanguagePackage.NAME)
            ),
            None,
        )

    @property
    def depth(self) -> int:
        """
        How many queries were being answered, one inside the other, when this one was
        asked.
        """
        return 0 if self.asker is None else self.asker.depth + 1


# %% observing asked queries


class QueryObserver(ABC):
    """
    Told about the queries asked where it observes.
    """

    @abstractmethod
    def on_query_asked(self, asked: AskedQuery) -> None:
        """
        Called when a query is asked, before any answer is looked for.

        :param asked: The query asked.
        """

    @abstractmethod
    def on_query_answered(self, asked: AskedQuery) -> None:
        """
        Called once the answering of a query has ended.

        :param asked: The query answered, with every answer it gave.
        """


@dataclass
class QueryObservation(metaclass=SingletonMeta):
    """
    The observers of the queries asked in the current execution context, and the query
    being answered there.

    Observers are scoped to the execution context that started observing, so queries
    asked in another thread are not reported to them.
    """

    observers: ContextVar[tuple[QueryObserver, ...]] = field(
        default_factory=lambda: ContextVar("query_observers", default=())
    )
    """
    The observers told about the queries asked in the current execution context.
    """

    being_answered: ContextVar[Optional[AskedQuery]] = field(
        default_factory=lambda: ContextVar("query_being_answered", default=None)
    )
    """
    The query whose answering is running in the current execution context, if any.
    """

    @contextmanager
    def observed_by(self, observer: QueryObserver) -> Iterator[None]:
        """
        Tell an observer about every query asked in the current execution context while
        the block runs, once even where it is already told.

        :param observer: The observer to tell.
        """
        observers = self.observers.get()
        token = self.observers.set(
            observers
            if any(told is observer for told in observers)
            else observers + (observer,)
        )
        try:
            yield
        finally:
            self.observers.reset(token)

    @contextmanager
    def unobserved(self) -> Iterator[None]:
        """
        Ask queries without telling any observer while the block runs, such as an
        observer's own queries about what it was told.
        """
        token = self.observers.set(())
        try:
            yield
        finally:
            self.observers.reset(token)

    def answers_of(
        self, query: Evaluable, backend: QueryBackend, answers: Iterable
    ) -> Iterator:
        """
        The answers a backend gives to a query, reported to the observers of the
        current execution context.

        :param query: The query asked.
        :param backend: What answers the query.
        :param answers: The answers the backend gives.
        :return: The same answers, or an iterator reporting them when observed.
        """
        observers = self.observers.get()
        if not observers or self._is_asked_by_the_query_language(sys._getframe(1)):
            return iter(answers)
        asked = AskedQuery(
            query=query,
            backend=backend,
            asking_stack=CallStack.capture(skip=1),
            asker=self.being_answered.get(),
        )
        with self.unobserved():
            for observer in observers:
                observer.on_query_asked(asked)
        return self._reported_answers(asked, iter(answers), observers)

    @staticmethod
    def _is_asked_by_the_query_language(evaluation: FrameType) -> bool:
        """
        :param evaluation: The frame of the evaluation entry a query was evaluated
            through.
        :return: Whether the query language itself evaluated the query, as a part of
            answering another one.
        """
        frame = evaluation.f_back
        while frame is not None and frame.f_code.co_name in set(EvaluationEntry):
            if not frame.f_globals["__name__"].startswith(QueryLanguagePackage.NAME):
                return False
            frame = frame.f_back
        return frame is not None and frame.f_globals["__name__"].startswith(
            QueryLanguagePackage.NAME
        )

    def _reported_answers(
        self,
        asked: AskedQuery,
        answers: Iterator,
        observers: tuple[QueryObserver, ...],
    ) -> Iterator:
        """
        Give the answers of an asked query one by one, with the query marked as being
        answered while each is looked for, and report the query answered once they end.

        :param asked: The query asked.
        :param answers: The answers its backend gives.
        :param observers: The observers to report to.
        :return: The answers.
        """
        try:
            while True:
                token = self.being_answered.set(asked)
                try:
                    answer = next(answers, AnsweringEnd.EXHAUSTED)
                finally:
                    self.being_answered.reset(token)
                if answer is AnsweringEnd.EXHAUSTED:
                    return
                asked.answers.append(answer)
                yield answer
        finally:
            asked.is_answered = True
            with self.unobserved():
                for observer in observers:
                    observer.on_query_answered(asked)
