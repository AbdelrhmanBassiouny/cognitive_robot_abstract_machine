"""
Where ``scripts/sync_version.py`` writes each package's version.

The script is a standalone file rather than part of an importable package, so it is
loaded from its path.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

SYNC_VERSION_SCRIPT = Path(__file__).parents[2] / "scripts" / "sync_version.py"
"""
The script under test.
"""


def load_sync_version() -> ModuleType:
    """
    :return: The script, imported from its file.
    """
    specification = importlib.util.spec_from_file_location(
        SYNC_VERSION_SCRIPT.stem, SYNC_VERSION_SCRIPT
    )
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


sync_version = load_sync_version()


@pytest.mark.parametrize("package", list(sync_version.Package), ids=str)
def test_every_package_version_file_is_where_the_script_writes_it(package):
    """
    A package whose layout the script has wrong would get a ``_version.py`` in a place
    nothing imports, and keep the old version where its import does read it.
    """
    assert package.version_file.is_file()
