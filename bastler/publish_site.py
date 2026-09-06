#!/usr/bin/env python3
"""
Publish a built site directory as the whole content of a branch, which is what GitHub
Pages then serves.

The branch carries the site and nothing else, so each publish replaces it entirely
rather than merging into it - a plan deleted from the notes branch has to stop being
served, and a page left behind by an earlier build would go on being served forever.
Each publish is one commit on top of the last, so the branch keeps the site's history.

Usage:
    python3 -m bastler.publish_site --source <built site directory> --branch <branch> \\
        --remote <remote> --message <commit message>

Safe to re-run: nothing is pushed when the branch already carries exactly this content,
so an unchanged rebuild adds no empty commit. Does its work in a scratch worktree, so it
never touches the caller's current branch or working tree.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from bastler.maintenance_git_commands import GitCommandRunner

# %% what goes on the branch

DEFAULT_SITE_BRANCH = "plan-dashboards-site"
"""
The branch the built site is pushed to and Pages serves from, unless one is named.

It holds the site and nothing else, which is what makes replacing its whole content the
right publishing rule.
"""


class SiteFile(StrEnum):
    """
    The files the publisher puts on the branch itself, beside the rendered pages.
    """

    JEKYLL_OPT_OUT = ".nojekyll"
    """
    Stops Pages running a Jekyll build over the branch, which would drop every path
    beginning with an underscore and rewrite the rest. The site is already HTML.
    """


SCRATCH_BRANCH_PREFIX = "__publish-site-tmp-"
"""
Opens the throwaway branch the scratch worktree is built on.

Suffixed with the running process's identifier, so two concurrent publishes never race
over one worktree branch name.
"""


@dataclass
class SiteSourceMissingError(RuntimeError):
    """
    Raised when the directory to publish does not exist - there is nothing to serve, and
    publishing an empty tree would take the whole site down.
    """

    source_directory: Path
    """
    The directory that was asked for.
    """

    def __str__(self) -> str:
        """:return: Which directory was not found."""
        return f"--source directory not found: {self.source_directory}"


# %% publishing


@dataclass(frozen=True)
class SitePublisher:
    """
    Publishes a built site to one branch of one remote.
    """

    git: GitCommandRunner
    """
    The runner, in the checkout the scratch worktree is added to.
    """

    remote: str
    """
    The remote the branch is published to.
    """

    branch: str
    """
    The branch whose whole content the site becomes.
    """

    def publish(self, source_directory: Path, commit_message: str) -> bool:
        """
        Replace the branch's content with a built site.

        :param source_directory: The built site to publish.
        :param commit_message: The message the publishing commit carries.
        :raises SiteSourceMissingError: If the built site is not there.
        :return: Whether anything was pushed - ``False`` when the branch already
            carried exactly this content.
        """
        if not source_directory.is_dir():
            raise SiteSourceMissingError(source_directory=source_directory)

        scratch_branch = f"{SCRATCH_BRANCH_PREFIX}{os.getpid()}"
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as scratch:
            worktree = Path(scratch)
            self._discard(scratch_branch)
            worktree_git = self._empty_worktree(worktree, scratch_branch)
            shutil.copytree(source_directory, worktree, dirs_exist_ok=True)
            (worktree / SiteFile.JEKYLL_OPT_OUT).touch()
            worktree_git.run("add", "--all")

            if worktree_git.attempt("diff", "--cached", "--quiet").succeeded:
                self._take_down(worktree, scratch_branch)
                return False

            worktree_git.run("commit", "--quiet", "--message", commit_message)
            worktree_git.run("push", "--quiet", self.remote, f"HEAD:{self.branch}")
            self._take_down(worktree, scratch_branch)
            return True

    def _empty_worktree(self, worktree: Path, scratch_branch: str) -> GitCommandRunner:
        """
        Add a worktree holding the branch's history with none of its content.

        Continues the published branch's history when it exists, and starts one when it
        does not - a first publish rather than a failure. ``FETCH_HEAD`` rather than
        ``<remote>/<branch>``: a remote given as a URL creates no remote-tracking ref.

        :param worktree: Where to put the worktree.
        :param scratch_branch: The throwaway branch it is built on.
        :return: A runner pointed at the worktree.
        """
        if self.git.attempt("fetch", self.remote, self.branch, "--quiet").succeeded:
            self.git.run(
                "worktree",
                "add",
                "-b",
                scratch_branch,
                str(worktree),
                "FETCH_HEAD",
                "--quiet",
            )
            worktree_git = GitCommandRunner(working_directory=worktree)
            worktree_git.run("rm", "-r", "--quiet", "--ignore-unmatch", ".")
            return worktree_git

        self.git.run("worktree", "add", "--detach", str(worktree), "--quiet")
        worktree_git = GitCommandRunner(working_directory=worktree)
        worktree_git.run("checkout", "--orphan", scratch_branch, "--quiet")
        worktree_git.run("rm", "-rf", "--quiet", "--ignore-unmatch", ".")
        return worktree_git

    def _take_down(self, worktree: Path, scratch_branch: str) -> None:
        """
        Remove the scratch worktree and its branch.

        :param worktree: The worktree to remove.
        :param scratch_branch: The branch to delete with it.
        """
        self.git.attempt("worktree", "remove", "--force", str(worktree))
        self._discard(scratch_branch)

    def _discard(self, scratch_branch: str) -> None:
        """
        Delete the scratch branch if this checkout still has one.

        :param scratch_branch: The branch to delete.
        """
        self.git.attempt("branch", "-D", scratch_branch)


def main() -> int:
    """
    Publish the given site directory to the given branch.

    See the module docstring for the CLI contract.
    """
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--source", required=True, help="The built site directory to publish"
    )
    parser.add_argument(
        "--branch",
        default=DEFAULT_SITE_BRANCH,
        help="The branch whose whole content the site becomes",
    )
    parser.add_argument(
        "--remote", required=True, help="The remote to publish the branch to"
    )
    parser.add_argument(
        "--message", required=True, help="The publishing commit's message"
    )
    arguments = parser.parse_args()

    publisher = SitePublisher(
        git=GitCommandRunner(working_directory=Path.cwd()),
        remote=arguments.remote,
        branch=arguments.branch,
    )
    published = publisher.publish(Path(arguments.source), arguments.message)
    if published:
        print(f"Published the site to '{arguments.branch}' on '{arguments.remote}'.")
    else:
        print(
            f"The site on '{arguments.branch}' is already up to date - "
            "nothing published."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
