"""
Base dataclass for all ``@rdr``-generated case types.

Each decorated function gets a ``FunctionCase`` subclass with one field per annotated
parameter plus an ``_output`` field for the return value.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing_extensions import Callable, ClassVar


@dataclass(kw_only=True)
class FunctionCase:
    """
    Base class for all ``@rdr``-generated case types.

    Subclasses are written as real ``@dataclass`` definitions in the RDR save file.  The
    ``function`` ClassVar is assigned the original (unwrapped) function object outside
    the class body, after the ``@dataclass`` decorator has processed the class.
    """

    function: ClassVar[Callable]
    """
    The original (unwrapped) function, assigned after the dataclass decorator has run.
    """
