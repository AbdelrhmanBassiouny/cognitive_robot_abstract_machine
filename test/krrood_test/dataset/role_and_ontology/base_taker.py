from dataclasses import dataclass
from .external_types import ExternalType


@dataclass
class BaseTaker:
    """
    A base class for role takers.
    """

    def get_external(self) -> ExternalType:
        return ExternalType(name="external")
