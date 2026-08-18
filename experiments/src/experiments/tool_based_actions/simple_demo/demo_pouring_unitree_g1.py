"""
Pouring demo run with the Unitree G1 instead of the PR2.
"""

from semantic_digital_twin.robots.unitree_g1 import UnitreeG1

from experiments.tool_based_actions.simple_demo import demo_pouring


def main() -> None:
    """
    Run the pouring demo with the Unitree G1.
    """
    demo_pouring.main(UnitreeG1)


if __name__ == "__main__":
    main()
