from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing_extensions import TYPE_CHECKING

if TYPE_CHECKING:
    from semantic_digital_twin.mixin import (
        HasSimulatorProperties,
        SimulatorAdditionalProperty,
    )


@dataclass
class DelegatorForHasSimulatorProperties(ABC):
    @property
    @abstractmethod
    def delegatee(self) -> HasSimulatorProperties: ...
    @property
    def simulator_additional_properties(self) -> list[SimulatorAdditionalProperty]:
        return self.delegatee.simulator_additional_properties

    @simulator_additional_properties.setter
    def simulator_additional_properties(self, value: list[SimulatorAdditionalProperty]):
        self.delegatee.simulator_additional_properties = value
