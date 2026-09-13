"""
Run the framework figure's plan end to end: every slot the plan leaves open closed by
the backend that can answer it.

The run is the simulated pickup demo -- the same lab, the same camera, the same
actuators -- performed from a plan that *states* what it wants instead of looking it up.
The piece to pick up is looked for, where it stands is read off the world the look stood
it in, the hole it goes through is concluded by rules, and how to take hold of it is
sampled. None of that is written into the plan: each backend declares what it can
answer, and the choice hands each slot to the first that declares it can.

Usage:
    python3 framework_demo.py [--execution simulated] [--headless]
        [--video-directory <directory>]

Needs MuJoCo and Tracy's description, like the pickup demo it runs; ``--execution`` takes
only ``simulated`` today, and is spelled out so a run against the real lab can be asked
for by name once there is one.
"""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass, field
from pathlib import Path

from typing_extensions import List

from experiments.montessori.perception.backend import MontessoriPerceptionBackend
from experiments.montessori.perception.scene_publishing import PerceivedScene
from experiments.open_slots.choice import backends_for
from experiments.open_slots.sorting import SortingByAnOpenPlan
from experiments.tracy_experiments.pickup.perceived_sorting import (
    PerceivedSorting,
    ShapeSorter,
)
from experiments.tracy_experiments.pickup.pickup_demo_mujoco import (
    SimulatedLab,
    SimulatedPickupDemo,
)
from krrood.entity_query_language.backends import AnsweredStatement, BackendChoice

logger = logging.getLogger(__name__)

EXECUTION_SIMULATED = "simulated"
"""
The one way this demo can be run today: in the simulated lab.
"""

# %% the run


@dataclass
class PickupDemoByAnOpenPlan(SimulatedPickupDemo):
    """
    The simulated pickup demo, performed from a plan that states its slots.
    """

    backends: BackendChoice = field(init=False)
    """
    The backends its statements are answered by, once :meth:`perform` has built them.
    """

    def sorting_over(
        self, scene: PerceivedScene, sorter: ShapeSorter
    ) -> PerceivedSorting:
        """
        The same run, asking for the hole each piece goes through rather than looking it
        up.

        :param scene: The board and the pieces, as the camera finds them.
        :param sorter: What picks each piece up and lets it go.
        :return: The run.
        """
        self.backends = backends_for(
            MontessoriPerceptionBackend(source=self.look), self.lab.belief
        )
        return SortingByAnOpenPlan(scene=scene, sorter=sorter, backends=self.backends)

    @property
    def answered_slots(self) -> List[AnsweredStatement]:
        """
        Which backend answered which of the plan's slots, in the order they were
        answered.
        """
        return self.backends.answered


# %% running it


def parse_arguments() -> argparse.Namespace:
    """
    :return: This demo's own command line arguments.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--execution",
        choices=[EXECUTION_SIMULATED],
        default=EXECUTION_SIMULATED,
        help="where the plan is run",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="run without opening MuJoCo's viewer window, as fast as the machine allows",
    )
    parser.add_argument(
        "--video-directory",
        type=Path,
        default=Path.cwd() / "framework_demo_videos",
        help="where the run's videos and the picture of what the look found are written",
    )
    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()
    demo = PickupDemoByAnOpenPlan(
        lab=SimulatedLab.build(),
        headless=arguments.headless,
        paced_to_the_wall_clock=not arguments.headless,
    )
    demo.perform()
    for answered in demo.answered_slots:
        logger.info(
            "%s answered %s.", type(answered.backend).__name__, answered.statement
        )
    for written in demo.write_artifacts(arguments.video_directory):
        logger.info("Written %s.", written)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
