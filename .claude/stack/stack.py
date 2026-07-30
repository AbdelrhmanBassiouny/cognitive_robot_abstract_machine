#!/usr/bin/env python3
"""Stacked-PR helper for the fork-staging / cram2-review workflow.

GitHub is the single source of truth. The stack is **not** declared in a ledger: it is read from a
``board.json`` export of the fork's pull requests, combined with plain ``git``:

  * dependency tree = each fork PR's **base branch** (base = parent);
  * ``draft`` <-> ``ready`` = the fork PR's draft flag;
  * ``in-review`` = the ``in_review_label`` on the fork PR (cram2 is not readable from the cloud);
  * ``merged`` = the branch is an ancestor of ``<upstream_remote>/<upstream_base>``.

``stack.toml`` carries the committed defaults (label names, remotes); a
``.claude/personal/stack.toml`` on the personal-notes branch, if present, layers per-user overrides on
top of them (see :func:`load_config`).

Commands (run from the repo root)::

    python .claude/stack/stack.py status        # the whole stack: parent, state, drift
    python .claude/stack/stack.py check         # would each branch merge cleanly onto its parent now?
    python .claude/stack/stack.py next          # which branches to submit to cram2 next
    python .claude/stack/stack.py next --porcelain   # machine-readable: one 'name<TAB>pr' line per branch
    python .claude/stack/stack.py restack-plan  # bottom-up restack plan as JSON, for the `restack` workflow
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tomllib
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

# %% configuration

CONFIG_PATH = Path(__file__).with_name("stack.toml")
BOARD_PATH = Path(__file__).with_name("board.json")

PERSONAL_STACK_CONFIG_PATH = ".claude/personal/stack.toml"
"""Path, relative to the project root, of the per-user config override file on the personal-notes
branch (see :func:`_personal_config_overrides`)."""


@dataclass
class Config:
    """Static configuration for the workflow (everything that is not derivable from GitHub)."""

    in_review_label: str
    """Fork-PR label marking a branch as promoted to the upstream and under review."""

    rebase_label: str
    """Fork-PR label opting a branch into the rebase strategy instead of the default merge."""

    needs_resolution_label: str
    """Fork-PR label marking a branch withheld from promotion pending conflict resolution."""

    fork_remote: str
    """Git remote for the fork that holds the full stack."""

    upstream_remote: str
    """Git remote for the upstream review repository."""

    upstream_base: str
    """The upstream base branch every stack ultimately targets."""


def load_config(path: Path = CONFIG_PATH) -> Config:
    """Parse the layered configuration into a :class:`Config`.

    Values from the committed *path* are the defaults; any key present in
    ``.claude/personal/stack.toml`` on the personal-notes branch overrides them, so a user's own
    remotes/labels never have to be hand-edited into the checked-in file.

    :param path: The committed defaults file.
    :return: The layered configuration.
    """
    values = tomllib.loads(path.read_text())
    values.update(_personal_config_overrides())
    return Config(
        in_review_label=values.get("in_review_label", "in-review"),
        rebase_label=values.get("rebase_label", "rebase"),
        needs_resolution_label=values.get("needs_resolution_label", "needs-resolution"),
        fork_remote=values.get("fork_remote", "origin"),
        upstream_remote=values.get("upstream_remote", "cram2"),
        upstream_base=values.get("upstream_base", "main"),
    )


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


def _personal_config_overrides() -> dict[str, object]:
    """Fetch the personal-notes branch and parse its config override file, if any.

    :return: The parsed contents of ``.claude/personal/stack.toml`` on the personal-notes branch, or
        an empty mapping if the branch or the file doesn't exist (e.g. before it has ever been
        written).
    """
    remote = _resolve_personal_notes_remote()
    branch = _resolve_personal_notes_branch()
    if not _git_succeeds("fetch", remote, branch, "--quiet"):
        return {}
    if not _git_succeeds("cat-file", "-e", f"FETCH_HEAD:{PERSONAL_STACK_CONFIG_PATH}"):
        return {}
    return tomllib.loads(_git("show", f"FETCH_HEAD:{PERSONAL_STACK_CONFIG_PATH}"))


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

    config: Config
    """The static configuration."""

    branches: list[Branch]
    """The derived stack nodes."""

    def needs_resolution(self, branch: Branch) -> bool:
        """:param branch: The branch to check.
        :return: Whether the branch is withheld from promotion pending conflict resolution.
        """
        return self.config.needs_resolution_label in branch.labels


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


def build_stack(config: Config, prs: list[PullRequest], is_merged) -> Stack:
    """Assemble the :class:`Stack` from the PR export and a merged-branch predicate.

    :param config: The static configuration.
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
                pr.draft, is_merged(pr.head), config.in_review_label in pr.labels
            ),
            strategy=(
                IntegrationStrategy.REBASE
                if config.rebase_label in pr.labels
                else IntegrationStrategy.MERGE
            ),
            labels=pr.labels,
            ci=pr.ci,
            session=pr.session,
        )
        for pr in prs
    ]
    return Stack(config=config, branches=branches)


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


def _merged_predicate(config: Config):
    """:param config: The static configuration.
    :return: A predicate testing whether a fork branch is an ancestor of the upstream base.
    """
    upstream = f"{config.upstream_remote}/{config.upstream_base}"

    def is_merged(name: str) -> bool:
        ref = f"{config.fork_remote}/{name}"
        return _git_succeeds("merge-base", "--is-ancestor", ref, upstream)

    return is_merged


def load_stack() -> Stack:
    """:return: the full live stack: config + board export + git merged-detection."""
    config = load_config()
    prs = load_board()
    fetch(config, [pr.head for pr in prs])
    return build_stack(config, prs, _merged_predicate(config))


def resolve_ref(config: Config, name: str) -> str:
    """:param config: The static configuration.
    :param name: A branch or parent name.
    :return: Its ref on the fork remote."""
    return f"{config.fork_remote}/{name}"


def fetch(config: Config, branches: list[str]) -> None:
    """Refresh the refs the stack references so drift and merged-detection are current.

    :param config: The static configuration.
    :param branches: The fork branch names to fetch.
    """
    _git("fetch", config.upstream_remote, config.upstream_base, "-q")
    _git("fetch", config.fork_remote, "-q", *branches)


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

    A root branch (base is the upstream base, so it has no tracked parent PR) is always unblocked.

    :param stack: The stack the branch belongs to.
    :param branch: The branch to check.
    :param by_name: Every branch in the stack, keyed by name.
    :return: Whether the branch's parent has landed.
    """
    parent = by_name.get(branch.parent)
    return parent is None or parent.status in {
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
    the child PR's base to the upstream base on GitHub.

    :param stack: The stack to plan.
    :return: The restack plan, one entry per not-yet-merged branch.
    """
    by_name = {b.name: b for b in stack.branches}
    plan: list[dict[str, str]] = []
    for branch in order(stack):
        if branch.status == BranchStatus.MERGED:
            continue
        parent = by_name.get(branch.parent)
        effective_parent = (
            stack.config.upstream_base
            if parent is not None and parent.status == BranchStatus.MERGED
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
    config = stack.config
    upstream = f"{config.upstream_remote}/{config.upstream_base}"
    print(f"Stack ({len(stack.branches)} branches) vs {upstream}\n")
    print(f"{'branch':<38} {'state':<10} {'PR':>4}  ahead/behind parent   behind base")
    print("-" * 92)
    for branch in order(stack):
        ref = resolve_ref(config, branch.name)
        parent_ref = resolve_ref(config, branch.parent)
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
    config = stack.config
    print(
        "Integration probe - would each branch merge cleanly onto its parent right now?\n"
    )
    for branch in order(stack):
        ref = resolve_ref(config, branch.name)
        parent_ref = resolve_ref(config, branch.parent)
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
    config = stack.config
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
            f"NEXT to submit to {config.upstream_remote} ({len(promotable)} branch{plural}):"
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


COMMANDS = {
    "status": print_status,
    "check": print_check,
    "next": print_next,
    "restack-plan": print_restack_plan,
}


# %% entry point


def main() -> int:
    """Dispatch the command-line invocation.

    :return: The process exit code.
    """
    arguments = sys.argv[1:]
    porcelain = "--porcelain" in arguments
    arguments = [argument for argument in arguments if argument != "--porcelain"]

    if len(arguments) != 1 or arguments[0] not in COMMANDS:
        print(
            f"usage: python stack.py [{' | '.join(COMMANDS)}] [--porcelain]\n"
            "  --porcelain (with `next`): print only 'name<TAB>pr' per branch to promote.",
            file=sys.stderr,
        )
        return 2

    try:
        stack = load_stack()
    except BoardUnavailable as error:
        print(f"{error}", file=sys.stderr)
        return 3

    if porcelain and arguments[0] == "next":
        print_next_porcelain(stack)
    else:
        COMMANDS[arguments[0]](stack)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
