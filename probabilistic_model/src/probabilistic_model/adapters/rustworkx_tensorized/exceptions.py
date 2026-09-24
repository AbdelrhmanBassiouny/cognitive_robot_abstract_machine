from __future__ import annotations

from dataclasses import dataclass, field

from krrood.exceptions import DataclassException
from typing_extensions import Type


@dataclass
class CannotConvertError(DataclassException):
    """
    Raised when no converter handles an object.
    """

    data_type: Type = field(kw_only=True)
    """
    The type of the object that could not be converted.
    """

    def error_message(self) -> str:
        return f"No converter handles {self.data_type.__name__}."

    def suggest_correction(self) -> str:
        return (
            "Subclass the converter base class for the type, binding it as the input "
            "type."
        )
