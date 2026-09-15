"""
Integration tests for setup-stacked-prs.sh: its argument contract, the setup it performs
in each install mode, and its safety behaviour around labels it hasn't been asked to
create.

Runs against a scratch project root whose upstream, notes and (for the fork-overlay
tests) fork remotes are local bare repositories, with ``gh`` and ``curl`` stubbed on
``PATH`` - so a full setup completes with no network access and no credentials.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

from github_api import GitHubRemoteUrl, RepositoryLabel
from scratch_repository import (
    HOOKS_SOURCE_DIRECTORY,
    NOTES_PATH,
    ScratchRepository,
    initialize_bare_repository,
)
from stub_executables import StubbedExecutable, StubExecutableDirectory
from tooling_files import (
    MAINTENANCE_SKILL_INVOCATION,
    HookScript,
    ProjectFile,
    RoutinePromptPlaceholder,
    StackToolingFile,
)

from test_check_stack_setup_sh import (
    UPSTREAM_BASE,
    UPSTREAM_REPOSITORY,
    install_stack_tooling,
    repository_url,
)

STACK_LABELS = (
    RepositoryLabel.IN_REVIEW,
    RepositoryLabel.REBASE,
    RepositoryLabel.NEEDS_RESOLUTION,
    RepositoryLabel.PROMOTION_LINK_SENT,
)
"""
The labels the stacked-pull-request workflow itself reads and writes - the subset of
:class:`RepositoryLabel` stack.toml names, rather than every label the tooling applies.
"""

CREATE_LABELS_FLAG = "--create-labels"
"""
What a run is re-invoked with to have the labels it reported missing created.
"""

STACK_BOARD_REPOSITORY_CONVENTION = "stack-board"
"""
The name the setup run suggests for the repository publishing the board.
"""

OVERLAY_BRANCH_DECLARATION_PATTERN = re.compile(
    r'^DEFAULT_OVERLAY_BRANCH="(?P<branch>[^"]+)"', re.MULTILINE
)
"""
How setup-stacked-prs.sh declares the branch a fork-overlay install writes to by
default.
"""

OVERLAY_BRANCH = OVERLAY_BRANCH_DECLARATION_PATTERN.search(
    (HOOKS_SOURCE_DIRECTORY / HookScript.SETUP_STACKED_PRS.value).read_text()
)["branch"]
"""
That branch, read from the script rather than restated - so these tests assert against
the default the run under test actually used.
"""

STUB_LOGIN = "stub-user"
"""
The login the stubbed GitHub reports, which the fork below is owned by so the ownership
check has something real to agree with.
"""

FORK_REPOSITORY = f"{STUB_LOGIN}/octo-repo"
"""
A fork that login owns.
"""

FORK_URL = GitHubRemoteUrl.HTTPS_WITH_SUFFIX.for_repository(FORK_REPOSITORY)
"""
How ``--fork`` is given that repository: a URL rather than an ``owner/name``, since both
spellings have to work and this is the one a contributor copies out of GitHub.
"""

UNOWNED_FORK_REPOSITORY = "someone-else/octo-repo"
"""
A repository :data:`STUB_LOGIN` does not own, which the ownership check must refuse.
"""


def assert_remote_points_at_the_fork(repository: ScratchRepository, remote_name: str):
    """
    Assert a remote resolves to the fork repository.

    Compares the repository path rather than the whole URL: a clone may carry
    ``url.<base>.insteadOf`` rewriting (a Claude Code cloud session's does, through its
    git proxy), which ``git remote get-url`` applies - so the exact string git stores is
    the environment's business, while which repository it names is the script's.

    :param repository: The repository whose remotes to inspect.
    :param remote_name: The remote that should point at the fork.
    """
    url = repository.run_git("remote", "get-url", remote_name).stdout.strip()
    assert url.endswith(f"{FORK_REPOSITORY}.git") or url.endswith(FORK_REPOSITORY), url


# %% the scratch layout


@pytest.fixture
def upstream_remote(tmp_path: Path) -> Path:
    """
    A bare repository standing in for the upstream review remote.

    Created at a path naming a repository, and passed as a ``file://`` URL, because
    ``--upstream`` has to say *which repository* the upstream is - a bare local path
    names no owner, which is exactly what github-api.sh refuses to attribute to an
    account.

    :param tmp_path: pytest's per-test temporary directory.
    :return: The bare repository's path.
    """
    return repository_url(tmp_path, UPSTREAM_REPOSITORY)[0]


@pytest.fixture
def setup_repository(
    scratch_repository: ScratchRepository, upstream_remote: Path
) -> ScratchRepository:
    """
    A scratch repository carrying the tooling but with none of the setup done: no
    remotes, no personal override, and a board that nothing ignores yet.

    :param scratch_repository: The initialized scratch repository and notes remote.
    :param upstream_remote: The bare repository standing in for the upstream.
    :return: The same repository, ready for a setup run.
    """
    scratch_repository.install_hook_scripts(HookScript.SETUP_STACKED_PRS)
    install_stack_tooling(scratch_repository)
    scratch_repository.write(
        ProjectFile.GIT_IGNORE,
        f"{ProjectFile.CLAUDE_LOCAL_MD}\n{ProjectFile.STACK_BOARD}\n",
    )
    scratch_repository.commit_everything("initial commit")
    scratch_repository.run_git(
        "push", "--quiet", f"file://{upstream_remote}", f"HEAD:{UPSTREAM_BASE}"
    )
    scratch_repository.publish_notes_branch({NOTES_PATH: "notes\n"})
    scratch_repository.resolve_notes_remote_to()
    return scratch_repository


def run_setup(
    repository: ScratchRepository,
    stub_executables: StubExecutableDirectory,
    *arguments: str,
    **stub_controls: str,
) -> subprocess.CompletedProcess[str]:
    """
    Run the scratch layout's setup-stacked-prs.sh against the stubbed GitHub.

    :param repository: A fixture-built scratch repository.
    :param stub_executables: The stub directory to run against.
    :param arguments: The arguments to pass to the script.
    :param stub_controls:``STUB_*`` variables declaring what the stubbed GitHub reports.
    :return: The finished subprocess.
    """
    stub_executables.install(StubbedExecutable.GH)
    return subprocess.run(
        [
            "bash",
            str(repository.hook_script_path(HookScript.SETUP_STACKED_PRS)),
            *arguments,
        ],
        cwd=repository.project_root,
        capture_output=True,
        text=True,
        env=stub_executables.subprocess_environment(
            STUB_GH_LOGIN=STUB_LOGIN, **stub_controls
        ),
    )


def native_arguments(upstream_remote: Path) -> tuple[str, ...]:
    """
    The arguments a plain native-mode run takes.

    :param upstream_remote: The upstream the run should point at.
    :return: The argument tuple.
    """
    return ("--fork", FORK_URL, "--upstream", f"file://{upstream_remote}")


# %% the argument contract


@pytest.mark.parametrize("omitted_argument", ["--fork", "--upstream"])
def test_requires_the_remotes_it_must_not_guess(
    setup_repository: ScratchRepository,
    stub_executables: StubExecutableDirectory,
    upstream_remote: Path,
    omitted_argument: str,
):
    complete = {"--fork": FORK_URL, "--upstream": f"file://{upstream_remote}"}
    arguments = [
        argument
        for name, value in complete.items()
        if name != omitted_argument
        for argument in (name, value)
    ]

    result = run_setup(setup_repository, stub_executables, *arguments)

    assert result.returncode != 0
    assert omitted_argument in result.stderr


def test_rejects_an_unrecognized_argument(
    setup_repository: ScratchRepository,
    stub_executables: StubExecutableDirectory,
    upstream_remote: Path,
):
    result = run_setup(
        setup_repository,
        stub_executables,
        *native_arguments(upstream_remote),
        "--nonsense",
    )

    assert result.returncode != 0
    assert "--nonsense" in result.stderr


def test_rejects_an_unknown_install_mode(
    setup_repository: ScratchRepository,
    stub_executables: StubExecutableDirectory,
    upstream_remote: Path,
):
    result = run_setup(
        setup_repository,
        stub_executables,
        *native_arguments(upstream_remote),
        "--mode",
        "sideways",
    )

    assert result.returncode != 0
    assert "sideways" in result.stderr


# %% a native run


def test_a_native_run_leaves_the_clone_fully_set_up(
    setup_repository: ScratchRepository,
    stub_executables: StubExecutableDirectory,
    upstream_remote: Path,
):
    result = run_setup(
        setup_repository, stub_executables, *native_arguments(upstream_remote)
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert_remote_points_at_the_fork(setup_repository, "origin")
    assert (
        setup_repository.run_git("remote", "get-url", "cram2").stdout.strip()
        == f"file://{upstream_remote}"
    )


def test_a_second_run_changes_nothing(
    setup_repository: ScratchRepository,
    stub_executables: StubExecutableDirectory,
    upstream_remote: Path,
):
    run_setup(setup_repository, stub_executables, *native_arguments(upstream_remote))
    notes_commit_after_first_run = setup_repository.notes_branch_commit()

    result = run_setup(
        setup_repository, stub_executables, *native_arguments(upstream_remote)
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert setup_repository.notes_branch_commit() == notes_commit_after_first_run


def test_prints_the_routine_prompt_with_the_repositories_substituted(
    setup_repository: ScratchRepository,
    stub_executables: StubExecutableDirectory,
    upstream_remote: Path,
):
    """
    An unsubstituted placeholder reaching a registered prompt becomes an instruction a
    live run cannot resolve, so the substitution is the part worth pinning.
    """
    result = run_setup(
        setup_repository, stub_executables, *native_arguments(upstream_remote)
    )

    for placeholder in RoutinePromptPlaceholder:
        assert placeholder not in result.stdout
    assert (
        f"{MAINTENANCE_SKILL_INVOCATION} fork={FORK_REPOSITORY} "
        f"upstream={UPSTREAM_REPOSITORY} --non-interactive" in result.stdout
    )


def test_names_the_stack_board_bootstrap_without_touching_another_repository(
    setup_repository: ScratchRepository,
    stub_executables: StubExecutableDirectory,
    upstream_remote: Path,
    tmp_path: Path,
):
    call_log = tmp_path / "gh-calls.log"

    result = run_setup(
        setup_repository,
        stub_executables,
        *native_arguments(upstream_remote),
        STUB_GH_CALL_LOG=str(call_log),
    )

    assert STACK_BOARD_REPOSITORY_CONVENTION in result.stdout
    assert "POST" not in call_log.read_text()


# %% the fork's ownership


def test_refuses_a_fork_owned_by_somebody_else(
    setup_repository: ScratchRepository,
    stub_executables: StubExecutableDirectory,
    upstream_remote: Path,
):
    result = run_setup(
        setup_repository,
        stub_executables,
        "--fork",
        GitHubRemoteUrl.HTTPS_WITH_SUFFIX.for_repository(UNOWNED_FORK_REPOSITORY),
        "--upstream",
        f"file://{upstream_remote}",
    )

    assert result.returncode != 0
    assert UNOWNED_FORK_REPOSITORY.split("/")[0] in result.stderr
    assert STUB_LOGIN in result.stderr


# %% the labels the workflow reads and writes


def test_reports_missing_labels_without_creating_them_unasked(
    setup_repository: ScratchRepository,
    stub_executables: StubExecutableDirectory,
    upstream_remote: Path,
    tmp_path: Path,
):
    call_log = tmp_path / "gh-calls.log"

    result = run_setup(
        setup_repository,
        stub_executables,
        *native_arguments(upstream_remote),
        STUB_GH_MISSING_LABELS=(
            f"{RepositoryLabel.REBASE} {RepositoryLabel.PROMOTION_LINK_SENT}"
        ),
        STUB_GH_CALL_LOG=str(call_log),
    )

    assert RepositoryLabel.REBASE in result.stdout
    assert RepositoryLabel.PROMOTION_LINK_SENT in result.stdout
    assert CREATE_LABELS_FLAG in result.stdout
    assert "POST" not in call_log.read_text()


def test_creates_only_the_missing_labels_when_asked(
    setup_repository: ScratchRepository,
    stub_executables: StubExecutableDirectory,
    upstream_remote: Path,
    tmp_path: Path,
):
    call_log = tmp_path / "gh-calls.log"

    run_setup(
        setup_repository,
        stub_executables,
        *native_arguments(upstream_remote),
        CREATE_LABELS_FLAG,
        STUB_GH_MISSING_LABELS=RepositoryLabel.REBASE,
        STUB_GH_CALL_LOG=str(call_log),
    )

    created = [line for line in call_log.read_text().splitlines() if "POST" in line]
    assert len(created) == 1
    assert "name=rebase" in created[0]


def test_reports_a_label_creation_the_token_is_not_allowed_to_make(
    setup_repository: ScratchRepository,
    stub_executables: StubExecutableDirectory,
    upstream_remote: Path,
):
    result = run_setup(
        setup_repository,
        stub_executables,
        *native_arguments(upstream_remote),
        CREATE_LABELS_FLAG,
        STUB_GH_MISSING_LABELS=RepositoryLabel.REBASE,
        STUB_GH_CREATE_LABEL_FAILS="1",
    )

    assert RepositoryLabel.REBASE in result.stderr


def test_checks_every_label_the_configuration_names(
    setup_repository: ScratchRepository,
    stub_executables: StubExecutableDirectory,
    upstream_remote: Path,
    tmp_path: Path,
):
    call_log = tmp_path / "gh-calls.log"

    run_setup(
        setup_repository,
        stub_executables,
        *native_arguments(upstream_remote),
        STUB_GH_CALL_LOG=str(call_log),
    )

    checked = call_log.read_text()
    for label in STACK_LABELS:
        assert f"labels/{label}" in checked


# %% the personal override


def test_writes_only_the_settings_that_differ_from_the_committed_defaults(
    setup_repository: ScratchRepository,
    stub_executables: StubExecutableDirectory,
    upstream_remote: Path,
    tmp_path: Path,
):
    run_setup(
        setup_repository,
        stub_executables,
        "--fork",
        FORK_URL,
        "--upstream",
        f"file://{upstream_remote}",
        "--personal-config",
        "fork_remote=my-own-fork",
        "--personal-config",
        "upstream_remote=cram2",
    )

    checkout = setup_repository.clone_notes_branch(tmp_path / "notes")
    written = (checkout / ProjectFile.PERSONAL_STACK_CONFIGURATION).read_text()
    assert 'fork_remote = "my-own-fork"' in written
    assert "upstream_remote" not in written


def test_adds_the_remote_under_the_name_the_override_gives_it(
    setup_repository: ScratchRepository,
    stub_executables: StubExecutableDirectory,
    upstream_remote: Path,
):
    result = run_setup(
        setup_repository,
        stub_executables,
        "--fork",
        FORK_URL,
        "--upstream",
        f"file://{upstream_remote}",
        "--personal-config",
        "fork_remote=my-own-fork",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert_remote_points_at_the_fork(setup_repository, "my-own-fork")


def test_rejects_a_personal_setting_the_configuration_does_not_have(
    setup_repository: ScratchRepository,
    stub_executables: StubExecutableDirectory,
    upstream_remote: Path,
):
    result = run_setup(
        setup_repository,
        stub_executables,
        *native_arguments(upstream_remote),
        "--personal-config",
        "favourite_colour=blue",
    )

    assert result.returncode != 0
    assert "favourite_colour" in result.stderr


# %% the fork-overlay install mode


@pytest.fixture
def overlay_repository(
    setup_repository: ScratchRepository, tmp_path: Path
) -> ScratchRepository:
    """
    The same scratch layout, but with a pushable local bare repository as the fork - so
    the overlay branch can actually be written and read back.

    Created at a path naming the fork, so the ownership check agrees with the login the
    stubbed GitHub reports.

    :param setup_repository: The scratch repository carrying the tooling.
    :param tmp_path: pytest's per-test temporary directory.
    :return: The same repository.
    """
    repository_url(tmp_path, FORK_REPOSITORY)
    return setup_repository


def overlay_fork_path(tmp_path: Path) -> Path:
    """
    :param tmp_path: pytest's per-test temporary directory.
    :return: The bare repository standing in for the fork.
    """
    return tmp_path / f"{FORK_REPOSITORY}.git"


def test_fork_overlay_installs_the_canonical_files_on_the_overlay_branch(
    overlay_repository: ScratchRepository,
    stub_executables: StubExecutableDirectory,
    upstream_remote: Path,
    tmp_path: Path,
):
    result = run_setup(
        overlay_repository,
        stub_executables,
        "--fork",
        f"file://{overlay_fork_path(tmp_path)}",
        "--upstream",
        f"file://{upstream_remote}",
        "--mode",
        "fork-overlay",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    checkout = overlay_repository.clone_branch(
        overlay_fork_path(tmp_path), OVERLAY_BRANCH, tmp_path / "overlay"
    )
    assert (checkout / StackToolingFile.STACK).is_file()
    assert (checkout / HookScript.CHECK_STACK_SETUP.path).is_file()
    assert (
        checkout / StackToolingFile.MAINTENANCE_SKILL
    ).is_file(), "an overlay carrying no instructions installs tooling nobody can run"


def test_re_running_fork_overlay_is_the_updater(
    overlay_repository: ScratchRepository,
    stub_executables: StubExecutableDirectory,
    upstream_remote: Path,
    tmp_path: Path,
):
    arguments = (
        "--fork",
        f"file://{overlay_fork_path(tmp_path)}",
        "--upstream",
        f"file://{upstream_remote}",
        "--mode",
        "fork-overlay",
    )
    run_setup(overlay_repository, stub_executables, *arguments)
    commit_after_first_run = overlay_repository.remote_branch_commit(
        overlay_fork_path(tmp_path), OVERLAY_BRANCH
    )

    overlay_repository.write(
        ".claude/skills/stacked-pr-maintenance/SKILL.md", "the doctrine, revised\n"
    )
    run_setup(overlay_repository, stub_executables, *arguments)

    checkout = overlay_repository.clone_branch(
        overlay_fork_path(tmp_path), OVERLAY_BRANCH, tmp_path / "overlay"
    )
    assert (
        checkout / ".claude" / "skills" / "stacked-pr-maintenance" / "SKILL.md"
    ).read_text() == "the doctrine, revised\n"
    assert (
        overlay_repository.remote_branch_commit(
            overlay_fork_path(tmp_path), OVERLAY_BRANCH
        )
        != commit_after_first_run
    )


def test_a_native_run_writes_no_overlay_branch(
    overlay_repository: ScratchRepository,
    stub_executables: StubExecutableDirectory,
    upstream_remote: Path,
    tmp_path: Path,
):
    run_setup(
        overlay_repository,
        stub_executables,
        "--fork",
        f"file://{overlay_fork_path(tmp_path)}",
        "--upstream",
        f"file://{upstream_remote}",
    )

    assert (
        overlay_repository.remote_branch_commit(
            overlay_fork_path(tmp_path), OVERLAY_BRANCH
        )
        is None
    )
