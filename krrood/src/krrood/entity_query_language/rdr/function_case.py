"""
Base dataclass for all ``@rdr``-generated case types.

Each decorated function gets a unique ``FunctionCase`` subclass written into
the corresponding RDR save file.  The subclass carries one dataclass field per
annotated function parameter, plus an ``_output`` field for the return value.
The ``function`` ClassVar is assigned the original (unwrapped) function object
outside the generated class body (so Python's @dataclass annotation processing
does not confuse it for an instance field) and is therefore not part of the
generated dataclass's ``__init__`` signature.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING
from typing_extensions import ClassVar

if TYPE_CHECKING:
    from typing_extensions import Callable


@dataclass
class FunctionCase:
    """Base class for all ``@rdr``-generated case types.

    Subclasses are written as real ``@dataclass`` definitions in the RDR save
    file.  The ``function`` ClassVar is assigned the original (unwrapped)
    function object outside the class body, after the ``@dataclass`` decorator
    has processed the class.
    """

    function: ClassVar["Callable"]
