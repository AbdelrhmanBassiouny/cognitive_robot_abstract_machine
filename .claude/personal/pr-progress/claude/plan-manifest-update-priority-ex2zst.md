PR #151 (`manifest-currency-first`, workflow-unification). This session folded in a
reversal the user asked for on 2026-08-11: `stacked-pr-maintenance` writes the manifest
and publishes rather than reporting, and `plan-create` republishes the master index.
Folded here rather than split out, because it rewrites the sections this PR introduced -
`manifest-currency.md`'s report-don't-write section, the matching one in
`stacked-pr-maintenance/SKILL.md`, and the contract test asserting the pass writes no
manifest. `main` was never a possible base: none of those exist there.

Done, pushed as 5fe15975 + 6c5203c8:
- `plan_item_bootstrap.py` gains `resolve`, `block`, `unblock`, all keyed on a branch.
  Blockers carry their owner (`MAINTENANCE_BLOCKER_OWNER`), so the pass replaces and
  withdraws its own and never a person's.
- `manifest-currency.md`'s asymmetry section reversed; `stacked-pr-maintenance` writes at
  the label transitions rather than in `Finish`, and gains the `Skill` grant it lacked.
- `plan-create` step 8 publishes the plan page and the index unconditionally.
- Contract test inverted; three added (Skill grant, shared blocker owner, index).
- Two defects the live run found: `fold` broke inside words (a folded scalar reads the
  break back as a space, so a branch name returned with a space in it), and withdrawing a
  blocker an item never carried wrote it `blockers: []`. Both fixed with failing tests
  first, both mutation-checked.
- 408 tests pass across the three CI directories, was 389. Two `test_check_setup_sh.py`
  failures are pre-existing and local-environment only (ambient python3 lacks the
  dashboard requirements); confirmed by stashing the diff.
- Plan state written and the dashboard republished in the same turn:
  `git-identity-from-personal-notes` is now `blocked` with the real conflict against #126.

Outstanding, nothing in flight:
- `test_each_lib` stays red base-side (greenlet 3.5.5 has no Linux wheel). Not this diff.
- The one line into `add-plan-item/SKILL.md` still waits on #135 merging, as before.
- The extend-a-note trap is documented, not fixed: `--notes` reads blank-line paragraphs
  while a folded scalar hands back single newlines. Worth deciding whether the writer
  should accept both.
