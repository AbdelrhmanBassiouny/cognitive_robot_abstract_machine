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

**Review round 2026-08-12** (one comment, posted twice as two threads): the
step-0 section is duplicated across the skills, dedupe it once unless another PR
already does. It does — #149 collapses the two plan-item copies into
`plan-dashboard/plan-item-gathering.md` — so the dedup is left there. Replied on
both threads with the measurement (the procedure is already single-sourced in
`prerequisite-check.md`; what repeats is a citation plus a per-skill consequence
clause, the same shape as `scope-decision.md` / `dependency-readiness.md` /
`pr-data-fetching.md`) and left both open, since the outcome is a deferral.

**Correction that round produced:** the recorded conflict resolution here was
wrong. #149's `plan-item-gathering.md` and #135's `add-plan-item/SKILL.md` are
new files still carrying "offer `/setup-personal-notes`", so neither conflicts
with this branch and nothing flags them at merge time — landing either after
#156 reinstates the gate. Right resolution for the two plan-item skills: take
#149's deletion, carry this PR's wording into its shared document. #135 also
conflicts in `prerequisite-check.md`, where it only adds `add-plan-item` to the
opening list. Flagged on both PRs; neither branch was pushed to (both are out of
draft, so both are the user's). Manifest + roadmap corrected, dashboard
republished, PR description updated.

**Enforcement added (85feee6d)**, so the hazard above no longer needs anyone to
remember it: `test_setup_prerequisite_documents.py` sweeps every markdown
document under `.claude/skills/` for a verb of offering governing
`/setup-personal-notes`. Discovered not listed, an absence assertion, plus a
vacuity guard. Mutation-checked: 0 offenders here (15 docs), 4 on `main`, 3 on
#149, 5 on #135. Landing order now stops mattering — whichever lands second goes
red instead of silently reinstating the gate. 464 tests pass across the three CI
directories (92 hooks, 194 plan-dashboard, 178 stack); pytest is installable in
this container after all (`pip install pytest`), so the suite did run.

**Awaiting a decision:** whether to push the one-word fix to #149 and #135
directly (plain fast-forward, no force-push — but both are out of draft and
carry `in-review`, so it re-triggers their upstream review), or leave the guard
to force it at merge time. Recommended the latter.

**Next:** nothing else outstanding. The plan's master index was not refreshed
(`/plan-dashboard` with no argument does that).
