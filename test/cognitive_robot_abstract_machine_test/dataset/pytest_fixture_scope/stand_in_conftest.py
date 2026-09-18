"""
The world-leak guard's hooks, wired against a stand-in world instead of the real one.

``test_leaked_worlds_pytest_integration.py`` copies this into an isolated pytest run as
its ``conftest.py``, rather than collecting it directly: the real ``test/conftest.py``
watches the real world type once and for good, so a second, nested run cannot watch it
again to prove the same pattern works.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from xdist import get_xdist_worker_id, is_xdist_controller, is_xdist_worker

from test.living_worlds import (
    FixtureScope,
    LeakedWorldsAcrossWorkersError,
    LeakedWorldsError,
    LivingWorlds,
    WorkerTally,
    WorldTallyLedger,
)
from test.pytest_environment import PytestEnvironmentVariable


class StandInWorld:
    """
    Stands in for the real world type the guard watches.
    """


LIVING_WORLDS = pytest.StashKey[LivingWorlds]()
"""
Where this run keeps the record of which test created each world.
"""

CURRENT_MODULE = pytest.StashKey[str]()
"""
Which test module the tests running now belong to.
"""

WORLD_TALLY_DIRECTORY_NAME = ".living_worlds_tally"
"""
Where each process of a run writes its final world tally.
"""


def world_tally_ledger(config: pytest.Config) -> WorldTallyLedger:
    """
    :param config: The run's configuration.
    :return: The ledger every process of this run shares to combine their tallies.
    """
    return WorldTallyLedger(
        directory=Path(config.rootpath) / WORLD_TALLY_DIRECTORY_NAME
    )


def pytest_configure(config: pytest.Config) -> None:
    """
    Start recording the worlds this run creates.
    """
    if not os.environ.get(PytestEnvironmentVariable.XDIST_WORKER):
        world_tally_ledger(config).clear()

    living_worlds = LivingWorlds(world_type=StandInWorld)
    living_worlds.watch()
    config.stash[LIVING_WORLDS] = living_worlds


def _report_and_fail(session: pytest.Session, error: Exception) -> None:
    """
    Report an error through the terminal reporter and the exit status, rather than
    raising it as a fixture or item outcome.
    """
    terminal_reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    if terminal_reporter is not None:
        terminal_reporter.write_line(str(error), red=True)
    session.exitstatus = pytest.ExitCode.TESTS_FAILED


def pytest_runtest_setup(item: pytest.Item) -> None:
    """
    Check the module being left behind once every one of its tests has run, then
    attribute the worlds created from now on to the test that is about to run.
    """
    living_worlds = item.config.stash[LIVING_WORLDS]
    module = item.nodeid.split("::", 1)[0]
    previous_module = item.config.stash.get(CURRENT_MODULE, None)
    if previous_module is not None and previous_module != module:
        try:
            living_worlds.enforce_limit(module=previous_module)
        except LeakedWorldsError as error:
            _report_and_fail(item.session, error)
    item.config.stash[CURRENT_MODULE] = module
    living_worlds.current_test = item.nodeid


@pytest.hookimpl(hookwrapper=True)
def pytest_fixture_setup(fixturedef: pytest.FixtureDef, request: pytest.FixtureRequest):
    """
    Stop recording worlds while a fixture whose scope outlives a single test is setting
    up.
    """
    scope = FixtureScope(getattr(fixturedef.scope, "value", fixturedef.scope))
    if not scope.outlives_a_single_test:
        yield
        return
    living_worlds = request.config.stash[LIVING_WORLDS]
    with living_worlds.ignore_worlds_created_here():
        yield


def pytest_sessionfinish(session: pytest.Session) -> None:
    """
    Check the last module that ran, write this process's final world tally, and once
    every process has, enforce a limit on their combined total.
    """
    living_worlds = session.config.stash[LIVING_WORLDS]
    last_module = session.config.stash.get(CURRENT_MODULE, None)
    if last_module is not None:
        try:
            living_worlds.enforce_limit(module=last_module)
        except LeakedWorldsError as error:
            _report_and_fail(session, error)

    ledger = world_tally_ledger(session.config)

    if not is_xdist_controller(session):
        ledger.record(
            WorkerTally(
                worker=get_xdist_worker_id(session),
                left_behind=living_worlds.collect_surviving_worlds(),
            )
        )

    if is_xdist_worker(session):
        return

    try:
        ledger.enforce_combined_limit()
    except LeakedWorldsAcrossWorkersError as error:
        _report_and_fail(session, error)


@pytest.fixture(scope="session")
def session_world() -> StandInWorld:
    """
    A world a session-scoped fixture builds once, expected to survive every test and
    every module.
    """
    return StandInWorld()


@pytest.fixture(scope="module")
def module_world() -> StandInWorld:
    """
    A world a module-scoped fixture builds once per module, expected to survive every
    test of that module.
    """
    return StandInWorld()


@pytest.fixture()
def function_world() -> StandInWorld:
    """
    A world built fresh for one test, expected to be released when that test ends.
    """
    return StandInWorld()
