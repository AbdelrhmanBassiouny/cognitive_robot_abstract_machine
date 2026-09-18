"""
Reading the personal-notes branch from Python.

The branch holds per-user data - plans, pull request progress, configuration overrides -
and which remote and branch carry it is decided by ``resolve-personal-notes-config.sh``,
the one home of that rule. This module fetches through that shell function rather than
re-deriving the rule, and reads plan data off the fetched reference.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from bastler.plan_item_bootstrap import PLANS_DIRECTORY, HookScript, PlanDocument


@dataclass(frozen=True)
class PersonalNotesBranch:
    """
    The personal-notes branch, as fetched into one repository clone.
    """

    repository_root: Path
    """
    The clone whose configuration resolves the branch, and which it is fetched into.
    """

    FETCH_FUNCTION: ClassVar[str] = "fetch_personal_notes_branch"
    """
    The shell function that fetches the branch, leaving ``FETCH_HEAD`` on it.
    """

    FETCHED_REFERENCE: ClassVar[str] = "FETCH_HEAD"
    """Where the fetch leaves the branch - a URL-form remote creates no tracking
    reference, so this is the one reference that always exists after a fetch."""

    MANIFEST_PATH_PATTERN: ClassVar[re.Pattern[str]] = re.compile(
        rf"^{re.escape(PLANS_DIRECTORY)}/([^/]+)/{re.escape(PlanDocument.MANIFEST)}$"
    )
    """
    What one plan's manifest path on the branch looks like, capturing its id.
    """

    def fetch(self) -> bool:
        """
        Fetch the branch, leaving :attr:`FETCHED_REFERENCE` pointing at it.

        Sources the shell file and calls its own fetch function rather than re-deriving
        which remote and branch the notes are on, so this and the hook scripts can never
        disagree about it. The shell's answer is also the fuller one: it falls back to
        the current branch's upstream remote when the configured one does not carry the
        branch.

        :return: Whether the branch was fetched.
        """
        configuration_script = self.repository_root / HookScript.CONFIGURATION.path
        completed = subprocess.run(
            [
                "bash",
                "-c",
                f'source "{configuration_script}" && {self.FETCH_FUNCTION}',
            ],
            capture_output=True,
            text=True,
            cwd=self.repository_root,
        )
        return completed.returncode == 0

    def read_file(self, path: str) -> str | None:
        """
        :param path: A path relative to the branch's root.
        :return: The file's content at the fetched reference, or ``None`` when absent.
        """
        result = self._git("show", f"{self.FETCHED_REFERENCE}:{path}")
        if result.returncode != 0:
            return None
        return result.stdout

    def read_plan_document(
        self, plan_identifier: str, document: PlanDocument
    ) -> str | None:
        """
        :param plan_identifier: The plan whose document to read.
        :param document: Which of the plan's documents.
        :return: The document's content, or ``None`` when the plan does not carry it.
        """
        return self.read_file(document.path_within_notes_branch(plan_identifier))

    def plan_identifiers(self) -> list[str]:
        """
        :return: Every plan with a manifest at the fetched reference, sorted.
        """
        listing = self._git(
            "ls-tree", "-r", "--name-only", self.FETCHED_REFERENCE
        ).stdout.splitlines()
        return sorted(
            match.group(1)
            for path in listing
            if (match := self.MANIFEST_PATH_PATTERN.match(path))
        )

    def _git(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        """
        :param arguments: The git subcommand and its arguments.
        :return: The finished command, output captured, not checked.
        """
        return subprocess.run(
            ["git", *arguments],
            capture_output=True,
            text=True,
            cwd=self.repository_root,
        )
