## cramera live mode draws the whole world, not just the loose objects

**The report.** `./run_montessori_demo.sh` opened cramera showing only the
montessori board and the shapes; the panda and the rest of the room appeared
only after switching the environment picker away and back.

**Root cause (measured, not guessed).** Two independent things:

1. `GET /models` on the live bridge answered `{"models": []}` for this demo, so
   the viewer had no robot/environment geometry to draw at all. The bridge only
   ever knew models it had seen `URDFParser.from_file` read, and this world has
   none: the panda comes from `MJCFParser`, the room is built in code. (The
   URDF-source hook is also installed *after* the demo builds its world, but
   that is moot -- there is no URDF to catch either way.)
2. `cramera/scenes/index.json` names `pr2_kitchen` as its default and no such
   bundle exists, so the landing page (no `?scene=`) loaded no recorded bundle
   either and sat on "Scene failed to load". Switching the picker navigated to
   `?scene=Franka_Montessori`, which does exist -- the workaround.

**The fix.** The bridge writes the running world's own geometry as URDF when no
parsed source describes it, and serves it through the endpoints that already
existed:

- `cramera/live/world_geometry.py` (new): the robot's branch as a model rooted
  in its base link (the bridge publishes that link's pose separately), and
  everything else as one environment model, minus the bodies the viewer already
  draws from `/objects`.
- `world_to_urdf.py`: mesh references became a strategy (`BundledMeshFiles` for
  a scene bundle, `OriginalMeshFiles` for a live one -- 33 MB of panda meshes
  are not copied per attach), plus `of_branch` for a document rooted in a body
  rather than in a synthesized link.
- `model_source.py`: `ParsedModelSource` infers its identity from the composed
  world's body names as before; `GeneratedModelSource` states it.
- `bridge.py`: writes on the `Executor.tick` hook, the only thread that may
  read the world, whenever the world, the loose objects or the registered
  scene entities changed.
- `panel.js`: a page with no bundle now gets the finishing pass `finalize()`
  gives a recorded one (materials, ground, camera, status), and takes the
  robot's part annotations off `/info` so an answer naming `PandaArm` still
  lights it up.

**Verified.** 477 cramera tests pass (17 new). Ran the demo and looked at
`http://localhost:8711/` in Chrome: LIVE, panda + both stands + board + floor +
shapes, no console errors. Writing the world takes 14 ms.

## Merging the stack (developer's instruction)

The stack turned out to be linear and this branch was already its tip -
`montessori_event_replay` contained `montessori_fast_inline_monitor` already.
What was missing was two commits pushed to `origin/montessori_fast_inline_monitor`
after the local copy: `11311d09e` (scenes pin that carries the bundle) and
`a5b24bb3d` (in-memory results-database fallback).

Committed the live-geometry work as `26f40d36e`, then merged
`origin/montessori_fast_inline_monitor` as `df413937f`. One conflict,
`cramera/scenes`, since both sides repinned it off the dead `2438a523`;
resolved to the incoming `64b98ed`, which is on `cram2/cram-scenes` *and*
carries the bundle, where this branch's `2230683` was that repository's
bundle-less main. Pushed to `origin/montessori_event_replay`.

Deliberately left out, both below the "starting from" point:
`origin/montessori_merge_db_creation`'s one extra commit is only an older
submodule repoint (`014c8796`), superseded; `montessori_thread_safe_reads`
(local only) has 4 of 5 commits in by content, the fifth (`f0e94fb48`) differing
because round 13 ported it with a different resolution - `_read_geometry_out`
is on HEAD as a warm-up, as the round-13 notes say.

**Still open.**

- No PR.
- `index.json` at the new pin *still* names `pr2_kitchen` as its default and no
  such scene exists there (`Franka_Montessori`, `G1_warehouse`,
  `garmi_pick_place`, `pr2_breakfast`, `pr2_pouring`). Harmless for the demo now
  that the landing page draws the live world, but a viewer opened with no demo
  running still says "Scene failed to load". Fixing it means a commit in
  `cram2/cram-scenes`, so left alone.
- The local `cramera/scenes` checkout is still at `2438a52` with
  `Franka_Montessori/` untracked, while the superproject records `64b98ed`. All
  68 bundle files are byte-identical to what `64b98ed` carries, plus one extra
  on disk (`stacking_scene.urdf`). `git submodule update` will refuse until the
  identical untracked copies are removed - the developer's delete to make, not
  mine.
