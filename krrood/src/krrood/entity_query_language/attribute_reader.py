"""
How an evaluation reads the attributes of the instances it ranges over.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from typing_extensions import Any, Iterator

# %% attribute readers


class AttributeReader(ABC):
    """
    Reads the value an attribute has on an instance during an evaluation.
    """

    @abstractmethod
    def read(self, instance: Any, attribute_name: str) -> Iterator[Any]:
        """
        :param instance: The instance whose attribute is read.
        :param attribute_name: The name of the attribute.
        :return: The value of the attribute, or nothing when *instance* has no value
            for it.
        """


@dataclass
class LiveAttributeReader(AttributeReader):
    """
    Reads the value an attribute currently has on the instance itself.
    """

    def read(self, instance: Any, attribute_name: str) -> Iterator[Any]:
        if hasattr(instance, attribute_name):
            yield getattr(instance, attribute_name)
