# how-to-look-concluded-from-the-request (#266, draft)

Plan `knowledge-directed-perception`, track `request-language`. Based on #239
(`claude/knowledge-directed-perception-detector-zrm57t`), which merges #159
(`EQLSingleClassRDR`) in. Both dependencies (#231, #239) report `open_ready`.

## The plan, and it held

Make *how a look is answered* a rule tree over the request, instead of the two
hand-written steps in `MontessoriPerceptionPipeline.detect`.

1. `RequestedLook` — the plain properties a rule reads about one request.
2. `WayOfLooking`, with `FindTheBoard` and `FindThePieces`, each stating the requests it
   answers as an entity query language condition.
3. `LookRules` — `EQLSingleClassRDR` over `RequestedLook`, authored by fitting known
   requests through an expert that reads the condition off the way being fitted.
4. The pipeline drops `board_detector` and `detector_rules` for one `look_rules`; six
   fields become five, and a way of looking is handed `SceneToSearch` and nothing else.
5. A test grows the tree at runtime and fails if the tree is rebuilt where it is read.

## Done

- Branch re-cut off #239's tip (it arrived cut from `integration`), #266 opened as a
  draft, `plan.yaml` and `roadmap.md` recorded by hand (`plan_item_bootstrap.py`'s
  four-space item indent still does not match this plan's two-space manifest — eighth
  round).
- All five steps built and pushed as `118fb140`.
- **412 passed, 1 skipped, 16 xfailed** against **397/1/16** on the parent, in a worktree
  with its own `*/src` on `PYTHONPATH`. The 15 added and nothing else moved.
- Three mutation checks, each failing its own test and nothing else.
- `scripts/format_docstrings.py` over every touched file.
- PR description rewritten to match what was built; roadmap section appended; dashboard
  republished.

## Findings worth carrying

- **A rule concluding a collaborator cannot be persisted.** `EQLSingleClassRDR` saves its
  model as Python source on every fit, and the serializer spells only enum members,
  numbers, strings, bools and `None`. `NullModelSaver` states that. **#239 will meet the
  same wall** when it concludes a `DetectionParameters`.
- **A capability claiming too much is refused when the rules are built**, not at look
  time: the fit stops converging. Recorded rather than pinned, since it pins the engine's
  convergence rule rather than this item's claim.

## Next

Nothing outstanding on this branch. It is a draft awaiting review; the item stays
`in_progress` until it is reviewed.

## Deliberately out of scope

- `headroom` — #239's to conclude, and its `DetectionParameters` is still unbuilt there.
- Skipping the board pass for a piece request — it would misattribute a piece on the lid
  to the table, since the board detection supplies the surfaces' extents.
- Narrowing the candidate pieces from the request — #239's widening; #232 moved the
  seeded half onto the belief.

## Open

- The tracking issue (201) subscription was refused by this session's permission
  classifier, and the artifact watch could not be armed either, so this session sees no
  events for either. Read the tracking issue's comments directly before any later round.
