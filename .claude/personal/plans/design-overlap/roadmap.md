# Catching two branches building the same thing

## Why this exists

Parallel branches in a plan - ones not stacked on each other - keep converging on the
same design independently. It surfaces late, often only when the user reviews what a
session built, and by then extracting the shared abstraction and restacking both
branches is expensive enough to be deferred. Deferring it is what makes it unfixable:
afterwards a duplicate is a merge conflict rather than a choice.

This is not a hypothesis about the workflow. It is written into the workflow's own
documents. `add-plan-item/scope-decision.md` records three branches folded back into
their parents after the fact and two sessions independently building the same artifact
under two filenames. `integration-conflict-triage/SKILL.md` says the reconcile case
"has happened on this repository more than once and cost a duplicated artifact each
time."

## The diagnosis: detection at both ends, nothing in the middle

The pipeline has two detectors, and the gap between them is exactly where design
duplication lives.

| when | what runs | what it can see |
|---|---|---|
| item creation | `check_scope_overlap.py` | paths named by hand, before any code exists |
| *(the gap)* | nothing | |
| integration build | `integration.py build` | a merge conflict, or a suite that breaks |

Two branches defining the same abstraction in differently named files are structurally
invisible to both. The first runs before either has written anything. The second sees no
conflict, because there is none - the files differ, so the merge is clean and the suite
passes. That middle window - both branches have code, neither has landed, no textual
collision - is unmonitored.

`scope-decision.md` already names the fix in prose: "compare by purpose, not only by
path." But it is a manual instruction to read every candidate branch's changed-file list
and judge intent, run once at item-creation time. The step most often skipped, by its own
admission. Making it mechanical and continuous is this plan's first half.

## The second diagnosis: reconcile is the only verdict without machinery

`/integration-conflict-triage` produces five verdicts. Four have somewhere to go:
`defer` records a resolution into the replay cache; `stack` is a base change the
maintenance pass already makes; `adapt` is fixed outright; `sequence` is recorded and
waits. `reconcile` - the verdict that means two branches are building the same thing -
is "propose, do not apply", and there it stops.

That is not an oversight in the skill. It is correct that a design call is not a script's
to make. But the *consequence* of the call - cut a shared parent, move the abstraction
onto it, retarget both bases, restack both branches, delete the loser's copy - is
entirely mechanical, and leaving it manual is what makes the verdict too expensive to
act on. The fix is not more judgement. It is giving reconcile the automation the other
verdicts got.

## Why the two graphs are not a third feature

The user asked for a graph of where each pull request lies and a graph of the classes and
what each does. These are one index viewed twice. Nothing can be compared across branches
without a machine-read record of what each branch introduces; once that record exists,
both graphs fall out of it. Building the graphs first would mean hand-maintaining their
data, which is the drift this system exists to avoid.

## Decisions

1. **The catalogue is derived, not written.** `ast` over each branch's diff. A
   hand-written or model-summarized record drifts the moment a session forgets to update
   it, and the whole system's philosophy - visible in `plan-schema.md`'s "why status is
   deliberately thin" - is to derive what can be derived and never store it. `AGENTS.md`
   mandates docstrings and dataclasses, so the derived catalogue is rich for free.

2. **No model call in the detector.** Scoring is deterministic: name equality, path
   equality, normalized name similarity, docstring-summary token overlap. It runs in CI,
   costs nothing, and is reproducible. It reports ranked pairs and no verdict, keeping the
   existing split where a script gathers evidence and a skill judges it.

3. **Non-Python files are catalogued too.** The #110/#106 collision was two sessions
   building the same markdown artifact under two names. A Python-only catalogue would have
   missed the very case that motivates this plan.

4. **Extraction and direction-change are one command.** Both are "give these branches a
   new common parent"; the only difference is whether files move onto the parent first.
   Modelling them separately would duplicate the restack logic - which would be this
   plan's own failure mode.

5. **Probe before apply, always.** `git merge-tree --write-tree` costs nothing and mutates
   nothing, so the cost of a direction change is knowable before committing to it. The
   user asked specifically to be able to decide against it; that is only possible if the
   cost is cheap to compute.

6. **Writing to feature branches is a deliberate exception, approved 2026-09-06.**
   `integration-conflict-triage` never writes a fix to a feature branch, and that rule
   stands for the integration build. `common-parent` breaks it knowingly, bounded by an
   always-available non-mutating probe and by requiring `--include-reviewed` before it
   touches a branch whose pull request has left draft - resetting an approval is a real
   cost and should never be silent.

7. **Freshness is tied to the dashboard publish, not to the scheduled Action.** The Action
   would be better, but `integration-refresh.yml` is unlanded on `integration`; taking a
   dependency on it would block this plan on that one. Rebuilding on publish means the
   index is current whenever anyone looks at it, which is the case that matters. Wiring it
   into the Action is a later item, not a prerequisite.

8. **Reusing tracking issue #102** rather than minting a new mailbox. Seven workflow
   tooling plans already share it; a new one would fragment the channel sessions subscribe
   to.

## Known collision hazards, from the scope check at creation

Recorded because this plan is about exactly this, and running the check on its own
creation is the honest thing to do.

- **#185** moves every `.claude/` Python module into the `bastler` package. Every Python
  item here lands in files it moves. Whichever lands second re-applies its delta in the new
  location - the pattern #111 already exercised. Check #185's state before starting
  `definition-catalogue`, not after.
- **`templates/dashboard.html` has four open editors**: #218 (Pages site), #206 (refresh
  button), #157 (hide deferred items), #111 (state chips). `plan-graphs` should be cut
  after as many have landed as possible, and its scope check re-run at kickoff. #253
  (cross-plan `depends_on`) changes the edge data it reads.
- **#282** already comments on branches an integration build leaves out. The post-review
  re-check in `skill-wiring` may belong there rather than as a third surface; decide at
  kickoff.

## Sequencing

`definition-catalogue` first: it establishes both the catalogue and the git plumbing for
reading revisions across branches. `overlap-detector` builds on it. `common-parent`
depends on the catalogue only for that plumbing - it is otherwise independent, and could
run in parallel with the detector. `plan-graphs` needs the detector's output.
`skill-wiring` is last because it wires both halves together.

The one deliberate serialization is `common-parent` after `definition-catalogue`. It
needs nothing from the catalogue functionally, but both read revisions across branches,
and letting them build that separately would duplicate a git-command runner - which is
the thing this plan exists to prevent.
