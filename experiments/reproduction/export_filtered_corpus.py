"""
Split the results database into two derived SQLite databases -- one holding only
simulated trials, one holding only a chosen allow-list of real-robot episodes -- so
``generate_paper_figures.py`` can be run once over each corpus unmodified.

Recalls one episode at a time rather than through
``LongTermMemory.recall_every_readable_trial``: that method's own conversion still
crashes the whole batch on the first episode whose kept world cannot be read back with
the current code (its "readable" filter only ever checked for missing mesh files), so a
single bad episode anywhere in the corpus would otherwise stop every other one from being
exported too. Recalling per episode isolates that failure to the one episode it belongs
to.

Each recalled trial is also recorded one at a time behind its own try/except: an episode
recorded before a fix to how an ``Enum`` field on a leaf type (a ``StrEnum``) was
JSON-serialized stores that field as a bare value rather than a typed reference, so it
reads back as a plain string where a typed field (for example
``ShapeSortingHole.shape_category``) is later required, and writing it into the derived
database raises there instead of at recall time. Isolating the write the same way the
recall already is keeps one such episode from stopping every other one's export.

Usage:
    python3 export_filtered_corpus.py \
        --source-database-uri postgresql+psycopg://semantic_digital_twin:montessori@localhost:5432/montessori_sorting_results \
        --simulated-output montessori_simulated.db \
        --real-output montessori_real_filtered.db \
        --real-episode <identifier> [<identifier> ...]
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

from coraplex.datastructures.enums import ExecutionType
from krrood.entity_query_language.factories import an, entity, variable
from semantic_digital_twin.exceptions import BrokenWorldModificationHistoryError
from sqlalchemy.exc import SQLAlchemyError
from typing_extensions import List, Optional, Sequence

from experiments.episodes.episode import Episode
from experiments.episodes.long_term_memory import LongTermMemory
from experiments.episodes.recording import open_recording
from experiments.montessori.results_database import ResultsDatabase


def episode_identifiers(
    memory: LongTermMemory, execution_type: ExecutionType
) -> List[str]:
    """
    Every episode's identifier of the given execution type, without converting any row
    to a domain object.
    """
    episode = variable(type_=Episode, domain=[])
    identifiers = memory.answer_with_identifiers(
        an(entity(episode).where(episode.execution_type == execution_type))
    )
    return sorted(set(identifiers))


def export(source_uri: str, output_path: Path, identifiers: Sequence[str]) -> int:
    memory = LongTermMemory(ResultsDatabase(uri=source_uri))
    kept = 0
    if output_path.exists():
        output_path.unlink()
    target = ResultsDatabase(uri="sqlite:///%s" % output_path)
    recording = open_recording(target)
    for identifier in identifiers:
        try:
            trials = memory.recall_trials(identifier)
        except BrokenWorldModificationHistoryError as error:
            print("%s: skipping, cannot be read back (%s)" % (identifier, error))
            continue
        for trial in trials:
            try:
                recording.record(trial)
            except SQLAlchemyError as error:
                recording.session.rollback()
                print(
                    "%s: skipping a trial, cannot be written back (%s)"
                    % (identifier, error)
                )
                continue
            kept += 1
    recording.close()
    print(
        "%s: kept %d trial(s) across %d episode(s)."
        % (output_path, kept, len(identifiers))
    )
    return kept


def main(argument_list: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-database-uri", required=True)
    parser.add_argument("--simulated-output", type=Path, default=None)
    parser.add_argument("--real-output", type=Path, default=None)
    parser.add_argument(
        "--real-episode", nargs="*", default=[], help="identifiers to keep"
    )
    arguments = parser.parse_args(argument_list)

    memory = LongTermMemory(ResultsDatabase(uri=arguments.source_database_uri))

    if arguments.simulated_output is not None:
        export(
            arguments.source_database_uri,
            arguments.simulated_output,
            episode_identifiers(memory, ExecutionType.SIMULATED),
        )

    if arguments.real_output is not None:
        export(
            arguments.source_database_uri, arguments.real_output, arguments.real_episode
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
