"""
Cutting demo run with the Tiago instead of the PR2.
"""

from semantic_digital_twin.robots.tiago import Tiago

from experiments.tool_based_actions.simple_demo import demo_cutting


def main() -> None:
    """
    Run the cutting demo with the Tiago.
    """
    demo_cutting.main(Tiago)


if __name__ == "__main__":
    main()
