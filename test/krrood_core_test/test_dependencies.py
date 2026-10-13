from __future__ import annotations

import json
import subprocess
import sys
import tomllib
from pathlib import Path

from packaging.requirements import Requirement

from .dataset import loaded_top_level_modules

PACKAGE_DIRECTORY = Path(__file__).parents[2] / "krrood_core"
"""
The directory holding the package's ``pyproject.toml``.
"""


def test_importing_every_module_loads_only_the_declared_dependencies():
    """
    The package is installed by tools that cannot afford krrood's scientific stack, so
    importing all of it must load nothing beyond the standard library and the
    dependencies it declares.
    """
    declaration = tomllib.loads((PACKAGE_DIRECTORY / "pyproject.toml").read_text())
    declared = {
        Requirement(requirement).name.replace("-", "_")
        for requirement in declaration["project"]["dependencies"]
    }
    probe = subprocess.run(
        [sys.executable, "-I", loaded_top_level_modules.__file__],
        capture_output=True,
        text=True,
        check=True,
    )
    loaded = set(json.loads(probe.stdout))

    undeclared = loaded - sys.stdlib_module_names - declared - {"krrood_core"}

    assert undeclared == set()
