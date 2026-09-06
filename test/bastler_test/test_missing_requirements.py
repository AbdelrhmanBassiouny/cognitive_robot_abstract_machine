"""
Tests for missing_requirements.py, the shared "which of these are not installed?" check.
"""

import subprocess
from pathlib import Path

import pytest

import bastler.missing_requirements
from bastler.missing_requirements import RequirementsFile

from .constants import REPOSITORY_ROOT
from .script_runner import PythonModuleRunner

INSTALLED_DISTRIBUTION = "pytest"
"""
A distribution every environment running this suite provably has, since it is the suite
runner itself.
"""

ABSENT_DISTRIBUTION = "no-such-distribution-exists"
"""
A name no environment can have installed, so it is always reported missing.
"""


@pytest.fixture
def requirements_path(tmp_path: Path) -> Path:
    """
    Where a test writes the requirements file it is about.

    :param tmp_path: pytest's per-test temporary directory.
    :return: The path to write, which no test creates until it has content for it.
    """
    return tmp_path / "requirements.txt"


# %% reading the distribution names out of a requirements file


def test_reads_a_bare_distribution_name(requirements_path: Path):
    requirements_path.write_text(f"{ABSENT_DISTRIBUTION}\n")

    assert RequirementsFile(requirements_path).distribution_names() == [
        ABSENT_DISTRIBUTION
    ]


@pytest.mark.parametrize(
    "specifier",
    [
        ">=2",
        "==2.0",
        "<3",
        "!=1.4",
        "~=2.1",
        ">=2 ; python_version >= '3.12'",
        "[extra]",
    ],
)
def test_reads_the_name_out_of_a_version_specifier(
    requirements_path: Path, specifier: str
):
    requirements_path.write_text(f"{ABSENT_DISTRIBUTION}{specifier}\n")

    assert RequirementsFile(requirements_path).distribution_names() == [
        ABSENT_DISTRIBUTION
    ]


def test_passes_over_comments_and_blank_lines(requirements_path: Path):
    requirements_path.write_text(
        f"# a leading comment\n\n{ABSENT_DISTRIBUTION}>=2  # trailing\n\n"
    )

    assert RequirementsFile(requirements_path).distribution_names() == [
        ABSENT_DISTRIBUTION
    ]


# %% judging them against what is installed


def test_reports_a_distribution_that_is_not_installed(requirements_path: Path):
    requirements_path.write_text(f"{ABSENT_DISTRIBUTION}>=2\n")

    assert RequirementsFile(requirements_path).missing() == [ABSENT_DISTRIBUTION]


def test_reports_nothing_for_a_distribution_that_is_installed(requirements_path: Path):
    requirements_path.write_text(f"{INSTALLED_DISTRIBUTION}\n")

    assert RequirementsFile(requirements_path).missing() == []


def test_reports_only_the_missing_half_of_a_mixed_file(requirements_path: Path):
    requirements_path.write_text(
        f"{INSTALLED_DISTRIBUTION}\n{ABSENT_DISTRIBUTION}>=2\n"
    )

    assert RequirementsFile(requirements_path).missing() == [ABSENT_DISTRIBUTION]


def test_reports_nothing_for_an_empty_file(requirements_path: Path):
    requirements_path.write_text("")

    assert RequirementsFile(requirements_path).missing() == []


# %% the command line every shell caller goes through


def run_missing_requirements(requirements_path: Path) -> subprocess.CompletedProcess:
    """
    Run the module the way a hook script does.

    :param requirements_path: The requirements file to check.
    :return: The finished subprocess.
    """
    return PythonModuleRunner(
        project_root=REPOSITORY_ROOT,
        module_name=bastler.missing_requirements.__name__,
    ).run(str(requirements_path))


def test_prints_every_missing_name_on_one_line(requirements_path: Path):
    requirements_path.write_text(
        f"{INSTALLED_DISTRIBUTION}\n{ABSENT_DISTRIBUTION}>=2\n"
    )

    finished = run_missing_requirements(requirements_path)

    assert finished.returncode == 0
    assert finished.stdout.split() == [ABSENT_DISTRIBUTION]


def test_prints_nothing_when_every_requirement_is_installed(requirements_path: Path):
    requirements_path.write_text(f"{INSTALLED_DISTRIBUTION}\n")

    finished = run_missing_requirements(requirements_path)

    assert finished.returncode == 0
    assert finished.stdout.split() == []
