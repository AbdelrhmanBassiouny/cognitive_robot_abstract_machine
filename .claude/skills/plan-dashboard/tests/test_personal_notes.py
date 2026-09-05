"""
Tests for reading plan data off the personal-notes branch.

The remote is a scratch bare repository seeded with a notes branch, so no network access
or real notes branch is involved. Two contract tests pin what is written here against
``resolve-personal-notes-config.sh``, the shell definition of the same layout and the
same precedence, since neither can read the other at runtime.
"""

import re
import subprocess
from pathlib import Path

import pytest

from personal_notes import (
    NOTES_BRANCH_SETTING,
    NOTES_REMOTE_SETTING,
    PLANS_DIRECTORY,
    PersonalNotesBranch,
    PersonalNotesUnavailableError,
    PlanDocument,
    PlanFileMissingError,
)
from scratch_repositories import PlanFiles

CONFIGURATION_SCRIPT = (
    Path(__file__).parent.parent.parent.parent
    / "hooks"
    / "resolve-personal-notes-config.sh"
)

SHELL_PLAN_PATH_VARIABLES = (
    "PLANS_DIR",
    "PLAN_MANIFEST_FILENAME",
    "PLAN_ROADMAP_FILENAME",
)
"""
The shell variables carrying the same three paths this module names, in the order
:func:`test_the_plan_paths_match_the_shell_configuration` prints and asserts them.
"""

SHELL_SETTING_VARIABLES = (
    (NOTES_REMOTE_SETTING, "NOTES_REMOTE"),
    (NOTES_BRANCH_SETTING, "NOTES_BRANCH"),
)
"""
Each setting beside the shell variable resolved through the same precedence.
"""

MANIFEST_TEXT = "schema_version: 1\nid: a-plan\n"
ROADMAP_TEXT = "# A plan\n"

FIRST_PLAN_ID = "alpha-plan"
SECOND_PLAN_ID = "beta-plan"
GENERATED_SIBLING_DIRECTORY = "_generated"
GENERATED_SIBLING_FILE = "branch-index.tsv"
ABSENT_PLAN_ID = "no-such-plan"
ABSENT_DOCUMENT = "absent.md"


@pytest.fixture
def two_plans() -> dict:
    """
    Two plans to seed a scratch notes branch with, deliberately out of sorted order.

    :return: The plans, keyed by identifier.
    """
    files = PlanFiles(manifest=MANIFEST_TEXT, roadmap=ROADMAP_TEXT)
    return {SECOND_PLAN_ID: files, FIRST_PLAN_ID: files}


@pytest.fixture
def fetched_notes(notes_clone, two_plans) -> PersonalNotesBranch:
    """
    The notes branch of a scratch clone holding those two plans, already fetched.

    :param notes_clone: The scratch notes remote.
    :param two_plans: The plans to seed.
    :return: The fetched branch.
    """
    notes = PersonalNotesBranch.resolve(notes_clone.seed(two_plans))
    notes.fetch()
    return notes


# %% resolving where the branch is


def test_resolve_falls_back_to_the_defaults(tmp_path: Path, scratch_git):
    """
    A clone that configures nothing is read at the zero-config remote and branch.
    """
    scratch_git.in_directory(tmp_path).run("init", "--quiet")

    notes = PersonalNotesBranch.resolve(tmp_path)

    assert notes.remote == NOTES_REMOTE_SETTING.default
    assert notes.branch == NOTES_BRANCH_SETTING.default


def test_resolve_prefers_the_environment_variable_over_the_default(
    tmp_path: Path, scratch_git, monkeypatch
):
    """
    An environment variable overrides the default when git config sets nothing.
    """
    scratch_git.in_directory(tmp_path).run("init", "--quiet")
    monkeypatch.setenv(NOTES_BRANCH_SETTING.environment_variable, "notes/elsewhere")

    assert PersonalNotesBranch.resolve(tmp_path).branch == "notes/elsewhere"


def test_resolve_prefers_git_config_over_the_environment_variable(
    tmp_path: Path, scratch_git, monkeypatch
):
    """
    Repository git config wins over the environment variable.
    """
    git = scratch_git.in_directory(tmp_path)
    git.run("init", "--quiet")
    git.run("config", NOTES_BRANCH_SETTING.git_config_key, "notes/from-config")
    monkeypatch.setenv(NOTES_BRANCH_SETTING.environment_variable, "notes/from-variable")

    assert PersonalNotesBranch.resolve(tmp_path).branch == "notes/from-config"


def test_an_unfetchable_branch_is_an_error(tmp_path: Path, scratch_git):
    """
    A clone whose remote serves no notes branch has no plan data to build from.
    """
    scratch_git.in_directory(tmp_path).run("init", "--quiet")

    with pytest.raises(PersonalNotesUnavailableError) as raised:
        PersonalNotesBranch.resolve(tmp_path).fetch()

    assert raised.value.branch == NOTES_BRANCH_SETTING.default
    assert raised.value.remote == NOTES_REMOTE_SETTING.default


# %% reading the branch


def test_plan_identifiers_lists_every_plan_sorted(fetched_notes: PersonalNotesBranch):
    """
    Plan discovery is by manifest, in a stable order rather than the branch's own.
    """
    assert fetched_notes.plan_identifiers() == [FIRST_PLAN_ID, SECOND_PLAN_ID]


def test_plan_identifiers_ignores_a_directory_without_a_manifest(
    notes_clone, two_plans
):
    """The generated siblings under the plans directory are not plans - only a
    directory holding a manifest is."""
    clone = notes_clone.seed(two_plans)
    generated = notes_clone.checkout / PLANS_DIRECTORY / GENERATED_SIBLING_DIRECTORY
    generated.mkdir(parents=True)
    (generated / GENERATED_SIBLING_FILE).write_text("")
    checkout_git = notes_clone.git.in_directory(notes_clone.checkout)
    checkout_git.run("add", ".")
    checkout_git.run("commit", "--quiet", "--message", "add a generated sibling")
    checkout_git.run(
        "push", "--quiet", str(notes_clone.remote), NOTES_BRANCH_SETTING.default
    )

    notes = PersonalNotesBranch.resolve(clone)
    notes.fetch()

    assert notes.plan_identifiers() == [FIRST_PLAN_ID, SECOND_PLAN_ID]


def test_plan_documents_are_read_back_verbatim(fetched_notes: PersonalNotesBranch):
    """
    A plan's manifest and roadmap come back exactly as they were committed.
    """
    assert (
        fetched_notes.plan_document(FIRST_PLAN_ID, PlanDocument.MANIFEST)
        == MANIFEST_TEXT
    )
    assert (
        fetched_notes.plan_document(FIRST_PLAN_ID, PlanDocument.ROADMAP) == ROADMAP_TEXT
    )


def test_reading_an_absent_path_reports_nothing_rather_than_failing(
    fetched_notes: PersonalNotesBranch,
):
    """
    A path the branch does not carry is an ordinary outcome of a read.
    """
    assert (
        fetched_notes.read(f"{PLANS_DIRECTORY}/{FIRST_PLAN_ID}/{ABSENT_DOCUMENT}")
        is None
    )


def test_a_plan_missing_a_document_is_an_error(fetched_notes: PersonalNotesBranch):
    """
    A plan without a file every plan must have fails loudly, naming the path, rather
    than rendering a page from a silently empty document.
    """
    with pytest.raises(PlanFileMissingError) as raised:
        fetched_notes.plan_document(ABSENT_PLAN_ID, PlanDocument.ROADMAP)

    assert raised.value.path == PlanDocument.ROADMAP.path_in(ABSENT_PLAN_ID)
    assert raised.value.branch == NOTES_BRANCH_SETTING.default


def test_a_document_names_its_path_under_its_own_plan():
    """
    Where a plan's document lives is composed once, from the plans directory and the
    document's own filename.
    """
    assert (
        PlanDocument.MANIFEST.path_in(FIRST_PLAN_ID)
        == f"{PLANS_DIRECTORY}/{FIRST_PLAN_ID}/{PlanDocument.MANIFEST}"
    )


# %% agreement with the shell configuration


def test_the_plan_paths_match_the_shell_configuration():
    """
    The plan paths here are the ones resolve-personal-notes-config.sh defines: the two
    cannot read each other at runtime, so nothing but this test keeps a rename in one
    from silently passing the other by.
    """
    printed = " ".join(f'"${{{variable}}}"' for variable in SHELL_PLAN_PATH_VARIABLES)
    reported = subprocess.run(
        [
            "bash",
            "-c",
            f'source "{CONFIGURATION_SCRIPT}"; ' f'printf "%s\\n%s\\n%s\\n" {printed}',
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()

    assert reported == [
        PLANS_DIRECTORY,
        PlanDocument.MANIFEST,
        PlanDocument.ROADMAP,
    ]


@pytest.mark.parametrize("setting, shell_variable", SHELL_SETTING_VARIABLES)
def test_each_setting_matches_the_shell_precedence(setting, shell_variable):
    """
    Each setting's config key, environment variable and default are the same three the
    shell script resolves that variable through.

    Read out of the script's text rather than by sourcing it: sourcing reports whatever
    the running clone and environment configure, which is what the precedence exists to
    vary.
    """
    script = CONFIGURATION_SCRIPT.read_text()
    configured = re.search(
        rf'^{shell_variable}="\$\(git config --get (\S+) \|\| true\)"$',
        script,
        re.MULTILINE,
    )
    precedence = re.search(
        rf'^{shell_variable}="\$\{{{shell_variable}:-\$\{{(\w+):-([^}}]+)\}}\}}"$',
        script,
        re.MULTILINE,
    )

    assert configured.group(1) == setting.git_config_key
    assert precedence.group(1) == setting.environment_variable
    assert precedence.group(2) == setting.default
