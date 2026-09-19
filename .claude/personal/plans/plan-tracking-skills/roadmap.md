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
- **#160's fix lands through #151, not on its own branch.** `plan-item-bootstrap-yaml-indent` fixes
  the indentation for the code as it stood before the `update` subcommand existed. `update` arrives
  on `stack-maintenance/manifest-currency-first` (#151), which carries the unfixed indent, and the
  two conflict - six hunks in the module, three in its tests. Rather than fixing it twice, #160 is
  merged into #151 and its `ItemIndentation` is carried through to the sequence-entry and block-body
  render paths it never saw. Nothing more is pushed to #160.

## Open

- **The notes-targeting exemption has no mechanism.** A branch whose pull request targets the notes
  branch should be exempt from the edit guard, and the obvious local test - the notes branch tip being
  an ancestor of `HEAD` - collides with the hook tests' own fixture, which builds its work branch off
  the notes branch. Either the fixture branches from the initial commit, or the test reads the pull
  request base.
- **Upstream review threads cannot be answered from this fork.** Sessions cannot write to the upstream
  repository, so reply text is handed to the user. Two threads on the execution-modes work stay open
  on purpose, each answered differently from what it asked.

## Propagating a resolve's fix downstream

`/plan-item-resolve` fixes the pull request it was pointed at and stops. Whatever is stacked on
that pull request keeps the broken parent until a `/stacked-pr-maintenance` pass happens to run,
and that pass is whole-board: `order()` is topological over every branch and `restack_plan()`
emits every not-yet-merged one, with no way to name a single subtree. A resolve therefore leaves
its own descendants stale by construction.

`resolve-propagates-downstream` closes that: a descendants selector over `Stack`, built on the
`is_ancestor` predicate already there; the existing `restack()` and its `RESTACK_STEPS` reused
rather than a second propagation path; and a conflict outcome that hands the collision back for
judgement instead of only refusing the move and leaving a comment.

The judgement is the part a script cannot do, and it is not the one
`/integration-conflict-triage` already makes. That skill weighs **sibling** collisions on the
integration branch, where neither branch is wrong and the rule is that the fix belongs in the
feature branch. This is **parent to descendant**, where there is a correct answer and it belongs
in the descendant - so the vocabulary carries over but the verdicts do not.

### Placement, and why

Decided through `/add-plan-item` rather than by default. `check_scope_overlap.py` against `main`
over nineteen unlanded tooling branches found no branch building this, under this name or another;
the only shared paths are `basstler-package`'s relocation itself, which is what makes this work on
top of an unlanded parent rather than a fold into it. It lands here rather than in
`stack-maintenance` because its subject is the resolve skill's duties and the restack machinery is
the means - and because `stack-maintenance` is already the plan `integration-tip-selection` was
split out of for size.

### Landing hazard

`.claude/skills/plan-item-resolve/SKILL.md` is contended: thirteen unlanded branches edit it, most
inserting `manifest-currency-first`'s "Record what you found" block in the same region. This item's
footprint in that file has to stay a reference line pointing at a document of its own, the way
`scope-decision.md` and `prerequisite-check.md` are referenced. A block inserted beside #151's is
how it becomes an integration collision instead of a clean merge.

### The plan this item is being built to (kickoff, 2026-09-19)

Three pieces of code and one of prose, in that order, tests first.

- **`branches_stacked_on(stack, branch)` in `basstler/stack.py`**, beside `order()`,
  `reparents()` and `landed_branches()`: every not-yet-merged branch whose parent chain
  reaches the named one, parent before child, excluding the branch itself.
  **It walks `Branch.parent` rather than git containment**, which departs from this
  section's "built on the `is_ancestor` predicate already there". The stack's parent
  relation is what `restack_plan()` consumes and what a pull request's base declares, so
  it is what "stacked on" means; git containment answers a different question - whether
  the fix is already in - and `SkipBranchAlreadyCurrent` already asks it, per branch,
  during the restack. Selecting by containment would also drop exactly the branches that
  need the propagation, since a descendant stops containing its parent's tip the moment
  the parent is fixed.
- **`restack_plan(stack, stacked_on=None)` and `restack(..., stacked_on=None)`**: the
  subtree the plan is limited to, so the existing `RESTACK_STEPS` do the work and there
  is no second propagation path.
- **A conflict response, chosen by that same argument**: `TellTheBranchOwner` (today's
  behaviour - the `needs-resolution` label plus the comment) for a whole-board pass, and
  `LeaveItToTheCaller` (the outcome and its conflicting paths, nothing written to GitHub)
  when a subtree was named. One argument rather than two knobs, because naming the
  subtree *is* the statement that the caller is present and will judge the collision:
  labelling the descendant would withhold it from later passes, and telling its owner to
  resolve what the session is about to resolve is noise on their pull request.
- **`.claude/skills/plan-item-resolve/propagating-a-fix.md`**, referenced by one line
  from that skill's `SKILL.md`, per this section's landing hazard: thirteen unlanded
  branches edit that file, so the footprint stays a reference. Referenced by its path
  rather than through a new `resolve-personal-notes-config.sh` constant - the document
  has one reader, and the constants exist for paths several skills share; it also keeps
  this item out of a second contended file.

Verified with the package's own suite (`python -m pytest test/basstler_test
--confcutdir=test/basstler_test`), against the real-git `ForkCheckout` fixture and the
`RecordingPullRequests` fake that already exist for the restack tests.
