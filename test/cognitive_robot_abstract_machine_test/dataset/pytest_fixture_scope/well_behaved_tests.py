"""
A module that only ever uses worlds a fixture is responsible for.

Copied into an isolated pytest run by ``test_leaked_worlds_pytest_integration.py``.
Its last test uses a function-scoped world on purpose: pytest keeps a finished test's
fixture arguments referenced on its own collected item until it moves on to the next
one, so a guard that checked too early would mistake that reference for a leak this
test itself made.
"""


def test_uses_the_session_and_module_worlds(
    session_world, module_world, function_world
):
    assert session_world is not None
    assert module_world is not None
    assert function_world is not None


def test_uses_them_again(session_world, module_world, function_world):
    assert session_world is not None
    assert module_world is not None
    assert function_world is not None


def test_uses_only_a_function_world_last(function_world):
    assert function_world is not None
