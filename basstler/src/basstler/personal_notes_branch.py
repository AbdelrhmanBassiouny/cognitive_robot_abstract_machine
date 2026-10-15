"""
The personal-notes branch: where it lives, fetching it, and writing files onto it.

Every write goes through a scratch worktree of the fetched branch, so the checkout a
session works in is never switched or touched.
"""

from __future__ import annotations

import shutil
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path, PurePosixPath
from types import TracebackType

from basstler.exceptions import NotesBranchMissingError, UnsafeNotesPathError
from basstler.maintenance_git_commands import GitCommandRunner
from basstler.setup_steps import PersonalNotesSetting

# %% where the notes live


@dataclass(frozen=True)
class PersonalNotesLocation:
    """
    Where a clone's personal notes are kept.
    """

    remote: str
    """
    The remote the notes branch is fetched from and pushed to: a name or a URL.
    """

    branch: str
    """
    The branch holding the notes.
    """

    notes_path: str
    """
    The personal-notes file, relative to the branch's root.
    """

    @classmethod
    def resolve(
        cls, project_root: Path, environment: Mapping[str, str]
    ) -> PersonalNotesLocation:
        """
        :param project_root: The clone whose git config to read.
        :param environment: The environment to read the settings' variables from.
        :return: The location the hooks resolve for that clone.
        """
        return cls(
            remote=PersonalNotesSetting.REMOTE.resolve(project_root, environment),
            branch=PersonalNotesSetting.BRANCH.resolve(project_root, environment),
            notes_path=PersonalNotesSetting.PATH.resolve(project_root, environment),
        )


# %% fetching


@dataclass(frozen=True)
class PersonalNotesBranch:
    """
    The personal-notes branch, as one clone reaches it.
    """

    location: PersonalNotesLocation
    """
    Where the notes are kept.
    """

    git: GitCommandRunner
    """
    The clone that fetches the branch.
    """

    def candidate_remotes(self) -> list[str]:
        """
        :return: The configured remote, then the current branch's upstream remote when
            that is a different one.
        """
        remotes = [self.location.remote]
        upstream = self.git.attempt(
            "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"
        )
        upstream_remote = upstream.output.split("/", 1)[0] if upstream.succeeded else ""
        if upstream_remote and upstream_remote not in remotes:
            remotes.append(upstream_remote)
        return remotes

    def fetch(self) -> str:
        """
        Fetch the branch into ``FETCH_HEAD`` from the first remote that has it.

        :return: That remote.
        :raises NotesBranchMissingError: If no candidate remote has the branch.
        """
        remotes = self.candidate_remotes()
        for remote in remotes:
            if self.git.attempt(
                "fetch", "--quiet", remote, self.location.branch
            ).succeeded:
                return remote
        raise NotesBranchMissingError(self.location.branch, tuple(remotes))


# %% writing


class NotesWriteOutcome(StrEnum):
    """
    What a write did to the notes branch.
    """

    PUSHED = "pushed"
    """
    The changes were committed and pushed.
    """

    UNCHANGED = "unchanged"
    """
    The branch already held every change, so nothing was committed.
    """


@dataclass
class ScratchWorktree:
    """
    A detached worktree of ``FETCH_HEAD`` in a temporary directory, removed on exit.
    """

    git: GitCommandRunner
    """
    The clone the worktree belongs to.
    """

    directory: Path = field(init=False)
    """
    The worktree's root, once entered.
    """

    def __enter__(self) -> GitCommandRunner:
        """
        :return: A runner for the new worktree.
        """
        self.directory = Path(tempfile.mkdtemp())
        self.git.run(
            "worktree", "add", "--detach", "--quiet", str(self.directory), "FETCH_HEAD"
        )
        return GitCommandRunner(self.directory)

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """
        Remove the worktree, whether or not the write succeeded.
        """
        self.git.attempt("worktree", "remove", "--force", str(self.directory))
        shutil.rmtree(self.directory, ignore_errors=True)


@dataclass(frozen=True)
class NotesBranchWriter:
    """
    Writes files onto the personal-notes branch and pushes them.
    """

    branch: PersonalNotesBranch
    """
    The branch written to.
    """

    def write(
        self, changes: Mapping[PurePosixPath, str | None], message: str
    ) -> NotesWriteOutcome:
        """
        Apply *changes* to the latest notes branch in one commit, and push it to the
        remote it was fetched from.

        :param changes: Each path relative to the branch's root, with its new content,
            or ``None`` to remove the file or directory there.
        :param message: The commit message.
        :raises UnsafeNotesPathError: If a path is absolute or contains ``..``; nothing
            is fetched or written then.
        :raises NotesBranchMissingError: If no remote has the branch.
        :return: Whether anything was pushed.
        """
        for path in changes:
            if path.is_absolute() or ".." in path.parts:
                raise UnsafeNotesPathError(path)
        remote = self.branch.fetch()
        with ScratchWorktree(self.branch.git) as worktree:
            for path, content in changes.items():
                target = worktree.working_directory / path
                if content is None and target.is_dir():
                    shutil.rmtree(target)
                    continue
                if content is None:
                    target.unlink(missing_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content)
            worktree.run("add", "--all")
            if worktree.attempt("diff", "--cached", "--quiet").succeeded:
                return NotesWriteOutcome.UNCHANGED
            worktree.run("commit", "--quiet", "-m", message)
            worktree.run(
                "push", "--quiet", remote, f"HEAD:{self.branch.location.branch}"
            )
        return NotesWriteOutcome.PUSHED
