#!/usr/bin/env python3
"""Stacked-PR helper for the fork-staging / cram2-review workflow.

GitHub is the single source of truth. The stack is **not** declared in a ledger: it is read from a
``board.json`` export of the fork's pull requests, combined with plain ``git``:

  * dependency tree = each fork PR's **base branch** (base = parent);
  * ``draft`` <-> ``ready`` = the fork PR's draft flag;
  * ``in-review`` = the ``in_review_label`` on the fork PR (cram2 is not readable from the cloud);
  * ``merged`` = the branch is an ancestor of ``<upstream_remote>/<upstream_base>``.

``stack.toml`` carries the committed defaults (label names, the upstream repository); a
``.claude/personal/stack.toml`` on the personal-notes branch, if present, layers per-user overrides on
top of them (see :func:`load_configuration`).

Commands (run from the repo root)::

    python .claude/stack/stack.py status        # the whole stack: parent, state, drift
    python .claude/stack/stack.py check         # would each branch merge cleanly onto its parent now?
    python .claude/stack/stack.py next          # which branches to submit to cram2 next
    python .claude/stack/stack.py next --porcelain   # machine-readable: one 'name<TAB>pr' line per branch
    python .claude/stack/stack.py restack-plan  # bottom-up restack plan as JSON, for the `restack` workflow
    python .claude/stack/stack.py configuration # every resolved setting, including the remotes
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tomllib
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import IntEnum, StrEnum
from pathlib import Path

# %% configuration

CONFIGURATION_PATH = Path(__file__).with_name("stack.toml")
BOARD_PATH = Path(__file__).with_name("board.json")

PERSONAL_STACK_CONFIGURATION_PATH = ".claude/personal/stack.toml"
"""Path, relative to the project root, of the per-user configuration override file on the personal-notes
branch (see :func:`_personal_configuration_overrides`)."""


@dataclass
class MalformedRepositoryError(ValueError):
    """Raised when a repository reference is not in ``owner/name`` form."""

    text: str
    """The value that could not be parsed."""

    def __str__(self) -> str:
        """:return: What was expected and what arrived instead."""
        return f"expected a repository as 'owner/name', got {self.text!r}"


@dataclass(frozen=True)
class Repository:
    """A GitHub repository, identified the way GitHub itself writes it."""

    owner: str
    """The user or organization the repository belongs to."""

    name: str
    """The repository's own name."""

    @classmethod
    def parse(cls, text: str) -> Repository:
        """Parse an ``owner/name`` repository reference.

        :param text: The reference to parse.
        :return: The parsed repository.
        :raises MalformedRepositoryError: If *text* is not ``owner/name``.
        """
        owner, separator, name = text.partition("/")
        if not (owner and separator and name):
            raise MalformedRepositoryError(text)
        return cls(owner, name)

    @staticmethod
    def _remote_url_segments(url: str) -> list[str]:
        """Split a remote URL into its path segments, discarding scheme and host.

        :param url: The remote URL to split.
        :return: The path segments, which name a repository when there are two or more.
        """
        reference = url.removesuffix(".git").rstrip("/")
        if "://" in reference:
            _, _, host_and_path = reference.partition("://")
            _, _, path = host_and_path.partition("/")
        elif ":" in reference:
            _, _, path = reference.rpartition(":")
        else:
            return []
        return [segment for segment in path.split("/") if segment]

    @classmethod
    def names_a_repository(cls, url: str) -> bool:
        """Test whether a remote URL points at a repository at all.

        :param url: The remote URL to test.
        :return: Whether it names an ``owner/name`` pair.
        """
        return len(cls._remote_url_segments(url)) >= 2

    @classmethod
    def from_remote_url(cls, url: str) -> Repository:
        """Read the repository a git remote URL points at.

        Accepts every form a fork remote takes - HTTPS, SSH, and the local proxy a cloud
        session is given - by discarding the host and taking the last two path segments.

        :param url: The remote URL to read.
        :return: The repository it names.
        :raises MalformedRepositoryError: If *url* names no ``owner/name`` pair.
        """
        segments = cls._remote_url_segments(url)
        if len(segments) < 2:
            raise MalformedRepositoryError(url)
        return cls.parse("/".join(segments[-2:]))

    def __str__(self) -> str:
        """:return: The ``owner/name`` form GitHub uses."""
        return f"{self.owner}/{self.name}"


@dataclass(frozen=True)
class Remote:
    """A git remote, identified by the repository its URL names rather than by its name."""

    name: str
    """What this checkout calls the remote."""

    repository: Repository
    """The repository the remote points at."""


@dataclass
class ForkRemoteNotFoundError(LookupError):
    """Raised when no remote points at a repository other than the upstream."""

    upstream_repository: Repository
    """The upstream every candidate turned out to be."""

    def __str__(self) -> str:
        """:return: What was searched for and why nothing qualified."""
        return (
            f"no remote points at a fork: every remote is {self.upstream_repository}. "
            f"Add a remote for your fork, or set fork_repository in stack.toml."
        )


@dataclass
class AmbiguousForkRemoteError(LookupError):
    """Raised when several remotes could each be the fork."""

    candidates: tuple[Remote, ...]
    """The remotes that are not the upstream, in the order git reported them."""

    def __str__(self) -> str:
        """:return: The candidates and how to disambiguate them."""
        listed = ", ".join(
            f"{remote.name} -> {remote.repository}" for remote in self.candidates
        )
        return (
            f"several remotes could be the fork ({listed}). "
            f"Set fork_repository in stack.toml to say which."
        )


@dataclass(frozen=True)
class RemoteResolution:
    """Which remote is the fork and which is the upstream, decided without trusting names."""

    fork: Remote
    """The remote holding the stack."""

    upstream: Remote | None
    """The remote for the upstream review repository, absent if the checkout has none."""

    upstream_repository: Repository
    """The upstream, whether or not a remote points at it yet."""

    preferred_upstream_name: str
    """What to call the upstream remote when one has to be added."""

    @property
    def upstream_name(self) -> str:
        """:return: The upstream remote's name, or the name it will get when added."""
        return self.upstream.name if self.upstream else self.preferred_upstream_name

    @property
    def upstream_setup_command(self) -> str | None:
        """:return: The command adding the missing upstream remote, or ``None`` if present."""
        if self.upstream:
            return None
        return (
            f"git remote add {self.preferred_upstream_name} "
            f"https://github.com/{self.upstream_repository}.git"
        )


def resolve_remotes(
    remote_urls: Mapping[str, str],
    upstream_repository: Repository,
    preferred_upstream_name: str,
    fork_repository: Repository | None = None,
) -> RemoteResolution:
    """Decide which remote is the fork and which is the upstream.

    Remotes are matched by the repository their URL names, so a checkout whose remotes are
    called anything at all resolves the same way.

    :param remote_urls: Remote name to URL, as git reports them.
    :param upstream_repository: The repository every fork is forked from.
    :param preferred_upstream_name: What to call the upstream remote if one must be added.
    :param fork_repository: The fork, when configuration names it outright.
    :return: The resolved remotes.
    :raises ForkRemoteNotFoundError: If no remote points at a fork.
    :raises AmbiguousForkRemoteError: If several do and configuration does not disambiguate.
    """
    remotes = [
        Remote(name, Repository.from_remote_url(url))
        for name, url in remote_urls.items()
        if Repository.names_a_repository(url)
    ]
    upstream = next(
        (remote for remote in remotes if remote.repository == upstream_repository), None
    )
    candidates = tuple(
        remote for remote in remotes if remote.repository != upstream_repository
    )
    return RemoteResolution(
        fork=_select_fork(candidates, fork_repository, upstream_repository),
        upstream=upstream,
        upstream_repository=upstream_repository,
        preferred_upstream_name=preferred_upstream_name,
    )


def _select_fork(
    candidates: tuple[Remote, ...],
    fork_repository: Repository | None,
    upstream_repository: Repository,
) -> Remote:
    """Pick the fork from the remotes that are not the upstream.

    :param candidates: The non-upstream remotes.
    :param fork_repository: The fork, when configuration names it outright.
    :param upstream_repository: The upstream, for reporting when nothing qualifies.
    :return: The fork's remote.
    :raises ForkRemoteNotFoundError: If no candidate qualifies.
    :raises AmbiguousForkRemoteError: If several do and configuration does not disambiguate.
    """
    if fork_repository:
        named = [
            remote for remote in candidates if remote.repository == fork_repository
        ]
        if not named:
            raise ForkRemoteNotFoundError(upstream_repository)
        return named[0]
    if not candidates:
        raise ForkRemoteNotFoundError(upstream_repository)
    if len(candidates) > 1:
        raise AmbiguousForkRemoteError(candidates)
    return candidates[0]


@dataclass
class Configuration:
    """Everything this checkout runs on: the layered settings and the remotes they resolve to."""

    in_review_label: str
    """Fork-PR label marking a branch as promoted to the upstream and under review."""

    rebase_label: str
    """Fork-PR label opting a branch into the rebase strategy instead of the default merge."""

    needs_resolution_label: str
    """Fork-PR label marking a branch withheld from promotion pending conflict resolution."""

    fork_repository: Repository
    """The fork that holds the full stack, as GitHub names it."""

    fork_remote: str
    """Git remote for the fork that holds the full stack."""

    upstream_repository: Repository
    """The repository every fork is forked from, and the only one constant across contributors."""

    upstream_remote: str
    """Git remote for the upstream review repository."""

    upstream_base: str
    """The upstream base branch every stack ultimately targets."""

    upstream_setup_command: str | None
    """The command adding the upstream remote, or ``None`` once this checkout has one."""


def load_configuration(path: Path = CONFIGURATION_PATH) -> Configuration:
    """Parse the layered configuration into a :class:`Configuration`.

    Values from the committed *path* are the defaults; any key present in
    ``.claude/personal/stack.toml`` on the personal-notes branch overrides them, so a user's own
    remotes/labels never have to be hand-edited into the checked-in file.

    :param path: The committed defaults file.
    :return: The layered configuration.
    """
    values = _configuration_values(path)
    upstream_repository = Repository.parse(values["upstream_repository"])
    resolution = resolved_remotes(path)
    return Configuration(
        in_review_label=values.get("in_review_label", "in-review"),
        rebase_label=values.get("rebase_label", "rebase"),
        needs_resolution_label=values.get("needs_resolution_label", "needs-resolution"),
        fork_repository=resolution.fork.repository,
        fork_remote=resolution.fork.name,
        upstream_repository=upstream_repository,
        upstream_remote=resolution.upstream_name,
        upstream_base=values.get("upstream_base", "main"),
        upstream_setup_command=resolution.upstream_setup_command,
    )


def _configuration_values(path: Path) -> dict[str, str]:
    """Read the committed defaults with any personal-notes overrides layered on top.

    :param path: The committed defaults file.
    :return: The layered values.
    """
    values = tomllib.loads(path.read_text())
    values.update(_personal_configuration_overrides())
    return values


def resolved_remotes(path: Path = CONFIGURATION_PATH) -> RemoteResolution:
    """Resolve this checkout's fork and upstream remotes.

    :param path: The committed defaults file.
    :return: The resolved remotes.
    :raises ForkRemoteNotFoundError: If no remote points at a fork.
    :raises AmbiguousForkRemoteError: If several do and configuration does not disambiguate.
    """
    values = _configuration_values(path)
    configured_fork = values.get("fork_repository")
    return resolve_remotes(
        _remote_urls(),
        Repository.parse(values["upstream_repository"]),
        values.get("upstream_remote", "cram2"),
        Repository.parse(configured_fork) if configured_fork else None,
    )


def _remote_urls() -> dict[str, str]:
    """:return: Every remote in this checkout, mapped to its fetch URL."""
    listed = _git("remote").splitlines()
    return {name: _git("remote", "get-url", name) for name in listed if name}


def _resolve_personal_notes_remote() -> str:
    """:return: the personal-notes remote, by the same precedence as
    ``resolve-personal-notes-config.sh``: git config, then an environment variable, then a default.
    """
    return (
        _git("config", "--get", "claude.personalNotesRemote")
        or os.environ.get("CLAUDE_PERSONAL_NOTES_REMOTE")
        or "origin"
    )


def _resolve_personal_notes_branch() -> str:
    """:return: the personal-notes branch name, by the same precedence as
    :func:`_resolve_personal_notes_remote`."""
    return (
        _git("config", "--get", "claude.personalNotesBranch")
        or os.environ.get("CLAUDE_PERSONAL_NOTES_BRANCH")
        or "claude/personal-notes"
    )


def _personal_configuration_overrides() -> dict[str, object]:
    """Fetch the personal-notes branch and parse its configuration override file, if any.

    :return: The parsed contents of ``.claude/personal/stack.toml`` on the personal-notes branch, or
        an empty mapping if the branch or the file doesn't exist (e.g. before it has ever been
        written).
    """
    remote = _resolve_personal_notes_remote()
    branch = _resolve_personal_notes_branch()
    if not _git_succeeds("fetch", remote, branch, "--quiet"):
        return {}
    if not _git_succeeds(
        "cat-file", "-e", f"FETCH_HEAD:{PERSONAL_STACK_CONFIGURATION_PATH}"
    ):
        return {}
    return tomllib.loads(
        _git("show", f"FETCH_HEAD:{PERSONAL_STACK_CONFIGURATION_PATH}")
    )


# %% domain model


class BranchStatus(StrEnum):
    """A stack node's lifecycle position."""

    DRAFT = "draft"
    READY = "ready"
    IN_REVIEW = "in-review"
    MERGED = "merged"


class IntegrationStrategy(StrEnum):
    """How a branch integrates its parent's moved tip during a restack."""

    MERGE = "merge"
    REBASE = "rebase"


@dataclass
class PullRequest:
    """One fork pull request as exported into ``board.json``."""

    number: int
    """The pull request number on the fork."""

    head: str
    """The PR's head branch - the branch this stack node names."""

    base: str
    """The PR's base branch - its parent in the stack (``base = parent``)."""

    draft: bool
    """Whether the PR is a draft (not yet approved for review)."""

    labels: list[str] = field(default_factory=list)
    """Labels currently on the PR."""

    ci: str | None = None
    """Latest CI conclusion on the PR head: ``success`` / ``failure`` / ``pending`` / None."""

    session: str | None = None
    """URL of the Claude session working this PR, parsed from the PR body (None if none)."""


@dataclass
class Branch:
    """A stack node derived from a fork PR plus git state."""

    name: str
    """The branch name (the PR head)."""

    parent: str
    """The parent branch (the PR base)."""

    pull_request_number: int
    """The fork PR number."""

    status: BranchStatus
    """Lifecycle status."""

    strategy: IntegrationStrategy
    """Integration strategy onto the parent."""

    labels: list[str]
    """Labels carried by the PR."""

    ci: str | None = None
    """Latest CI conclusion on the PR head."""

    session: str | None = None
    """URL of the Claude session working this PR, if any."""


@dataclass
class Stack:
    """The whole stack: configuration plus the branches derived from GitHub and git."""

    configuration: Configuration
    """The static configuration."""

    branches: list[Branch]
    """The derived stack nodes."""

    is_merged: Callable[[str], bool]
    """Maps any branch name - tracked by this stack or not - to whether it has landed
    upstream."""

    def needs_resolution(self, branch: Branch) -> bool:
        """:param branch: The branch to check.
        :return: Whether the branch is withheld from promotion pending conflict resolution.
        """
        return self.configuration.needs_resolution_label in branch.labels

    def has_landed_upstream(self, branch_name: str) -> bool:
        """Whether a branch's commits are already in the upstream base.

        Answered from git ancestry, so it holds for any branch name - including one no open
        pull request describes, which the board therefore never mentions.

        :param branch_name: The branch to check.
        :return: Whether its commits are in the upstream base.
        """
        return branch_name == self.configuration.upstream_base or self.is_merged(
            branch_name
        )


class BoardUnavailable(RuntimeError):
    """Raised when ``board.json`` is missing."""


def load_board(path: Path = BOARD_PATH) -> list[PullRequest]:
    """Parse ``board.json`` into the list of fork pull requests.

    :param path: The board export file.
    :return: The exported pull requests.
    :raises BoardUnavailable: If *path* does not exist.
    """
    if not path.exists():
        raise BoardUnavailable(f"{path.name} not found")
    data = json.loads(path.read_text())
    return [
        PullRequest(
            number=pr["number"],
            head=pr["head"],
            base=pr["base"],
            draft=bool(pr["draft"]),
            labels=list(pr.get("labels", [])),
            ci=pr.get("ci"),
            session=pr.get("session"),
        )
        for pr in data["pull_requests"]
    ]


def derive_status(draft: bool, merged: bool, in_review: bool) -> BranchStatus:
    """Map a PR's raw facts to a lifecycle status.

    Precedence: a merged branch is ``merged``; an ``in-review``-labelled branch is ``in-review``; an
    un-drafted branch is ``ready`` (self-approved for promotion); otherwise ``draft``.

    :param draft: Whether the PR is still a draft.
    :param merged: Whether the branch has landed upstream (git ancestry).
    :param in_review: Whether the PR carries the in-review label.
    :return: The derived status.
    """
    if merged:
        return BranchStatus.MERGED
    if in_review:
        return BranchStatus.IN_REVIEW
    return BranchStatus.DRAFT if draft else BranchStatus.READY


def build_stack(
    configuration: Configuration,
    prs: list[PullRequest],
    is_merged: Callable[[str], bool],
) -> Stack:
    """Assemble the :class:`Stack` from the PR export and a merged-branch predicate.

    :param configuration: The static configuration.
    :param prs: The exported pull requests.
    :param is_merged: Maps a branch name to whether it has landed upstream; injected so the pure
        assembly logic can be tested without git.
    :return: The assembled stack.
    """
    branches = [
        Branch(
            name=pr.head,
            parent=pr.base,
            pull_request_number=pr.number,
            status=derive_status(
                pr.draft, is_merged(pr.head), configuration.in_review_label in pr.labels
            ),
            strategy=(
                IntegrationStrategy.REBASE
                if configuration.rebase_label in pr.labels
                else IntegrationStrategy.MERGE
            ),
            labels=pr.labels,
            ci=pr.ci,
            session=pr.session,
        )
        for pr in prs
    ]
    return Stack(configuration=configuration, branches=branches, is_merged=is_merged)


# %% git plumbing


def _git(*args: str) -> str:
    """Run a git command and return its stripped stdout (empty string on failure).

    :param args: The git subcommand and its arguments.
    :return: The command's stripped stdout.
    """
    result = subprocess.run(
        ["git", *args], capture_output=True, text=True, cwd=Path.cwd()
    )
    return result.stdout.strip()


def _git_succeeds(*args: str) -> bool:
    """Run a git command, discarding its output.

    :param args: The git subcommand and its arguments.
    :return: Whether the command exited successfully.
    """
    result = subprocess.run(
        ["git", *args], capture_output=True, text=True, cwd=Path.cwd()
    )
    return result.returncode == 0


def _merged_predicate(configuration: Configuration):
    """:param configuration: The static configuration.
    :return: A predicate testing whether a fork branch is an ancestor of the upstream base.
    """
    upstream = f"{configuration.upstream_remote}/{configuration.upstream_base}"

    def is_merged(name: str) -> bool:
        ref = f"{configuration.fork_remote}/{name}"
        return _git_succeeds("merge-base", "--is-ancestor", ref, upstream)

    return is_merged


def load_stack() -> Stack:
    """:return: the full live stack: configuration + board export + git merged-detection."""
    configuration = load_configuration()
    prs = load_board()
    fetch(configuration, [pr.head for pr in prs])
    return build_stack(configuration, prs, _merged_predicate(configuration))


def resolve_ref(configuration: Configuration, name: str) -> str:
    """:param configuration: The static configuration.
    :param name: A branch or parent name.
    :return: Its ref on the fork remote."""
    return f"{configuration.fork_remote}/{name}"


def fetch(configuration: Configuration, branches: list[str]) -> None:
    """Refresh the refs the stack references so drift and merged-detection are current.

    :param configuration: The static configuration.
    :param branches: The fork branch names to fetch.
    """
    _git("fetch", configuration.upstream_remote, configuration.upstream_base, "-q")
    _git("fetch", configuration.fork_remote, "-q", *branches)


def _count(rev_range: str) -> int | None:
    """:param rev_range: A git rev-range expression.
    :return: The number of commits in it, or ``None`` if a ref is missing."""
    out = _git("rev-list", "--count", rev_range)
    return int(out) if out.isdigit() else None


# %% stack assembly


def order(stack: Stack) -> list[Branch]:
    """:param stack: The stack to order.
    :return: Its branches, topologically ordered so a parent always precedes its children.
    """
    by_name = {b.name: b for b in stack.branches}
    ordered: list[Branch] = []
    seen: set[str] = set()

    def visit(branch: Branch) -> None:
        if branch.name in seen:
            return
        seen.add(branch.name)
        parent = by_name.get(branch.parent)
        if parent is not None:
            visit(parent)
        ordered.append(branch)

    for branch in stack.branches:
        visit(branch)
    return ordered


def parent_landed(stack: Stack, branch: Branch, by_name: dict[str, Branch]) -> bool:
    """Whether a branch's parent has reached the upstream (merged or in-review), so it can promote.

    A parent no open pull request describes cannot carry an in-review label, so git ancestry is the
    only evidence available for it - and absence from the board is not itself evidence of a root
    branch.

    :param stack: The stack the branch belongs to.
    :param branch: The branch to check.
    :param by_name: Every branch in the stack, keyed by name.
    :return: Whether the branch's parent has landed.
    """
    parent = by_name.get(branch.parent)
    if parent is None:
        return stack.has_landed_upstream(branch.parent)
    return parent.status in {
        BranchStatus.IN_REVIEW,
        BranchStatus.MERGED,
    }


# %% promotion policy


def promotion_order(stack: Stack) -> list[Branch]:
    """The branches to submit to the upstream next, in dependency order.

    A branch is a candidate when it is approved (``ready``), its parent has landed, and it has not
    been withheld pending conflict resolution. Every such branch promotes together - there is no
    admission cap or per-stack slot limit (see the module's history for why: a ``wip_cap`` large
    enough to never bind made that machinery a no-op, so it was removed rather than fixed).

    :param stack: The stack to evaluate.
    :return: The promotable branches, in dependency order.
    """
    by_name = {b.name: b for b in stack.branches}
    return [
        branch
        for branch in order(stack)
        if branch.status == BranchStatus.READY
        and parent_landed(stack, branch, by_name)
        and not stack.needs_resolution(branch)
    ]


def next_to_promote(stack: Stack) -> Branch | None:
    """:param stack: The stack to evaluate.
    :return: The first branch to submit to the upstream next, or ``None`` if nothing is ready.
    """
    ordered = promotion_order(stack)
    return ordered[0] if ordered else None


def restack_plan(stack: Stack) -> list[dict[str, str]]:
    """The bottom-up restack plan the ``restack`` workflow consumes as its ``args``.

    One entry per branch not yet ``merged``, in parent-before-child order. In-review branches are
    included so they pick up a moved parent; their ``merge`` strategy keeps that update conflict-free
    and force-push-free, so an open review is never disrupted.

    When a branch's parent has **merged** into the upstream, its commits are already in the base, so
    the child is reparented onto the upstream base: the restack rebases it there and it stops
    depending on a landed (and about-to-be-closed) branch. The routine mirrors this by retargeting
    the child PR's base to the upstream base on GitHub. This holds however the parent landed -
    including when its own pull request was closed rather than merged, leaving the board with no
    entry for it at all.

    :param stack: The stack to plan.
    :return: The restack plan, one entry per not-yet-merged branch.
    """
    plan: list[dict[str, str]] = []
    for branch in order(stack):
        if branch.status == BranchStatus.MERGED:
            continue
        effective_parent = (
            stack.configuration.upstream_base
            if stack.has_landed_upstream(branch.parent)
            else branch.parent
        )
        plan.append(
            {
                "branch": branch.name,
                "parent": effective_parent,
                "strategy": branch.strategy,
            }
        )
    return plan


# %% commands


def print_status(stack: Stack) -> None:
    """Print the whole stack: parent, state, and drift versus the upstream.

    :param stack: The stack to report.
    """
    configuration = stack.configuration
    upstream = f"{configuration.upstream_remote}/{configuration.upstream_base}"
    print(f"Stack ({len(stack.branches)} branches) vs {upstream}\n")
    print(f"{'branch':<38} {'state':<10} {'PR':>4}  ahead/behind parent   behind base")
    print("-" * 92)
    for branch in order(stack):
        ref = resolve_ref(configuration, branch.name)
        parent_ref = resolve_ref(configuration, branch.parent)
        ahead = _count(f"{parent_ref}..{ref}")
        behind_parent = _count(f"{ref}..{parent_ref}")
        behind_base = _count(f"{ref}..{upstream}")
        drift = f"+{ahead}/-{behind_parent} ({branch.strategy} onto {branch.parent})"
        print(
            f"{branch.name:<38} {branch.status:<10} #{branch.pull_request_number:<3}  {drift:<28} {behind_base}"
        )


def print_check(stack: Stack) -> None:
    """Print whether each branch would merge cleanly onto its parent right now.

    :param stack: The stack to probe.
    """
    configuration = stack.configuration
    print(
        "Integration probe - would each branch merge cleanly onto its parent right now?\n"
    )
    for branch in order(stack):
        ref = resolve_ref(configuration, branch.name)
        parent_ref = resolve_ref(configuration, branch.parent)
        result = subprocess.run(
            ["git", "merge-tree", "--write-tree", parent_ref, ref],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            verdict = "CLEAN"
        elif result.returncode == 1:
            verdict = f"CONFLICTS onto {branch.parent}"
        else:
            verdict = f"UNKNOWN (ref missing: {parent_ref} / {ref})"
        print(f"  {branch.name:<40} {verdict}")


def print_next(stack: Stack) -> None:
    """Print which branch(es) are ready to submit to the upstream next.

    :param stack: The stack to report.
    """
    configuration = stack.configuration
    by_name = {b.name: b for b in stack.branches}
    promotable = promotion_order(stack)
    withheld = [
        b
        for b in stack.branches
        if b.status == BranchStatus.READY
        and parent_landed(stack, b, by_name)
        and stack.needs_resolution(b)
    ]

    def report_withheld() -> None:
        if withheld:
            print(
                f"  Withheld (delegated, needs-resolution): {', '.join(b.name for b in withheld)}"
            )

    if promotable:
        plural = "es" if len(promotable) != 1 else ""
        print(
            f"NEXT to submit to {configuration.upstream_remote} ({len(promotable)} branch{plural}):"
        )
        for branch in promotable:
            print(
                f"  {branch.name} (PR #{branch.pull_request_number}) - approved, parent '{branch.parent}' landed"
            )
        report_withheld()
        return

    ready_blocked = [
        b
        for b in stack.branches
        if b.status == BranchStatus.READY and not parent_landed(stack, b, by_name)
    ]
    draft_candidates = [b for b in order(stack) if b.status == BranchStatus.DRAFT]

    print("Nothing to promote - no branch is both approved and unblocked.")
    if ready_blocked:
        print(
            f"  Approved but waiting on a parent to land: {', '.join(b.name for b in ready_blocked)}"
        )
    report_withheld()
    if draft_candidates:
        print(
            "  The gate: self-review a fork PR, then un-draft it (or set its status ready). "
            f"Draft candidates: {draft_candidates[0].name}"
        )


def print_next_porcelain(stack: Stack) -> None:
    """Print machine-readable :func:`print_next`: one ``name<TAB>pr`` line per promotable branch.

    :param stack: The stack to report.
    """
    for branch in promotion_order(stack):
        print(f"{branch.name}\t{branch.pull_request_number}")


def print_restack_plan(stack: Stack) -> None:
    """Print the restack plan as JSON - pipe it into the ``restack`` workflow's ``args``.

    :param stack: The stack to plan.
    """
    print(json.dumps(restack_plan(stack), indent=2))


def print_configuration(configuration: Configuration) -> None:
    """Print the resolved configuration as one ``field<TAB>value`` line per setting.

    Keys are :class:`Configuration`'s own field names, so a caller reading one by name cannot
    be reading a name this module never prints. A setting with no value is omitted rather than
    printed empty, which is what keeps ``upstream_setup_command`` readable as "run this".

    :param configuration: The configuration to report.
    """
    for name, value in vars(configuration).items():
        if value is None:
            continue
        print(f"{name}\t{value}")


COMMANDS = {
    "status": print_status,
    "check": print_check,
    "next": print_next,
    "restack-plan": print_restack_plan,
}

BOARDLESS_COMMANDS = frozenset({"configuration"})
"""Commands answerable from git alone, which must run before ``board.json`` exists."""


# %% entry point


class ExitCode(IntEnum):
    """What this tool's exit status tells a caller.

    A distinct status per failure lets a caller - a shell script, or a Routine acting on
    what it gets back - tell "you asked for something that does not exist" from "the
    checkout is not in a state I can read", without parsing stderr.
    """

    SUCCESS = 0
    """The command ran and printed its result."""

    USAGE = 2
    """No such command, or the wrong number of arguments; the conventional status for a
    usage error, as `argparse` also uses."""

    BOARD_UNAVAILABLE = 3
    """`board.json` is missing or unreadable, so the stack cannot be derived."""

    REMOTES_UNRESOLVED = 4
    """The fork could not be identified from this checkout's remotes."""


def _print_configuration_or_report() -> ExitCode:
    """Print the resolved configuration, or report why the remotes could not be resolved.

    :return: The process exit code, non-zero when resolution is not deterministic.
    """
    try:
        configuration = load_configuration()
    except (ForkRemoteNotFoundError, AmbiguousForkRemoteError) as error:
        print(f"{error}", file=sys.stderr)
        return ExitCode.REMOTES_UNRESOLVED
    print_configuration(configuration)
    return ExitCode.SUCCESS


def main() -> ExitCode:
    """Dispatch the command-line invocation.

    :return: The process exit code.
    """
    arguments = sys.argv[1:]
    porcelain = "--porcelain" in arguments
    arguments = [argument for argument in arguments if argument != "--porcelain"]

    known = [*COMMANDS, *BOARDLESS_COMMANDS]
    if len(arguments) != 1 or arguments[0] not in known:
        print(
            f"usage: python stack.py [{' | '.join(known)}] [--porcelain]\n"
            "  --porcelain (with `next`): print only 'name<TAB>pr' per branch to promote.",
            file=sys.stderr,
        )
        return ExitCode.USAGE

    if arguments[0] in BOARDLESS_COMMANDS:
        return _print_configuration_or_report()

    try:
        stack = load_stack()
    except BoardUnavailable as error:
        print(f"{error}", file=sys.stderr)
        return ExitCode.BOARD_UNAVAILABLE

    if porcelain and arguments[0] == "next":
        print_next_porcelain(stack)
    else:
        COMMANDS[arguments[0]](stack)
    return ExitCode.SUCCESS


if __name__ == "__main__":
    raise SystemExit(main())
