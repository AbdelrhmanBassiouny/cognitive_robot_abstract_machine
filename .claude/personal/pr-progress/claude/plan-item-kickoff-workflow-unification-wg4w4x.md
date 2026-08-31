# `integration-branch-ci-verdict` — getting the pipeline publishing again

Working PR #211 on `claude/plan-item-kickoff-workflow-unification-wg4w4x` (the
session's own `claude/integration-pipeline-ci-verdict-50sx6b` is unused; you
named #211's branch explicitly).

## The plan, in the order it had to happen

1. **Discriminator before the base.** `find-candidate` told the candidate a run
   settles from a `--plan` one by its base alone, so the base could not move
   until something else carried that. — **done**, `CandidateTitle` in
   `integration_verdict.py`.
2. **The base.** Every candidate opens against `configuration.upstream_base`,
   which a build merges with by construction. — **done**.
3. **Close and move past.** `CANDIDATE_UNCHECKED` closed the run; it now closes
   the *candidate* and assembles the build that replaces it, still exiting 17. —
   **done**, `close-candidate` plus `RefreshPipeline`.
4. **Bootstrap, two dispatches.** — **first dispatch spent**, second outstanding.

Committed as `c77b9ea79` and pushed. 967 tests across the four CI directories,
from 956; seven mutations checked; docstrings formatted, byte-identical on a
re-run. Not re-drafted, deliberately.

## Where it stands

- "Integration refresh" dispatched on this branch (the only arm running the new
  pipeline — every trigger is read from the copy on `integration`, a build
  output). It assembles and opens a candidate, then stops.
- **Not polled and not subscribed**, per your standing rules. The verdict is
  read by a *later* run.

## Next, when you come back to it

1. Read the build's `left_out` and confirm it carries #211 and #154 — expected,
   never yet measured. The publish guard refuses a build with no rebuild in it.
2. Confirm the candidate has a merge reference and checks (the whole point).
3. Second dispatch to settle and, if green, publish.

## Two things measured that correct the record

- `#154` is based on `main`, not `#151`'s branch, and `#151` is not a draft — so
  the "rooted on a draft, left out entire" hazard recorded on the item does not
  apply.
- `plan_item_bootstrap.py update` writes item fields at a hardcoded four-space
  indent, so replacing this item's `blockers` produced a manifest that no longer
  parses. That is the `ItemIndentation` fix `manifest-currency-first` (#151)
  already records against its own branch — #151 introduces `update`, so it is
  the only branch that can test one. **Not folded in here**, reported instead.
  Every manifest write this session went through a hand-edited splice plus
  `save-plan.sh`. Your call whether it belongs here.
