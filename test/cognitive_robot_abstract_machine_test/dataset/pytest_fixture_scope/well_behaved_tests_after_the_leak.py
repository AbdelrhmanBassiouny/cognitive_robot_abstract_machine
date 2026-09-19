"""
A clean module that runs after ``leaking_test.py``, proving that an already-reported
leak does not spill over and misattribute itself to a later, innocent module.

Copied into an isolated pytest run by ``test_leaked_worlds_pytest_integration.py``.
"""


def test_uses_a_function_world(function_world):
    assert function_world is not None
