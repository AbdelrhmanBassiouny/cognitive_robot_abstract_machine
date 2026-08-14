"""
Tests for building the ORM interfaces a checkout needs before it can persist objects.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from typing_extensions import Set, Tuple

from cognitive_robot_abstract_machine.exceptions import (
    MissingOrmGeneratorError,
    MissingOrmInterfaceError,
)
from cognitive_robot_abstract_machine.orm_interfaces import (
    OrmInterface,
    WORKSPACE_ORM_INTERFACES,
    WorkspaceOrmInterfaces,
)

from .dataset import generate_orm

# %% a checkout of packages that generate an interface

PACKAGE_NAMES: Tuple[str, ...] = ("upstream", "downstream")
"""
Packages of the checkout under test, in dependency order.
"""

STALE_INTERFACE_CONTENT = "# interface of a previous run\n"
"""
Content the interfaces hold before the checkout is regenerated.
"""


@pytest.fixture
def checkout(tmp_path: Path) -> Path:
    """
    A git checkout of two packages whose interfaces hold content of a previous run.
    """
    for package_name in PACKAGE_NAMES:
        package_root = tmp_path / package_name
        (package_root / "scripts").mkdir(parents=True)
        shutil.copy(
            Path(generate_orm.__file__),
            package_root / "scripts" / "generate_orm.py",
        )
        interface = generate_orm.interface_of(package_root)
        interface.parent.mkdir(parents=True)
        interface.write_text(STALE_INTERFACE_CONTENT, encoding="utf-8")

    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "add", "--all"], cwd=tmp_path, check=True, capture_output=True
    )
    return tmp_path


@pytest.fixture
def workspace(checkout: Path) -> WorkspaceOrmInterfaces:
    """
    The ORM interfaces of the checkout under test.
    """
    return WorkspaceOrmInterfaces(
        tuple(OrmInterface(package_name, checkout) for package_name in PACKAGE_NAMES)
    )


def interfaces_git_ignores_changes_of(repository_root: Path) -> Set[str]:
    """
    Read which of a checkout's files git was told to ignore the local changes of.

    :param repository_root: Root of the checkout.
    :return: The repository-relative paths carrying git's skip-worktree bit.
    """
    listing = subprocess.run(
        ["git", "ls-files", "-v"],
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return {
        line.split(" ", 1)[1]
        for line in listing.stdout.splitlines()
        if line.startswith("S ")
    }


# %% telling a generated checkout from a fresh one


def test_workspace_is_not_generated_while_one_interface_is_empty(
    workspace: WorkspaceOrmInterfaces,
):
    assert workspace.are_generated

    workspace.interfaces[-1].clear()

    assert workspace.interfaces[0].is_generated
    assert not workspace.interfaces[-1].is_generated
    assert not workspace.are_generated


# %% regeneration


def test_regeneration_runs_the_generators_in_dependency_order(
    workspace: WorkspaceOrmInterfaces, checkout: Path
):
    workspace.regenerate()

    records = generate_orm.read_generation_log(checkout)
    assert [record.package_name for record in records] == list(PACKAGE_NAMES)


def test_regeneration_clears_every_interface_before_generating_any(
    workspace: WorkspaceOrmInterfaces, checkout: Path
):
    workspace.regenerate()

    records = generate_orm.read_generation_log(checkout)
    assert records[0].generated_packages == []
    assert records[1].generated_packages == [PACKAGE_NAMES[0]]


def test_regeneration_fills_every_interface(workspace: WorkspaceOrmInterfaces):
    workspace.regenerate()

    assert workspace.are_generated
    for interface in workspace.interfaces:
        assert interface.path.read_text(
            encoding="utf-8"
        ) == generate_orm.interface_content(interface.package_name)


def test_regeneration_lets_git_ignore_the_generated_content(
    workspace: WorkspaceOrmInterfaces, checkout: Path
):
    workspace.regenerate()

    assert interfaces_git_ignores_changes_of(checkout) == {
        str(interface.path.relative_to(checkout)) for interface in workspace.interfaces
    }


# %% incomplete checkouts


def test_missing_generator_names_its_package(workspace: WorkspaceOrmInterfaces):
    incomplete = workspace.interfaces[-1]
    incomplete.generator.unlink()

    with pytest.raises(MissingOrmGeneratorError) as error:
        workspace.regenerate()

    assert error.value.package_name == incomplete.package_name
    assert error.value.path == incomplete.generator


def test_missing_interface_names_its_package(workspace: WorkspaceOrmInterfaces):
    incomplete = workspace.interfaces[-1]
    incomplete.path.unlink()

    with pytest.raises(MissingOrmInterfaceError) as error:
        workspace.regenerate()

    assert error.value.package_name == incomplete.package_name
    assert error.value.path == incomplete.path


# %% this repository


def test_every_workspace_package_has_a_generator_and_an_interface():
    incomplete = [
        interface.package_name
        for interface in WORKSPACE_ORM_INTERFACES.interfaces
        if not (interface.generator.exists() and interface.path.exists())
    ]
    assert incomplete == []
