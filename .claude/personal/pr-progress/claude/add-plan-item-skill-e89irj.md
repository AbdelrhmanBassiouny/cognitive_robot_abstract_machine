# `/add-plan-item` — where does a new piece of work belong?

Tracked as `add-plan-item-skill` on the `workflow-unification` plan (track
`personal-data`, wave `immediate`, `depends_on: []`). No PR opened — the user
hasn't asked for one.

## Plan (all four points settled with the user before implementing)

1. **Tracked as** a new item on `workflow-unification`, not its own plan.
2. **Branch folded**, not stacked: reset `claude/add-plan-item-skill-e89irj`
   onto `claude/plan-scope-before-new-item` so one branch carries the scope rule
   *and* the skill. That branch is retired — it had no PR.
3. **Rule extracted, not restated**: one `scope-decision.md`, referenced in a
   line by all four plan skills, replacing three worded-differently copies.
4. **Ships a script**, not prose alone: `check_scope_overlap.py` + tests in CI.

## Done

- Branch reset onto `3e23270a`/`96a5b30b`; both carried.
- `scope-decision.md` — the rule once, merging all three copies' distinct
  content (including `plan-item-resolve`'s decide-before-either-lands clause).
- `SKILL.md` — steps 0–6, four outcomes, plan-mode-only, never touches git.
- `check_scope_overlap.py` — paths absent from base, per-candidate
  `shared_paths` + full `changed_paths`; merge-base derived; pure git.
- 8 tests (TDD, written failing first) reusing the hooks suite's
  `ScratchRepository`. **230 pass, was 222.**
- Three skills now reference the shared doc; `resolve-personal-notes-config.sh`
  gained 4 constants; `ci.yml`, both READMEs, `prerequisite-check.md` updated.
- Committed as the human user, pushed. Manifest item + roadmap entry saved;
  issue #102 commented; dashboard republished.

## Next

- Open a draft PR **only if asked** — base `main`, no `bug` label (this is
  tooling that never existed, not a defect), session link in the description,
  subscribe to its activity.
- Note for whoever reviews: `.claude/stack/tests/` does **not** exist on `main`
  (it arrives with the unlanded #106), so the three-directory pytest command
  from the original brief can't run here; the two that exist do, plus the new one.
- Watch for textual conflict on `resolve-personal-notes-config.sh` with #121 /
  #126 — new constants were appended at the end of the plan-tooling block to
  keep the overlap minimal.
