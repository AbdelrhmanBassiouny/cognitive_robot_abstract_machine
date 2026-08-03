"""
Reading session-start.sh's summary report back in a test.

The hook's report is its only observable output, so more than one test module asserts
against it; parsing it lives here rather than being written out again in each of them.
"""

from __future__ import annotations


def summary_value(output: str, label: str) -> str:
    """
    Extract one line's value from the summary report.

    :param output: session-start.sh's standard output.
    :param label: The summary line's label, such as ``plan``.
    :return: Everything after the label, stripped.
    :raises AssertionError: If the report has no such line.
    """
    prefix = f"  {label}:"
    for line in output.splitlines():
        if line.startswith(prefix):
            return line[len(prefix) :].strip()
    raise AssertionError(f"no '{label}' line in this summary report:\n{output}")
