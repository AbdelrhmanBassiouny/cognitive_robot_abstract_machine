"""
Pouring demo run with the GARMI instead of the PR2.
"""

from semantic_digital_twin.robots.garmi import Garmi

from experiments.tool_based_actions.simple_demo import demo_pouring


def main() -> None:
    """
    Run the pouring demo with the GARMI.
    """
    demo_pouring.main(Garmi)


if __name__ == "__main__":
    main()
