"""
The plan the size-limit, manifest-tool and hook suites share, with its items picked out
by the state each one stands for rather than by a retyped id.
"""

from __future__ import annotations

from dataclasses import dataclass

from basstler.plan_model import ItemStatus, PlanItem, PlanManifest

from .constants import DatasetLocation

# %% the plan with landed items


@dataclass(frozen=True)
class LandedItemsPlan:
    """
    :attr:`DatasetLocation.PLAN_WITH_LANDED_ITEMS`, read.
    """

    manifest: PlanManifest
    """
    The plan as the dataset holds it.
    """

    @classmethod
    def read(cls) -> LandedItemsPlan:
        """
        :return: The plan, read from the dataset.
        """
        return cls(PlanManifest.from_file(DatasetLocation.PLAN_WITH_LANDED_ITEMS))

    def item_with_status(self, status: ItemStatus) -> PlanItem:
        """
        :param status: The status of the item to return: done for the landed item, in
            progress for the one depending on it, not started for the one depending on
            both.
        :return: That item.
        """
        (item,) = [item for item in self.manifest.items if item.status is status]
        return item
