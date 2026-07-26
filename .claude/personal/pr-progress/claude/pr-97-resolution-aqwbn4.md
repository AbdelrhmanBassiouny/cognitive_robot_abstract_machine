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

- Ruff check-vs-format question resolved and thread closed: confirmed empirically
  (diffed check-only vs format-only vs both against the real generated source) that
  `run_ruff_check_on_file` and `run_ruff_format_on_file` do non-overlapping jobs
  (import sort/typing-modernization vs line-wrap/quote-style) -- both calls stay.
- Conftest-driven regeneration (developer confirmed: run at every test run, from
  conftest, like ormatic, reusable for any package): added
  `regenerate_verbalization_surfaces(package, destination)` to `surface_generation.py`
  (atomic temp-file + `os.replace`, mirroring `generate_sqlalchemy_interface()`);
  `test/krrood_test/conftest.py` calls it right after the ormatic one. Deleted the now-
  obsolete `krrood/scripts/generate_verbalization_surfaces.py`, deleted
  `test_verbalization_surfaces.py` (its two assertions became tautological once the
  file is always freshly regenerated before it's imported), and deleted
  `test_generated_krrood_module_matches_the_committed_file` from
  `test_surface_generation.py` for the identical reason (explicit developer ask,
  flagged the CI-visibility trade-off this accepts, matching the `ormatic_interface.py`
  precedent already in this repo). Kept the one test that exercises generation logic
  against a small controlled domain. Verified: `test_verbalization/` +
  `test_code_generation/` + `test_class_diagram/` green (876 passed/3 skips), full
  `test/krrood_test/` green (2003 passed/6 skipped, only the 2 pre-existing unrelated
  `graphviz`/`dot` failures). Pushed as commit 12247569. PR description rewritten to
  match. Both clean-fix threads + both newly-clear threads (conftest scope, ruff
  check-vs-format, and the byte-comparison-test question) replied and resolved.

### Open (awaiting developer reply, not resolved)
- `OverriddenOperand`/`SymbolicCallable._placeholder_operand_overrides_` in
  `predicate.py`: developer rejected the type-based auto-detection I'd proposed ("no
  rule to automate by type") and floated two alternatives instead: (a) detect from the
  verbalization fragment's own implementation that it accesses a field's raw value, or
  (b) always fall back to first-order form. Replied with concrete problems for each
  against `HasType` specifically: (a) the fragment's `fields["types_"]` access is
  syntactically identical to every other field access -- nothing to distinguish by
  inspection at that layer, asked for a concrete statement shape to detect if they mean
  something more specific; (b) first-order form renders every operand generically and
  would lose the named "Integer" example the committed surface actually wants, unless
  scoped per-field -- which is functionally the override mechanism again. Also still
  need to apply their "hard-wired example-value tests, not exhaustive per-class" testing
  convention once the mechanism itself is settled. Not implementing until they clarify.
- Subscription: `subscribe_pr_activity` failed twice in a row with a generic error (not
  the "already watched by a steward" message the tool documents) -- PR has no watching
  label, so cause unclear. Flagged to the developer rather than retried further; may be
  worth trying again next session.

### Next
- Once the developer clarifies the OverriddenOperand mechanism, implement it, add the
  hard-wired example-value tests they asked for, regenerate the snapshot if wording
  changes, keep tests green, then push and reply-resolve.
- Retry `subscribe_pr_activity` next session if the developer wants events watched.
