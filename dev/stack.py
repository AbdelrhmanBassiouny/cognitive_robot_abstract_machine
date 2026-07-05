#!/usr/bin/env python3
"""Stacked-PR helper for the fork-staging / cram2-review workflow.

GitHub is the single source of truth. The stack is **not** declared in a ledger: it is read from a
``board.json`` export of the fork's pull requests (refreshed by the routine via the GitHub MCP, or by
``stack.py export`` where ``gh`` is available) combined with plain ``git``:

  * dependency tree = each fork PR's **base branch** (base = parent);
  * ``draft`` <-> ``ready`` = the fork PR's draft flag;
  * ``in-review`` = the ``in_review_label`` on the fork PR (cram2 is not readable from the cloud);
  * ``merged`` = the branch is an ancestor of ``<upstream_remote>/<upstream_base>``.

``stack.toml`` carries only configuration (WIP cap, label names, remotes).

Commands (run from the repo root)::

    python dev/stack.py status        # the whole stack: parent, state, drift
    python dev/stack.py check         # would each branch merge cleanly onto its parent now?
    python dev/stack.py next          # which branch to submit to cram2 next (gate + deps + WIP cap)
    python dev/stack.py next --porcelain   # machine-readable: 'name<TAB>pr' or nothing
    python dev/stack.py restack-plan  # bottom-up restack plan as JSON, for the `restack` workflow
    python dev/stack.py export        # (re)write board.json from live fork PRs via `gh`
"""
from __future__ import annotations

import json
import subprocess
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_PATH = Path(__file__).with_name("stack.toml")
BOARD_PATH = Path(__file__).with_name("board.json")

DRAFT = "draft"
READY = "ready"
IN_REVIEW = "in-review"
MERGED = "merged"


@dataclass
class Config:
    """Static configuration for the workflow (everything that is not derivable from GitHub)."""

    wip_cap: int
    """Maximum feature branches simultaneously in review on the upstream."""

    wip_exempt_labels: list[str]
    """PR labels whose presence excludes a PR from the WIP count (e.g. a standalone bug fix)."""

    in_review_label: str
    """Fork-PR label marking a branch as promoted to the upstream and under review."""

    rebase_label: str
    """Fork-PR label opting a branch into the rebase strategy instead of the default merge."""

    fork_remote: str
    """Git remote for the fork that holds the full stack."""

    upstream_remote: str
    """Git remote for the upstream review repository."""

    upstream_base: str
    """The upstream base branch every stack ultimately targets."""


@dataclass
class PullRequest:
    """One fork pull request as exported into ``board.json``."""

    number: int
    """The pull request number on the fork."""

    head: str
    """The PR's head branch — the branch this stack node names."""

    base: str
    """The PR's base branch — its parent in the stack (``base = parent``)."""

    draft: bool
    """Whether the PR is a draft (not yet approved for review)."""

    labels: list[str] = field(default_factory=list)
    """Labels currently on the PR."""


@dataclass
class Branch:
    """A stack node derived from a fork PR plus git state."""

    name: str
    """The branch name (the PR head)."""

    parent: str
    """The parent branch (the PR base)."""

    pr: int
    """The fork PR number."""

    status: str
    """Lifecycle status: ``draft`` / ``ready`` / ``in-review`` / ``merged``."""

    strategy: str
    """Integration strategy onto the parent: ``merge`` (default) or ``rebase``."""

    labels: list[str]
    """Labels carried by the PR (used for WIP exemption)."""


@dataclass
class Stack:
    """The whole stack: configuration plus the branches derived from GitHub and git."""

    config: Config
    """The static configuration."""

    branches: list[Branch]
    """The derived stack nodes."""

    def counts_against_wip(self, branch: Branch) -> bool:
        """Whether a branch occupies a review slot (labelled-exempt PRs, e.g. bugs, do not)."""
        return not any(label in self.config.wip_exempt_labels for label in branch.labels)


def _git(*args: str) -> str:
    """Run a git command and return its stripped stdout (empty string on failure)."""
    result = subprocess.run(["git", *args], capture_output=True, text=True, cwd=Path.cwd())
    return result.stdout.strip()


def load_config(path: Path = CONFIG_PATH) -> Config:
    """Parse ``stack.toml`` into a :class:`Config`."""
    data = tomllib.loads(path.read_text())
    return Config(
        wip_cap=data.get("wip_cap", 3),
        wip_exempt_labels=list(data.get("wip_exempt_labels", ["bug"])),
        in_review_label=data.get("in_review_label", "in-review"),
        rebase_label=data.get("rebase_label", "rebase"),
        fork_remote=data.get("fork_remote", "origin"),
        upstream_remote=data.get("upstream_remote", "cram2"),
        upstream_base=data.get("upstream_base", "main"),
    )


class BoardUnavailable(RuntimeError):
    """Raised when ``board.json`` is missing — run ``stack.py export`` or the refresh routine first."""


def load_board(path: Path = BOARD_PATH) -> list[PullRequest]:
    """Parse ``board.json`` into the list of fork pull requests."""
    if not path.exists():
        raise BoardUnavailable(f"{path.name} not found — run `python dev/stack.py export` first")
    data = json.loads(path.read_text())
    return [
        PullRequest(
            number=pr["number"],
            head=pr["head"],
            base=pr["base"],
            draft=bool(pr["draft"]),
            labels=list(pr.get("labels", [])),
        )
        for pr in data["pull_requests"]
    ]


def derive_status(draft: bool, merged: bool, in_review: bool) -> str:
    """Map a PR's raw facts to a lifecycle status.

    Precedence: a merged branch is ``merged``; an ``in-review``-labelled branch is ``in-review``; an
    un-drafted branch is ``ready`` (self-approved for promotion); otherwise ``draft``.
    """
    if merged:
        return MERGED
    if in_review:
        return IN_REVIEW
    return READY if not draft else DRAFT


def build_stack(config: Config, prs: list[PullRequest], is_merged) -> Stack:
    """Assemble the :class:`Stack` from the PR export and a merged-branch predicate.

    ``is_merged`` maps a branch name to whether it has landed upstream; it is injected so the pure
    assembly logic can be tested without git.
    """
    branches = [
        Branch(
            name=pr.head,
            parent=pr.base,
            pr=pr.number,
            status=derive_status(pr.draft, is_merged(pr.head), config.in_review_label in pr.labels),
            strategy="rebase" if config.rebase_label in pr.labels else "merge",
            labels=pr.labels,
        )
        for pr in prs
    ]
    return Stack(config=config, branches=branches)


def _merged_predicate(config: Config):
    """Return a predicate testing whether a fork branch is an ancestor of the upstream base."""
    upstream = f"{config.upstream_remote}/{config.upstream_base}"

    def is_merged(name: str) -> bool:
        ref = f"{config.fork_remote}/{name}"
        result = subprocess.run(
            ["git", "merge-base", "--is-ancestor", ref, upstream],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0

    return is_merged


def load_stack() -> Stack:
    """Load the full live stack: config + board export + git merged-detection."""
    config = load_config()
    prs = load_board()
    fetch(config, [pr.head for pr in prs])
    return build_stack(config, prs, _merged_predicate(config))


def resolve_ref(config: Config, name: str) -> str:
    """Resolve a branch/parent name to its ref on the fork remote."""
    return f"{config.fork_remote}/{name}"


def fetch(config: Config, branches: list[str]) -> None:
    """Refresh the refs the stack references so drift and merged-detection are current."""
    _git("fetch", config.upstream_remote, config.upstream_base, "-q")
    _git("fetch", config.fork_remote, "-q", *branches)


def _count(rev_range: str) -> int | None:
    """Return the number of commits in a rev-range, or None if a ref is missing."""
    out = _git("rev-list", "--count", rev_range)
    return int(out) if out.isdigit() else None


def order(stack: Stack) -> list[Branch]:
    """Topologically order branches so a parent always precedes its children."""
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
    """
    parent = by_name.get(branch.parent)
    return parent is None or parent.status in {IN_REVIEW, MERGED}


def next_to_promote(stack: Stack) -> Branch | None:
    """The single branch to submit to the upstream next, or None if blocked or nothing is ready.

    Encodes the whole policy: approved (``ready``) + parent landed + under the (bug-exempt) WIP cap.
    """
    counted = [
        b for b in stack.branches if b.status == IN_REVIEW and stack.counts_against_wip(b)
    ]
    if len(counted) >= stack.config.wip_cap:
        return None
    by_name = {b.name: b for b in stack.branches}
    for branch in order(stack):
        if branch.status == READY and parent_landed(stack, branch, by_name):
            return branch
    return None


def restack_plan(stack: Stack) -> list[dict[str, str]]:
    """The bottom-up restack plan the ``restack`` workflow consumes as its ``args``.

    One entry per branch not yet ``merged``, in parent-before-child order. In-review branches are
    included so they pick up a moved parent; their ``merge`` strategy keeps that update conflict-free
    and force-push-free, so an open review is never disrupted.
    """
    return [
        {"branch": b.name, "parent": b.parent, "strategy": b.strategy}
        for b in order(stack)
        if b.status != MERGED
    ]


def cmd_status(stack: Stack) -> None:
    config = stack.config
    upstream = f"{config.upstream_remote}/{config.upstream_base}"
    print(f"Stack ({len(stack.branches)} branches, WIP cap {config.wip_cap}) vs {upstream}\n")
    print(f"{'branch':<38} {'state':<10} {'PR':>4}  ahead/behind parent   behind base")
    print("-" * 92)
    for branch in order(stack):
        ref = resolve_ref(config, branch.name)
        parent_ref = resolve_ref(config, branch.parent)
        ahead = _count(f"{parent_ref}..{ref}")
        behind_parent = _count(f"{ref}..{parent_ref}")
        behind_base = _count(f"{ref}..{upstream}")
        drift = f"+{ahead}/-{behind_parent} ({branch.strategy} onto {branch.parent})"
        print(f"{branch.name:<38} {branch.status:<10} #{branch.pr:<3}  {drift:<28} {behind_base}")


def cmd_check(stack: Stack) -> None:
    config = stack.config
    print("Integration probe — would each branch merge cleanly onto its parent right now?\n")
    for branch in order(stack):
        ref = resolve_ref(config, branch.name)
        parent_ref = resolve_ref(config, branch.parent)
        result = subprocess.run(
            ["git", "merge-tree", "--write-tree", parent_ref, ref], capture_output=True, text=True
        )
        if result.returncode == 0:
            verdict = "CLEAN"
        elif result.returncode == 1:
            verdict = f"CONFLICTS onto {branch.parent}"
        else:
            verdict = f"UNKNOWN (ref missing: {parent_ref} / {ref})"
        print(f"  {branch.name:<40} {verdict}")


def cmd_next(stack: Stack) -> None:
    config = stack.config
    in_review = [b for b in stack.branches if b.status == IN_REVIEW]
    counted = [b for b in in_review if stack.counts_against_wip(b)]
    exempt = [b for b in in_review if not stack.counts_against_wip(b)]
    print(f"In review on {config.upstream_remote}: {len(counted)}/{config.wip_cap}", end="")
    print(f"  [{', '.join(b.name for b in counted) or 'none'}]", end="")
    print(f"  (+{len(exempt)} exempt: {', '.join(b.name for b in exempt)})" if exempt else "")
    print()

    by_name = {b.name: b for b in stack.branches}
    promotable = [
        b for b in order(stack) if b.status == READY and parent_landed(stack, b, by_name)
    ]
    ready_blocked = [
        b for b in stack.branches if b.status == READY and not parent_landed(stack, b, by_name)
    ]
    draft_candidates = [b for b in order(stack) if b.status == DRAFT]

    if not promotable:
        print("Nothing to promote — no branch is both approved and unblocked.")
        if ready_blocked:
            print(f"  Approved but waiting on a parent to land: {', '.join(b.name for b in ready_blocked)}")
        if draft_candidates:
            print(
                "  The gate: self-review a fork PR, then un-draft it (or set its status ready). "
                f"Draft candidates: {draft_candidates[0].name}"
            )
        return
    if len(counted) >= config.wip_cap:
        print(f"WIP cap reached. Approved and waiting for a slot: {promotable[0].name}")
        return
    nxt = promotable[0]
    print(f"NEXT to submit to {config.upstream_remote}: {nxt.name} (PR #{nxt.pr})")
    print(f"  -> you approved it, and its parent '{nxt.parent}' has landed, so the diff is minimal.")
    if len(promotable) > 1:
        print(f"  (then, once approved: {', '.join(b.name for b in promotable[1:])})")


def cmd_next_porcelain(stack: Stack) -> None:
    """Machine-readable :func:`next`: print ``name<TAB>pr`` for the branch to promote, or nothing."""
    branch = next_to_promote(stack)
    if branch is not None:
        print(f"{branch.name}\t{branch.pr}")


def cmd_restack_plan(stack: Stack) -> None:
    """Print the restack plan as JSON — pipe it into the ``restack`` workflow's ``args``."""
    print(json.dumps(restack_plan(stack), indent=2))


def export_board(config: Config, path: Path = BOARD_PATH) -> int:
    """Write ``board.json`` from the fork's open PRs via ``gh``. Returns the number of PRs exported.

    Where ``gh`` is unavailable (e.g. the cloud routine), the caller refreshes ``board.json`` through
    the GitHub MCP instead; this command is the local convenience path.
    """
    slug = "/".join(
        _git("remote", "get-url", config.fork_remote).removesuffix(".git").rstrip("/").split("/")[-2:]
    )
    result = subprocess.run(
        ["gh", "pr", "list", "--repo", slug, "--state", "open", "--limit", "200",
         "--json", "number,headRefRefName,baseRefName,isDraft,labels"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise BoardUnavailable(result.stderr.strip() or "gh not available")
    raw = json.loads(result.stdout)
    prs = [
        {
            "number": pr["number"],
            "head": pr.get("headRefRefName") or pr.get("headRefName"),
            "base": pr["baseRefName"],
            "draft": pr["isDraft"],
            "labels": [label["name"] for label in pr.get("labels", [])],
        }
        for pr in raw
    ]
    path.write_text(json.dumps({"pull_requests": prs}, indent=2) + "\n")
    return len(prs)


COMMANDS = {
    "status": cmd_status,
    "check": cmd_check,
    "next": cmd_next,
    "restack-plan": cmd_restack_plan,
}


def main() -> int:
    args = sys.argv[1:]
    porcelain = "--porcelain" in args
    args = [a for a in args if a != "--porcelain"]

    if args == ["export"]:
        config = load_config()
        count = export_board(config)
        print(f"Wrote {BOARD_PATH.name} ({count} open fork PRs).")
        return 0

    if len(args) != 1 or args[0] not in COMMANDS:
        print(
            f"usage: python dev/stack.py [{' | '.join(COMMANDS)} | export] [--porcelain]\n"
            "  export: (re)write board.json from live fork PRs via `gh`.\n"
            "  --porcelain (with `next`): print only 'name<TAB>pr' for the branch to promote.",
            file=sys.stderr,
        )
        return 2

    try:
        stack = load_stack()
    except BoardUnavailable as error:
        print(f"{error}", file=sys.stderr)
        return 3

    if porcelain and args[0] == "next":
        cmd_next_porcelain(stack)
    else:
        COMMANDS[args[0]](stack)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
