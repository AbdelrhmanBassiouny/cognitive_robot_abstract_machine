"""
A test carrying no marker, standing for every other test in the repository.

Named without the ``test_`` prefix so the stack suite's own directory scan passes this
over; it is run by an explicit path from the test that checks an unmarked test records
no break.
"""


def test_something_unrelated_to_any_integration_break():
    """Passes, and records nothing."""
    assert True
