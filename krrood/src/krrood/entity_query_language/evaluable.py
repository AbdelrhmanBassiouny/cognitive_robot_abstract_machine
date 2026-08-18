"""
Shared evaluation interface for the Entity Query Language.

Both queries (which select existing data) and structural matches (which can generate new
instances) are evaluable. Defining a single interface lets backends treat them uniformly
and gives them a consistent ``evaluate``/``tolist``/``first`` surface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from typing_extensions import Iterator, List, Optional, TYPE_CHECKING

from krrood.entity_query_language.utils import make_list
from krrood.thread_exit_sentinel import ThreadExitSentinel

if TYPE_CHECKING:
    from krrood.entity_query_language.backends import QueryBackend


class Evaluable(ABC):
    """
    Interface for objects that can be evaluated to produce results.

    Implementations provide :meth:`_evaluate_natively_`, the in-process (backend-free)
    evaluation strategy. The public :meth:`evaluate` dispatches to a chosen backend,
    which by default is the native ``EntityQueryLanguageBackend``.
    """

    @abstractmethod
    def _evaluate_natively_(self) -> Iterator:
        """
        Produce results by evaluating this object in the current python process.

        :return: An iterator over the results.
        """
        ...

    def evaluate(self, backend: Optional[QueryBackend] = None) -> Iterator:
        """
        Evaluate using the given backend, returning an iterator over the results.

        :param backend: The query backend to evaluate with. Defaults to the
            ``EntityQueryLanguageBackend`` (native in-process evaluation / generation).
        :return: An iterator over the results.
        """
        if backend is None:
            backend = self._default_backend_()
        return backend.evaluate(self)

    @staticmethod
    def _default_backend_() -> QueryBackend:
        """
        Load and instantiate the backend used when the caller names none.

        The backend module is imported here rather than at the top of this one because
        it imports :class:`Evaluable` back. The module chain it drags in registers an
        interpreter exit sentinel of its own, which would leave the thread that first
        evaluates a query unjoinable, so the calling thread's sentinel is put back
        afterwards.

        :return: A backend that evaluates natively in this process.
        """
        sentinel = ThreadExitSentinel()
        from krrood.entity_query_language.backends import EntityQueryLanguageBackend

        sentinel.ensure_registered()
        return EntityQueryLanguageBackend()

    def tolist(self, backend: Optional[QueryBackend] = None) -> List:
        """
        Evaluate and return the results as a list.

        :param backend: The query backend to evaluate with; forwarded to
            :meth:`evaluate`.
        """
        return make_list(self.evaluate(backend=backend))

    def first(self, backend: Optional[QueryBackend] = None):
        """
        Evaluate and return the first result.

        :param backend: The query backend to evaluate with; forwarded to
            :meth:`evaluate`.
        :raises StopIteration: If no results are found.
        """
        return next(self.evaluate(backend=backend))
