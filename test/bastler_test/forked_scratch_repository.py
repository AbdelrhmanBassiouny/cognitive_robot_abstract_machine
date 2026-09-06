"""
The scratch fork, its upstream, and the operations that move their copies of the default
branch apart.

Testing a hook that catches a fork's default branch up needs three copies of that branch
that can genuinely disagree: this clone's, the fork's and the upstream's. All three are
built locally here, laid out under ``<owner>/<name>.git`` so their URLs name a
repository the way GitHub does - which is what lets tooling reading which repository a
remote points at resolve them, with no network access and no test-only seam in the hook.

Kept beside :mod:`scratch_repository` rather than in it: every other hook test builds on
that plain clone, and none of them has a fork.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from bastler.maintenance_git_commands import GitCommandRunner, GitSetting, ProposedPush
from bastler.package_layout import PACKAGE_DIRECTORY

from .constants import NOTES_BRANCH, WORK_BRANCH, PersonalNotesPath
from .scratch_repository import (
    SCRATCH_IDENTITY,
    ScratchRepository,
    initialize_bare_repository,
)

GITHUB_URL_PREFIX = "https://github.com/"
"""
The prefix of the URL a hook builds for a repository it knows only as ``owner/name``.
"""

HOOK_SCRIPT = "fast-forward-default-branch.sh"
"""
The hook under test.
"""

STACK_MODULE = "bastler.stack"
"""
The module a hook runs to resolve that repository.
"""

STACK_CONFIGURATION_PATH = f"{PACKAGE_DIRECTORY.name}/stack.toml"
"""
Where its committed defaults sit, relative to a project root.
"""

FORK_REPOSITORY = "a-fork-owner/a-project"
"""
The ``owner/name`` the scratch clone's own remote points at.
"""

UPSTREAM_REPOSITORY = "an-upstream-owner/a-project"
"""
The ``owner/name`` the fork is forked from.
"""

DEFAULT_BRANCH = "main"
"""
The branch all three copies carry, and the one the hook under test moves.
"""

FORK_REMOTE = "origin"
"""
What the scratch clone calls its fork.
"""

UPSTREAM_REMOTE = "an-upstream-remote"
"""
What it would call the upstream, whether or not it has that remote.
"""

STACK_CONFIGURATION = f"""\
fork_remote = "{FORK_REMOTE}"
upstream_repository = "{UPSTREAM_REPOSITORY}"
upstream_remote = "{UPSTREAM_REMOTE}"
upstream_base = "{DEFAULT_BRANCH}"
"""

SHARED_FILE = "a-source-file.txt"
"""
The one file every copy of the default branch carries, rewritten by each commit the
upstream gains - so a working tree with uncommitted changes to it is one git will refuse
to fast-forward over.
"""


@dataclass(frozen=True)
class GitHubRepositoryStandIn:
    """
    A bare repository standing in for a GitHub repository, named the way GitHub names
    it.

    Laid out under ``<owner>/<name>.git``, so tooling that reads which repository a
    remote points at resolves it to :attr:`repository` from the local URL alone; a hook
    that instead builds the repository's GitHub URL reaches it through
    :meth:`ForkedScratchRepository.reach_by_github_url`.
    """

    repository: str
    """
    The ``owner/name`` this stand-in answers for.
    """

    path: Path
    """
    The bare repository itself.
    """

    @classmethod
    def created_beside(
        cls, project_root: Path, repository: str
    ) -> GitHubRepositoryStandIn:
        """
        Create the bare repository standing in for *repository*.

        :param project_root: The scratch clone to put it beside.
        :param repository: The ``owner/name`` to stand in for.
        :return: The stand-in.
        """
        path = project_root.parent / "repositories" / f"{repository}.git"
        path.parent.mkdir(parents=True, exist_ok=True)
        return cls(repository, initialize_bare_repository(path))

    @property
    def url(self) -> str:
        """
        :return: The URL a remote in the scratch clone points at.
        """
        return f"file://{self.path}"

    @property
    def github_url(self) -> str:
        """
        :return: The URL a hook builds for a repository it knows only as ``owner/name``.
        """
        return f"{GITHUB_URL_PREFIX}{self.repository}.git"

    @property
    def url_rewriting(self) -> GitSetting:
        """
        :return: The setting that makes git resolve this stand-in's GitHub URL to the
            stand-in itself.
        """
        return GitSetting(key=f"url.{self.url}.insteadOf", value=self.github_url)

    def branch_tip(self, branch: str) -> str:
        """
        Read a branch's commit out of the stand-in, for asserting on what a hook actually
        pushed rather than on what it reported.

        :param branch: The branch to read.
        :return: The commit it points at.
        """
        return GitCommandRunner(self.path).commit_at(branch)


@dataclass(frozen=True)
class ForkedScratchRepository:
    """
    A scratch clone of a fork whose default branch, fork and upstream all sit at one
    commit, checked out on an ordinary work branch.
    """

    repository: ScratchRepository
    """
    The clone the hook under test runs in.
    """

    fork: GitHubRepositoryStandIn
    """
    The repository its ``origin`` points at - the copy a later session is cloned from.
    """

    upstream: GitHubRepositoryStandIn
    """
    The repository the fork is forked from, reachable by its GitHub URL.
    """

    git: GitCommandRunner
    """
    The runner every git command against the clone goes through.
    """

    @classmethod
    def laid_out_in(cls, repository: ScratchRepository) -> ForkedScratchRepository:
        """
        Install the hook under test and the tooling it resolves the upstream through,
        then build all three copies of the default branch at one commit.

        :param repository: The initialized scratch repository and notes remote.
        :return: The laid-out fork.
        """
        repository.install_hook_scripts(
            "resolve-personal-notes-config.sh",
            "session-start-messages.sh",
            HOOK_SCRIPT,
        )
        install_stack_tooling(repository)
        repository.write(SHARED_FILE, "the shared base\n")

        git = GitCommandRunner(repository.project_root)
        git.checkout_orphan(DEFAULT_BRANCH)
        repository.commit_everything("the shared base")
        repository.resolve_notes_remote_to()

        forked = cls(
            repository,
            GitHubRepositoryStandIn.created_beside(
                repository.project_root, FORK_REPOSITORY
            ),
            GitHubRepositoryStandIn.created_beside(
                repository.project_root, UPSTREAM_REPOSITORY
            ),
            git,
        )
        git.add_remote(FORK_REMOTE, forked.fork.url)
        forked.reach_by_github_url(forked.upstream)
        forked.publish_default_branch_to(FORK_REMOTE)
        forked.publish_default_branch_to(forked.upstream.url)
        repository.publish_notes_branch(
            {
                PersonalNotesPath.NOTES_FILE: "personal notes\n",
                PersonalNotesPath.GIT_IDENTITY: SCRATCH_IDENTITY.as_git_config_file(),
            }
        )
        return forked

    # %% moving the three copies apart

    def advance_upstream(self, commit_count: int) -> str:
        """
        Add commits to the upstream's default branch that neither this clone nor the
        fork has, leaving both of them where they were.

        :param commit_count: How many commits to add.
        :return: The upstream's new tip.
        """
        starting_point = self.local_default_branch_tip()
        self.check_out_default_branch()
        for index in range(commit_count):
            self.repository.write(SHARED_FILE, f"an upstream revision ({index})\n")
            self.repository.commit_everything(f"an upstream commit ({index})")
        tip = self.local_default_branch_tip()
        self.publish_default_branch_to(self.upstream.url)
        self.git.checkout(WORK_BRANCH, WORK_BRANCH)
        self.set_local_default_branch_to(starting_point)
        return tip

    def advance_local_default_branch(self) -> str:
        """
        Commit onto this clone's default branch alone, the one state a fast-forward
        cannot reconcile.

        :return: The commit the default branch now points at.
        """
        self.check_out_default_branch()
        self.repository.write("a-local-only-change.txt", "only here\n")
        self.repository.commit_everything("a commit the upstream does not have")
        self.git.checkout(WORK_BRANCH, WORK_BRANCH)
        return self.local_default_branch_tip()

    def set_local_default_branch_to(self, commit: str) -> None:
        """
        Move this clone's default branch without touching the fork's, the state an
        earlier session's refused push leaves behind.

        :param commit: The commit to move it to.
        """
        self.git.move_branch(DEFAULT_BRANCH, commit)

    def check_out_default_branch(self) -> None:
        """
        Put the working tree on the default branch, as a session doing trunk work is.
        """
        self.git.checkout(DEFAULT_BRANCH, DEFAULT_BRANCH)

    def publish_default_branch_to(self, destination: str) -> None:
        """
        Push this clone's default branch to a remote or a URL.

        :param destination: The remote name or URL to publish to.
        """
        self.git.push(
            ProposedPush(
                remote=destination, refspec=f"{DEFAULT_BRANCH}:{DEFAULT_BRANCH}"
            )
        ).raise_if_failed()

    # %% which routes to the upstream are open

    def reach_by_github_url(self, stand_in: GitHubRepositoryStandIn) -> None:
        """
        Make this clone resolve a stand-in's GitHub URL to the stand-in, through git's
        own URL rewriting - the case of a clone that never added the remote.

        :param stand_in: The stand-in to reach.
        """
        self.git.configure(stand_in.url_rewriting)

    def make_the_upstream_unreachable(self) -> None:
        """
        Cut off the upstream's GitHub URL, leaving a named upstream that cannot be
        fetched.
        """
        self.git.remove_setting(self.upstream.url_rewriting.key)

    def reach_the_upstream_only_through_its_remote(self) -> None:
        """
        Register the upstream as a remote and cut off its GitHub URL, so the only route
        left to it is the remote - the clone of a contributor who added it.
        """
        self.git.add_remote(UPSTREAM_REMOTE, self.upstream.url)
        self.make_the_upstream_unreachable()

    def forget_the_fork_remote(self) -> None:
        """
        Remove the fork's remote, leaving a clone whose remotes resolve to no fork at
        all.
        """
        self.git.remove_remote(FORK_REMOTE)

    def forget_the_stack_configuration(self) -> None:
        """
        Delete the committed defaults naming the upstream, leaving a clone that names no
        upstream repository.
        """
        (self.repository.project_root / STACK_CONFIGURATION_PATH).unlink()

    # %% reading the three copies back

    @property
    def shared_base(self) -> str:
        """
        :return: The commit all three copies of the default branch start at.
        """
        return self.fork.branch_tip(DEFAULT_BRANCH)

    def local_default_branch_tip(self) -> str:
        """
        :return: The commit this clone's default branch points at.
        """
        return self.git.commit_at(f"refs/heads/{DEFAULT_BRANCH}")

    def notes_branch_tip(self) -> str:
        """
        :return: The commit this clone's copy of the notes branch points at.
        """
        return self.git.commit_at(f"refs/heads/{NOTES_BRANCH}")

    def checked_out_commit(self) -> str:
        """
        :return: The commit the working tree is on.
        """
        return self.git.commit_at("HEAD")

    # %% running what is under test

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
            ["python3", "-m", STACK_MODULE, "configuration"],
            cwd=self.repository.project_root,
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0, result.stdout
        return result.stderr.strip()


def install_stack_tooling(repository: ScratchRepository) -> None:
    """
    Copy the real package into a scratch layout and write the committed defaults the
    hooks resolve the upstream repository from.

    Written rather than committed here, unlike
    :meth:`ScratchRepository.install_stack_configuration`: the layout is committed as a
    whole onto the orphan default branch a few lines later.

    :param repository: The clone to install into.
    """
    repository.install_package()
    repository.write(STACK_CONFIGURATION_PATH, STACK_CONFIGURATION)
