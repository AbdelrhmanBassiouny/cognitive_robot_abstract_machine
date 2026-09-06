"""
A reproduction whose break is still there, written the way the triage skill writes one.

Named without the ``test_`` prefix so the stack suite's own directory scan passes this
over - it fails on purpose, and is run by an explicit path from the tests that exercise
the plugin.
"""

import pytest

from recorded_break import BREAKING_BRANCH


@pytest.mark.integration_conflict(BREAKING_BRANCH)
def test_the_two_branches_still_agree():
    """
    Fails, which is what keeps the block on the branch it names.
    """
    assert False
