"""
Regenerate the ORM interfaces of every package that has one.

Runnable from any working directory: the interfaces are resolved relative to the
installed :mod:`cognitive_robot_abstract_machine` package.
"""

from __future__ import annotations

from cognitive_robot_abstract_machine.orm_interfaces import WORKSPACE_ORM_INTERFACES


def main() -> None:
    """
    Build every ORM interface of this repository anew.
    """
    WORKSPACE_ORM_INTERFACES.regenerate()


if __name__ == "__main__":
    main()
