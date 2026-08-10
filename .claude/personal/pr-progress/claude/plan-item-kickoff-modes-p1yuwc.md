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
  status `in_progress`, dashboard republished.
- All five implementation steps, pushed as `1dc0a52a`. Verified: the full CI
  set (382 passed), a mutation check proving the new assertions bite,
  `check-setup.sh` exit 0, `format_docstrings.py`, and the live `resolve`
  calls in this clone (`ask`/`committed_default`, `--requested` overriding,
  a bad mode exiting 3).
- PR description refreshed to match what actually shipped; PR still draft.

## Round 2 (2026-08-10), pushed as `99732801`

The user reversed the default and asked for a way to set it in passing.

- **Committed default is now `auto` for both skills.** Their argument settles
  it: auto mode already reads the item's state and the plan/PR progress, and
  the escalation rule already returns anything that changes the settled plan —
  so `ask` was ceremony on items the gathered material had already settled.
  Every test that pins a personal setting now pins a mode the default is *not*,
  so a fall-through to the default fails instead of coinciding.
- **`/plan-item-mode <auto|plan|ask> [kickoff|resolve|both]`** — the script
  could already write the setting; nothing let the user say it in passing. The
  skill maps the phrasing, calls `set`, then reports what `resolve` reads back.
- **`--skill` is repeatable**, so pinning both is one rewrite and one push; a
  test counts commits on the notes branch to pin that.
- Roadmap section rewritten to record the reversal and its reasoning rather
  than quietly editing away the old argument; dashboard republished (drift 0
  after rebuilding `pr_data.json`, which was missing #150/#151/#153).

## Round 3 (2026-08-10), pushed as `ea5c2baa`

Review comment on `plan-item-resolve/SKILL.md:130` asking whether the
duplication with `plan-item-kickoff` could be defined once and injected.

- Measured: **41 byte-identical non-blank lines**, plus the subscription, the
  read-roadmap-in-full rule, the conventions cross-check and the
  already-answered check each identical but for a clause.
- There is no include mechanism for `SKILL.md` — the repo's answer, used five
  times already, is state-once-and-cite, which is why `execution-modes.md`
  made the mode step one of the two places they did *not* duplicate.
- `plan-dashboard/plan-item-gathering.md` now holds the shared procedure;
  each skill runs it and adds only its own part. 41 → 10 identical lines;
  kickoff 263 → 191, resolve 200 → 129. `PLAN_ITEM_GATHERING_DOCUMENT` added.
- Thread replied to and resolved. Scope flagged on the thread: this was
  offered as its own item (the prose predates the PR, and #135 is
  ready-for-review editing both files, so the conflict there is now wide);
  the user chose to land it here.

## Next

- Nothing outstanding on the implementation. 384 tests pass; #149 is a draft
  with its description current.
- CI history on #149, two distinct causes, neither this branch's:
  1. `greenlet` 3.5.5 shipped no Linux wheel, so every job died at dependency
     install. `main` failed the same 7 jobs identically and `1dc0a52a` was
     20/20 green before the base merge. **Now cleared** — those jobs pass.
  2. On `99732801`, `test_each_lib (robokudo)` fails on
     `Network is unreachable` to `gitlab.informatik.uni-bremen.de`, which
     `robokudo/src/robokudo/utils/data_downloader.py` fetches test data from.
     Round 2's commit is 6 files, all `.claude/`; robokudo passed before the
     base merge brought 145 robotics files. `main` has not re-run since
     `greenlet` cleared, so there is no green base run to compare against.
  Both reported on the PR, one comment each. Nothing pushed for either.
- Still not done deliberately: the user's own
  `.claude/personal/plan-item-modes.toml` is unwritten. With the committed
  default now `auto`, they need no pin to get the behaviour they asked for.

## Watch

- `add-plan-item-skill` (in flight) edits both the same `SKILL.md` files to add
  its `scope-decision.md` reference. Expect a merge conflict there; it is not a
  fold — neither PR exists to change the other.
