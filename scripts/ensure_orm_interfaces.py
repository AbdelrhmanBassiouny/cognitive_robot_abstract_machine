"""
Generate the ORM interfaces of this checkout unless it already has current ones.

The repository ignores every ``ormatic_interface.py`` rather than tracking it, so a
fresh clone carries no database mapping at all and anything that persists an object or
reads one back fails until the interfaces have been generated. Runnable before anything
that needs them, since a checkout whose interfaces are current pays nothing.

A test run makes the same check for itself (see ``--orm-build`` in
``doc/contributing.rst``); this is the same check for everything that is not a test run.
Use ``scripts/regenerate_all_orm.py`` instead to build them whatever the checkout holds.
"""

from __future__ import annotations

from cognitive_robot_abstract_machine.orm_interfaces import WORKSPACE_ORM_INTERFACES


def main() -> None:
    """
    Build the ORM interfaces of this repository unless they are already current.
    """
    print(
        "Checking the ORM interfaces of this checkout. Building them, which a checkout "
        "whose sources have outrun them needs, takes about a minute."
    )
    if not WORKSPACE_ORM_INTERFACES.is_outdated:
        print("They were already current.")
        return
    WORKSPACE_ORM_INTERFACES.regenerate()
    print("Built them; this checkout can persist objects now.")


if __name__ == "__main__":
    main()
