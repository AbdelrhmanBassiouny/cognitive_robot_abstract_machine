# how-to-look-concluded-from-the-request (#266, draft)

Plan `knowledge-directed-perception`, track `request-language`. Based on #239
(`claude/knowledge-directed-perception-detector-zrm57t`), which merges #159
(`EQLSingleClassRDR`) in. Both dependencies (#231, #239) report `open_ready`.

## The plan

Make *how a look is answered* a rule tree over the request, instead of the two
hand-written steps in `MontessoriPerceptionPipeline.detect` (the board detector always
runs; the pieces are searched exactly one way).

1. `RequestedLook` in `detector_choice.py`'s style — plain properties a rule reads about
   one request: whether a shape can answer it, whether the board or a hole can, whether a
   surface was named.
2. `WayOfLooking`, one interface with three members: find the board and its holes, find
   the pieces on each requested surface, find everything (the composite).
3. `LookRules` — `EQLSingleClassRDR` over `RequestedLook` concluding a `WayOfLooking`,
   authored by fitting the three known kinds of request through a scripted expert
   (`FunctionInterface`), readable by `render_tree`.
4. `MontessoriPerceptionPipeline` drops `board_detector` and `detector_rules` for one
   `look_rules`; `detect` asks the rules and runs what they conclude.
5. A test grows the tree at runtime for a kind of request no rule covers, and fails if
   the tree is rebuilt per look — the shape #231's `add_rule` test already pins.

TDD throughout: each part's test first.

## Done

- Branch re-cut off #239's tip (it arrived cut from `integration`), pushed, #266 opened
  as a draft.
- `plan.yaml` recorded (branch / PR / session / `in_progress`) and the roadmap section
  appended, both by hand — `plan_item_bootstrap.py`'s four-space item indent still does
  not match this plan's two-space manifest, eighth time.

## Next

- Step 1: `RequestedLook` and its tests.

## Deliberately out of scope

- `headroom` — #239's to conclude, and its `DetectionParameters` is still unbuilt there.
- Skipping the board pass for a piece request — it would misattribute a piece on the lid
  to the table, since the board detection supplies the surfaces' extents.

## Open

- Nothing blocking. The tracking-issue (201) subscription was refused by this session's
  permission classifier, so concurrent structural changes to the plan will not reach this
  session as events.
