from abc import abstractmethod, ABC
from dataclasses import dataclass

from typing_extensions import Any, Optional, Iterable

from .entity import has_solution_for, ConditionType


@dataclass
class HasAxiom(ABC):
    """
    An abstract class defining an abstract interface for classes that have axioms. Axioms are
    statements that describe the class and can be applied to candidates to check if a candidate
    belongs to that class.
    """

    @classmethod
    @abstractmethod
    def axiom(cls, candidate: Optional[Any] = None) -> Iterable[ConditionType]:
        """
        The abstract method defining the axiom for this class as an EQL statement.
        """
        ...

    @classmethod
    def check_axiom(cls, candidate: Any) -> bool:
        return has_solution_for(candidate, cls.axiom)


@dataclass
class HasPythonAxiom(HasAxiom, ABC):
    """
    An abstract class defining an abstract interface for classes that have axioms and have a python equivalent axiom
    that is checkable.
    """
    @classmethod
    @abstractmethod
    def check_axiom_python(cls, candidate: Any) -> bool:
        """
        The abstract method defining the axiom for this class as a Python statement.
        """
        ...