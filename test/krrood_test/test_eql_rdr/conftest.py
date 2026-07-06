"""Shared fixtures for the EQL-RDR tests.

Some tests drive the ripple-down-rules fitting loop through the *real* embedded IPython shell,
which blocks waiting for a human to type answers. Those tests are meaningful only with an actual
user at an interactive terminal, so when the session is non-interactive (CI, ``pytest`` without a
TTY) any test that reaches the real shell is skipped automatically instead of hanging.
"""

from __future__ import annotations

import sys

import pytest

from krrood.entity_query_language.rdr.interactive import IPythonInterface


@pytest.fixture(autouse=True)
def skip_tests_needing_a_real_user(monkeypatch: pytest.MonkeyPatch) -> None:
    """Skip a test the moment it would open the real interactive shell with no user present."""
    if sys.stdin.isatty():
        return

    def _skip_no_user(*_args: object, **_kwargs: object) -> None:
        pytest.skip("interactive: needs a real user at a terminal (run with `pytest -s` in a TTY)")

    monkeypatch.setattr(IPythonInterface, "_default_run_shell", _skip_no_user)
