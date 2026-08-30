# plan-tracking-skills — Roadmap

Narrative companion to `plan.yaml`. Kept short on purpose: the size budget this split was made
under counts these lines.

## Where this plan came from

Split out of `workflow-unification` on 2026-08-30, under `plan-size-limits`'
`split-workflow-unification`. That plan had reached 59 items and 16,917 lines across its manifest
and roadmap, well past the 15-item / 2,000-line budget, and became seven plans seamed on subject.

This plan is the half of the old `personal-data` track that is about the plan-item skills; the other
half - the session-start hook, the notes branch and the conventions riding in them - is
`session-notes-infrastructure`. The two were split because the track was 16 items and 4,329 lines,
over both halves of the budget, and the seam is where its own items already draw it.

Every item keeps its branch, pull request number, status and session verbatim. **The full
predecessor roadmap remains in the personal-notes branch's history**; what is kept here is what binds
future work.

## Why this work exists

The plan skills covered creating a plan, starting an item, unblocking one and publishing status. Two
things they did not cover turned out to cost the most:

- **Where a new piece of work belongs** was decided by default, which produced a fold chain of three
  pull requests and one collision where two sessions independently built the same artifact under two
  names. `/add-plan-item` makes that decision explicit, and ships a script rather than prose alone,
  since eyeballing is exactly what missed the collision.
- **When the manifest gets written.** A session went straight from an approved plan to writing code,
  with the branch, the pull request, the manifest fields and the roadmap entry all following at the
  end - so for the whole length of the implementation the plan said the item was `not_started` with
  no branch, and any other session reading it was reading a lie. `plan-item-bootstrap` inverts that
  for the kickoff moment; `manifest-currency-first`, in `stack-maintenance`, generalises it.

## Decisions this plan inherits

Numbering is the predecessor's, kept so cross-references in item notes still resolve.

**12. The standard-library floor.** These modules are reachable from a hook, so they stay
standard-library-only, and the Python floor is 3.11 - which is what rules out a `Path` enum mixin and
several other shapes a review round would otherwise ask for.

**13. The package extraction moves all six of these files into one home**, which is where a shared
report base would live and why `report-document-naming` is best done inside or after it.

## Rules this track settled

- **Two operations, not one shared procedure.** Recording an item and *opening* the work are
  separate, and each skill takes only the one it needs, in that order - the pull request number does
  not exist until the pull request does. Referencing the whole thing from `/add-plan-item` would have
  handed a branch-and-push step to a skill whose own opening paragraph promises it never creates a
  branch.
- **A pull request a script creates is attributed to the app its requests are proxied through**,
  while the same creation through a session's own tool is attributed to the user - verified minutes
  apart on the same repository. That is the authorship problem `AGENTS.md` rules out for commits, so
  a session creates the pull request and the script records its number. The creating path survives for
  an unattended run whose credential is a real one.
- **Within a session the credential is irrelevant.** The identical response comes back with an
  exported token, a junk token and no authorization header at all, because the proxy supplies the
  identity. Portability is why a token still matters: the same script run from a terminal or an Action
  has no proxy.
- **Single-sourcing an external contract deletes the guard the duplicated literals were providing.**
  With both sides reading the same enum, a rename changes them identically and nothing notices -
  verified by renaming a member and watching every test still pass. Whether to replace that guard with
  a dedicated test depends on who reads the contract.
- **The surviving name for a dict-returning serializer is `to_json`**, settled by count rather than
  argument: 93 definitions outside `.claude/` against 3 for the three alternatives together, and it is
  what `SubclassJSONSerializer` declares. That leaves `as_json` free for the text-returning methods,
  so the collision dissolves rather than needing a ruling.

## Landing hazards

- **A rename sweep across five files on main.** `report-document-naming` touches files several other
  plans' branches also carry, so it is cheapest inside or just after the package extraction.
- **The edit guard is committed configuration.** `.claude/settings.json` ships to every contributor
  who inherits this repository, so a hook that blocked their edits would be indefensible upstream.
  Inertness for a clone that uses neither plans nor personal notes is a hard constraint, not a
  preference, and it is derived from state rather than from a setting.

## Open

- **The notes-targeting exemption has no mechanism.** A branch whose pull request targets the notes
  branch should be exempt from the edit guard, and the obvious local test - the notes branch tip being
  an ancestor of `HEAD` - collides with the hook tests' own fixture, which builds its work branch off
  the notes branch. Either the fixture branches from the initial commit, or the test reads the pull
  request base.
- **Upstream review threads cannot be answered from this fork.** Sessions cannot write to the upstream
  repository, so reply text is handed to the user. Two threads on the execution-modes work stay open
  on purpose, each answered differently from what it asked.
