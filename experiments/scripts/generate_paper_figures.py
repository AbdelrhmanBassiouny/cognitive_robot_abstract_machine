"""
Regenerate every figure the paper prints from the recorded episodes: its tables, and the
card of every query shown beside a picture of what its answer means.

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

from experiments.episodes.artifacts import ArtifactDirectory
from experiments.episodes.long_term_memory import LongTermMemory
from experiments.montessori.results_database import (
    ConfiguredDatabase,
    ResultsDatabase,
    database_label,
)
from experiments.paper.figure_set import FigureSet
from experiments.paper.query_card import QueryCardSet

DEFAULT_OUTPUT_DIRECTORY = Path(__file__).parent.parent / "doc" / "figures"
"""
Where the tables go when no other directory is asked for, beside the paper's own
bibliography.
"""

CARD_DIRECTORY = "cards"
"""
What the directory holding the query cards is called inside the output directory, so a
table and the many files one card is made of do not lie in one heap.
"""


def main(argument_list: Optional[List[str]] = None) -> int:
    """
    Write every table of the paper, and draw every query card, from what the episode
    database holds.

    :param argument_list: Arguments to read; the process's own when omitted.
    :return: 0, the figures were written.
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

    cards = QueryCardSet.for_the_paper().write_every_episode(
        trials, arguments.output_directory / CARD_DIRECTORY, ArtifactDirectory()
    )
    for card in cards:
        print("Drew %s." % card.markup_path)
    print("Drew %d query card(s)." % len(cards))
    return 0


if __name__ == "__main__":
    sys.exit(main())
