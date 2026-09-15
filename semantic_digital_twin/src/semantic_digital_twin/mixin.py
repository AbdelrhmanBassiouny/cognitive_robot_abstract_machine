from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from typing_extensions import Optional, Type, TypeVar

from semantic_digital_twin.exceptions import DuplicateSimulatorPropertyError


@dataclass
class SimulatorAdditionalProperty:
    """
    Class representing an additional property for a simulator.
    """

    ...


TSimulatorAdditionalProperty = TypeVar(
    "TSimulatorAdditionalProperty", bound=SimulatorAdditionalProperty
)


@dataclass(eq=False)
class HasSimulatorProperties:
    """
    Mixin class to add simulator additional properties to a data class.
    """

    simulator_additional_properties: List[SimulatorAdditionalProperty] = field(
        default_factory=list, kw_only=True, repr=False
    )
    """
    A list of additional properties for the simulator, it can contain properties of
    multiple simulators.
    """

    def simulator_property(
        self, property_type: Type[TSimulatorAdditionalProperty]
    ) -> Optional[TSimulatorAdditionalProperty]:
        """
        The one property of ``property_type`` this entity carries.

        :param property_type: The type of property to look up.
        :return: The property, or ``None`` if none of that type is attached.
        :raises DuplicateSimulatorPropertyError: If more than one is attached, since a
            simulator reads exactly one and would silently ignore the rest.
        """
        matches = [
            simulator_property
            for simulator_property in self.simulator_additional_properties
            if isinstance(simulator_property, property_type)
        ]
        if len(matches) > 1:
            raise DuplicateSimulatorPropertyError(property_type, len(matches))
        if not matches:
            return None
        return matches[0]

    def simulator_property_or_default(
        self, property_type: Type[TSimulatorAdditionalProperty]
    ) -> TSimulatorAdditionalProperty:
        """
        The one property of ``property_type`` this entity carries, attaching a default-
        constructed one first if it carries none yet, so callers modify the property a
        simulator will actually read.

        :param property_type: The type of property to look up or attach.
        :return: The property.
        """
        existing = self.simulator_property(property_type)
        if existing is not None:
            return existing
        created = property_type()
        self.simulator_additional_properties.append(created)
        return created
