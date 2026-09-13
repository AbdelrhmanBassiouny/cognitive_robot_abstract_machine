
## Branch `claude/experiments-film-memory-q7mx2v` - PR #354 (draft) - experiments CI memory: fixed, awaiting CI

Base **`claude/icra-experiments-simulation-pipeline-w4ep7n` (#265)** - reparented from
`claude/coraplex-ci-hang-ckj3nh` once #350 merged into #265 on 2026-09-13 (d74ba45937).
Label `bug`. Commits: 7f5e9376dd (the film change), 92f988873f (merge of #265's later
work), 362b2b6c7d (the scene-file race, see below).

**Root cause**: `SimulationFilm` kept every frame it drew in a list until the run was
over - 960x540 at 15 fps, two films a run, nothing released. Measured at that resolution,
a 60-second film peaks at 1376 MB of memory kept whole against 42 MB written as it goes.
`test_tracy_pickup_demo_mujoco.py` performs two whole runs in module-scoped fixtures, both
alive at once on a two-worker runner, so the runner is SIGKILLed inside the module: exit
137 with no pytest summary on #346, #348 and #349.

**The change**: `FilmBeingTaken` in `experiments/episodes/trace.py` encodes each frame
into its video as it arrives and keeps nothing of it but the moment - the write-side
counterpart of the existing `TimedFramesFile`. The run gives its two films a temporary
file each and copies them out in `keep()`/`write_artifacts()` rather than re-encoding.
`FramesByMoment` now declares the `write` both implementations already had.

**CI so far**
- `7f5e9376d` (film change alone, pre-merge base): experiments job **green**, 32m27s,
  job 103722075125. Every changed tracy assertion passed, on gw1.
- `92f988873f` (after merging #265): 1 failed, 1688 passed in 29m56s -
  `test_montessori_watched_run.py::test_a_watched_run_keeps_a_trace_of_its_joints_with_the_episode`,
  `ValueError: Error: keyframe 'home': invalid qpos size, expected 0, got 43`.
- `362b2b6c7d`: pushed 2026-09-13 ~13:30, not yet read.

**The second root cause (362b2b6c7d)**: `MujocoSim` writes the world to
`default_file_path` and reads it back to compile it; the default is `/tmp/scene.xml`,
shared by every xdist worker in the container. At 12:42:44 gw1 was in the failing test
while gw0 finished a `test_paper_scene_render.py` render in the same tenth of a second -
both build a `MujocoSim`. The base's new scene-render tests made the collision likely.
`test_adapters/conftest.py` already solved this for the sdt tests; moved to the root
conftest so every suite gets it, reading the worker off
`PytestEnvironmentVariable.XDIST_WORKER`. `test_multi_sim.py` gained a test that the
scene path is inside this worker's own temporary directory. **Bundled into #354 rather
than split** because it is what stands between the PR and a green run - offered in the
description and in chat to lift it onto its own branch instead.

Noted but untouched: `MJCFParser.from_xml_string` hardcodes the same `/tmp/scene.xml`;
only the robocasa loader and sdt's own tests reach it.

**Verified locally**: the four new film tests and the seven existing camera tests in
`test_episode_trace.py` pass against the real `trace.py`, before and after the merge
(numpy + imageio installed into this container by hand; the rest of the workspace is not
installable here). The race fix could not be run here - no mujoco - so it goes through CI.
Caught before pushing earlier: the encoder rounds 540 up to 544, so the first draft of the
tracy frame-shape assertion would have failed in CI.

**Next step**: the user asked for #354 to be folded into #265 once CI is green, and chose
to ping rather than have a check armed. Nothing is armed. When told it is green: merge
`claude/experiments-film-memory-q7mx2v` into
`claude/icra-experiments-simulation-pipeline-w4ep7n` and close #354.

