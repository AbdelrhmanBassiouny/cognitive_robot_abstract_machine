import argparse

from giskardpy.middleware.ros2.giskard import Giskard
from giskardpy.middleware.ros2.scripts.iai_robots.daisy.configs import (
    DAiSyInteractiveMarkerChain,
    WorldWithDAiSyConfig,
)
from giskardpy.middleware.ros2.scripts.tools.interactive_marker import (
    InteractiveMarkerNode,
)
from giskardpy.qp.qp_controller_config import QPControllerConfig
from semantic_digital_twin.adapters.ros import rospy


def main() -> None:
    """
    Run a Giskard that simulates DAiSy, described by the file its robot class declares,
    as a ros node until ROS shuts down.
    """
    parser = argparse.ArgumentParser(description="DAiSy Giskard standalone controller.")
    parser.add_argument(
        "--interactive-marker",
        action="store_true",
        help="Also start the interactive marker server for Cartesian control via RViz.",
    )
    # parse_known_args ignores ROS 2 arguments (--ros-args ...) that argparse does not know about.
    args, _ = parser.parse_known_args()

    rospy.init_node("giskard")
    giskard = Giskard.standalone(
        world_config=WorldWithDAiSyConfig(),
        qp_controller_config=QPControllerConfig(target_frequency=33),
    )

    if args.interactive_marker:
        InteractiveMarkerNode.start_in_background_thread(
            chains=[chain.value for chain in DAiSyInteractiveMarkerChain]
        )

    giskard.live()


if __name__ == "__main__":
    main()
