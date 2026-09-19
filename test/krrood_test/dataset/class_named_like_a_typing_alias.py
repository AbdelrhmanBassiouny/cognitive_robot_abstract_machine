"""
A class whose name is also the name of a typing alias other modules annotate with.

Nothing in the workspace stops a domain class from being called ``Sequence``, so a class
diagram holding one has to keep it apart from the alias a different module means when it
writes ``Sequence[...]``.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Sequence:
    """
    A domain class that answers to the name of a typing alias.
    """

    label: str = ""
    """
    What this one is called.
    """
