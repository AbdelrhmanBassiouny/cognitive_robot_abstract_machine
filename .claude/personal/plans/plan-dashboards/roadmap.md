# plan-dashboards — Roadmap

Narrative companion to `plan.yaml`. Kept short on purpose: the size budget this split was made
under counts these lines.

## Where this plan came from

Split out of `workflow-unification` on 2026-08-30, under `plan-size-limits`'
`split-workflow-unification`. That plan had reached 59 items and 16,917 lines across its manifest
and roadmap, well past the 15-item / 2,000-line budget, and became seven plans seamed on subject.

This plan is the `dashboards` track, carried across unchanged. Every item keeps its branch, pull
request number, status and session verbatim. **The full predecessor roadmap remains in the
personal-notes branch's history**; what is kept here is what binds future work.

## Why this work exists

Two dashboard pipelines existed - a stack board and the plan dashboards - each fetching pull request
state and rendering it. The one-dashboard decision of 2026-07-31 retired the board: GitHub's native
stack map covers derived stack mechanics, so the plan dashboards are the single surface. That made
this renderer the only page anyone reads about in-flight work, and its computation bugs stopped
being cosmetic.

Most items here are bug fixes with the same shape: a predicate that was *nearly* right, whose
failure inverted the intent rather than merely narrowing it. Dependency-free items dropped out of
the ready list entirely; a dependency becoming more finished made its dependent look less reviewable;
an item stacked on a dead base had no signal anywhere. Each was fixed on its own root cause, one
pull request each, per the standing rule for bug fixes.

## Decisions this plan inherits

Numbering is the predecessor's, kept so cross-references in item notes still resolve.

**5. The plan data model and the stack data model stay separate.** The board is derived mechanics
now - pull request bases and git ancestry; plans are intent over time, with waves, tracks and
dependencies. Only the fetch and render layer unifies, which is what `shared-pr-state-chips` is.

**3. Portability.** A plan without an upstream configured renders no promotion group and no links;
no repository is named outside configuration defaults.

**13. The bastler pivot inverted one dependency.** `shared-pr-state-chips` no longer creates the
tooling package - `bastler-package` does, off main - so that branch rebases onto it and folds its
modules in under the package's naming. What stays this item's own is the feature half.

## Conventions this track settled

- **Whichever lands second merges.** Seven items here edit `build_dashboard.py` and its template with
  no dependency between them. That is textual overlap, not ownership, and it has been the working
  arrangement throughout.
- **Bug-fix pull requests carry the `bug` label; tooling that never existed does not.** An item that
  *surfaces* bug fixes is not itself a bug fix.
- **Wording is not pinned by tests.** Twice a round added a test asserting a rendered sentence, and
  twice the user cut it: nobody parses a drift description or a summary line, so pinning the sentence
  buys a failing test per reword and catches no defect. What survives asserts that each case renders
  *something*, and pins rules rather than phrasings.
- **Check the neighbours before defending a guard.** Three rounds argued about one test, and what
  ended it was reading how the module already treats the identical pattern - not reasoning about what
  the test was worth.

## Landing hazards

- **The formatter's non-convergence is positional.** An attribute docstring directly before a
  decorated definition makes `docformatter` drop a blank line, `black` restore it, and
  `format_docstrings.py` discard the lot - so the whole file is silently declined. Two changes here
  hit it by placing a new class at exactly that adjacency, and the fix both times was placement.
  `stack.py` is in the identical state and is left alone.
- **The package extraction moves this file wholesale.** Every open item here merges main across that
  move and re-applies its delta.
- **Screenshots are binary and regenerated from the committed example**, so two branches that both
  regenerate them conflict. Whoever lands second re-regenerates, which is mechanical since the image
  is deterministic from the fixture.

## Open

- **No automated audit of the dashboard URL cache.** The recording fix validates at write time and
  nothing re-checks later, and an entry has already gone dead on its own afterwards. Worth having,
  because a stale entry costs a duplicate artifact rather than an error.
- **No recorded rule for an ambiguous title.** The recorder refuses when two artifacts share a plan's
  title and demands an explicit URL, which is right, but leaves the caller with nothing to choose by.
  Most-recently-updated is what both hand corrections have used.
- **Cross-plan dependencies are not representable.** Two items here have real preconditions in other
  plans, recorded as blockers rather than `depends_on`, so they lose their dependency chips and
  automatic readiness. A `<plan-id>:<item-id>` reference in the schema would restore it - code rather
  than data, and a candidate item for this plan.
