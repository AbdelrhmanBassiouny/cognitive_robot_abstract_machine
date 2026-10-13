from __future__ import annotations

from dataclasses import dataclass
from typing_extensions import Any

from krrood_core.adapters.exceptions import (
    ClassNotDeserializableError,
    ClassNotFoundError,
    ClassNotSerializableError,
    InvalidTypeFormatError,
    JSONSerializationError,
    MissingTypeError,
    UnknownModuleError,
)


@dataclass
class UntrackedObjectError(JSONSerializationError):
    """
    Raised when a JSON document refers to an object by a key that no object was
    deserialized with.
    """

    key: Any
    """
    The key the document refers to the object with.
    """

    def error_message(self) -> str:
        return f"No object was deserialized with the key '{self.key}'."

    def suggest_correction(self) -> str:
        return (
            "Deserialize the referenced object before the objects that refer to it, "
            "within the same JSON document."
        )
