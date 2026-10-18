"""
The packages that modules of ``cramph`` may not import.
"""

from __future__ import annotations

import ast
import pkgutil
from dataclasses import dataclass
from importlib.util import find_spec
from pathlib import Path

import pytest

import cramph
from cramph.context import StatechartContext
from cramph.statechart import Statechart
from semantic_digital_twin.world import World

FORBIDDEN_PACKAGES: set[str] = {
    "giskardpy",
    "coraplex",
    "segmind",
    "rclpy",
    "rclpy_message_converter",
    "ament_index_python",
    "builtin_interfaces",
    "geometry_msgs",
    "sensor_msgs",
    "std_msgs",
    "visualization_msgs",
    "tf2_ros",
}
"""
Top-level packages that ``cramph`` must stay independent of: the motion control and
robot packages built on top of it, and ROS.
"""


@dataclass
class ImportedModule:
    """
    A module that a source file of ``cramph`` imports.
    """

    importer: str
    """
    Name of the module of ``cramph`` that imports it.
    """

    name: str
    """
    Absolute name of the imported module.
    """

    @property
    def top_level_package(self) -> str:
        """
        :return: The package the imported module belongs to.
        """
        return self.name.split(".")[0]


def cramph_module_names() -> list[str]:
    """
    :return: The names of every module of the installed ``cramph`` package.
    """
    return [cramph.__name__] + [
        module.name
        for module in pkgutil.walk_packages(
            cramph.__path__, prefix=f"{cramph.__name__}."
        )
    ]


def imports_of(module_name: str) -> list[ImportedModule]:
    """
    :param module_name: The module whose source is read.
    :return: Every module its source imports, wherever in the source the import is.
    """
    source = Path(find_spec(module_name).origin).read_text(encoding="utf-8")
    imported = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported.extend(
                ImportedModule(importer=module_name, name=alias.name)
                for alias in node.names
            )
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            imported.append(ImportedModule(importer=module_name, name=node.module))
    return imported


# %% cramph stays independent of motion control and ROS


def test_submodules_of_cramph_are_found() -> None:
    assert Statechart.__module__ in cramph_module_names()


def test_imports_of_a_module_are_found() -> None:
    assert ImportedModule(
        importer=StatechartContext.__module__, name=World.__module__
    ) in imports_of(StatechartContext.__module__)


@pytest.mark.parametrize("module_name", cramph_module_names())
def test_cramph_module_imports_no_forbidden_package(module_name: str) -> None:
    forbidden_imports = [
        imported
        for imported in imports_of(module_name)
        if imported.top_level_package in FORBIDDEN_PACKAGES
    ]

    assert forbidden_imports == []
