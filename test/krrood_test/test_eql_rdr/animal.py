"""
Plain ``Animal`` dataclass for the EQL-based RDR (zoo dataset).

Deliberately ordinary: no EQL base classes, no ORM, no special treatment. The RDR
declares a shared ``variable(Animal, domain=...)`` over instances of this class, and
``species`` is the *underspecified* attribute the RDR predicts.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass

from typing_extensions import Optional


class Species(enum.Enum):
    """
    The seven mutually-exclusive zoo species classes (UCI dataset target).

    The member values are not arbitrary: they are the UCI zoo dataset's own numeric
    category codes, so a target read from the dataset can be converted with
    ``Species(int(code))`` without a lookup table.
    """

    mammal = 1
    """
    UCI category code 1.
    """

    bird = 2
    """
    UCI category code 2.
    """

    reptile = 3
    """
    UCI category code 3.
    """
    fish = 4
    """
    UCI category code 4.
    """
    amphibian = 5
    """
    UCI category code 5.
    """

    insect = 6
    """
    UCI category code 6.
    """

    molusc = 7
    """
    UCI category code 7.
    """

    def __repr__(self) -> str:
        return f"Species.{self.name}"


@dataclass
class Animal:
    """
    A zoo animal described by its boolean/numeric traits.

    ``species`` is ``None`` for an unclassified (underspecified) animal and is the
    attribute the RDR fills in.
    """

    name: str
    """
    The animal's name (its identifying label in the dataset).
    """

    hair: bool
    """
    Whether the animal has hair.
    """

    feathers: bool
    """
    Whether the animal has feathers.
    """
    eggs: bool
    """
    Whether the animal lays eggs.
    """
    milk: bool
    """
    Whether the animal produces milk.
    """

    airborne: bool
    """
    Whether the animal can fly.
    """

    aquatic: bool
    """
    Whether the animal lives in water.
    """

    predator: bool
    """
    Whether the animal preys on other animals.
    """

    toothed: bool
    """
    Whether the animal has teeth.
    """
    backbone: bool
    """
    Whether the animal has a backbone.
    """
    breathes: bool
    """
    Whether the animal breathes air.
    """

    venomous: bool
    """
    Whether the animal is venomous.
    """

    fins: bool
    """
    Whether the animal has fins.
    """

    legs: int
    """
    The number of legs the animal has.
    """

    tail: bool
    """
    Whether the animal has a tail.
    """
    domestic: bool
    """
    Whether the animal is domesticated.
    """

    catsize: bool
    """
    Whether the animal is approximately cat-sized or larger.
    """

    species: Optional[Species] = None
    """
    The animal's species; ``None`` when unclassified (the attribute the RDR predicts).
    """


def make_animal(name: str, **kwargs) -> Animal:
    """
    Build an :class:`Animal` with all-False/zero defaults, overriding with ``kwargs``.

    :param name: The animal's name.
    :param kwargs: Attribute overrides; keys must match :class:`Animal` field names.
    :return: A fully specified :class:`Animal` instance.
    """
    defaults = dict(
        hair=False,
        feathers=False,
        eggs=False,
        milk=False,
        airborne=False,
        aquatic=False,
        predator=False,
        toothed=False,
        backbone=True,
        breathes=True,
        venomous=False,
        fins=False,
        legs=0,
        tail=False,
        domestic=False,
        catsize=False,
    )
    return Animal(name=name, **{**defaults, **kwargs})
