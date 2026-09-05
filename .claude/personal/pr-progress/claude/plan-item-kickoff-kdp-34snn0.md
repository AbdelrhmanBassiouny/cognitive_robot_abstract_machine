# `surfaces-found-by-looking` - PR #259 (draft)

`knowledge-directed-perception`, `method-selection` track. Branch
`claude/plan-item-kickoff-kdp-34snn0`, off **#231** - not #222, because
`WorkspaceSurface.finish` and the capability/rule-tree mechanism are #231's.
`depends_on` records `choose-detection-method` alongside #222 and #216.

## Built

- `surface_finding.py`: `SoughtSurface`, `SurfaceFinder` +
  `ModelledSurfaceFinder`/`MeasuredSurfaceFinder`, `SurfaceRules`.
- `pipeline.table_in(frame)`, used by `detect` and by the drawn windows;
  `rectify` takes a surface, `searched_surfaces` takes the table it searches.
- `recorded_setup` states that Tracy's table is brushed steel.
- `orthophoto`: `ImageWindow` + `WorkspaceBox.window_in`, with `clip` rewritten
  in terms of them.

## Measured

- Searched stretch 0.635 m2 (tuned) -> ~0.51 m2, and the untuned 1.2 m2 reaches
  the **same** answer on all six captures. The tuning no longer decides.
- 5/6 captures bit-identical to the parent; the 6th moves one prism 0.15 mm /
  0.02 agreement, a two-valued fit that exists on the parent too.
- `detect` 1.07x the parent, same-run interleaved. Measurement 0.061 s/frame.
- 430 passed / 1 skipped / 16 xfailed vs 390 / 1 / 16 on the parent.

## Review round of 2026-09-05

Five threads. Answered in code as `946017c70`: `SoughtSurface` was a copy of the
surface's finish, a constant that was always true, and a frame property. It now
holds the `WorkspaceSurface` and the `RgbdFrame`, and the conditions read into
them. EQL traverses nested attributes and properties (probed first) - so the
flattening in `TargetOnSurface` and `RequestedLook` was never needed either.
`carries_depth` moved onto `RgbdFrame`, `area` onto `WorkspaceRegion`, and
`find` takes the pair. One test added, pinning that the finish deciding a look
is the one a twin Body's own collision shape states.

### Second pass, same day: the developer answered, and two items are added

He answered three of the four threads I had left open, all with "add the plan
item". Both are now in the manifest and `roadmap.md`, and those threads plus the
one he routed ("Answered in the rdr thread") are **replied to and resolved** -
four of five:

- **`a-look-is-described-by-a-match`** (`method-selection`) - the description a
  rule tree is stated over becomes an underspecified `Match` over the twin's own
  entities, read by an EQL-based RDR on the #77 stack. Removes `SoughtSurface`,
  `TargetOnSurface` and `RequestedLook`, so `depends_on` names all three owning
  items. Not folded into any of them: #159 is 9,236 lines over 50 files, #77 is
  22,745.
- **`camera-pose-fitted-to-the-model`** (`method-selection`) - the calibration
  thread and the combine-the-finders thread folded into one at his direction,
  since both are the same third `SurfaceFinder`. Carries the three measurements
  that cut against the obvious version: ~1 mm of transform error in z here,
  #236's 0.865 board being a wrong *model* not a wrong pose, and the two finders
  being layered rather than independent.

**One thread stays open**, answered differently: the finish belongs on the twin's
body, and it does - #239 states it for the world, and #238's `recorded_world`
already has the bodies, so the fold there is one line rather than a third copy
written here.

## CI - both red checks belong elsewhere, bisected

| branch | krrood | sdt |
| --- | --- | --- |
| `main` | green | green |
| #221 | green (23/23) | green |
| #222 | **red** | green |
| #231 | **red** | green |
| #259 | **red** | **red** |

- **krrood is #222's.** #221 green on all 23, #222 red on krrood alone, and #222
  is the first branch in the stack to touch krrood; the failing test file is
  byte-identical to `main`, which is green. Reported on #222 with a proposed
  first step (`raise RDRLoadError(...) from e`, which is why CI shows no cause),
  and recorded as a blocker on `perception-backend` - whose blocker had gone
  stale claiming "green on all 23 checks".
- **sdt is `conftest.py`'s module-scoped `count_worlds`**, 1494 passed and no
  failing assertion, attributed to whichever test ran last. #231 is green on that
  job with identical sdt sources; this diff is experiments-only.

Correction comment posted on #259, since my earlier one said krrood was green
here.

## Outstanding

- `tune_workspace` used by nothing but its own tests; removal **asked on the
  PR**, not taken.
- The finish-on-the-twin thread, open for the developer.
- Tracking-issue subscription refused by the permission classifier, so this
  session sees no structural plan changes as they arrive.

Per my notes: opening the PR ends this session's obligation to it. No watching,
no scheduled checks.
