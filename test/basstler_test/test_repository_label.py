"""
The labels this tooling reads or applies: one list, held to every other place a label
name is configured or interpreted.
"""

from __future__ import annotations

import tomllib

from basstler.build_dashboard import PullRequestLabel
from basstler.locations import PackageLocation
from basstler.repository import Repository
from basstler.repository_label import RepositoryLabel

STACK_LABEL_SETTINGS = ("in_review_label", "rebase_label", "needs_resolution_label")
"""
The keys under which ``stack.toml`` lets a fork rename a label the stack workflow
applies.
"""

REPOSITORY = Repository("some-user", "some-repository")
"""
The repository a creation command is built for.
"""


def test_every_label_the_dashboard_interprets_is_one_the_tooling_offers() -> None:
    """
    Held by member name as well as value, so a label added to the dashboard and not here
    would leave a fork missing it with nothing else to notice.
    """
    offered = {label.name: label.value for label in RepositoryLabel}
    for member in PullRequestLabel:
        assert offered[member.name] == member.value


def test_every_label_stack_toml_ships_is_one_the_tooling_offers() -> None:
    """
    The shipped defaults are labels a fork is set up with; a renamed one would be
    applied by the stack workflow and never created.
    """
    shipped = tomllib.loads(PackageLocation.STACK_CONFIGURATION.value.read_text())
    for setting in STACK_LABEL_SETTINGS:
        assert shipped[setting] in set(RepositoryLabel)


def test_every_label_says_what_it_means_in_words_of_its_own() -> None:
    """
    A description is most of what creating a label ahead of time buys, so none may be
    empty and none may be another's.
    """
    purposes = [label.purpose for label in RepositoryLabel]
    assert all(purposes)
    assert len(set(purposes)) == len(RepositoryLabel)


def test_the_creation_command_names_the_repository_and_the_description() -> None:
    """
    The pasted command creates exactly this label, described, in the given repository.
    """
    for label in RepositoryLabel:
        assert label.creation_command(REPOSITORY) == (
            f"gh label create {label.value} --repo {REPOSITORY.full_name} "
            f'--description "{label.purpose}"'
        )
