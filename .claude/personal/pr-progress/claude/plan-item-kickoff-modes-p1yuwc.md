# PR #149 — auto/plan execution modes for the plan-item skills

Item `plan-item-execution-modes` in plan `workflow-unification`, track
`personal-data`. Draft PR #149 off `main`. Design rationale is in that plan's
`roadmap.md` (section dated 2026-08-09).

## Plan

Give `/plan-item-kickoff` and `/plan-item-resolve` an execution mode: `plan`
(today's `ExitPlanMode` gate), `auto` (plan implicitly, implement without
asking, leave the draft PR ready to review), `ask` (put the choice to the user
after gathering — the built-in default). Precedence: invocation argument >
`.claude/personal/plan-item-modes.toml` > committed defaults at
`.claude/hooks/plan-item-modes.toml`.

The script resolves the mode and nothing else; the recommendation stays the
skill's judgement, since steps 1-4 already hold every signal it would need.

1. `.claude/hooks/tests/test_plan_item_mode.py` first (TDD), against the
   existing `ScratchRepository` harness.
2. `.claude/hooks/plan_item_mode.py` (`resolve`, `set`) + the committed
   defaults TOML.
3. `.claude/skills/plan-dashboard/execution-modes.md` — mode meanings, the
   question, auto-path obligations, the escalation rule — stated once, with a
   one-line reference from each skill.
4. Four constants in `resolve-personal-notes-config.sh`; `hooks/README.md`.
5. Both `SKILL.md` files: mode step, auto path, frontmatter, `allowed-tools`.

## Done

- Item registered in the manifest, roadmap section appended, branch pushed,
  draft PR #149 opened, `branch`/`session`/`pull_request_number` recorded,
  status `in_progress`.

## Next

- Steps 1-5 above, then the CI test set, `format_docstrings.py`,
  `check-setup.sh`, and a dashboard republish.

## Watch

- `add-plan-item-skill` (in flight) edits both the same `SKILL.md` files to add
  its `scope-decision.md` reference. Expect a merge conflict there; it is not a
  fold — neither PR exists to change the other.
