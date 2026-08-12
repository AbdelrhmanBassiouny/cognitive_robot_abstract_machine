**Goal:** the planning skills must never ask whether to run
`/setup-personal-notes` — they run it themselves when `check-setup.sh` reports
something missing.

**Done:**
- `setup-personal-notes/prerequisite-check.md`: the offer step is now "say what
  is missing, invoke `/setup-personal-notes`, re-run the check"; the rationale
  section explains why the yes/no gate is gone and which questions stay inside
  the setup skill (notes remote, notes content, labels).
- Step 0 of `plan-create`, `plan-dashboard`, `plan-item-kickoff` and
  `plan-item-resolve` reworded to "run it if not".
- Follow-on wording: `resolve-personal-notes-config.sh`'s constant comment,
  `hooks/README.md` quick start, `plan-dashboard/example-walkthrough.md`.

**Next:** nothing outstanding. `check-setup.sh` still exits 1 here only for
`dashboard_dependencies` (markdown, nh3 not installed in this container) —
unrelated to this change. No PR opened; ask if one is wanted.
