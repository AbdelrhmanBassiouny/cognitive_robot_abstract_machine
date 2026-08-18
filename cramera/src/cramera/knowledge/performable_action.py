"""
What an answer row offers to have the robot do.
"""

from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import Any, Dict


@dataclass(frozen=True)
class PerformableAction:
    """
    An action an answer row names, which the robot can be asked to carry out.

    Carries no plan of its own: what the action *is* stays with the demo that will
    perform it, and this is only how the viewer asks for it by name.
    """

    name: str
    """
    How the demo performing this action identifies it.
    """

    description: str
    """
    What carrying it out would do, in words, for the viewer to say so on its button.
    """

    def to_payload(self) -> Dict[str, Any]:
        """
        The JSON shape the viewer's perform button reads.
        """
        return {"name": self.name, "description": self.description}
