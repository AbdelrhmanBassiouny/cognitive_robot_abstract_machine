
## Branch `claude/experiments-film-memory-q7mx2v` - PR #354 (draft) - experiments CI memory: fixed

Base `claude/coraplex-ci-hang-ckj3nh` (#350, itself based on #265), label `bug`. One
commit: 7f5e9376dd.

**Root cause**: `SimulationFilm` kept every frame it drew in a list until the run was
over - 960x540 at 15 fps, two films a run, nothing released. Measured at that resolution,
a 60-second film peaks at 1376 MB of memory kept whole against 42 MB written as it goes.
`test_tracy_pickup_demo_mujoco.py` performs two whole runs in module-scoped fixtures, both
alive at once on a two-worker runner, so the runner is SIGKILLed inside the module: exit
137 with no pytest summary on #346 (44 min), #348 (1h21m) and #349 (49 min), after 25-30
minutes of silence. The job takes ~8 min on `main`, which has none of that module.

**The change**: `FilmBeingTaken` in `experiments/episodes/trace.py` encodes each frame
into its video as it arrives and keeps nothing of it but the moment - the write-side
counterpart of the existing `TimedFramesFile`. The run gives its two films a temporary
file each and copies them out in `keep()`/`write_artifacts()` rather than re-encoding.
`FramesByMoment` now declares the `write` both implementations already had.

**Verified**: the four new tests and the seven existing camera tests in
`test_episode_trace.py` run locally against the real `trace.py` and pass (no numpy/imageio
in this container until installed; the rest of the workspace is not installable here, so
everything else goes through CI). Caught before pushing: the encoder rounds 540 up to 544,
so the first draft of the tracy frame-shape assertion would have failed in CI.

**Outstanding**: CI on #354 not yet read - the experiments job is what to watch. Per the
fold rule this work is #265's (every file it touches is introduced there and absent from
`main`); merging #354 into its base is that fold.

