"""
Tests for the stubbed ``PATH`` the hook tests run their subprocesses against.

The subject is test infrastructure, but it is worth pinning down: it decides which
backend the scripts under test select, and a mistake in it fails whole test modules for
reasons that have nothing to do with what they assert.
"""

from __future__ import annotations

import shutil

from stub_executables import StubExecutableDirectory


def test_hiding_one_executable_leaves_its_neighbours_findable(
    stub_executables: StubExecutableDirectory,
):
    # Hiding used to drop the whole PATH entry providing the executable. That entry is
    # normally /usr/bin, which also provides bash - so on a machine that has the hidden
    # executable installed, every test hiding it failed before its subject even started.
    environment = stub_executables.subprocess_environment(hidden_executables=("git",))

    assert shutil.which("git", path=environment["PATH"]) is None
    assert shutil.which("bash", path=environment["PATH"]) is not None


def test_an_installed_stub_wins_over_a_real_executable(
    stub_executables: StubExecutableDirectory,
):
    stub_executables.install("curl")
    environment = stub_executables.subprocess_environment()

    assert shutil.which("curl", path=environment["PATH"]) == str(
        stub_executables.path / "curl"
    )


def test_strips_the_callers_own_github_credentials(
    stub_executables: StubExecutableDirectory,
):
    # Whoever runs the tests may have real credentials set - this environment does - and a
    # run that reached GitHub with them would be neither reproducible nor safe.
    environment = stub_executables.subprocess_environment()

    assert "GH_TOKEN" not in environment
    assert "GITHUB_TOKEN" not in environment


def test_keeps_a_token_a_test_sets_deliberately(
    stub_executables: StubExecutableDirectory,
):
    environment = stub_executables.subprocess_environment(GH_TOKEN="a-token")

    assert environment["GH_TOKEN"] == "a-token"
