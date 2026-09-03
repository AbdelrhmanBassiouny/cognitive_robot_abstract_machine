# expectations-from-events (#257, draft) - knowledge-directed-perception

Kicked off and built 2026-09-03 in `auto` mode. Branch
`claude/plan-item-kickoff-expectations-2zvpmn`, cut from #232. Full reasoning
is in the plan's `roadmap.md` sections of the same name.

## Done

- Branch cut from #232's tip; **#222 and #246 merged in** (the #222 merge was
  five hunks in `pipeline.py` and `test_montessori_perception.py`, resolved as
  the union #238 recorded; #246 was clean).
- `perception/expectations.py`: `Expectation`, `ExpectedProperty`,
  `ExpectationReport`, `Expectations`, `SUPPORT_AFTER_EVENT`.
- `SceneRequest.expected`; `pipeline.detect` evaluates it beside
  `expected_pieces()`.
- `piece_matcher.offsets_within` - the grid fix a stated reach exposed.
- `LID_PIECES_STILL_MISSED`'s recorded reason re-pointed (no assertion
  changed).
- 482 passed / 453 baseline, failing set identical by name, four rules
  mutation-checked, docstrings formatted, pushed, PR description rewritten to
  match, manifest + roadmap saved, dashboard republished.

## The two things worth remembering

1. **A stated reach exposed a real fault.** Every belief before this one
   reached exactly `SEED_REACH`, so nothing varied a radius. The sweep's grid
   was laid out from `-radius`, so its phase moved with the reach: the cube is
   fitted at 20 mm and 40 mm and not at 24 mm or 30 mm. Same shape as #238's
   lattice finding. Fixed; the "reach is a bound" test caught an overshoot the
   first fix introduced.
2. **The lid marks deliberately did not come off.** Armed, the cube *is*
   fitted in both cube-at-a-hole captures - but at 0.645 against a ghost
   cylinder's 0.641, so which reach works is not stable. Stating a reach that
   happens to work is the tuning this plan refused three times.
   `competing-explanations` owns it, and the marks now say so.

## Next, if anything

Nothing outstanding on the branch. Open for review; the two questions put to
the developer on the PR are the store's placement (experiments vs krrood/sdt,
overturned twice on #222) and whether the re-pointed mark reasons read right.

## Watch out

- **I clobbered 66 lines of #255's roadmap section on one `save-plan.sh`**, by
  building the file from a fetch taken before writing rather than immediately
  before saving - the exact failure the notes warn about. Restored by merging
  their version with mine and re-saving; verified nothing is lost. Fetch
  *immediately* before every save, not at the start of the edit.
- `plan_item_bootstrap.py open` fails here (four-space `ITEM_FIELD_INDENT`
  against this plan's two-space fields, error swallowed by
  `capture_output=True`). Sixth time; manifest edited directly.
- The tracking-issue subscription was refused by the permission classifier, so
  read #201's comments directly. Doing so at kickoff is what turned up
  `icra-experiments`' cross-plan record: this item is the one thing that plan
  still needs and its only critical-path item that had no branch.
- The artifact wake subscription could not register in this session, so a
  republish elsewhere will not notify it.
- #255 renames `MontessoriShapeDetection` across `pipeline.py`,
  `detections.py` and `occupancy.py`; this branch edits `pipeline.py` and
  `piece_matcher.py` and inherits it.
