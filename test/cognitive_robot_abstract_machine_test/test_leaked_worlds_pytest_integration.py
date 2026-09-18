"""
The guard's hooks, exercised against a real, separate pytest run.

The unit tests in ``test_leaked_worlds.py`` cover :mod:`test.living_worlds` directly,
but never the hooks in ``test/conftest.py`` that wire it into a real pytest session:
whether a fixture's scope is read correctly, whether the check fires at the right moment
relative to pytest's own fixture teardown, and whether an already-reported leak stays
reported. Those only show up under a real, separate pytest run, driven here with the
:func:`pytest.pytester` fixture against the stand-in conftest and test modules in
``dataset/pytest_fixture_scope``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

DATASET_DIRECTORY = Path(__file__).parent / "dataset" / "pytest_fixture_scope"
"""
Where the stand-in conftest and test modules this file copies into an isolated run live.
"""


def _copy_dataset_file(
    pytester: pytest.Pytester, name: str, source_file_name: str
) -> None:
    """
    Copy one dataset file into the isolated run as a test module.

    :param pytester: The isolated run to copy into.
    :param name: The module name to give it there, without the ``.py`` suffix.
    :param source_file_name: The dataset file's own name, with the suffix.
    """
    pytester.makepyfile(**{name: (DATASET_DIRECTORY / source_file_name).read_text()})


@pytest.fixture()
def isolated_run(pytester: pytest.Pytester) -> pytest.Pytester:
    """
    An isolated pytest run wired with the same fixture-scope-owner and deferred-module-
    boundary-check pattern as the real ``test/conftest.py``, against a stand-in world.
    """
    pytester.makeconftest((DATASET_DIRECTORY / "stand_in_conftest.py").read_text())
    return pytester


# %% a world a durably-scoped fixture is why it exists is never flagged


def test_a_module_of_well_behaved_tests_passes(isolated_run: pytest.Pytester):
    _copy_dataset_file(isolated_run, "test_well_behaved", "well_behaved_tests.py")

    result = isolated_run.runpytest()

    result.assert_outcomes(passed=3)
    assert result.ret == 0


# %% a genuine leak is caught and named, not the last test that happened to run


def test_a_genuine_leak_is_caught_and_named(isolated_run: pytest.Pytester):
    _copy_dataset_file(isolated_run, "test_leaky", "leaking_module.py")

    result = isolated_run.runpytest()

    # The leak is reported directly, not as any test's own outcome - both tests in
    # the leaking module still pass, since neither one's own assertions failed.
    result.assert_outcomes(passed=2)
    assert result.ret != 0

    stdout = result.stdout.str()
    assert "test_leaky.py finished" in stdout
    assert "test_that_leaks_a_world: 1" in stdout


# %% an already-reported leak does not spill into a later, innocent module


def test_a_reported_leak_does_not_recur_for_a_later_module(
    isolated_run: pytest.Pytester,
):
    _copy_dataset_file(isolated_run, "test_a_leaky", "leaking_module.py")
    _copy_dataset_file(
        isolated_run, "test_b_clean", "well_behaved_tests_after_the_leak.py"
    )

    result = isolated_run.runpytest()

    result.assert_outcomes(passed=3)
    assert result.ret != 0

    stdout = result.stdout.str()
    assert stdout.count("test_a_leaky.py finished") == 1
    assert "test_b_clean.py finished" not in stdout
