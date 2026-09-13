
## Branch `claude/experiments-film-memory-q7mx2v` - PR #354 (draft) - experiments CI memory: fixed, awaiting CI

Base **`claude/icra-experiments-simulation-pipeline-w4ep7n` (#265)** - reparented from
`claude/coraplex-ci-hang-ckj3nh` once #350 merged into #265 on 2026-09-13 (d74ba45937).
Label `bug`. Commits: 7f5e9376dd (the change), 92f988873f (merge of #265's later work).

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

**Merge of #265 (1bcef7d49f)**: one conflict, in `artifacts.py`'s import block - my
`Union` against their `Mesh` import; both kept. `pickup_demo_mujoco.py` auto-merged
(their change was `SceneAsSetUp.read_from`, nowhere near the films). Re-checked after
merging: no new `FramesByMoment` implementation and no new `keep_video`/`keep_camera`
caller arrived with it. `pytest.ini` now also blocks `launch_pytest`.

**Verified**: the four new tests and the seven existing camera tests in
`test_episode_trace.py` run locally against the real `trace.py` and pass, before and
after the merge (numpy + imageio installed into this container by hand; the rest of the
workspace is not installable here, so everything else goes through CI). Caught before
pushing: the encoder rounds 540 up to 544, so the first draft of the tracy frame-shape
assertion would have failed in CI.

**Next step**: the user asked for #354 to be folded into #265 once its CI is green. CI on
92f988873f started 12:30 UTC (run 34757264079 / 34757264063) and was not read this turn.
Waiting for it needs either a scheduled check or a PR subscription, both of which these
notes forbid, so the user was asked which they want rather than one being armed. Nothing
is armed.

