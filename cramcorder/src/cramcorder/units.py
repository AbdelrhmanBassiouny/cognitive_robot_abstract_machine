"""
Amounts of data, and how fast they flow.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import timedelta

from krrood.ormatic.utils import classproperty
from krrood.patterns.subclass_safe_generic import SubClassSafeGeneric
from typing_extensions import Generic, Self, TypeVar

# %% quantities


class Quantity(ABC):
    """
    An amount that can be taken a share or a multiple of.
    """

    @abstractmethod
    def scaled(self, factor: float) -> Self:
        """
        :param factor: What to multiply the amount by.
        :return: The amount that many times over.
        """


@dataclass(frozen=True, order=True)
class DataSize(Quantity):
    """
    An amount of data, such as a file takes on disk.
    """

    bits: int
    """
    How many bits it is.
    """

    @classproperty
    def bits_per_byte(cls) -> int:
        """
        How many bits make a byte.
        """
        return 8

    @classmethod
    def of_bytes(cls, count: float) -> DataSize:
        """
        :param count: How many bytes.
        :return: That amount of data, to the nearest bit.
        """
        return cls(round(count * cls.bits_per_byte))

    @property
    def bytes(self) -> int:
        """
        How many whole bytes it is.
        """
        return self.bits // self.bits_per_byte

    def scaled(self, factor: float) -> DataSize:
        return DataSize(round(self.bits * factor))

    def __add__(self, other: DataSize) -> DataSize:
        return DataSize(self.bits + other.bits)

    def __sub__(self, other: DataSize) -> DataSize:
        return DataSize(self.bits - other.bits)


# %% rates

QuantityT = TypeVar("QuantityT", bound=Quantity)
"""
The quantity a :class:`Rate` measures the flow of.
"""


@dataclass
class Rate(Generic[QuantityT], SubClassSafeGeneric):
    """
    How much of a quantity flows in each second.
    """

    per_second: QuantityT
    """
    The amount that flows in one second.
    """

    def over(self, duration: timedelta) -> QuantityT:
        """
        :param duration: How long it flows.
        :return: The amount that flows in that time.
        """
        return self.per_second.scaled(duration.total_seconds())

    def scaled(self, factor: float) -> Self:
        """
        :param factor: What to multiply the rate by.
        :return: The rate that many times over.
        """
        return type(self)(self.per_second.scaled(factor))

    @classmethod
    def filling(cls, amount: QuantityT, duration: timedelta) -> Self:
        """
        :param amount: An amount.
        :param duration: How long it may take to flow.
        :return: The rate at which exactly that amount flows in that time.
        """
        return cls(amount.scaled(1 / duration.total_seconds()))


@dataclass
class BitRate(Rate[DataSize]):
    """
    How much data flows in each second, such as a stream of a video takes.
    """
