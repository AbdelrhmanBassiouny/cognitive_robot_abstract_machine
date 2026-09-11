"""
Draw every query card of one recorded episode.

A table says how often the queries were answered correctly; a card says what one of those
answers means in the twin. The paper shows both, and both are regenerated from the
database rather than assembled by hand, so a run added to it changes the paper by running
this again.

Usage:
    python3 render_query_cards.py --episode <identifier> [--database-uri <uri>]
                                  [--output-directory <path>]
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
from experiments.paper.query_card import QueryCardSet

DEFAULT_OUTPUT_DIRECTORY = Path(__file__).parent.parent / "doc" / "cards"
"""
Where the cards go when no other directory is asked for, beside the tables the paper's
own figures are written to.
"""


def main(argument_list: Optional[List[str]] = None) -> int:
    """
    Draw every card of one episode from what the database recorded of it.

    :param argument_list: Arguments to read; the process's own when omitted.
    :return: 0, the cards were drawn.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episode", required=True)
    parser.add_argument("--database-uri", default=None)
    parser.add_argument(
        "--output-directory", type=Path, default=DEFAULT_OUTPUT_DIRECTORY
    )
    arguments = parser.parse_args(argument_list)

    database = ConfiguredDatabase.resolve(arguments.database_uri)
    print("Reading episodes from %s." % database_label(database.uri))
    trials = LongTermMemory(ResultsDatabase(uri=database.uri)).recall_trials(
        arguments.episode
    )
    print("Recalled %d trial(s) of episode %s." % (len(trials), arguments.episode))

    written = QueryCardSet.for_the_paper().write_every_episode(
        trials, arguments.output_directory, ArtifactDirectory()
    )
    for card in written:
        print("Wrote %s and %d picture(s)." % (card.markup_path, len(card.panel_paths)))
    print("Drew %d card(s)." % len(written))
    return 0


if __name__ == "__main__":
    sys.exit(main())
