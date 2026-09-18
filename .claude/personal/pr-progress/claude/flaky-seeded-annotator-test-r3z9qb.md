PR: https://github.com/AbdelrhmanBassiouny/cognitive_robot_abstract_machine/pull/405 (draft)

## Plan
Fix the flaky `test_a_seeded_annotator_finds_the_same_plane_every_time`
failure reported on upstream PR #646's CI. Root cause: `o3d.utility.random.seed()`
seeds Open3D's RNG but not the thread-scheduling order of its parallel RANSAC,
so two seeded `segment_plane()` calls can pick different near-tied candidates
under CPU contention. Fix: restrict Open3D to one thread for the duration of a
seeded call (new `_deterministic_ransac` context manager in
`robokudo/src/robokudo/annotators/plane.py`), restoring the previous thread
limit afterwards.

## Done
- Re-cut this branch from fork `main` (it originally descended from `integration`,
  flagged as not PR-able by session-start.sh setup check).
- Confirmed fork `main` already carries the exact code from upstream PR #646
  (commit 8fd1d7aec1 by nvasant, "ci fix") - so basing this fix on `main` is
  equivalent to basing it on PR #646's tip.
- Reproduced the exact nondeterminism locally (matches the CI traceback's
  failing value bit-for-bit) by installing open3d in a scratch venv and
  inducing CPU contention with background busy processes.
- Implemented and committed the single-thread-during-seeded-call fix
  (commit e4f149f259).
- Verified the fix against the real shipped `_deterministic_ransac` and the
  test's exact cloud/seed under simulated contention: 15/15 trials pass with
  the fix, fails intermittently without it.
- Ran `scripts/format_docstrings.py` on the changed file.
- Pushed branch, opened draft PR #405 against fork `main`, applied `bug` label.

## Next
- Could not run `pytest test/robokudo_test/test_plane.py` itself in this
  environment (needs ROS2 + MongoDB, not available here) - PR body flags this
  and asks the user to run it.
- Waiting on user review per their standing instructions; no PR-activity
  subscription taken (per personal notes).
