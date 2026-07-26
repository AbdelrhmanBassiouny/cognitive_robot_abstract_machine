## PR #97 (Auto-generate verbalization surfaces snapshot) resolution

Note: this designated branch (`claude/pr-97-resolution-aqwbn4`) is a fresh branch off
`main`, not PR #97's actual head. PR #97's real head is
`claude/verbalization-surfaces-autogen-sh2saj` -- confirmed with the developer
(AskUserQuestion) before force-pushing there, same situation as P2/PR #87 previously.
Every commit made here is mirrored with a force-with-lease push to that branch.

### Done
- Restack: PR #39 and #87 (this PR's deps) are merged to `main`. Cherry-picked this
  branch's 3 unique, non-empty commits onto current `main` (dropping the merged-in
  #39/#87 history) instead of hand-merging the conflicting generated
  `verbalization_surfaces.py` the routine's status comment flagged. Diff shrank from 68
  files/+3237/-772 to 10 files/+275/-71; `mergeable_state` clean. Regenerated the
  snapshot via `generate_verbalization_surfaces.py` rather than hand-resolving -- it
  dropped a stale `SymbolicCallable` import on its own. Full `test_verbalization/`
  (737 passed/3 pre-existing skips) + `test_code_generation/` + `test_class_diagram/`
  (142 passed) green. PR description rewritten to match the focused diff; replied on
  the routine's status comment explaining the fix. Pushed as commit 7d2c31d5.
- Review round (2026-07-26, 4 threads): 2 clear fixes done and resolved --
  `REPOSITORY_ROOT` now derived from `Path(krrood.__file__).resolve().parents[3]`
  (the already-imported module object) instead of the script's own `__file__`;
  `VerbalizationSurfaceGenerator.write()` now runs `run_ruff_check_on_file` +
  `run_ruff_format_on_file` instead of Black, matching `ormatic`'s own generator --
  regenerated the committed snapshot with it (ruff's `check --fix` also modernized
  `Tuple[...]` to stdlib `tuple[...]`, a nice side effect) and rewrote the round-trip
  test to exercise `write()` directly instead of duplicating its formatting step with
  `black.format_str`. Verified idempotent (regenerating twice produces identical
  output). Full `test_verbalization/` suite green (737/3 skipped). Pushed as commit
  51be24de.

### Open (awaiting developer reply, not resolved)
- `SURFACES_MODULE_PATH` hard-coded as a global: asked whether the ask is (a) derive
  the path from the target package itself (like `generate_orm.py` does, still a
  manually-run script) or (b) actually trigger generation from a package's
  `conftest.py` -- a bigger, different-in-kind change from a human-run/reviewed
  script. Not implementing either until the scope is confirmed.
- `OverriddenOperand`/`SymbolicCallable._placeholder_operand_overrides_` in
  `predicate.py`: developer questioned whether this testing-only mechanism belongs in
  source at all. Verified every real call site (`match.py`, `explanation.py`,
  `exceptions.py` doctest) -- `HasType`/`HasTypes.types_` is always a literal type,
  never symbolic, so this isn't really an "override" of a symbolic operand. Proposed:
  move the special-casing into `placeholder_operands()` itself (detect `Type`/
  `Tuple[Type, ...]`-typed fields and supply a literal default automatically), which
  would delete `OverriddenOperand` and `_placeholder_operand_overrides_` entirely --
  the opposite direction from round 2's own request to move overrides onto the
  classes. Awaiting confirmation before touching it either way.

### Next
- Once the developer answers both open threads, implement whichever design they pick,
  regenerate the snapshot again if the predicate.py mechanism changes, keep tests
  green, then push and reply-resolve.
