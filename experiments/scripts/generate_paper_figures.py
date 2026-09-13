"""
Regenerate every table the paper prints from the recorded episodes.

The paper's experiments section includes what this writes, so a run added to the
database changes the paper by running this again rather than by anyone retyping a
number. Every table is written even when nothing has been recorded yet, so the first
draft is already made of the script's own output.

Usage:
    python3 generate_paper_figures.py [--database-uri <uri>] [--output-directory <path>]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from typing_extensions import List, Optional

from experiments.episodes.long_term_memory import LongTermMemory
from experiments.montessori.results_database import (
    ConfiguredDatabase,
    ResultsDatabase,
    database_label,
)
from experiments.paper.figure_set import FigureSet

DEFAULT_OUTPUT_DIRECTORY = Path(__file__).parent.parent / "doc" / "figures"
"""
Where the tables go when no other directory is asked for, beside the paper's own
bibliography.
"""


def main(argument_list: Optional[List[str]] = None) -> int:
    """
    Write every table of the paper from what the episode database holds.

    :param argument_list: Arguments to read; the process's own when omitted.
    :return: 0, the tables were written.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-uri", default=None)
    parser.add_argument(
        "--output-directory", type=Path, default=DEFAULT_OUTPUT_DIRECTORY
    )
    arguments = parser.parse_args(argument_list)

    database = ConfiguredDatabase.resolve(arguments.database_uri)
    print("Reading episodes from %s." % database_label(database.uri))
    trials = LongTermMemory(ResultsDatabase(uri=database.uri)).recall_every_trial()
    print("Recalled %d trial(s)." % len(trials))

    for written in FigureSet.for_the_paper().write(trials, arguments.output_directory):
        print("Wrote %s and %s." % (written.table_path, written.row_manifest_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
