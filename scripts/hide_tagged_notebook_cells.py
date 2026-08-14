"""
Hide the cells a notebook tags for Jupyter Book in a live Jupyter session too.

Tags such as ``hide-cell`` and ``hide-input`` only reach the book Jupyter Book renders.
Anyone who opens the notebook itself -- in JupyterLab, or on Binder -- sees every cell,
example solutions included. This writes the tags into the per-cell metadata a live
session reads, so those cells start collapsed behind a toggle and are one click away.

Run it again after tagging or untagging a cell::

    python scripts/hide_tagged_notebook_cells.py experiments/src/ijcai_demo.ipynb
"""

from __future__ import annotations

import sys
from argparse import ArgumentParser
from pathlib import Path

from typing_extensions import Sequence

from cognitive_robot_abstract_machine.notebooks import Notebook


def parse_notebook_paths(arguments: Sequence[str]) -> Sequence[Path]:
    """
    Read the notebooks to work on from the command line.

    :param arguments: Command line arguments, without the program name.
    :return: Path of each notebook given.
    """
    parser = ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument(
        "notebooks",
        nargs="+",
        type=Path,
        help="the .ipynb files whose tagged cells should start collapsed",
    )
    return parser.parse_args(list(arguments)).notebooks


def main(arguments: Sequence[str]) -> None:
    """
    Collapse the tagged cells of every notebook given on the command line.

    :param arguments: Command line arguments, without the program name.
    """
    for path in parse_notebook_paths(arguments):
        changed = Notebook(path).hide_tagged_cells()
        print(f"{path}: {len(changed)} cell(s) changed {changed}")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
