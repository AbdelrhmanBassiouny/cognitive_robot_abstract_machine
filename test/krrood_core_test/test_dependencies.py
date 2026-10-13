from __future__ import annotations

import json
import subprocess
import sys
import tomllib
from pathlib import Path
from types import ModuleType

import pytest
from packaging.requirements import Requirement

import krrood_core.class_property
import krrood_core.exceptions
import krrood_core.path_enumeration
import krrood_core.standard_streams

PACKAGE_DIRECTORY = Path(__file__).parents[2] / "krrood_core"
"""
The directory holding the package's ``pyproject.toml``.
"""

PROBES_DIRECTORY = Path(__file__).parent / "dataset"
"""
The scripts each test runs in an interpreter of its own, so that what they load is not
already loaded by the test run.
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
        [sys.executable, "-I", PROBES_DIRECTORY / "loaded_top_level_modules.py"],
        capture_output=True,
        text=True,
        check=True,
    )
    loaded = set(json.loads(probe.stdout))

    undeclared = loaded - sys.stdlib_module_names - declared - {"krrood_core"}

    assert undeclared == set()


@pytest.mark.parametrize(
    "module",
    [
        krrood_core.exceptions,
        krrood_core.path_enumeration,
        krrood_core.class_property,
        krrood_core.standard_streams,
    ],
    ids=lambda m: m.__name__,
)
def test_the_modules_a_tool_reads_before_installing_need_only_the_standard_library(
    module: ModuleType,
):
    """
    A tool that checks what it has to install uses these before anything is installed,
    with the package's source on its import path and nothing else.
    """
    probe = subprocess.run(
        [
            sys.executable,
            "-I",
            PROBES_DIRECTORY / "standard_library_only.py",
            module.__name__,
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    assert json.loads(probe.stdout) == []
