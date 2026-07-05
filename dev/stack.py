#!/usr/bin/env python3
"""Stacked-PR helper for the fork-staging / cram2-review workflow.

Reads ``dev/stack.toml`` and answers three questions without ever mutating your branches:

  status  -- the whole stack at a glance: each branch, its parent, lifecycle state, and how far
             it has drifted (ahead/behind its parent, behind cram2/main).
  check   -- would each branch integrate cleanly onto its declared parent right now? (a fast,
             non-mutating conflict probe via ``git merge-tree``).
  next    -- which branch to submit to cram2 next, honouring dependency order and the WIP cap.

Run with the repo root as the working directory::

    python dev/stack.py status
    python dev/stack.py check
    python dev/stack.py next
"""
from __future__ import annotations

import subprocess
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

LEDGER_PATH = Path(__file__).with_name("stack.toml")


@dataclass
class Branch:
    """One entry in the stack ledger."""

    name: str
    parent: str
    strategy: str
    pr: int | None
    status: str
    pr_repo: str  # "fork" (origin) or "upstream" (cram2) — which repo the PR lives in
    labels: list[str] = field(default_factory=list)


@dataclass
class Ledger:
    """The parsed stack ledger."""

    wip_cap: int
    wip_exempt_labels: list[str]
    fork_remote: str
    upstream_remote: str
    upstream_base: str
    branches: list[Branch]

    def counts_against_wip(self, branch: Branch) -> bool:
        """Whether a branch occupies a review slot (labelled-exempt PRs, e.g. bugs, do not)."""
        return not any(label in self.wip_exempt_labels for label in branch.labels)


def _git(*args: str) -> str:
    """Run a git command and return its stripped stdout (empty string on failure)."""
    result = subprocess.run(
        ["git", *args], capture_output=True, text=True, cwd=Path.cwd()
    )
    return result.stdout.strip()


def load_ledger() -> Ledger:
    """Parse ``stack.toml`` into a :class:`Ledger`."""
    data = tomllib.loads(LEDGER_PATH.read_text())
    branches = [
        Branch(
            name=entry["name"],
            parent=entry["parent"],
            strategy=entry.get("strategy", "rebase"),
            pr=entry.get("pr"),
            status=entry.get("status", "draft"),
            pr_repo=entry.get("pr_repo", "fork"),
            labels=list(entry.get("labels", [])),
        )
        for entry in data["branch"]
    ]
    return Ledger(
        wip_cap=data.get("wip_cap", 3),
        wip_exempt_labels=list(data.get("wip_exempt_labels", ["bug"])),
        fork_remote=data.get("fork_remote", "origin"),
        upstream_remote=data.get("upstream_remote", "cram2"),
        upstream_base=data.get("upstream_base", "main"),
        branches=branches,
    )


def resolve_ref(ledger: Ledger, name: str) -> str:
    """Resolve a ledger name to a git ref: a bare name is a fork branch, a ``a/b`` name is verbatim."""
    return name if "/" in name else f"{ledger.fork_remote}/{name}"


class LiveStatusUnavailable(RuntimeError):
    """Raised when the GitHub PR state cannot be read (e.g. ``gh`` missing/unauthenticated)."""


def derive_status(state: str, is_draft: bool, merged: bool, is_upstream: bool) -> str:
    """Map a GitHub PR's raw state to a ledger lifecycle status.

    A merged PR is ``merged``. An open non-draft PR is ``in-review`` upstream (actively reviewed on
    cram2) or ``ready`` on the fork (self-approved). An open *draft* PR is ``ready`` upstream (staged
    on cram2, not yet opened for review) or ``draft`` on the fork (still WIP). Anything else
    (closed-unmerged, no PR) is ``draft``.
    """
    if merged or state == "MERGED":
        return "merged"
    if state != "OPEN":
        return "draft"
    if is_upstream:
        return "in-review" if not is_draft else "ready"
    return "ready" if not is_draft else "draft"


def _repo_slug(remote: str) -> str:
    """Return the ``owner/repo`` slug for a git remote (from its fetch URL)."""
    url = _git("remote", "get-url", remote)
    return "/".join(url.removesuffix(".git").rstrip("/").split("/")[-2:])


def _pr_state(slug: str, pr: int) -> tuple[str, bool, bool, list[str]]:
    """Return ``(state, is_draft, merged, labels)`` for a PR via ``gh``. Raises if ``gh`` is missing."""
    import json as _json

    try:
        result = subprocess.run(
            ["gh", "pr", "view", str(pr), "--repo", slug, "--json", "state,isDraft,mergedAt,labels"],
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as error:
        raise LiveStatusUnavailable("`gh` is not installed") from error
    if result.returncode != 0:
        raise LiveStatusUnavailable(result.stderr.strip() or "gh not available")
    data = _json.loads(result.stdout)
    labels = [label["name"] for label in data.get("labels", [])]
    return data["state"], bool(data["isDraft"]), data.get("mergedAt") is not None, labels


def apply_live(ledger: Ledger) -> None:
    """Overwrite each branch's ledger status with its live GitHub PR status.

    GitHub becomes the source of truth: flip a PR to draft / ready-for-review on GitHub and the tool
    reflects it. Branches without a PR keep their ledger status.
    """
    slugs = {
        "fork": _repo_slug(ledger.fork_remote),
        "upstream": _repo_slug(ledger.upstream_remote),
    }
    for branch in ledger.branches:
        if branch.pr is None:
            continue
        state, is_draft, merged, labels = _pr_state(slugs[branch.pr_repo], branch.pr)
        branch.labels = labels
        branch.status = derive_status(
            state, is_draft, merged, is_upstream=branch.pr_repo == "upstream"
        )


def fetch(ledger: Ledger) -> None:
    """Refresh the refs the ledger references so drift numbers are current."""
    fork_branches = [b.name for b in ledger.branches if "/" not in b.parent or True]
    _git("fetch", ledger.upstream_remote, ledger.upstream_base, "-q")
    _git("fetch", ledger.fork_remote, "-q", *[b.name for b in ledger.branches])


def _count(rev_range: str) -> int | None:
    """Return the number of commits in a rev-range, or None if a ref is missing."""
    out = _git("rev-list", "--count", rev_range)
    return int(out) if out.isdigit() else None


def _order(ledger: Ledger) -> list[Branch]:
    """Topologically order branches so a parent always precedes its children."""
    by_name = {b.name: b for b in ledger.branches}
    ordered: list[Branch] = []
    seen: set[str] = set()

    def visit(branch: Branch) -> None:
        if branch.name in seen:
            return
        parent = by_name.get(branch.parent)
        if parent is not None:
            visit(parent)
        seen.add(branch.name)
        ordered.append(branch)

    for branch in ledger.branches:
        visit(branch)
    return ordered


def cmd_status(ledger: Ledger) -> None:
    fetch(ledger)
    upstream = f"{ledger.upstream_remote}/{ledger.upstream_base}"
    print(f"Stack ({len(ledger.branches)} branches, WIP cap {ledger.wip_cap}) vs {upstream}\n")
    print(f"{'branch':<38} {'state':<10} {'PR':>4}  ahead/behind parent   behind main")
    print("-" * 92)
    for branch in _order(ledger):
        ref = resolve_ref(ledger, branch.name)
        parent_ref = resolve_ref(ledger, branch.parent)
        ahead = _count(f"{parent_ref}..{ref}")
        behind_parent = _count(f"{ref}..{parent_ref}")
        behind_main = _count(f"{ref}..{upstream}")
        pr = f"#{branch.pr}" if branch.pr else "-"
        drift = f"+{ahead}/-{behind_parent} ({branch.strategy} onto {branch.parent})"
        print(
            f"{branch.name:<38} {branch.status:<10} {pr:>4}  {drift:<28} {behind_main}"
        )


def cmd_check(ledger: Ledger) -> None:
    fetch(ledger)
    print("Integration probe — would each branch merge cleanly onto its parent right now?\n")
    for branch in _order(ledger):
        ref = resolve_ref(ledger, branch.name)
        parent_ref = resolve_ref(ledger, branch.parent)
        result = subprocess.run(
            ["git", "merge-tree", "--write-tree", parent_ref, ref],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            verdict = "CLEAN"
        elif result.returncode == 1:
            conflicts = [
                line for line in result.stdout.splitlines() if line and "\t" not in line
            ]
            verdict = f"CONFLICTS onto {branch.parent}"
        else:
            verdict = f"UNKNOWN (ref missing: {parent_ref} / {ref})"
        print(f"  {branch.name:<40} {verdict}")


def cmd_next(ledger: Ledger) -> None:
    fetch(ledger)
    by_name = {b.name: b for b in ledger.branches}
    in_review = [b for b in ledger.branches if b.status == "in-review"]
    counted = [b for b in in_review if ledger.counts_against_wip(b)]
    exempt = [b for b in in_review if not ledger.counts_against_wip(b)]
    print(f"In review on {ledger.upstream_remote}: {len(counted)}/{ledger.wip_cap}", end="")
    print(f"  [{', '.join(b.name for b in counted) or 'none'}]", end="")
    print(f"  (+{len(exempt)} not counted: {', '.join(b.name for b in exempt)})" if exempt else "")
    print()

    def parent_landed(branch: Branch) -> bool:
        parent = by_name.get(branch.parent)
        return parent is None or parent.status in {"in-review", "merged"}

    # The gate: only branches YOU marked "ready" (self-reviewed on the fork) may be promoted.
    promotable = [
        b for b in _order(ledger) if b.status == "ready" and parent_landed(b)
    ]
    ready_but_blocked = [
        b for b in ledger.branches if b.status == "ready" and not parent_landed(b)
    ]
    approvable = [b for b in _order(ledger) if b.status == "draft"]

    if not promotable:
        print("Nothing to promote — no branch is both approved and unblocked.")
        if ready_but_blocked:
            names = ", ".join(b.name for b in ready_but_blocked)
            print(f"  Approved but waiting on their parent to land: {names}")
        if approvable:
            print(
                "  Your gate: self-review a fork PR, then set its status to \"ready\" in "
                f"stack.toml. Candidates (draft): {approvable[0].name}"
            )
        return
    if len(counted) >= ledger.wip_cap:
        print(f"WIP cap reached. Approved and waiting for a slot: {promotable[0].name}")
        return
    nxt = promotable[0]
    print(f"NEXT to submit to {ledger.upstream_remote}: {nxt.name} (PR #{nxt.pr})")
    print(f"  -> you approved it, and its parent '{nxt.parent}' has landed, so the diff is minimal.")
    if len(promotable) > 1:
        print(f"  (then, once approved: {', '.join(b.name for b in promotable[1:])})")


COMMANDS = {"status": cmd_status, "check": cmd_check, "next": cmd_next}


def main() -> int:
    args = sys.argv[1:]
    live = "--live" in args
    args = [a for a in args if a != "--live"]
    if len(args) != 1 or args[0] not in COMMANDS:
        print(
            f"usage: python dev/stack.py [{' | '.join(COMMANDS)}] [--live]\n"
            "  --live: derive each branch's status from its live GitHub PR (needs `gh`), "
            "so the draft/ready gate follows GitHub instead of the ledger.",
            file=sys.stderr,
        )
        return 2
    ledger = load_ledger()
    if live:
        try:
            apply_live(ledger)
        except LiveStatusUnavailable as error:
            print(
                f"--live unavailable ({error}). Install/authenticate `gh`, or drop --live to use "
                "the ledger's status column.",
                file=sys.stderr,
            )
            return 3
    COMMANDS[args[0]](ledger)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
