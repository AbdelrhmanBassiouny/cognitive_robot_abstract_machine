from dataclasses import dataclass
from typing import List
from typing_extensions import Dict
from .external_types import ExternalType


@dataclass
class BaseTaker:
    """
    A base class for role takers.
    """

    def get_external(self) -> ExternalType:
        return ExternalType(name="external")

    @property
    def external_list(self) -> List[ExternalType]:
        return []

    def to_dict(self) -> Dict[str, str]:
        """Returns a dict representation. Dict is imported in base_taker but NOT in
        reproduction_module, so the transformer must resolve it via the method globals."""
        return {}
