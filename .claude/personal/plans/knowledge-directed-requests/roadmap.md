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

## `a-look-is-described-by-a-match`: one mechanism for all three families, and why it is not folded

Kicked off 2026-09-05. The item's own `notes` had already been corrected twice, and the
plan settled after that correction reads: what is left here is *the vocabulary the
conditions are stated in*, not the shape the engine demands. `EQLSingleClassRDR`
takes one case object of one class and infers one attribute on it
(`UnderspecifiedMatch.case_type` is `match.type`, `target_attribute_name` an attribute of
it), so `a(Body)(detector=...)` is not a thing the engine can be handed - a twin entity
carries no detector slot. The achievable and already-validated reading is #266's: a
family states its own `Look` subclass, that subclass *holds* the world's entities instead
of copying values out of them, and conditions traverse into them. That is not a
flattening, because nothing is copied that could drift.

So the work is to apply #266's shape to the two families that still predate it:

- `TargetOnSurface` (#231) copies three values out of `WorkspaceSurface` and `KnownPiece`
  at construction. It becomes a `Look` holding the surface and the target, with the
  readings restated as properties over them, plus the open `detector` slot.
- `SoughtSurface` (#259) already holds the world's own things - that half was fixed on
  #259's own review round - but `SurfaceRules` still builds its tree by hand with
  `entity().where()` and `Alternative.insert_at`. It moves onto
  `EQLSingleClassRDR.from_underspecified` and `SurfaceFinder` onto
  `PerceptionDetector[SoughtSurface]`, which also deletes the `capability`/`stated_surface`
  /`answerable_surfaces`/`answers` quartet each family was re-declaring.

### The scope check, and why it still gets its own branch

`check_scope_overlap.py --base origin/main` reports **every** path this item touches as
absent from `main`: `detector_choice.py` and its test are introduced by #231,
`surface_finding.py` and its test by #259, `look_choice.py` by #266. Read mechanically
that is the fold signal, and the item's originally recorded reason for staying separate
(that it needed #77, the tip of the RDR stack) no longer holds - `from_underspecified` is
#159's, and #239 already merged it into this stack.

It stays its own branch for a different reason than the one recorded: the work modifies
files introduced by *three* different unlanded branches, so there is no single parent to
fold into, and folding one mechanism into three in-flight pull requests would be worse
than the one coherent story. It is where those branches converge.

### Base, and the sibling merged in

Base is `claude/plan-item-kickoff-perception-idzwsk` (#266): the only tip carrying all of
`Look`, `PerceptionDetector` and `from_underspecified`. `claude/plan-item-kickoff-kdp-
34snn0` (#259) is merged in rather than based on, because it carries none of them - it
sits on #231, before the RDR stack entered at #239. The merge conflicts on three files
(`exceptions.py`, `pipeline.py`, `test_montessori_perception_backend.py`) and all three
are additive: both siblings appended to the same region, so both sides are kept.

The cost, recorded rather than hidden: this pull request's diff against its base carries
#259's own 1,235 lines. That is the diamond the two `method-selection` tips make, not
scope creep.

### Not resolved here

The plan's tracking issue (#201) could not be subscribed to - the session's permission
classifier refused the call - so this branch will not see structural changes announced
there. Also inherited, not this item's: `test_each_lib` is red across the whole stack
from #222 onward, waiting on `main`-branch #251 (see `perception-backend`'s blockers).

### The two design calls the item actually turned on, and how they were answered

Both were put to the developer on 2026-09-05 and both took the recommended option; the
second only surfaced once the first was being built.

**A rule's condition is not a capability.** `LookRules` authors its tree with
`state_the_detectors_own_condition`, which answers the engine with the detector's own
capability, and that works there because each of its detectors declares a condition no
other satisfies. Neither family here is like that: both piece detectors answer a look at
a piece colour separates from a matte surface, and both finders answer any surface the
world bounds in a picture with depth. What tells them apart is `surface.finish` --
`MATTE` for the colour blob, `MIRROR` for the measurement -- and that is the *rules'*
knowledge about when a detector is worth its cost (89 ms against 126 ms), not part of
what either says it can answer. #231's own module docstring is explicit that neither part
subsumes the other, so moving the finish onto a capability was rejected. Each rules class
supplies its own expert instead, answering with the capability and'ed with the situation
the rules choose that detector in. `ConditionResolver` cannot stand in for this: it
reuses conditions already in the tree rather than inventing one.

**The situation is read off the case, not hardcoded.** The first build wrote
`finish == MIRROR` into `SurfaceRules` directly, and
`test_a_rule_added_while_the_rules_are_in_use_changes_the_next_answer` caught it at once:
a rule added for a glossy surface got the mirror condition and never fired. The rules'
knowledge is that *the finish* decides; *which* finish is a property of the look the rule
is being stated from, which `CaseContext.case_instance` supplies. That is what makes
`add_rule` work for a finish nobody foresaw, and it is why the general answer (the edge
fit, the model) is the one that carries no situation at all rather than one guarded by a
name.

**Fitting cases need a picture.** `MeasuredSurfaceFinder` asks whether the camera
returned any depth, so a case the rules are fitted from needs an `RgbdFrame`, which
`SceneRequest` never did. `SurfaceRules` builds one-pixel pictures for it: only whether
there is any depth at all separates the kinds of look these rules tell apart, so a single
pixel says everything a rule reads of a picture and nothing is claimed about a scene that
was never photographed.

Behaviour is unchanged by any of it, which is the point: a mirror-finished surface is
still searched by fitting edges, a matte one by colour where colour separates the piece,
and a surface whose finish nothing states is still taken from the model.

### Left standing, and why

`TargetOnSurface.target_outline_is_known` reads `target.outline is not None` over a
`KnownPiece` whose `outline` is typed non-optional, so it holds for every piece the set
contains -- the same shape of defect the item's notes record for `SoughtSurface`.
Removing the flattening does not fix it; it only moves the reading from a copied field to
a property. Whether a `KnownPiece` may have no outline is a question about that type
rather than about these rules, so the guard the edge fit's capability was written around
is kept and the question is left for the developer.