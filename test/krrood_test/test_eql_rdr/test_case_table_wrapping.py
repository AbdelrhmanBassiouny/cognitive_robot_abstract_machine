"""
Tests that the case table wraps an over-wide value rather than truncating it, so the
expert always sees the whole value they are labelling.
"""

from __future__ import annotations

import unittest
from dataclasses import dataclass

from krrood.entity_query_language.rdr.case_table import CaseTableRenderer


class TestCaseTableWrapping(unittest.TestCase):
    """
    CaseTableRenderer wraps long values instead of truncating them with ellipsis.
    """

    def test_long_value_wraps_not_truncates(self):
        """
        A value longer than value_width is present in full across multiple lines (no
        ellipsis).
        """
        long_str = "x" * 200
        # Force a very narrow max_width to guarantee the value exceeds value_width.
        renderer = CaseTableRenderer(min_column_width=24, max_width=40, use_color=False)

        @dataclass
        class WideCase:
            """
            A case whose single value is far wider than any column.
            """

            field_name: str = ""
            """
            The over-wide value under test.
            """

        case = WideCase(field_name=long_str)
        rendered = renderer.render(case)
        # The full string must appear somewhere in the output (possibly wrapped across lines)
        self.assertIn("x" * 10, rendered)
        # And the ellipsis truncation marker must NOT be present
        self.assertNotIn("...", rendered)

    def test_short_value_unchanged(self):
        """
        A value shorter than value_width appears verbatim and without modification.
        """

        @dataclass
        class NarrowCase:
            """
            A case whose single value fits a column with room to spare.
            """

            label: str = ""
            """
            The short value under test.
            """

        renderer = CaseTableRenderer(
            min_column_width=24, max_width=200, use_color=False
        )
        case = NarrowCase(label="hello")
        rendered = renderer.render(case)
        self.assertIn("hello", rendered)
        self.assertNotIn("...", rendered)


if __name__ == "__main__":
    unittest.main()
