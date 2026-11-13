"""
The entity query language loads without the probabilistic libraries installed.
"""

from __future__ import annotations

import subprocess
import sys
from enum import StrEnum
from pathlib import Path

import krrood.entity_query_language

# %% probabilistic libraries


class ProbabilisticLibrary(StrEnum):
    """
    The top-level packages of the libraries only the probabilistic part of krrood needs.
    """

    RANDOM_EVENTS = "random_events"
    PROBABILISTIC_MODEL = "probabilistic_model"


# %% importing without them


def test_every_entity_query_language_module_imports_without_probabilistic_libraries():
    """
    A fresh interpreter, since this one has already loaded the libraries.
    """
    import_script = (
        Path(__file__).parent / "dataset" / "import_package_without_libraries.py"
    )
    report = subprocess.run(
        [
            sys.executable,
            str(import_script),
            krrood.entity_query_language.__name__,
            *ProbabilisticLibrary,
        ],
        capture_output=True,
        text=True,
    )

    assert report.returncode == 0, report.stderr
