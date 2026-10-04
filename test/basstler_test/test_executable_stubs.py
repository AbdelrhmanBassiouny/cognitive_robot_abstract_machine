"""
Tests for the stubbed ``PATH`` the suites run their subprocesses against.

The subject is test infrastructure, but it is worth pinning down: it decides which
backend the scripts under test select, and a mistake in it fails whole test modules for
reasons that have nothing to do with what they assert.
"""

from __future__ import annotations

import shutil

from .constants import GitHubCredentialVariable
from .executable_stubs import ExecutableStubDirectory, StubbedExecutable

DELIBERATE_TOKEN = "a-token"
"""
A token a test sets on purpose, which the scrubbing must leave alone.
"""


def test_hiding_one_executable_leaves_its_neighbours_findable(
    stub_bin: ExecutableStubDirectory,
):
    # Hiding used to drop the whole PATH entry providing the executable. That entry is
    # normally /usr/bin, which also provides bash - so on a machine that has the hidden
    # executable installed, every test hiding it failed before its subject even started.
    environment = stub_bin.subprocess_environment(
        hidden_executables=(StubbedExecutable.GIT,)
    )

    assert shutil.which(StubbedExecutable.GIT, path=environment["PATH"]) is None
    assert shutil.which("bash", path=environment["PATH"]) is not None


def test_an_installed_stub_wins_over_a_real_executable(
    stub_bin: ExecutableStubDirectory,
):
    stub_bin.install(StubbedExecutable.CURL)
    environment = stub_bin.subprocess_environment()

    assert shutil.which(StubbedExecutable.CURL, path=environment["PATH"]) == str(
        stub_bin.path / StubbedExecutable.CURL.value
    )


def test_strips_the_callers_own_github_credentials(
    stub_bin: ExecutableStubDirectory,
):
    # Whoever runs the tests may have real credentials set - this environment does - and a
    # run that reached GitHub with them would be neither reproducible nor safe.
    environment = stub_bin.subprocess_environment()

    assert not set(GitHubCredentialVariable) & environment.keys()


def test_keeps_a_token_a_test_sets_deliberately(
    stub_bin: ExecutableStubDirectory,
):
    environment = stub_bin.subprocess_environment(GH_TOKEN=DELIBERATE_TOKEN)

    assert environment[GitHubCredentialVariable.GH_TOKEN] == DELIBERATE_TOKEN
