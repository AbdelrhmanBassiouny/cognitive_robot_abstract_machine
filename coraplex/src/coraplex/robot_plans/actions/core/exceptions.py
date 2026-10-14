from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import TYPE_CHECKING

from krrood.exceptions import DataclassException

if TYPE_CHECKING:
    from coraplex.robot_plans.actions.core.misc import DetectAction

# %% detecting


@dataclass
class DetectionTargetMissing(DataclassException):
    """
    Raised when a detection is given neither the type of object to look for nor the box
    to look in.
    """

    instance: DetectAction
    """
    The detection that has no target.
    """

    def error_message(self) -> str:
        return f"{self.instance} has neither an object type nor a detection box."

    def suggest_correction(self) -> str:
        return "provide the type of object to detect, a box to detect in, or both."
