## Why the pipeline had never published a build, and the six fixes for it

**Status**: done and pushed as `8227ef57c` on #211. Manifest, roadmap and dashboard all
current. #211 and #154 both stay out of draft, on your explicit instruction - a draft is
excluded from every integration build, which is the process this work serves.

### The four defects, each verified live before it was fixed

- **The rebuild's own check judged the branch it ran on.** `ReportedChecks.verdict`
  returned FAILED for any failed check, so #211's ready-flip fired a rebuild whose own
  failure attached to #211's head and the red-tip exclusion then left #211 out of the
  build its flip had triggered. `ChecksAboutTheBuild` reads the job names off the two
  pipeline workflows and filters them out. Naming the probe's jobs was forced by it: the
  keys `to-lowercase` and `test` collided with `ci.yml`'s.
- **The `pull_request` arm could not work.** It pins the checkout to the default branch,
  correctly, and that branch's `integration.py` predates `refresh`. It asks the pinned
  copy whether it can rebuild and says so plainly when it cannot, rather than dying on
  `invalid choice: 'refresh'` in 19 seconds. Kept as a bootstrap rather than reshaped.
- **The warm-up was one to two orders of magnitude short.** Measured: +19m on #214,
  +2h47m on #217. The verdict is settled by a later run now - `find-candidate` reads the
  open candidate off the fork and `refresh` settles it before building anything, so no
  run waits for its own candidate.
- **The maintenance pass adopted candidates and restacked them.** `is_a_candidate`
  recognises one by base *or* title, so the board never carries it. `work_in_flight` is
  gone with it.

### The two new features

- **Recorded passes**, on `refs/integration/passed/*` - reachable with
  `INTEGRATION_REFRESH_TOKEN`, no personal-notes access, read in one `ls-remote`, pruned
  in the same push that records. Keyed by build tree hash and by branch head. Only passes
  are recorded, never failures: a red is cleared by re-running the same commit, and the
  rule that a red branch re-enters a build by going green would be unreachable if a red
  were remembered. Seven-day retention, because the container the matrix runs in is
  rebuilt from the upstream base even when the tree has not changed.
- **`--plan`**, on `build` and through `refresh`, repeatable or comma-separated, reading
  `_generated/branch-index.tsv`. A branch the index does not name is reported
  `no-plan-recorded` rather than silently dropped or forced in. A filtered build never
  publishes, enforced structurally: its candidate opens against the upstream base, so
  `find-candidate` cannot see it.

### Verified against the fork, not only the harness
26 check runs on #211's head, of which only the two rebuild runs failed. `PlanFilter`
over the live index: 125 branches, 9 plans, 42 under `rdr-refactor`.

899 tests across the four CI directories, from 851. 32 mutations checked.

### Outstanding
- **No rebuild was dispatched.** Publishing needs your say-so, and the fixes reach the
  schedule only through a dispatch on this branch or a hand push to `integration`.
- **Seven `integration-2026*` build branches remain.** `git push --delete` returns
  HTTP 403 through the session git proxy - the standing constraint recorded 2026-07-29,
  not a transfer failure. They need deleting outside the harness.
- `per-plan-integration-branches` is recorded as deferred under `stack-tooling`,
  depending on `integration-branch-ci-verdict`, and was deliberately not built.
