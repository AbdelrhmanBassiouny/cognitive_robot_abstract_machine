# session-start-plan-and-setup-guards → draft PR #121

Plan `workflow-unification`, track `personal-data`, `depends_on: []`. Based on fork
`main`, independent of the #101/#106 chain. Session:
https://claude.ai/code/session_01JSxeoePmxWoA4aETrwhFcx

## Plan

Fixes 1 and 2 of the item's three (the two it recommends). Fix 3 (the `PreToolUse`
guard) is split out as its own item, `plan-item-edit-guard`.

The constraint that shaped it, from the user: someone who wants neither plans nor
personal notes must see none of this. It needed no new setting — everything added sits
after `session-start.sh`'s existing `fetch_personal_notes_branch || exit 0`, and within
the group that does use the branch, whether the generated branch index exists separates
notes-but-no-plans from plans-in-use.

## Done

- Four distinct plan-line outcomes replacing one bare `none`, including an index entry
  whose manifest has gone missing (previously invisible).
- A `setup:` line carrying `check-setup.sh`'s needs-setup rows — run after
  `CLAUDE.local.md` is written, captured with `|| true`, run as a subprocess.
- `plan_branch_index_exists` / `tracked_plan_count` in
  `resolve-personal-notes-config.sh`, which already owns that path.
- Fixed a latent crash TDD exposed: a plan with no `tracking_issue` made `grep` exit 1,
  which `pipefail` + `set -e` turned into the hook dying with no output at all.
- First tests `session-start.sh` has ever had: 9, TDD, 6 failing before the change.
  `ScratchRepository` gained `run_hook_script` and `write_setup_prerequisites` (the
  fully-set-up layout `test_check_setup_sh.py` previously built inline).
- 231 tests green across both CI directories (was 222). Verified live in this clone:
  the plan line moved from the ambiguity message to `'workflow-unification'` once
  `save-plan.sh` recorded the item, and `setup:` reads `ok`.
- Manifest + roadmap updated and saved; structural change recorded on issue #102;
  dashboard republished; draft PR #121 opened and subscribed.

## Next

- Wait for review on #121. `bug` label applied at the user's request (it carries the
  `tracking_issue` crash fix); the description's "no bug label" paragraph was rewritten
  to match rather than left contradicting the label.
- Expect a textual merge with #109 and #115 in the summary block,
  `resolve-personal-notes-config.sh` and `scratch_repository.py` — no `depends_on`
  either way, whichever lands second resolves it.
- Possible follow-up flagged on #102, not an item yet: grep the remaining hooks for
  `set -o pipefail` plus a `grep` used as a test rather than a filter. Two instances
  now (this one and #115's `default_repository` grep).
- Recorded from this session but *not* part of #121:
  `git-identity-from-personal-notes` (`personal-data`, no dependencies). The assistant
  git identity turns out to be the container's global config, so it is the default
  rather than a slip — hence an item. Not started; no branch.
