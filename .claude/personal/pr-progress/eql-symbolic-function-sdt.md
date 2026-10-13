## Next
- Wait on the two review decisions. Nothing else in P4 is actionable without them.
- **CI history, two distinct rounds — neither ours.**
  - *Round 1 (`2ea44271`, user merged `main`)*: red on sdt + giskardpy + coraplex, all
    `PackageNotFoundError: package 'ur_robot_driver'`. The DAiSy work on `main` dropped
    `daisy.urdf` (`157cd1bf`) for `package://ur_robot_driver/...`, absent from the CI
    image. Verified against `main`'s own run of the merge parent (30577674356): same
    three jobs, coraplex byte-identical at 326/5/7. Reported on #33 (5135970013, plus
    5136043683 correcting "two jobs" to three). **Now resolved upstream** — the image
    was rebuilt.
  - *Round 2 (`eda2399a`, another `main` merge)*: 18/20 green, giskardpy included, sdt
    up to 886 passed. One new failure,
    `test_ros/test_world_synchronizer.py::test_semantic_annotation_modifications_merge_world`
    — flaky, not ours: it passed on `2ea44271` with all our changes already in; the
    assertion shows the receiver world got `[]` (message never arrived) rather than
    wrong content; the test syncs by `time.sleep(1)` over real ROS pub/sub (87 sleeps
    in that file); and that file's recent `main` history is literally "Fix
    subscriber-count race … causing flaky collision checks". Analysis on #33
    (5142155247).
  - *Round 3 (`36e2624f`, the `semdt_specifications_rewrite` merge, #402 — 93 files,
    +10569/-2472)*: `coraplex_real_tracy` demo failed. `tracy_standalone` (a prebuilt
    binary in the ROS overlay) died with **exit -11 = SIGSEGV**, so `fetch_world` never
    came up and the demo timed out at 276s. Not ours: the job passed on both previous
    runs with all our changes in, and the demo dies at world fetch before touching
    anything of ours. Analysis on #33 (5159902918).
    **Verified our own work against that rewrite locally**: sdt verbalization test
