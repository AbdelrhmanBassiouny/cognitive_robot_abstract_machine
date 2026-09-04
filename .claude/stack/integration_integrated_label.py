"""
Which pull requests the branch a developer works from actually holds, said on each of
them.

A build carries some of what is in flight and leaves the rest out, and nothing on a pull
request says which it was - so somebody working from the integration branch cannot tell
whether the change they are looking at is in the tree they are running. A label answers
that, and it is written when the pointer moves rather than when a build is assembled: a
build that is assembled may go red and never be adopted, and a label claiming membership
of one is the single thing this must never say.

The two runs are what makes a record necessary. A rebuild settles the *previous* run's
candidate before assembling its own build, so the report of the build being published
was produced by a run that has already ended. Each build therefore writes down which
pull requests it carried, as one git reference per pull request on the fork itself - the
shape :mod:`integration_block_record` and :mod:`integration_pass_record` already keep
their records in.

Publishing then reconciles rather than writes: the pull requests carrying the label are
made to be exactly the ones the published build holds. Removal has to reach a pull
request the build considered and left out, one whose tip it never attempted, and one an
earlier run labelled that this build's report does not mention at all - and reconciling
to an exact set is what covers all three through one rule.
"""

from __future__ import annotations

from dataclasses import dataclass

from git_commands import ReferenceUpdate
from stack import Configuration, LabelWrite

from maintenance_board import PullRequestField
from maintenance_git_commands import MaintenanceGitCommandRunner
from maintenance_github import ForkPullRequests

from integration_report import IntegrationReport

INTEGRATED_RECORD_NAMESPACE = "refs/integration/carried"
"""
Where a build's record of what it carried lives on the fork.

Below ``refs/`` rather than under ``refs/heads/``, so a record is not a branch: nothing
lists one, clones it, or offers to check it out.
"""

# %% what a build wrote down about itself


@dataclass(frozen=True)
class IntegratedTipRecord:
    """
    One pull request whose tip a build carried, kept as a reference on the fork.
    """

    build_branch: str
    """
    The build that carried it, which is what tells one build's records from another's.
    """

    pull_request_number: int
    """
    The pull request publishing the tip.
    """

    commit: str
    """
    The build's own head, which is what the reference is pointed at so it names
    something the fork can still resolve.
    """

    @property
    def reference(self) -> str:
        """:return: The git reference this record is kept as."""
        return (
            f"{INTEGRATED_RECORD_NAMESPACE}/{self.build_branch}/"
            f"{self.pull_request_number}"
        )

    @classmethod
    def named_by(cls, reference: str, commit: str) -> IntegratedTipRecord | None:
        """
        Read a record back out of the reference it is kept as.

        :param reference: A reference on the fork.
        :param commit: What it points at.
        :return: The record it is, or ``None`` when it is not one - a reference below the
            namespace that this cannot read is absent rather than an error, so a record
            written by something newer never stops a rebuild.
        """
        if not reference.startswith(f"{INTEGRATED_RECORD_NAMESPACE}/"):
            return None
        parts = reference[len(INTEGRATED_RECORD_NAMESPACE) + 1 :].split("/")
        if len(parts) != 2 or not parts[1].isdigit():
            return None
        build_branch, number = parts
        return cls(
            build_branch=build_branch,
            pull_request_number=int(number),
            commit=commit,
        )


@dataclass(frozen=True)
class IntegratedTipRecords:
    """
    Every build this fork has recorded a membership for, and what they let a publication
    say.
    """

    git: MaintenanceGitCommandRunner
    """
    The runner the fork is read and written through.
    """

    remote: str
    """
    The fork remote.
    """

    records: tuple[IntegratedTipRecord, ...]
    """
    The records the fork carries.
    """

    @classmethod
    def read(
        cls, git: MaintenanceGitCommandRunner, remote: str
    ) -> IntegratedTipRecords:
        """
        Read the whole set off the fork in one call.

        :param git: The runner to read through.
        :param remote: The fork remote.
        :return: What the fork has recorded.
        """
        listed = git.run("ls-remote", remote, f"{INTEGRATED_RECORD_NAMESPACE}/*")
        found = (
            IntegratedTipRecord.named_by(
                line.split("\t")[-1].strip(), line.split("\t")[0]
            )
            for line in listed.splitlines()
            if line.strip()
        )
        return cls(
            git=git,
            remote=remote,
            records=tuple(record for record in found if record is not None),
        )

    def carried_by(self, build_branch: str) -> tuple[int, ...]:
        """
        :param build_branch: The build to ask about.
        :return: Every pull request it recorded itself as carrying, in number order.
            Empty for a build nothing recorded, which a publication reads as *unknown*
            rather than as *nothing*.
        """
        return tuple(
            sorted(
                record.pull_request_number
                for record in self.records
                if record.build_branch == build_branch
            )
        )

    def record(self, report: IntegrationReport, commit: str) -> IntegratedTipRecords:
        """
        Write down which pull requests a build carried, so a later run can label them.

        Written for every build rather than only for one that could be published: what
        must not be claimed early is the label, and a build nothing publishes loses its
        branch and its records with it.

        :param report: What the build did.
        :param commit: The build's head, which the references are pointed at.
        :return: What the fork now holds.
        """
        written = tuple(
            IntegratedTipRecord(
                build_branch=report.build_branch,
                pull_request_number=outcome.pull_request_number,
                commit=commit,
            )
            for outcome in report.tips
            if outcome.is_integrated
        )
        if not written:
            return self
        self.git.write_remote_references(
            self.remote,
            [ReferenceUpdate(record.reference, record.commit) for record in written],
        )
        return IntegratedTipRecords(
            git=self.git, remote=self.remote, records=(*self.records, *written)
        )

    def forget_dropped_builds(self) -> IntegratedTipRecords:
        """
        Drop the records of every build the fork no longer carries a branch for.

        What keeps a record is the branch it is about: publishing deletes that branch,
        and every other ending loses it to the take-down that drops a build nothing is
        judging. So this needs no knowledge of how the run that wrote a record ended,
        which is what a rule hanging off the publishing path would have needed.

        A set with nothing in it asks the fork nothing: there is no answer that would
        drop a record, and this runs on every publication.

        :return: What the fork now holds.
        """
        if not self.records:
            return self
        built = set(self.git.remote_branch_heads(self.remote))
        dropped = tuple(
            record for record in self.records if record.build_branch not in built
        )
        if not dropped:
            return self
        self.git.write_remote_references(
            self.remote, [ReferenceUpdate(record.reference) for record in dropped]
        )
        return IntegratedTipRecords(
            git=self.git,
            remote=self.remote,
            records=tuple(record for record in self.records if record not in dropped),
        )


# %% making the label say what the published build holds


@dataclass(frozen=True)
class IntegratedLabelWrite:
    """
    One pull request whose label a publication changed.
    """

    pull_request_number: int
    """
    The pull request written to.
    """

    label: str
    """
    The label added or removed.
    """

    carried: bool
    """
    Whether the published build holds this pull request's commits, which is whether the
    label was added or removed.
    """


def reconcile_integrated_label(
    build_branch: str,
    configuration: Configuration,
    fork: ForkPullRequests,
    records: IntegratedTipRecords,
) -> tuple[IntegratedLabelWrite, ...]:
    """
    Make the pull requests carrying the label be exactly the ones a published build
    holds.

    A build nothing recorded changes nothing: that is a build assembled before anything
    wrote a record, and reading its silence as "carried nothing" would take the label off
    the whole fork on the first publication after an upgrade.

    Every write is computed from what the pull request carries now rather than from the
    build's own report, so a label another run added between the assembly and this is
    seen.

    :param build_branch: The build that was published.
    :param configuration: The resolved configuration, naming the label.
    :param fork: The fork to label.
    :param records: What the fork has recorded about its builds.
    :return: What was written, one entry per pull request changed.
    """
    carried = records.carried_by(build_branch)
    if not carried:
        return ()
    label = configuration.integrated_label
    written: list[IntegratedLabelWrite] = []
    for pull_request in fork.open_pull_requests():
        number = PullRequestField.NUMBER.read(pull_request)
        labels = PullRequestField.LABELS.read(pull_request, number)
        is_carried = number in carried
        if is_carried == (label in labels):
            continue
        fork.replace_labels(
            number,
            LabelWrite.replacing(
                labels,
                added=[label] if is_carried else [],
                removed=[] if is_carried else [label],
            ).labels,
        )
        written.append(
            IntegratedLabelWrite(
                pull_request_number=number, label=label, carried=is_carried
            )
        )
    return tuple(written)
