# Branch `claude/robot-perception-understanding-auif6i`

**This branch carries no code and needs no pull request.** The session's work
was a planning pass over the three ICRA plans, and all of it lives on
`claude/personal-notes` (plan.yaml + roadmap.md), not on this branch. If code
work starts here later, re-cut it from `main` first - the SessionStart hook
flagged that it descends from `integration`, which is not a valid pull-request
base.

## Done 2026-09-08: the ICRA plans refocused on the shared representation

Recorded in full on tracking issue #252
(https://github.com/AbdelrhmanBassiouny/cognitive_robot_abstract_machine/issues/252#issuecomment-5582757730)
and in each plan's roadmap.md under its "2026-09-08" section.

- Thesis restated in all three plans: one knowledge representation and one
  query language across perception (any backend), control (as optimization
  constraints), event segmentation, working memory and long-term memory.
- `episode-artifacts-recorded` lost its dependency on
  `simulated-camera-feeds-perception`, which frees the whole long-term-memory
  track from lane 1. That is the one edge that changes who can work on what.
- Five items added (33 -> 38, all three plans under the 15-item cap):
  `episode-corpus-generated-at-scale`, `perception-backends-are-interchangeable`,
  `control-constraints-and-degrees-of-freedom-queried`,
  `question-set-answered-from-memory`, `resource-cost-measured-per-system`.
- The control item was rewritten the same day at the developer's second
  correction: building statecharts from queries has never been implemented and
  is far larger than the week holds. What was wanted is a read - ask a task for
  its GiskardConstraint objects and for the degrees of freedom it used, fixed or
  ignored. ConstraintCollection, NodeArtifacts.constraints and
  Scalar.free_variables() already hold all of it; only the reach (private
  attributes, only the current statechart kept) and the naming are missing.
- A sixth, `self-model-and-control-state-recorded`, was added and folded the
  same day at the developer's challenge: ORMatic already maps World, Body,
  Connection, DegreeOfFreedom and the whole giskardpy motion statechart by
  default, so all that was missing is two references on #271's own Episode
  model - that PR's work by the scope rule, not an item. Correction recorded
  on #252 and in icra-foundation's roadmap.
- Question set widened to six buckets (self-model and control added), every
  bucket spelled over both working and long-term memory, each labelled by
  Bloom level.
- All three manifests saved and all three dashboards republished.

## Next, if this session continues

- Nothing is outstanding from the refocus itself.
- The budget table still says 2026-09-15 and was deliberately not re-cut -
  that is the developer's call, and it is the one open item.
- The natural next action is `/plan-item-kickoff icra-evidence
  question-set-and-ground-truth`, which everything downstream is written
  against, on a branch cut from `main`.
