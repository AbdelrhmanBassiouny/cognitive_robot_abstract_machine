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
