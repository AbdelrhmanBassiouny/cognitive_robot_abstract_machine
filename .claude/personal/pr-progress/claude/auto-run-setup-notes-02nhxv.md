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

- Draft PR #156 opened off `main`. No `bug` label (behaviour change, not a fix).
- Tracked as `setup-runs-without-asking` in `workflow-unification`
  (`personal-data` track, `in_progress`, PR #156); roadmap entry added, saved
  with `save-plan.sh`.
- Dashboard republished at the plan's existing URL. The refresh ran the new
  no-ask path end to end: `dashboard_dependencies` was missing, `/setup-personal-notes`
  ran without being offered, installed markdown/nh3, and the check then exited 0.

**Next:** nothing outstanding. The plan's master index was not refreshed
(`/plan-dashboard` with no argument does that). #107 and #149 will conflict
textually with this branch in `hooks/README.md` and the two plan-item skills
when they land; resolution is to keep both edits.
