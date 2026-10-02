PR #280, `claude/stack-maintenance-action` - resolves `workflow-cutover`'s
`routine-cutover` item.

**Plan:** the item's gate ("stack tooling on cram2/main, fork main
fast-forwards") is clear and the deterministic executor (`maintenance.py`,
#139) is already built and merged. What's missing is (1) a notice for a
pending `reparent` - the one residue nothing posts a comment for today - and
(2) a plain Action calling `run-report` on `pull_request:closed` / schedule /
`workflow_dispatch`. Routine deletion and flipping the item `done` wait on
this item's own gate: one green cycle of that Action, which needs the PR on
the default branch first (`workflow_dispatch` is default-branch-only, same
constraint #218 already documented).

**Done:**
- `maintenance_reparent_notice.py` (`reparent_notice`/`resolve_reparents`),
  wired into `RunReportCommand.run`; reads the fork's *current* labels
  (`fork.pull_request`), not the stack snapshot, to avoid the same staleness
  class `promote()` already reads around.
- Renamed `CONFLICT_COMMENT_PREFIX` -> `NEEDS_RESOLUTION_COMMENT_PREFIX`
  (one rename, one new caller) rather than a second identical constant.
- `.github/workflows/stack-maintenance.yml` - resolves the upstream remote
  via `stack.py configuration`'s own `upstream_setup_command`, no new secret.
- **Review round (2026-09-06), both threads resolved:**
  - Retargeting a base *is* doable from this credential - the 403 #139
    recorded was through a Claude session's own proxied credential, never
    tested from a plain Actions token. `resolve_reparents` now attempts
    `ForkPullRequests.retarget_base` (a plain `PATCH`) first, falling back
    to the label+comment notice only on a genuine `403`/`422`. Reparenting
    now runs before restack, matching the session doctrine's own order.
    `MaintenanceReport` gained `reparents_retargeted` alongside `reparents`.
  - Widened workflow triggers: `opened`/`ready_for_review` alongside
    `closed`, so a fresh PR or one leaving draft is picked up promptly.
  - Replied on both threads (`3943265849`, `3943265930`) and resolved them.
- 7 new/updated tests in `test_maintenance.py`; full stack suite green
  (161 passed). PR description updated to match.
- Manifest/roadmap updated on `claude/personal-notes`; dashboard republished.
- **Review round 2 (2026-09-06), both threads resolved:**
  - `RetargetRefusal(IntEnum)` (`CREDENTIAL_REFUSED = 403`,
    `STACK_MEMBER = 422`) replaces the bare `frozenset({403, 422})` literal
    the previous round's own fix left as a magic-number lapse.
  - Researched (not assumed) whether this conflicts with the unlanded
    `integration-branch` pipeline: no - its candidate exclusion
    (`BoardExport.is_a_candidate`) lives in the same board-export module
    this Action's `maintenance.py` already reads through, and ships in the
    same pull request that starts opening candidates, so there's no
    landing-order gap. Documented as a comment in `stack-maintenance.yml`.
  - Replied on both threads (`3943501919`, `3943502121`) and resolved them.
  - PR description, roadmap and this note updated to match; pushed as
    `a1409d71`.

- **Resolved 2026-10-02** (session https://claude.ai/code/session_017wfueWmCbN76Z5MQo2EWAv),
  after the user asked how this integrates with basstler and whether it is
  usable:
  - #280 had never crossed #185. Merged #185's branch in (`eeb76241`):
    every import is now `basstler.*`, `maintenance_reparent_notice.py` and both
    test files moved into the package, the whole-pass tests rely on the autouse
    `board_snapshot_set_aside`, and the workflow test uses
    `PackageLocation.REPOSITORY_ROOT`.
  - The Action had run 158 times on integration candidates since 2026-09-17,
    and all failed with exit 10. `run-unattended` (`0b6e9776`) treats a branch
    already reported on its pull request (CONFLICT/WITHHELD) as success, and
    still fails on unreported faults. The workflow installs `./basstler` and
    runs `python -m "${MAINTENANCE_MODULE}"`, with the JSON going to the step
    summary.
  - 705 tests pass in `test/basstler_test`. Base retargeted to #185's branch,
    `integration-conflict` removed, description rewritten.
  - The duplicate-comment bug (91 comments on #156) is split out as #482, off
    `main`, labelled `bug`.

**Next:** #185 lands first, since this now stacks on it. Then a real run of
`stack-maintenance.yml` on this head is the green cycle the gate needs. That
run also answers whether the Actions token may retarget a base (no run so far
had a pending reparent). #482 should land before the Routine trigger
(`trig_01N79jHmLo3bSbg8pLM6MNTB`) is deleted. The upstream promotion link
predates the re-cut and would carry #185's diff, so rebuild it after #185
lands. The PR was left out of draft as found: it was not re-drafted, in case
the user marked it ready.
