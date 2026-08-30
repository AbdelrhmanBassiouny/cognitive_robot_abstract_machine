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
    PLAN_MANIFEST_FILENAME,
    PLAN_ROADMAP_FILENAME,
    PLANS_DIRECTORY,
    PersonalNotesBranch,
    PersonalNotesUnavailableError,
    PlanFileMissingError,
)

CONFIGURATION_SCRIPT = (
    Path(__file__).parent.parent.parent.parent
    / "hooks"
    / "resolve-personal-notes-config.sh"
)

MANIFEST_TEXT = "schema_version: 1\nid: a-plan\n"
ROADMAP_TEXT = "# A plan\n"


@pytest.fixture
def two_plans(plan_files) -> dict:
    """
    Two plans to seed a scratch notes branch with, deliberately out of sorted order.

    :param plan_files: The plan-files type.
    :return: The plans, keyed by identifier.
    """
    files = plan_files(manifest=MANIFEST_TEXT, roadmap=ROADMAP_TEXT)
    return {"beta-plan": files, "alpha-plan": files}


@pytest.fixture
def fetched_notes(notes_clone, two_plans) -> PersonalNotesBranch:
    """
    The notes branch of a scratch clone holding those two plans, already fetched.

    :param notes_clone: The scratch notes-branch builder.
    :param two_plans: The plans to seed.
    :return: The fetched branch.
    """
    notes = PersonalNotesBranch.resolve(notes_clone(two_plans))
    notes.fetch()
    return notes


# %% resolving where the branch is


def test_resolve_falls_back_to_the_defaults(tmp_path: Path, run_git):
    """
    A clone that configures nothing is read at the zero-config remote and branch.
    """
    run_git(tmp_path, "init", "--quiet")

    notes = PersonalNotesBranch.resolve(tmp_path)

    assert notes.remote == NOTES_REMOTE_SETTING.default
    assert notes.branch == NOTES_BRANCH_SETTING.default


def test_resolve_prefers_the_environment_variable_over_the_default(
    tmp_path: Path, run_git, monkeypatch
):
    """
    An environment variable overrides the default when git config sets nothing.
    """
    run_git(tmp_path, "init", "--quiet")
    monkeypatch.setenv(NOTES_BRANCH_SETTING.environment_variable, "notes/elsewhere")

    assert PersonalNotesBranch.resolve(tmp_path).branch == "notes/elsewhere"


def test_resolve_prefers_git_config_over_the_environment_variable(
    tmp_path: Path, run_git, monkeypatch
):
    """
    Repository git config wins over the environment variable.
    """
    run_git(tmp_path, "init", "--quiet")
    run_git(
        tmp_path, "config", NOTES_BRANCH_SETTING.git_config_key, "notes/from-config"
    )
    monkeypatch.setenv(NOTES_BRANCH_SETTING.environment_variable, "notes/from-variable")

    assert PersonalNotesBranch.resolve(tmp_path).branch == "notes/from-config"


def test_an_unfetchable_branch_is_an_error(tmp_path: Path, run_git):
    """
    A clone whose remote serves no notes branch has no plan data to build from.
    """
    run_git(tmp_path, "init", "--quiet")

    with pytest.raises(PersonalNotesUnavailableError):
        PersonalNotesBranch.resolve(tmp_path).fetch()


# %% reading the branch


def test_plan_identifiers_lists_every_plan_sorted(fetched_notes: PersonalNotesBranch):
    """
    Plan discovery is by manifest, in a stable order rather than the branch's own.
    """
    assert fetched_notes.plan_identifiers() == ["alpha-plan", "beta-plan"]


def test_plan_identifiers_ignores_a_directory_without_a_manifest(
    notes_clone, two_plans, run_git, tmp_path: Path
):
    """The generated siblings under the plans directory are not plans - only a
    directory holding a manifest is."""
    clone = notes_clone(two_plans)
    seed = tmp_path / "seed"
    generated = seed / PLANS_DIRECTORY / "_generated"
    generated.mkdir(parents=True)
    (generated / "branch-index.tsv").write_text("")
    run_git(seed, "add", ".")
    run_git(seed, "commit", "--quiet", "--message", "add a generated sibling")
    run_git(
        seed,
        "push",
        "--quiet",
        str(tmp_path / "remote.git"),
        NOTES_BRANCH_SETTING.default,
    )

    notes = PersonalNotesBranch.resolve(clone)
    notes.fetch()

    assert notes.plan_identifiers() == ["alpha-plan", "beta-plan"]


def test_plan_files_are_read_back_verbatim(fetched_notes: PersonalNotesBranch):
    """
    A plan's manifest and roadmap come back exactly as they were committed.
    """
    assert fetched_notes.plan_manifest("alpha-plan") == MANIFEST_TEXT
    assert fetched_notes.plan_roadmap("alpha-plan") == ROADMAP_TEXT


def test_reading_an_absent_path_reports_nothing_rather_than_failing(
    fetched_notes: PersonalNotesBranch,
):
    """
    A path the branch does not carry is an ordinary outcome of a read.
    """
    assert fetched_notes.read(f"{PLANS_DIRECTORY}/alpha-plan/absent.md") is None


def test_a_plan_missing_its_roadmap_is_an_error(fetched_notes: PersonalNotesBranch):
    """
    A plan without the file every plan must have fails loudly, naming the path, rather
    than rendering a page from a silently empty roadmap.
    """
    with pytest.raises(PlanFileMissingError) as raised:
        fetched_notes.plan_roadmap("no-such-plan")

    assert f"{PLANS_DIRECTORY}/no-such-plan/{PLAN_ROADMAP_FILENAME}" in str(
        raised.value
    )


# %% agreement with the shell configuration


def test_the_plan_paths_match_the_shell_configuration():
    """
    The plan paths here are the ones resolve-personal-notes-config.sh defines: the two
    cannot read each other at runtime, so nothing but this test keeps a rename in one
    from silently passing the other by.
    """
    reported = subprocess.run(
        [
            "bash",
            "-c",
            f'source "{CONFIGURATION_SCRIPT}"; '
            'printf "%s\\n%s\\n%s\\n" '
            '"${PLANS_DIR}" "${PLAN_MANIFEST_FILENAME}" "${PLAN_ROADMAP_FILENAME}"',
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()

    assert reported == [PLANS_DIRECTORY, PLAN_MANIFEST_FILENAME, PLAN_ROADMAP_FILENAME]


@pytest.mark.parametrize(
    "setting, shell_variable",
    [(NOTES_REMOTE_SETTING, "NOTES_REMOTE"), (NOTES_BRANCH_SETTING, "NOTES_BRANCH")],
)
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
