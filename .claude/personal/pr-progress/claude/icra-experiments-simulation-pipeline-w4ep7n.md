### icra-experiments / integrated-simulation-pipeline — PR #265

**Plan.** Cut off `main`; merge, in order: #244, #256, #262, #229, #238, #236, #231, #223,
then cherry-pick #239's `3a493be9`. Keep #169 and #192 out. Regenerate the ORM, add a
headless integration test over the merged world + monitor + predicates, let CI verify.

**Decisions taken (all recorded in roadmap.md and the PR description).**
- #262's copies win the recording-trio add/add against #256.
- The perception lineage's `world.py`/`semantics.py`/`hole_geometry.py` win against #256's;
  the monitor needs only `MontessoriShape` and `MontessoriWorld`, which both copies define.
- #223 added to the merge list: this is the branch that puts the two `Footprint`s together,
  and #223 already carries the `RectifiedFootprint` rename.
- Done-criterion moved to this branch's own headless test; the demo proof belongs to
  `tracy-demo-takes-the-integrated-branch` (user's call, 2026-09-04).

**Done.** Branch re-cut off `main`, bootstrapped, pushed. Draft PR #265 open. Manifest and
roadmap written. Conflict census run over every merge source.

**Next.** Work the nine merge steps in order, resolving as above; regenerate the ORM; write
the integration test; push and let CI report.

**Known limit.** `regenerate_all_orm.py`, `experiments_test` and `segmind_test` need the ROS
image — not runnable in this container. CI is the verifier.
