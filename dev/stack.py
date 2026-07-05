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
from dataclasses import dataclass
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


@dataclass
class Ledger:
    """The parsed stack ledger."""

    wip_cap: int
    fork_remote: str
    upstream_remote: str
    upstream_base: str
    branches: list[Branch]


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
            status=entry.get("status", "staging"),
        )
        for entry in data["branch"]
    ]
    return Ledger(
        wip_cap=data.get("wip_cap", 3),
        fork_remote=data.get("fork_remote", "origin"),
        upstream_remote=data.get("upstream_remote", "cram2"),
        upstream_base=data.get("upstream_base", "main"),
        branches=branches,
    )


def resolve_ref(ledger: Ledger, name: str) -> str:
    """Resolve a ledger name to a git ref: a bare name is a fork branch, a ``a/b`` name is verbatim."""
    return name if "/" in name else f"{ledger.fork_remote}/{name}"


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
    print(f"In review on {ledger.upstream_remote}: {len(in_review)}/{ledger.wip_cap}", end="")
    print(f"  [{', '.join(b.name for b in in_review) or 'none'}]\n")

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
    if len(in_review) >= ledger.wip_cap:
        print(f"WIP cap reached. Approved and waiting for a slot: {promotable[0].name}")
        return
    nxt = promotable[0]
    print(f"NEXT to submit to {ledger.upstream_remote}: {nxt.name} (PR #{nxt.pr})")
    print(f"  -> you approved it, and its parent '{nxt.parent}' has landed, so the diff is minimal.")
    if len(promotable) > 1:
        print(f"  (then, once approved: {', '.join(b.name for b in promotable[1:])})")


COMMANDS = {"status": cmd_status, "check": cmd_check, "next": cmd_next}


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in COMMANDS:
        print(f"usage: python dev/stack.py [{' | '.join(COMMANDS)}]", file=sys.stderr)
        return 2
    COMMANDS[sys.argv[1]](load_ledger())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
