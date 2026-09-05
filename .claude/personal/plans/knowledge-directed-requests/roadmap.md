# Knowledge-directed perception: query language and method selection

One of three successors to `knowledge-directed-perception`, split on 2026-09-05 for
`plan-size-limits` (tracking issue #200). **See `knowledge-directed-grounding`'s
roadmap.md for the programme-wide why, the three waves, the deadline budget, the shared
"stacked on, never waiting for a merge" and "demo merges into `tracy_icra` as soon as it
works" rules, and the sequencing decisions this plan inherits.** Per-round implementation
narrative about already-built items is compressed into each item's own `notes` in
`plan.yaml`; the full predecessor roadmap stays reachable in the personal-notes branch's
history immediately before the split commit.

## Standing correction: "unmerged" is not "unusable"

Recorded independently on `choose-detection-method` and `detector-parameters-from-
knowledge`, both corrected 2026-08-31: an earlier note on each read krrood's RDR/EQL
refactor stack's *merge* state as its *usability*, which contradicts this plan's own rule
that `depends_on` means stacked on, never waiting for a merge. The EQL-native rule trees
are usable on `main` today; `EQLSingleClassRDR` and the rest of that stack (`#159 -> #210
-> #79 -> #76 -> #80 -> #77`) are open, out of draft and reviewed, so an item stacks on
them directly rather than waiting for them to land. Only the classic
`krrood.ripple_down_rules` machinery (source-string conditions, an `Expert` required for
every mutation) is genuinely unusable. Worth checking again before assuming any item in
this plan is blocked on that stack.

## Standing convention: measure cost as a ratio to a same-run baseline

First recorded on `pieces-looked-for-where-expected`: an absolute-seconds reading of
`detect`'s per-frame cost is not reproducible, because this container's own speed moves
between runs by more than the difference being measured. Every cost comparison in this
plan from that item onward is stated as a ratio against a baseline measured in the same
run (e.g. "1.08x the parent", "0.25x an unnarrowed look"), never as a bare number of
seconds.

## The krrood CI bisection: `test_each_lib` red from `perception-backend` onward

`perception-backend` (#222) is the first branch in this plan's stack that adds krrood
tests, and every branch stacked on it inherited a red `test_each_lib` check -
`test_draw_evaluated_tree_for_drawer_cabinet_rdr` is an order-dependent test on `main`
itself (it depends on file output an earlier test in the same file writes, which lines up
by luck outside `pytest -n auto`'s worker distribution but not inside it); `#222` changed
the count `xdist` distributes by and is what first exposed it. Root-caused and recorded as
a blocker on `perception-backend` rather than fixed here: the fix is `main`-branch #251
(open since 2026-09-03), which every branch in this stack needs merged before the check
clears. A second, duplicate fix (#269) was closed in favour of #251; #269's other two
changes are not needed for this check.

## Standing design: `PlacementRelation` and `Relation`, and where each narrowing decision lives

`search-clipped-to-a-predicates-region` introduced `semantic_digital_twin.
PlacementRelation` (a relation that answers the stretch of world it leaves, and whether
one place satisfies it, exactly rather than from a box) and krrood's `Relation` (a
predicate asserted about one subject, of which `Triple` is the two-operand case) to widen
spatial-predicate clipping from the two relations `perception-predicates-guide-the-search`
could read to every placement relation. A direction (`left of`, `above`, ...) is read from
where the *camera* stands, via `RgbdFrame.point_of_view`, not from the world's own axes -
without this a camera-relative direction narrows nothing, since no axis-aligned box holds
a half space across the world's axes.

`expectations-from-events` tried subclassing `Match` as `StatedRelation` to carry a
relation's own equality, and the developer reversed that decision explicitly ("I don't
think inheriting from match is the right approach here ... use match instead of stated
relation altogether"): a relation asserted about the thing sought is now an ordinary
entity-query-language `Match` over the relation's own class, with value comparison stated
explicitly at the two call sites that need it rather than an overridden equality on the
type itself. Worth knowing before reusing the `StatedRelation` shape anywhere else in this
plan.

## Open, at the developer's own discretion (not this plan's to resolve)

- `predicates-answer-whether-they-hold`: whether `Reachable`'s subject reads as *"a
  HomogeneousTransformationMatrix is reachable by a Body"* or as `montessori-eql-stack`'s
  own wording, once that stack rebases here (review thread r3896606294).
- `choose-detection-method`: whether an unmet look should ask krrood's `Expert` for a new
  rule, which needs the expert interface still on the unmerged RDR stack rather than on
  `main`.
- `search-clipped-to-a-predicates-region`: the demonstration's own call shape
  (`show_step_by_step(query)` versus the statement-first shape it actually took), accepted
  by the developer on 2026-09-02 and left open only because resolving it is his call to
  make, not this plan's.
- `how-to-look-concluded-from-the-request`: three mechanisms put back to the developer
  rather than built - wiring one detector per *part* of a description; conditions stated
  in the twin's own vocabulary for this detector family (waits on
  `imagination-world-rejects-what-a-predicate-refuses`); and this family conditioning on
  the sensor itself, since a request's rules are stated before any frame exists.
