"""
Run the experiments ORM generator in an interpreter that has no ROS message packages.

A checkout without the ROS overlay sourced can still map the experiments package, so the
generator has to get by without ``json_msgs``, whatever the interpreter running this
launcher happens to have installed.
"""

from __future__ import annotations

import runpy
import sys
from dataclasses import dataclass
from importlib.abc import MetaPathFinder
from pathlib import Path
from typing import Sequence

BLOCKED_PACKAGE = "json_msgs"
"""
The ROS message package the generator must not need.
"""

GENERATOR = Path(__file__).parents[3] / "experiments" / "scripts" / "generate_orm.py"
"""
The generator under test.
"""


@dataclass
class BlockedPackageFinder(MetaPathFinder):
    """
    Make one package, and everything in it, unimportable.
    """

    package_name: str
    """
    The package to refuse.
    """

    def find_spec(self, fullname: str, path: Sequence[str] | None, target=None):
        if fullname != self.package_name and not fullname.startswith(
            self.package_name + "."
        ):
            return None
        raise ModuleNotFoundError(f"No module named {fullname!r}", name=fullname)


if __name__ == "__main__":
    sys.meta_path.insert(0, BlockedPackageFinder(BLOCKED_PACKAGE))
    runpy.run_path(str(GENERATOR), run_name="__main__")
