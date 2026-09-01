"""
The libraries the continuous-integration matrix runs a job for.

Read from the workflow that declares them rather than listed here: a library added to
the matrix is one a candidate can newly go red on, and a list written beside the matrix
would answer that it is not localisable while saying nothing about being out of date.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from workflow_document import MatrixKey, WorkflowFile

MATRIX_CHECK_PATTERN = re.compile(r"\(([^)]+)\)")
"""
Finds the library a matrix job's check name is for.

The matrix names each job ``test_each_lib (<lib>)``, optionally suffixed with the
reusable job's own name; the library is what the parentheses hold.
"""


@dataclass(frozen=True)
class LibraryUnderTest:
    """
    One library the matrix runs a job for, which is a failure this can localise.

    Read from ``ci.yml`` rather than listed here: a library added to the matrix is one a
    candidate can newly go red on, and a list written beside the matrix would answer that
    it is not localisable while saying nothing about being out of date.
    """

    name: str
    """
    What the matrix calls it, which is also what the check name carries.
    """

    def __str__(self) -> str:
        return self.name

    @classmethod
    def in_the_matrix(cls) -> tuple[LibraryUnderTest, ...]:
        """:return: Every library the matrix runs a job for, in the order it declares
        them."""
        fanning_out = (
            WorkflowFile.CONTINUOUS_INTEGRATION.read().job_fanning_out_over_a_matrix
        )
        return tuple(
            cls(entry[str(MatrixKey.LIBRARY)]) for entry in fanning_out.matrix_entries
        )

    @classmethod
    def named_by(cls, check: str) -> LibraryUnderTest | None:
        """
        A check this search can answer about is one the matrix runs per library, so what
        makes it answerable is that the name holds a library the matrix declares.

        :param check: A failing check's name.
        :return: The library to re-run over each prefix, or ``None`` when the check names
            none - in which case there is nothing here to re-run.
        """
        found = MATRIX_CHECK_PATTERN.search(check)
        if found is None:
            return None
        named = found.group(1).strip()
        return next(
            (library for library in cls.in_the_matrix() if library.name == named),
            None,
        )
