"""
Print the domain class the recorded results are mapped through, in a fresh interpreter.

Run with the URI of a results database as its only argument. Whether the mapping
resolves depends on the generated ``experiments`` ORM interface having been imported,
which nothing but opening a session does -- so this has to happen in an interpreter that
no other test has already imported it into.
"""

from __future__ import annotations

import sys

from krrood.ormatic.data_access_objects.helper import get_dao_class

from experiments.montessori.results_database import ResultsDatabase
from experiments.montessori.sorting_results import ShapeInsertionResult

ResultsDatabase(uri=sys.argv[1]).open_session(create_missing_tables=False).close()
print(get_dao_class(ShapeInsertionResult).original_class().__name__)
