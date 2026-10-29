"""
The coraplex demos that live in a folder of their own rather than in a package, loaded
for tests.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

from krrood.patterns.path_enumeration import PathEnumeration

# %% demo folders


class DemoFolder(PathEnumeration):
    """
    The folder of a coraplex demo that lives outside any package.
    """

    HSR_MUJOCO = (
        Path(__file__).parents[1] / "coraplex" / "demos" / "coraplex_hsr_mujoco_demo"
    )
    """
    The HSR carrying a milk carton from a counter to a table in MuJoCo.
    """

    def load_module(self, module_name: str) -> ModuleType:
        """
        Load a module of the demo, with the demo's folder on the path for the modules
        it imports.

        The module is registered under the folder's name followed by its own, so the
        modules of different demos sharing a name never take each other's place.

        :param module_name: The name of the module's file, without its suffix.
        :return: The loaded module.
        """
        with pytest.MonkeyPatch.context() as patch:
            patch.syspath_prepend(str(self))
            specification = importlib.util.spec_from_file_location(
                f"{self.name}_{module_name}", self / f"{module_name}.py"
            )
            module = importlib.util.module_from_spec(specification)
            patch.setitem(sys.modules, specification.name, module)
            specification.loader.exec_module(module)
        return module
