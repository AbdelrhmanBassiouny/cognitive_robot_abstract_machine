## Task

Reparent the branches whose parents are merged/closed/deferred, which the last stacking
maintenance missed. Operational pass, not a code change: **no commit on this branch, and
none expected** — the fix already exists as PR #198.

## Root cause (established, reproduced)

`load_stack()` on main fetches only `[pr.head for pr in prs]`, so a parent that is not
itself an open PR head is never fetched; `is_merged` then runs `merge-base --is-ancestor`
through a helper that cannot tell exit 128 (missing ref) from exit 1 (not an ancestor), and
answers "has not landed". On this clone `stack.py reparents` printed nothing before the fork
refs were fetched and printed #64 after. Fixed, unlanded, by **PR #198**
(`unfetched-parent-branches`, workflow-unification). Second unlanded fix needed:
**PR #160** (`plan-item-bootstrap-yaml-indent`) — `plan_item_bootstrap.py block` writes
four-space-indented fields into rdr-refactor's two-space manifest and `save-plan.sh` dies in
`yaml.safe_load`, with the error swallowed by `capture_output`.

## Done

- Ran the whole pass from a worktree of #198's branch (already contains current main).
- Dissolved GitHub stacks 152/195/179 (membership recorded first), reparented
  **#64 -> main** and **#192 -> main**, rebuilt 152 as **stack 219** (7 open members).
  195 and 179 could not be rebuilt: a stack needs >= 2 members, one open member each.
- **#178** refused its base change — its commits are already contained in
  `montessori_fast_inline_monitor`, so it needs closing, not reparenting. Reported, untouched.
- `run-report`: fast-forward already-current, 50 up-to-date, 11 withheld (pre-existing
  conflicts, already labelled), 2 parent-gone (**#79**, **#21**) newly commented to owners,
  **#64 promoted** (it had never been promoted on any pass), #185 promoted.
- Manifests: rdr-refactor D-ui-rendering -> blocked + blocker; rdr-oo-recognition keeps
  `deferred` and gains a blocker; match-query #192's stale blocker rewritten for its new base.
  Roadmaps: rdr-refactor §33, match-query-ergonomics §23. Both dashboards republished.
- Evidence for #198 and #160 posted on workflow-unification's tracking issue #102.

## Next / outstanding (for the developer)

- **#79** and **#21** need a base chosen by hand; the pass never invents one. #79's manifest
  note still says "re-target onto D-core-engine", which is stale — #68 is deferred.
- **#178** should be closed as already-landed-into-its-parent.
- #192 is still `needs-resolution`; it conflicts against `main` now rather than its old base.
- Nothing armed: no PR subscription, no scheduled check-in.

