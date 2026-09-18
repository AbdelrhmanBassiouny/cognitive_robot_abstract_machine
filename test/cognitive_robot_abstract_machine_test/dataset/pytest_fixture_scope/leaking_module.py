"""
A module with one genuine leak: a test that stashes its function-scoped world where it
outlives the test.

Copied into an isolated pytest run by ``test_leaked_worlds_pytest_integration.py``.
"""

kept_alive_after_its_test_finished = []


def test_that_leaks_a_world(function_world):
    kept_alive_after_its_test_finished.append(function_world)


def test_that_does_nothing_leaky():
    assert True
