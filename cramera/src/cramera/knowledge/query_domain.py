"""
The unit a query source offers the EQL runner: one named, typed set of objects.
"""

from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import Any, List, Type


@dataclass(frozen=True)
class QueryDomain:
    """
    One ready-made EQL variable: a name to write queries with, and what it ranges over.

    A source declares its domains rather than building a namespace itself, so it cannot
    shadow the EQL factories a query is written in.
    """

    name: str
    """
    Name the variable is bound to in a query.
    """

    entity_type: Type[Any]
    """
    Type of the objects the variable ranges over; also in scope under its class name.
    """

    objects: List[Any]
    """
    The objects themselves.

    Read whenever a query runs rather than copied, so a source that keeps appending to
    this list is queried against its current contents.
    """
