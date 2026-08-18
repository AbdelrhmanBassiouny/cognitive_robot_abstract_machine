"""
Generate the ORM interfaces of this checkout unless it already has them.

The repository ignores every ``ormatic_interface.py`` rather than tracking it, so a
fresh clone carries no database mapping at all and anything that persists an object or
reads one back fails until the interfaces have been generated once. Runnable before
anything that needs them, since a checkout that has them already pays nothing.

Use ``scripts/regenerate_all_orm.py`` instead to build them anew after changing a mapped
datastructure; this one leaves interfaces that are already there alone.
"""

from __future__ import annotations

from cognitive_robot_abstract_machine.orm_interfaces import WORKSPACE_ORM_INTERFACES


def main() -> None:
    """
    Build the ORM interfaces of this repository if it has none yet.
    """
    print(
        "Checking the ORM interfaces of this checkout. Building them, which a checkout "
        "that has none needs, takes about a minute."
    )
    if WORKSPACE_ORM_INTERFACES.ensure_generated():
        print("Built them; this checkout can persist objects now.")
    else:
        print("They were already there.")


if __name__ == "__main__":
    main()
