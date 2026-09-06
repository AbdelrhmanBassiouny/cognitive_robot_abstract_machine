"""
What this fork has already seen pass, so nothing is checked twice while it has not moved.

A rebuild runs four times a day over a set of branches that is usually unchanged, and
what one costs is a whole matrix plus the wait before GitHub starts it - see
:class:`~integration_verdict.CandidateCheckTiming`. Almost all of that is spent
re-establishing what the previous rebuild established.

Only a pass is recorded. A failure is cleared by re-running the same commit - a flake, a
runner that died, a base image rebuilt - and the rule a red branch re-enters a build by
is its checks going green rather than a label coming off, which a remembered red would
make unreachable. A pass has no such asymmetry: the checks that passed over one tree
passed over it.

Kept as one git reference per record, on the fork itself. Nothing has to be created or
merged to write one, two runs writing at once cannot lose each other's, and the whole
set is read in a single ``ls-remote``. A missing or expired record means the thing is
checked again, which is the state this started from.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import StrEnum

from maintenance_git_commands import MaintenanceGitCommandRunner

RECORD_NAMESPACE = "refs/integration/passed"
"""
Where a record lives on the fork.

Below ``refs/`` rather than under ``refs/heads/``, so a record is not a branch: nothing
lists one, clones it, or offers to check it out.
"""

RECORDED_ON_FORMAT = "%Y%m%d"
"""
How the day a record was written is spelled in its name.

In the name rather than read off the object, so the whole set's ages come out of the one
``ls-remote`` that reads it and no record has to be fetched to find out that it is old.
"""

RETENTION = timedelta(days=7)
"""
How long a record is reused for.

Nothing about the *content* decays: a key is a tree or a commit, so any change to what
was checked produces a different key and the record simply does not apply. What decays
is everything around it - the container image the matrix runs in is rebuilt from the
upstream base, and a pass says nothing about an image that has since changed. This
bounds how long a run may answer for an environment that has moved, and any window
longer than a day already gives the reuse its value, which is between one rebuild and
the next.
"""


class RecordedSubject(StrEnum):
    """
    What kind of thing a record says passed.
    """

    BUILD_TREE = "build-tree"
    """
    An assembled build's tree.

    Keyed by the tree rather than by the commit because a build is regenerated from
    scratch: re-assembling the same branches over the same base produces a different
    commit every time and the same tree every time, so the commit answers "never seen
    before" about a build that is byte-for-byte one already published.
    """

    BRANCH_HEAD = "branch-head"
    """
    The commit a branch in flight points at.

    What decides whether a build carries that branch at all, so a head already recorded
    is one a rebuild need not ask GitHub about again.
    """


@dataclass(frozen=True)
class PassRecord:
    """
    One thing this fork has seen pass, and when it was written down.
    """

    subject: RecordedSubject
    """
    What kind of thing passed.
    """

    key: str
    """
    The tree or commit it passed over.
    """

    recorded_on: date
    """
    The day it was written.
    """

    @property
    def reference(self) -> str:
        """:return: The git reference this record is kept as."""
        return (
            f"{RECORD_NAMESPACE}/{self.subject}/"
            f"{self.recorded_on.strftime(RECORDED_ON_FORMAT)}/{self.key}"
        )

    @classmethod
    def named_by(cls, reference: str) -> PassRecord | None:
        """
        Read a record back out of the reference it is kept as.

        :param reference: A reference on the fork.
        :return: The record it is, or ``None`` when it is not one - a reference below the
            namespace that this cannot read is treated as absent rather than as an error,
            so a record written by something newer never stops a rebuild.
        """
        if not reference.startswith(f"{RECORD_NAMESPACE}/"):
            return None
        parts = reference[len(RECORD_NAMESPACE) + 1 :].split("/")
        if len(parts) != 3:
            return None
        subject, written, key = parts
        if subject not in set(RecordedSubject):
            return None
        try:
            recorded_on = datetime.strptime(written, RECORDED_ON_FORMAT).date()
        except ValueError:
            return None
        return cls(subject=RecordedSubject(subject), key=key, recorded_on=recorded_on)

    def is_current_on(self, day: date, retention: timedelta = RETENTION) -> bool:
        """
        :param day: The day the record is being read.
        :param retention: How long a record is reused for.
        :return: Whether it still answers for what it recorded.
        """
        return day - self.recorded_on <= retention


@dataclass(frozen=True)
class PassedChecks:
    """
    Every pass this fork has recorded, and what they let a rebuild skip.
    """

    records: tuple[PassRecord, ...]
    """
    The records the fork carries, expired ones included.
    """

    read_on: date
    """
    The day they were read, which is what decides which of them still answer.
    """

    @classmethod
    def read(
        cls,
        git: MaintenanceGitCommandRunner,
        remote: str,
        today: date | None = None,
    ) -> PassedChecks:
        """
        Read the whole set off the fork in one call.

        :param git: The runner to read through.
        :param remote: The fork remote.
        :param today: The day to judge currency by; the actual day when not given.
        :return: What the fork has recorded.
        """
        listed = git.run("ls-remote", remote, f"{RECORD_NAMESPACE}/*")
        found = (
            PassRecord.named_by(line.split("\t")[-1].strip())
            for line in listed.splitlines()
            if line.strip()
        )
        return cls(
            records=tuple(record for record in found if record is not None),
            read_on=today or date.today(),
        )

    def holds(self, subject: RecordedSubject, key: str) -> bool:
        """
        :param subject: What kind of thing to ask about.
        :param key: The tree or commit to ask about.
        :return: Whether it has passed recently enough to be taken as passing now.
        """
        return any(
            record.subject is subject
            and record.key == key
            and record.is_current_on(self.read_on)
            for record in self.records
        )

    @property
    def expired(self) -> tuple[PassRecord, ...]:
        """:return: Every record too old to be reused, which is every record to drop."""
        return tuple(
            record for record in self.records if not record.is_current_on(self.read_on)
        )

    def record(
        self,
        git: MaintenanceGitCommandRunner,
        remote: str,
        subject: RecordedSubject,
        key: str,
        commit: str,
    ) -> PassedChecks:
        """
        Write one record, dropping whatever has expired in the same push.

        Written together because this is the moment the expired set is already known: a
        pass that has to remember to prune separately is one that stops being pruned.

        Answered with the set as it now stands rather than in place, so a second write in
        the same run does not ask the fork to delete a reference the first one removed.

        A fork that refuses the write costs the reuse and nothing else: the record is an
        optimisation, so a credential that may read the fork but not write this
        namespace has to leave the rebuild running rather than end it. Said on standard
        error, since a rebuild silently paying for a full matrix every run is one nobody
        can explain.

        :param git: The runner to push through.
        :param remote: The fork remote.
        :param subject: What kind of thing passed.
        :param key: The tree or commit it passed over.
        :param commit: A commit to point the reference at, so the record names something
            the fork can still resolve.
        :return: What the fork now holds, unchanged when it refused the write.
        """
        written = PassRecord(subject=subject, key=key, recorded_on=self.read_on)
        expired = self.expired
        pushed = git.attempt(
            "push",
            "--force",
            remote,
            f"{commit}:{written.reference}",
            *(f":{stale.reference}" for stale in expired),
        )
        if not pushed.succeeded:
            print(
                f"{remote} refused a record under {RECORD_NAMESPACE}, so this pass is "
                f"not remembered: {pushed.error_output}",
                file=sys.stderr,
            )
            return self
        return PassedChecks(
            records=(
                *(record for record in self.records if record not in expired),
                written,
            ),
            read_on=self.read_on,
        )
