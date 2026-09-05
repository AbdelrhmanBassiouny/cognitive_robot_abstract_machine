# how-to-look-concluded-from-the-request (#266, draft)

Plan `knowledge-directed-perception`, track `request-language`. Based on #239
(`claude/knowledge-directed-perception-detector-zrm57t`), which merges #159
(`EQLSingleClassRDR`) in.

## Round one: the rule tree (118fb140)

Made *how a look is answered* a rule tree over the request instead of the two hand-written
steps in `MontessoriPerceptionPipeline.detect`. 412/1/16 against 397/1/16 on the parent;
three mutation checks, each failing its own test.

## Round two: the review of 2026-09-05 (0bb9aa89a)

Four threads, one ask with four faces, all four replied to and **none resolved** — each has
a half answered differently, and the standing rule is to leave those for the developer.

- **No case class, no attribute-name string.** `RequestedLook` and
  `WAY_OF_LOOKING_ATTRIBUTE_NAME` are gone. The rules come from
  `from_underspecified(a(SceneRequest)(detector=...))`; conditions are stated over the
  request, and the two a rule reads are properties derived from its `detection_type`.
- **One detector concept.** `PerceptionDetector` in krrood beside `PerceptionBackend`,
  binding the kind of look it answers as a type parameter. `PieceDetector` (#231) had its
  own copy of the same four members and now inherits it. `WayOfLooking` → `SceneDetector`,
  `take` → `detect`.
- **krrood gained a mimic family and six tests**, so the concept is exercised without the
  demo — and the mimic is where conditioning on what the sensor provides is shown.
- 414/1/16 experiments against 412/1/16 on the previous tip; 1554/3 krrood against 1548/3.
  Both baselines in a worktree with its own `*/src` on `PYTHONPATH`.

## Findings worth carrying

- **A rule concluding a collaborator cannot be persisted.** The serializer spells enum
  members, numbers, strings, bools and `None`. **#239 will meet the same wall** when it
  concludes a `DetectionParameters`.
- **`from_underspecified` is on #159, not #77** — half of `a-look-is-described-by-a-match`'s
  premise is wrong, and that item's notes are corrected. It only lacked a `model_saver`.
- **A case class was never needed for the engine's sake**: EQL traverses nested attributes
  and property reads. Second item in two days to spend one on a constraint that is not there.
- **A detector must state identity comparison itself** once it is a dataclass, or `add()`
  refuses to conclude one.

## Round three: the second review of 2026-09-05 (0063f9824)

Two threads about the concept in krrood, both answered exactly and **resolved** — the first
resolves on this pull request.

- **`LookT` is bound to `Look`**, the question put to perception. Not an empty marker:
  `LookRequest` is one too, so `Look` / `LookRequest` stop reading as two names for one thing.
- **`asked_about` replaces `answers`**, returning the detector's own standing query. Renamed
  rather than retyped, because a `Query` is always truthy and `if detector.answers(look)`
  would have been silently true forever.

1311/3 krrood eql, 414/1/16 experiments unchanged.

## Open, for the developer

- **The two-stack merge**, which is what three of the open asks actually need. Not only #255's
  `Role`: #227 gives the backend a statement's relations in place of an attribute name, #238
  makes a relation answer the stretch of world it allows. Merging #255 supplies all three —
  measured at 68 commits, 62 files, +8,613/−752, seven conflicted files. A re-base is not
  available as it was for #257, since #231 and #239 must stay beneath this branch.
  Recommended, not taken (r3941601972).
- Wiring a detector per *part* of one description (r3941623073) — answered in
  `icra-experiments`' `query-routed-per-predicate`, one level up (among backends, not among
  detectors). Proposed as an item of that track, not added. Waits on the same merge.
- This family conditioning on the sensor: its look would have to carry what the *source*
  offers, since the rules are stated before any frame exists (r3941305756).
- The remote branch was merged forward by a maintenance pass mid-round; that merge is in.

## Deliberately out of scope

- `headroom` — #239's to conclude.
- Skipping the board pass for a piece request — would misattribute a lid piece to the table.
- Narrowing the candidate pieces from the request — #239's widening.
- `SUPPORTING_SURFACE_ATTRIBUTE_NAME` in `backend.py` — **already removed on #227**
  (`narrowing_relations = (SupportedBy,)`); it survives only on this sibling stack and goes
  when the two meet. Recorded there at his ask (issuecomment-5554306138).

## Note

The tracking issue (201) subscription and the artifact watch were both refused by this
session's permission classifier, so it sees no events for either. Read the tracking issue's
comments directly before any later round.
