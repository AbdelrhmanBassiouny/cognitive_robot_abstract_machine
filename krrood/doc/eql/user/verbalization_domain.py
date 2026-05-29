from dataclasses import dataclass


@dataclass(unsafe_hash=True)
class Robot:
    """An example autonomous robot used in EQL verbalization documentation."""

    name: str
    battery: int


@dataclass(unsafe_hash=True)
class Mission:
    """An example mission assigned to a robot, used in EQL verbalization documentation."""

    assigned_to: Robot
    priority: int
