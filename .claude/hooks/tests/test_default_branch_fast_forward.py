"""
Integration tests for fast-forward-default-branch.sh, the session-start step that keeps
the base every session starts from level with the upstream repository the fork tracks.

The defect it exists for: a fork's default branch drifts behind its upstream, every
session is cloned from it, and the whole session plans and implements against a base
that is already stale.

Run against a scratch project root whose fork and upstream are local bare repositories
reachable at their real GitHub URLs (see
:meth:`ScratchRepository.stand_in_for_github_repository`), so the hook performs real
fetches and pushes with no network access and no test-only seam in the script.
"""

from __future__ import annotations

import subprocess

import pytest

from scratch_repository import (
    NOTES_BRANCH,
    PERSONAL_GIT_IDENTITY_PATH,
    SCRATCH_IDENTITY,
    ScratchRepository,
    WORK_BRANCH,
)
from session_start_summary import SummaryMessage, summary_message, summary_value

FORK_REPOSITORY = "a-fork-owner/a-project"

UPSTREAM_REPOSITORY = "an-upstream-owner/a-project"

DEFAULT_BRANCH = "main"

FORK_REMOTE = "origin"

STACK_CONFIGURATION_PATH = ".claude/stack/stack.toml"

UPSTREAM_REMOTE = "an-upstream-remote"

STACK_CONFIGURATION = f"""\
fork_remote = "{FORK_REMOTE}"
upstream_repository = "{UPSTREAM_REPOSITORY}"
upstream_remote = "{UPSTREAM_REMOTE}"
upstream_base = "{DEFAULT_BRANCH}"
"""

HOOK_SCRIPT = "fast-forward-default-branch.sh"

SUMMARY_LABEL = "default branch"

FOLLOW_UP_ROW_INDENT = "    "

COMMITS_THE_UPSTREAM_IS_AHEAD = 3

SHARED_FILE = "a-source-file.txt"

NOTES_PATH = ".claude/personal/cram-notes.md"


def reported_outcome(result: subprocess.CompletedProcess[str]) -> str:
    """
    Read the outcome the hook reports, which session-start.sh prints as its summary
    line's value.

    :param result: The finished hook process.
    :return: The first line of its output.
    """
    return result.stdout.splitlines()[0]


def follow_up_rows(result: subprocess.CompletedProcess[str]) -> list[str]:
    """
    Read the indented rows the hook prints under its outcome, naming what is left for
    the session to do.

    :param result: The finished hook process.
    :return: The rows, with their indent stripped.
    """
    return [
        row.removeprefix(FOLLOW_UP_ROW_INDENT) for row in result.stdout.splitlines()[1:]
    ]


def fork_pushed_row() -> str:
    """
    :return: The row reporting that the fork's copy of the default branch was behind and
        has been pushed.
    """
    return summary_message(SummaryMessage.FORK_PUSHED, FORK_REMOTE)


def current_branch_behind_row(commit_count: int) -> str:
    """
    :param commit_count: How far behind the default branch the checked-out branch is.
    :return: The row reporting it.
    """
    return summary_message(
        SummaryMessage.CURRENT_BRANCH_BEHIND, DEFAULT_BRANCH, str(commit_count)
    )


# %% the scratch layout


class ForkedScratchRepository:
    """
    A scratch clone of a fork, its upstream, and the operations that move the three
    copies of the default branch apart.

    Wraps rather than extends :class:`ScratchRepository` so the plain scratch repository
    stays what every other hook test builds on, with no fork-specific setup in it.
    """

    def __init__(self, repository: ScratchRepository) -> None:
        """
        Lay out a clone whose default branch, fork and upstream all sit at one commit,
        with a published notes branch and an ordinary work branch checked out.

        :param repository: The initialized scratch repository and notes remote.
        """
        self.repository = repository
        repository.install_hook_scripts(
            "resolve-personal-notes-config.sh",
            "session-start-messages.sh",
            HOOK_SCRIPT,
        )
        repository.install_stack_tooling(STACK_CONFIGURATION)
        repository.write(SHARED_FILE, "the shared base\n")
        repository.run_git("checkout", "--quiet", "-b", DEFAULT_BRANCH)
        repository.commit_everything("the shared base")
        repository.resolve_notes_remote_to()

        self.fork = repository.stand_in_for_github_repository(FORK_REPOSITORY)
        repository.add_remote(FORK_REMOTE, self.fork)
        self.upstream = repository.stand_in_for_github_repository(UPSTREAM_REPOSITORY)
        repository.reach_by_github_url(self.upstream)
        repository.run_git("push", "--quiet", FORK_REMOTE, DEFAULT_BRANCH)
        repository.run_git("push", "--quiet", self.upstream.url, DEFAULT_BRANCH)
        repository.publish_notes_branch(
            {
                NOTES_PATH: "personal notes\n",
                PERSONAL_GIT_IDENTITY_PATH: SCRATCH_IDENTITY.as_git_config_file(),
            }
        )

    @property
    def shared_base(self) -> str:
        """
        :return: The commit all three copies of the default branch start at.
        """
        return self.fork.branch_tip(DEFAULT_BRANCH)

    def advance_upstream(self, commit_count: int) -> str:
        """
        Add commits to the upstream's default branch that neither this clone nor the
        fork has, leaving both of them where they were.

        Each commit rewrites the file the clone already carries, so a working tree with
        uncommitted changes to it is one git will refuse to fast-forward over.

        :param commit_count: How many commits to add.
        :return: The upstream's new tip.
        """
        starting_point = self.local_default_branch_tip()
        self.repository.run_git("checkout", "--quiet", DEFAULT_BRANCH)
        for index in range(commit_count):
            self.repository.write(SHARED_FILE, f"an upstream revision ({index})\n")
            self.repository.commit_everything(f"an upstream commit ({index})")
        tip = self.local_default_branch_tip()
        self.repository.run_git("push", "--quiet", self.upstream.url, DEFAULT_BRANCH)
        self.repository.run_git("checkout", "--quiet", WORK_BRANCH)
        self.repository.run_git(
            "update-ref", f"refs/heads/{DEFAULT_BRANCH}", starting_point
        )
        return tip

    def advance_local_default_branch(self) -> str:
        """
        Commit onto this clone's default branch alone, the one state a fast-forward
        cannot reconcile.

        :return: The commit the default branch now points at.
        """
        self.repository.run_git("checkout", "--quiet", DEFAULT_BRANCH)
        self.repository.write("a-local-only-change.txt", "only here\n")
        self.repository.commit_everything("a commit the upstream does not have")
        self.repository.run_git("checkout", "--quiet", WORK_BRANCH)
        return self.local_default_branch_tip()

    def set_local_default_branch_to(self, commit: str) -> None:
        """
        Move this clone's default branch without touching the fork's, the state an
        earlier session's refused push leaves behind.

        :param commit: The commit to move it to.
        """
        self.repository.run_git("update-ref", f"refs/heads/{DEFAULT_BRANCH}", commit)

    def check_out_default_branch(self) -> None:
        """
        Put the working tree on the default branch, as a session doing trunk work is.
        """
        self.repository.run_git("checkout", "--quiet", DEFAULT_BRANCH)

    def local_default_branch_tip(self) -> str:
        """
        :return: The commit this clone's default branch points at.
        """
        return self.repository.run_git(
            "rev-parse", f"refs/heads/{DEFAULT_BRANCH}"
        ).stdout.strip()

    def checked_out_commit(self) -> str:
        """
        :return: The commit the working tree is on.
        """
        return self.repository.run_git("rev-parse", "HEAD").stdout.strip()

    def make_the_upstream_unreachable(self) -> None:
        """
        Cut off the upstream's GitHub URL, leaving a named upstream that cannot be
        fetched.
        """
        self.repository.stop_reaching_by_github_url(self.upstream)

    def reach_the_upstream_only_through_its_remote(self) -> None:
        """
        Register the upstream as a remote and cut off its GitHub URL, so the only route
        left to it is the remote - the clone of a contributor who added it.
        """
        self.repository.add_remote(UPSTREAM_REMOTE, self.upstream)
        self.repository.stop_reaching_by_github_url(self.upstream)

    def local_default_branch_tip(self) -> str:
        """
        :return: The commit this clone's default branch points at.
        """
        return self.repository.run_git(
            "rev-parse", f"refs/heads/{DEFAULT_BRANCH}"
        ).stdout.strip()

    def checked_out_commit(self) -> str:
        """
        :return: The commit the working tree is on.
        """
        return self.repository.run_git("rev-parse", "HEAD").stdout.strip()

    def make_the_upstream_unreachable(self) -> None:
        """
        Cut off the upstream's GitHub URL, leaving a named upstream that cannot be
        fetched.
        """
        self.repository.stop_reaching_by_github_url(self.upstream)

    def add_upstream_remote(self, commit_count: int) -> str:
        """
        Register a second copy of the upstream as a remote under the configured upstream
        remote name, ahead of the one reachable by GitHub URL.

        The two tips differ so that which of the two routes the hook took is visible in
        where the default branch lands.

        :param commit_count: How far ahead of the shared base to put it.
        :return: The registered remote's tip.
        """
        mirror = self.repository.stand_in_for_github_repository(
            f"{UPSTREAM_REPOSITORY}-mirror"
        )
        self.repository.add_remote(UPSTREAM_REMOTE, mirror)
        starting_point = self.local_default_branch_tip()
        self.repository.run_git("checkout", "--quiet", DEFAULT_BRANCH)
        for index in range(commit_count):
            self.repository.write(SHARED_FILE, f"a mirrored revision ({index})\n")
            self.repository.commit_everything(f"a mirrored commit ({index})")
        tip = self.local_default_branch_tip()
        self.repository.run_git("push", "--quiet", UPSTREAM_REMOTE, DEFAULT_BRANCH)
        self.repository.run_git("checkout", "--quiet", WORK_BRANCH)
        self.repository.run_git(
            "update-ref", f"refs/heads/{DEFAULT_BRANCH}", starting_point
        )
        return tip

    def run_hook(self) -> subprocess.CompletedProcess[str]:
        """
        :return: The finished fast-forward-default-branch.sh process.
        """
        return self.repository.run_hook_script(HOOK_SCRIPT)

    def run_session_start(self) -> subprocess.CompletedProcess[str]:
        """
        Run the whole session-start hook, for the report line it prints around this one.

        :return: The finished session-start.sh process.
        """
        self.repository.install_hook_scripts("session-start.sh")
        return self.repository.run_hook_script("session-start.sh")

    def stack_configuration_refusal(self) -> str:
        """
        Read the refusal the stacked-PR configuration reports for this clone, from the
        same command the hook resolves the upstream through.

        :return: What it printed to standard error.
        """
        result = subprocess.run(
            ["python3", ".claude/stack/stack.py", "configuration"],
            cwd=self.repository.project_root,
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0, result.stdout
        return result.stderr.strip()


@pytest.fixture
def forked_repository(scratch_repository: ScratchRepository) -> ForkedScratchRepository:
    """
    A scratch clone of a fork whose default branch, fork and upstream all match.

    :param scratch_repository: The initialized scratch repository and notes remote.
    :return: The laid-out fork.
    """
    return ForkedScratchRepository(scratch_repository)


# %% a default branch behind its upstream


def test_fast_forwards_the_default_branch_to_the_upstream_tip(
    forked_repository: ForkedScratchRepository,
):
    upstream_tip = forked_repository.advance_upstream(COMMITS_THE_UPSTREAM_IS_AHEAD)

    result = forked_repository.run_hook()

    assert result.returncode == 0, result.stderr
    assert forked_repository.local_default_branch_tip() == upstream_tip


def test_pushes_the_fast_forwarded_default_branch_to_the_fork(
    forked_repository: ForkedScratchRepository,
):
    upstream_tip = forked_repository.advance_upstream(COMMITS_THE_UPSTREAM_IS_AHEAD)

    result = forked_repository.run_hook()

    assert forked_repository.fork.branch_tip(DEFAULT_BRANCH) == upstream_tip
    assert fork_pushed_row() in follow_up_rows(result)


def test_reports_how_far_the_default_branch_was_behind(
    forked_repository: ForkedScratchRepository,
):
    forked_repository.advance_upstream(COMMITS_THE_UPSTREAM_IS_AHEAD)

    result = forked_repository.run_hook()

    assert reported_outcome(result) == summary_message(
        SummaryMessage.DEFAULT_BRANCH_FAST_FORWARDED,
        DEFAULT_BRANCH,
        str(COMMITS_THE_UPSTREAM_IS_AHEAD),
        UPSTREAM_REPOSITORY,
    )


def test_reports_how_far_the_current_branch_is_behind_the_moved_default_branch(
    forked_repository: ForkedScratchRepository,
):
    forked_repository.advance_upstream(COMMITS_THE_UPSTREAM_IS_AHEAD)

    result = forked_repository.run_hook()

    assert current_branch_behind_row(COMMITS_THE_UPSTREAM_IS_AHEAD) in follow_up_rows(
        result
    )


def test_fast_forwards_the_default_branch_while_it_is_checked_out(
    forked_repository: ForkedScratchRepository,
):
    upstream_tip = forked_repository.advance_upstream(COMMITS_THE_UPSTREAM_IS_AHEAD)
    forked_repository.check_out_default_branch()

    result = forked_repository.run_hook()

    assert result.returncode == 0, result.stderr
    assert forked_repository.checked_out_commit() == upstream_tip


def test_says_nothing_about_the_current_branch_when_it_is_the_default_branch(
    forked_repository: ForkedScratchRepository,
):
    forked_repository.advance_upstream(COMMITS_THE_UPSTREAM_IS_AHEAD)
    forked_repository.check_out_default_branch()

    result = forked_repository.run_hook()

    assert follow_up_rows(result) == [fork_pushed_row()]


# %% a default branch that needs nothing done to it


def test_reports_the_default_branch_as_current_when_nothing_has_moved(
    forked_repository: ForkedScratchRepository,
):
    result = forked_repository.run_hook()

    assert result.returncode == 0, result.stderr
    assert reported_outcome(result) == summary_message(
        SummaryMessage.DEFAULT_BRANCH_CURRENT, DEFAULT_BRANCH, UPSTREAM_REPOSITORY
    )


def test_leaves_nothing_to_do_when_nothing_has_moved(
    forked_repository: ForkedScratchRepository,
):
    result = forked_repository.run_hook()

    assert follow_up_rows(result) == []


# %% a fork left behind by an earlier session


def test_pushes_to_the_fork_when_this_clone_is_already_current(
    forked_repository: ForkedScratchRepository,
):
    upstream_tip = forked_repository.advance_upstream(COMMITS_THE_UPSTREAM_IS_AHEAD)
    forked_repository.set_local_default_branch_to(upstream_tip)

    result = forked_repository.run_hook()

    assert forked_repository.fork.branch_tip(DEFAULT_BRANCH) == upstream_tip
    assert reported_outcome(result) == summary_message(
        SummaryMessage.DEFAULT_BRANCH_CURRENT, DEFAULT_BRANCH, UPSTREAM_REPOSITORY
    )
    assert fork_pushed_row() in follow_up_rows(result)


# %% states a fast-forward must not resolve


def test_leaves_a_diverged_default_branch_alone(
    forked_repository: ForkedScratchRepository,
):
    forked_repository.advance_upstream(COMMITS_THE_UPSTREAM_IS_AHEAD)
    diverged_tip = forked_repository.advance_local_default_branch()

    result = forked_repository.run_hook()

    assert result.returncode == 0, result.stderr
    assert forked_repository.local_default_branch_tip() == diverged_tip
    assert reported_outcome(result) == summary_message(
        SummaryMessage.DEFAULT_BRANCH_DIVERGED, DEFAULT_BRANCH, UPSTREAM_REPOSITORY
    )


def test_leaves_the_fork_alone_when_the_default_branch_has_diverged(
    forked_repository: ForkedScratchRepository,
):
    shared_base = forked_repository.shared_base
    forked_repository.advance_upstream(COMMITS_THE_UPSTREAM_IS_AHEAD)
    forked_repository.advance_local_default_branch()

    forked_repository.run_hook()

    assert forked_repository.fork.branch_tip(DEFAULT_BRANCH) == shared_base


def test_leaves_a_checked_out_default_branch_alone_when_git_refuses_to_move_it(
    forked_repository: ForkedScratchRepository,
):
    shared_base = forked_repository.shared_base
    forked_repository.advance_upstream(COMMITS_THE_UPSTREAM_IS_AHEAD)
    forked_repository.check_out_default_branch()
    forked_repository.repository.write(SHARED_FILE, "work in progress\n")

    result = forked_repository.run_hook()

    assert result.returncode == 0, result.stderr
    assert forked_repository.local_default_branch_tip() == shared_base
    assert reported_outcome(result) == summary_message(
        SummaryMessage.DEFAULT_BRANCH_LOCAL_UPDATE_REFUSED,
        DEFAULT_BRANCH,
        UPSTREAM_REPOSITORY,
    )


# %% an upstream this clone cannot resolve or reach


def test_reports_an_unreachable_upstream_without_touching_the_default_branch(
    forked_repository: ForkedScratchRepository,
):
    shared_base = forked_repository.shared_base
    forked_repository.make_the_upstream_unreachable()

    result = forked_repository.run_hook()

    assert result.returncode == 0, result.stderr
    assert forked_repository.local_default_branch_tip() == shared_base
    assert reported_outcome(result) == summary_message(
        SummaryMessage.DEFAULT_BRANCH_UPSTREAM_UNREACHABLE,
        DEFAULT_BRANCH,
        UPSTREAM_REPOSITORY,
    )


def test_reports_a_clone_that_names_no_upstream_at_all(
    forked_repository: ForkedScratchRepository,
):
    (forked_repository.repository.project_root / STACK_CONFIGURATION_PATH).unlink()

    result = forked_repository.run_hook()

    assert result.returncode == 0, result.stderr
    assert reported_outcome(result) == summary_message(
        SummaryMessage.DEFAULT_BRANCH_NOT_CONFIGURED, STACK_CONFIGURATION_PATH
    )


def test_reports_a_refused_upstream_resolution_in_the_words_it_was_refused_with(
    forked_repository: ForkedScratchRepository,
):
    forked_repository.repository.run_git("remote", "remove", FORK_REMOTE)

    result = forked_repository.run_hook()

    assert result.returncode == 0, result.stderr
    assert reported_outcome(result) == summary_message(
        SummaryMessage.DEFAULT_BRANCH_UPSTREAM_UNRESOLVED,
        forked_repository.stack_configuration_refusal(),
    )


# %% the line session-start.sh prints


def test_session_start_reports_the_default_branch_it_fast_forwarded(
    forked_repository: ForkedScratchRepository,
):
    forked_repository.advance_upstream(COMMITS_THE_UPSTREAM_IS_AHEAD)

    result = forked_repository.run_session_start()

    assert result.returncode == 0, result.stderr
    assert summary_value(result.stdout, SUMMARY_LABEL) == summary_message(
        SummaryMessage.DEFAULT_BRANCH_FAST_FORWARDED,
        DEFAULT_BRANCH,
        str(COMMITS_THE_UPSTREAM_IS_AHEAD),
        UPSTREAM_REPOSITORY,
    )
    assert f"{FOLLOW_UP_ROW_INDENT}{fork_pushed_row()}" in result.stdout


def test_a_clone_that_names_no_upstream_does_not_fail_session_start(
    forked_repository: ForkedScratchRepository,
):
    (forked_repository.repository.project_root / STACK_CONFIGURATION_PATH).unlink()

    result = forked_repository.run_session_start()

    assert result.returncode == 0, result.stderr
    assert summary_value(result.stdout, SUMMARY_LABEL) == summary_message(
        SummaryMessage.DEFAULT_BRANCH_NOT_CONFIGURED, STACK_CONFIGURATION_PATH
    )


def test_fetches_from_the_upstream_remote_when_the_clone_already_has_one(
    forked_repository: ForkedScratchRepository,
):
    upstream_tip = forked_repository.advance_upstream(COMMITS_THE_UPSTREAM_IS_AHEAD)
    forked_repository.reach_the_upstream_only_through_its_remote()

    result = forked_repository.run_hook()

    assert result.returncode == 0, result.stderr
    assert forked_repository.local_default_branch_tip() == upstream_tip


def test_session_start_stamps_the_notes_branch_it_read_not_the_upstream_it_fetched(
    forked_repository: ForkedScratchRepository,
):
    """
    Catching the default branch up leaves the upstream's tip in ``FETCH_HEAD``, so the
    recheck baseline has to be read from what was recorded rather than from whichever
    fetch happened to run last.
    """
    forked_repository.advance_upstream(COMMITS_THE_UPSTREAM_IS_AHEAD)

    result = forked_repository.run_session_start()

    notes_branch_tip = forked_repository.repository.run_git(
        "rev-parse", f"refs/heads/{NOTES_BRANCH}"
    ).stdout.strip()
    assert summary_value(result.stdout, "plan state SHA").startswith(notes_branch_tip)
