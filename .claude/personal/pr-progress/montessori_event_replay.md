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

**Next.** No PR opened yet. Untouched, worth telling the developer: the
`cramera/scenes` submodule has `Franka_Montessori/` untracked while `index.json`
lists it, and that `index.json`'s `default` still names the missing
`pr2_kitchen`.
