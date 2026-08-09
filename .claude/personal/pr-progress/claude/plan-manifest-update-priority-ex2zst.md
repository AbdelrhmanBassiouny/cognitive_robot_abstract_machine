# manifest-currency-first (workflow-unification)

Branch: `claude/plan-manifest-update-priority-ex2zst`, based on fork `main`.
No pull request yet — this session did the placement analysis and recorded the
item; implementation has not started.

## The item

Every skill that can affect a plan writes the manifest and republishes the
dashboard first, at every transition that makes a recorded field stale.
Generalizes what `plan-item-bootstrap` (#143) did for the single kickoff moment.

Six bound surfaces, settled with the user: `plan-create`, `add-plan-item`,
`plan-item-kickoff`, `plan-item-resolve`, `plan-dashboard`,
`stacked-pr-maintenance`. As scripted as possible — the shared document keeps
only what a script cannot do.

## Done

- Placement analysed: `workflow-unification`, track `personal-data`, wave
  `immediate`, `depends_on: []`, based on fork `main`. Verified with
  `add-plan-item`'s `check_scope_overlap.py` (from #135's branch) rather than by
  eye: every path exists on `main` except the shared doc this item introduces and
  `add-plan-item/SKILL.md`.
- Checked against every existing item: nothing duplicates it. `plan-item-bootstrap`
  covers one moment, `plan-item-execution-modes` (#149) covers whether to ask,
  `plan-item-edit-guard` covers item *existence* rather than currency.
- Reuse seams surveyed in `plan_item_bootstrap.py`, `sync_manifest_status.py`,
  `build_dashboard.py`, `record_dashboard_url.py`, `stack.py`. Three real gaps
  and four don't-duplicate constraints recorded in the item's notes.
- `plan.yaml` + `roadmap.md` written and saved (`save-plan.sh`), dashboard
  republished (41 items, drift 0), structural change posted to issue #102.

## Next

1. Kick off implementation via `/plan-item-kickoff workflow-unification
   manifest-currency-first` — branch and draft PR before the first edit.
2. Extend `plan_item_bootstrap.py`: an update operation that writes any tracked
   field without a mandatory roadmap section, `notes`/`blockers` writes, and a
   transition-time staleness check reusing `sync_manifest_status.py`.
3. Write `.claude/skills/plan-dashboard/manifest-currency.md`; add the one-line
   reference to each of the six skills.
4. TDD throughout, tests under `.claude/hooks/tests/` (already in CI's
   `test_claude_dev_tooling` job — no `ci.yml` change needed).

## Open calls for the user

- Renaming `plan_item_bootstrap.py` once it writes more than a bootstrap. Two
  skills and `resolve-personal-notes-config.sh` reference the path, and
  `dev-tooling-save-plan-python` absorbs the file anyway. Not taken unilaterally.
- The `add-plan-item/SKILL.md` reference line, which cannot be written from
  `main` and cannot go on #135 now that it is marked ready.
