
## Branch `claude/experiments-film-memory-q7mx2v` - PR #354 - MERGED, nothing outstanding

Folded into `claude/icra-experiments-simulation-pipeline-w4ep7n` (#265) on 2026-09-13 at
14:00 UTC as merge commit 62e046bf95, once CI went green on 362b2b6c7d (runs 34759497779
and 34759497806, both success). #354 is closed and merged. Label `bug`. Nothing armed, no
subscription, no open thread.

**What it fixed (two root causes, bundled deliberately)**

1. *The experiments job being SIGKILLed.* `SimulationFilm` kept every frame it drew in a
   list until the run was over - 960x540 at 15 fps, two films a run, nothing released.
   Measured at that resolution, a 60-second film peaks at 1376 MB kept whole against 42 MB
   written as it goes. `test_tracy_pickup_demo_mujoco.py` performs two whole runs in
   module-scoped fixtures, both alive at once on a two-worker runner: exit 137, no pytest
   summary, on #346, #348 and #349. Fix: `FilmBeingTaken` in
   `experiments/episodes/trace.py` encodes each frame into its video as it arrives and
   keeps nothing of it but the moment - the write-side counterpart of the existing
   `TimedFramesFile`. The run gives its two films a temporary file each and copies them
   out in `keep()`/`write_artifacts()` rather than re-encoding. `FramesByMoment` now
   declares the `write` both implementations already had.
2. *A shared MuJoCo scene file.* `MujocoSim` writes the world to `default_file_path` and
   reads it back to compile it; the default `/tmp/scene.xml` is shared by every xdist
   worker. At 12:42:44 gw1 was in
   `test_montessori_watched_run.py::test_a_watched_run_keeps_a_trace_of_its_joints_with_the_episode`
   while gw0 finished a `test_paper_scene_render.py` render in the same tenth of a second;
   the second compiled a scene it had not written -> `keyframe 'home': invalid qpos size,
   expected 0, got 43`. The per-worker fixture that already existed in
   `test_adapters/conftest.py` moved to the root conftest so every suite gets it.

**Proof it was not the film change**: the film change alone was green on `7f5e9376d` (job
103722075125, 32m27s); the scene-file failure only appeared after merging #265's newer
commits, which added the scene-render tests that made the collision likely.

**Left for later, deliberately untouched**: `MJCFParser.from_xml_string` hardcodes the same
`/tmp/scene.xml` and the root fixture cannot reach it. Only the robocasa loader and
`semantic_digital_twin`'s own tests call it, so it was not implicated - but it is the same
race waiting. Also worth knowing: the experiments job still takes ~30 min; the fix was for
memory, not runtime.

