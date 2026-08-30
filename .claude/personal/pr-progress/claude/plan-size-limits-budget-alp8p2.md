**PR #207** — `plan-size-limits` / `size-budget-and-report` (wave 1, measurement only).

**Plan.** Answer the 2026-08-30 review round; the PR was otherwise green
(23/23 checks) and mergeable, so the review was the only thing stalling it.

**Done (6cde496, pushed).**
- Names read from their definitions: tests import `PlanDocument`,
  `PLANS_DIRECTORY` and a new `HookScript.PLAN_SIZE_REPORT`; new
  `ScratchRepository.install_hook_modules` names `.py` files by the module
  objects; `plan-size-report.sh` uses new `resolve-personal-notes-config.sh`
  constants (`CREATE_PERSONAL_NOTES_BRANCH_SCRIPT`, `HOOKS_REQUIREMENTS_FILE`,
  `MISSING_REQUIREMENTS_SCRIPT`, `PLAN_SIZE_BUDGET_SCRIPT`,
  `PLAN_SIZE_REPORT_SCRIPT`).
- Generic dependency check: new `missing_requirements.py` + `requirements.txt`
  (needed a `.gitignore` exception — the repo ignores `*.txt`, so without it the
  file never reaches CI); `check-setup.sh`'s inline copy of the same parse is
  gone. Mirror test holds the Python path equal to the shell constant.
- `plan_size_budget.py` restructured: budget numbers are `SizeBudget` class
  variables (no `PLAN_SIZE_BUDGET` mid-module), and the eight free functions
  moved onto `PlanSize`, a new `PlansDirectory` and a new `SizeReport`.
- 419 tests pass locally; PR description and dashboard both updated.

**Outstanding — both waiting on the reviewer, not on me.**
- Thread on `plan-size-report.sh:49`: should the eight scripts already on `main`
  that spell `create-personal-notes-branch.sh` convert to the new constant here
  or in a follow-up? Left open.
- Thread on `README.md:196`: should the script be Python? Replied with the
  constraint (the notes-branch config resolver is bash with no Python half, so
  a Python entry point needs that resolver ported first — its own item, and it
  collides with #185). Left open.

**Next.** Nothing until one of those two is answered. CI on 6cde496:
`test_claude_dev_tooling` (the job running these tests) passed, 16 checks green,
7 still running, none failing.
