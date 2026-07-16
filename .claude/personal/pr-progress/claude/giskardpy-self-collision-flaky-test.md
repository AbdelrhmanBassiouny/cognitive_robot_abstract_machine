## Status: MERGED (2026-07-16)

PR #72 merged into main; webhook confirmed the merge and auto-unsubscribed
the steward session. Final outcome - do not reopen or re-create unless
explicitly asked. Historical plan/progress kept below for reference.

## Plan (PR #72, branch claude/giskardpy-self-collision-flaky-test)

Requested follow-up from PR #71: try to fix the flaky `giskardpy` CI failure
(`test_ros2_stuff/test_integration_pr2.py::TestSelfCollisionAvoidance::test_attached_self_collision_avoid_stick`,
`assert len(collisions.contacts) > 0`), as its own PR off `main`.

1. Investigate root cause via an Explore agent + manual code reading (no ROS
   available to actually run/reproduce it - see "Blocked" below).
2. Root-cause hypothesis: `Synchronizer.publish()` in
   `semantic_digital_twin/src/semantic_digital_twin/adapters/ros/world_synchronizer.py`
   snapshots the subscriber count once, immediately before a synchronous
   publish, via `_snapshot_subscribers()`. ROS graph discovery is async, so a
   remote subscriber created moments earlier can be undercounted (worst case
   0), letting `publish()` return before the real subscriber actually applied
   the update - silently breaking the synchronous contract. This lines up
   with a pre-existing xfail test in the same file
   (`test_snapshot_subscribers_counts_in_process_peer`) that documents a
   related (but distinct - same-node-name undercounting) bug in the same
   function, so the function is a known trouble spot.
3. Fix: added `Synchronizer._snapshot_subscribers_after_discovery_settles()`,
   polling until two consecutive reads agree (or a short grace period
   elapses), used by `publish()` instead of the single-shot snapshot.
4. Added two unit tests in
   `test/semantic_digital_twin_test/test_ros/test_world_synchronizer.py`
   using a fake rclpy node (no real ROS needed) exercising the new method's
   stabilize/bounded-wait behavior. Verified the polling algorithm logic
   correct via a standalone throwaway script (couldn't import the real
   module/run these tests myself - see "Blocked").
5. Committed as the human user's git identity, pushed to
   `claude/giskardpy-self-collision-flaky-test`, opened draft PR #72 against
   `main`, labeled `bug`, linked this session, subscribed to PR activity.

## Blocked (documented in PR #72 description)

- Could not reproduce the original failure locally: the test needs a full
  ROS2 (Jazzy) install; this sandbox's network policy blocks
  `packages.ros.org`.
- Could not use the CI's prebuilt Docker image either
  (`ghcr.io/.../cognitive_robot_abstract_machine:jazzy`, reachable) because
  starting a Docker daemon in this sandbox was blocked by the sandbox's own
  safety policy (creating an RCE surface without explicit authorization) -
  did not attempt to work around this.
- So this fix is unverified locally and explicitly flagged in the PR body as
  a best-effort attempt depending on CI to validate.

## Done (review round 1)

Owner (AbdelrhmanBassiouny) left 6 review comments shortly after opening,
all addressed and resolved in commit 49191e5:
- 2x "use timedelta instead of float" on the grace-period/poll-interval
  fields - converted both to `datetime.timedelta`.
- 3x "dataclass?" on the test's fake Synchronizer/node mimic classes -
  converted all three to `@dataclass` per AGENTS.md.
- 1x substantive question: "could falling back to the last observed count
  cause wrong behaviour, and is that better than the original design?" -
  genuinely reconsidered this: yes, last-sample fallback could still
  undercount if a low reading landed right as the grace period elapsed
  even after a higher count was already seen. Fixed to fall back to the
  *highest* observed count instead (undercount silently breaks the sync
  contract = the bug being fixed; overcount just costs the existing,
  already-logged timeout - not symmetric, so biasing toward "never
  undercount" is strictly safer than both the last-sample fallback and
  the original no-wait design). Added a third test
  (`test_snapshot_subscribers_falls_back_to_highest_sample_not_last_sample`)
  covering this specifically. Replied to each thread explaining the fix,
  then resolved all 6.

## Round 2 (this session) - reviewer's deadlock concern

Reviewer comment on the PR (referenced by the user as
https://github.com/cram2/cognitive_robot_abstract_machine/pull/448): could
falling back to the *highest* observed subscriber count cause a deadlock
later on, if that count is higher than the truth?

Unlike Round 1, this session's sandbox has real ROS 2 Jazzy available
(`source /opt/ros/jazzy/setup.bash`, `.venv` has `rclpy`), so used it to add
real-ROS integration tests (not just the existing fake-node unit tests) to
`test/semantic_digital_twin_test/test_ros/test_world_synchronizer.py`:

- `test_synchronous_publish_settles_promptly_with_multiple_real_subscribers` -
  control case: 3 real subscribers, no churn, no timeout paid.
- `test_overcounted_expected_acknowledgments_times_out_but_recovers_on_next_publish` -
  deterministically injects a +1 over-count; proves publish still returns
  (bounded by `wait_for_synchronization_timeout`, not an infinite hang), the
  message is still delivered, and the very next publish recomputes the count
  fresh and returns promptly - self-heals because
  `_expected_acknowledgment_count` is recomputed on every `publish()` call,
  never cached across calls.
- `test_subscriber_disconnecting_during_discovery_grace_period_does_not_hang_forever` -
  genuine (unmocked) subscriber flap during the discovery grace period; only
  asserts the bounded/recovers invariant since whether the real race actually
  triggers an over-count is timing-dependent. It did trigger the timeout
  warning path at least once across repeated runs, confirming the scenario is
  real and not just theoretical.

Ran all 3 five times standalone (no flakiness), then the full
`test_world_synchronizer.py` file: 97 passed, 1 pre-existing skip, 1
pre-existing xfail (the unrelated same-node-name undercounting bug), 158s,
no regressions.

Answer to the reviewer: an over-count is not a deadlock - it's a one-time
bounded wait (the existing, already-logged
`wait_for_synchronization_timeout`) on the single affected publish, because
the expected acknowledgment count is never cached across publishes.

Also reverted an unrelated `ormatic_interface.py` diff that appeared as a
side effect of running the test suite (unrelated Rerun-adapter DAO classes
from someone else's in-progress work) - did not commit it, per AGENTS.md's
guidance to avoid touching `ormatic_interface.py`.

Committed (`242913798`) as the human user's git identity and pushed to
`claude/giskardpy-self-collision-flaky-test`.

Could not update the PR description/labels via the GitHub API this session:
no `gh` CLI and no token/credential available in this sandbox (unlike
whatever session merged PRs #451/#449 earlier in the git log). Drafted the
description addition in the session chat for the user to paste in manually.

## Next

- User needs to paste the drafted PR-description addition (given in the
  session chat) onto the PR, since this session can't reach the GitHub API.
- Watch for the reviewer's response to the new tests once posted.
- Watching for further CI completion and review comments via the
  subscription (once reachable again).
- (PR #71 on `claude/ipython-shell-ci-hang-vvetyg` is tracked separately
  under its own branch-keyed progress file, not duplicated here. Update as
  of this check: owner marked it ready for review, and its `giskardpy` leg
  was re-run and passed - all 17 checks green, mergeable_state clean.
  Confirms the original giskardpy failure is intermittent. No action taken
  by me, just observed via webhook.)
