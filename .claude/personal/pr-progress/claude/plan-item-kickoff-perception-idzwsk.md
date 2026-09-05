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

## Open, for the developer

- Wiring a detector per *part* of one description (thread r3941256826).
- Conditions in the twin's own vocabulary for this family — waits on #255 making a detection
  a `Role` over a world entity (r3941290762).
- This family conditioning on the sensor: its look would have to carry what the *source*
  offers, since the rules are stated before any frame exists (r3941305756).
- The remote branch was merged forward by a maintenance pass mid-round; that merge is in.

## Deliberately out of scope

- `headroom` — #239's to conclude.
- Skipping the board pass for a piece request — would misattribute a lid piece to the table.
- Narrowing the candidate pieces from the request — #239's widening.
- `SUPPORTING_SURFACE_ATTRIBUTE_NAME` in `backend.py` — the same smell, #227's to remove.

## Note

The tracking issue (201) subscription and the artifact watch were both refused by this
session's permission classifier, so it sees no events for either. Read the tracking issue's
comments directly before any later round.
