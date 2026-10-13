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
