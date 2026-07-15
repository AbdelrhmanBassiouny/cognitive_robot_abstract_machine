## Plan (PR #73, branch claude/krrood-expert-answers-race-condition)

User's instruction: "i cannot merge 73 while it's failing, merge #74 in it so that it
succeedes or make 74 it's parent instead of main." Goal: make PR #73's own CI green so
it can be merged, using PR #74 (the Oracle expert) as one lever, but ultimately by
finding and fixing the REAL cause of the remaining `NonInteractiveTerminalError`
failures.

## Done

1. Merged `origin/claude/krrood-oracle-expert` into this branch (`ce01959`) - resolved
   one conflict in `test_rdr_alchemy.py` (kept both my own
   `test_get_fit_scrdr_does_not_mutate_committed_expert_answers_fixture` and #74's
   `test_fit_scrdr_with_oracle_expert_needs_no_pre_recorded_answers`). Oracle now
   available on this branch too.
2. Investigated whether Oracle-based fixture regeneration would actually be needed:
   discovered `get_fit_scrdr` (the shared helper, used by many currently-PASSING
   tests) already succeeds with the CURRENT committed fixture over the full 101-case
   dataset, while tests that construct `Human` directly (bypassing the helper) fail -
   despite both reading the identical committed file. Traced this down empirically
   (side-by-side load-count comparisons) to `get_fit_scrdr`'s double-load pattern
   (`Human.__init__` loads-then-deletes an isolated copy, then an explicit
   `load_answers()` call falls back to a STRAY LEGACY `.json` sibling file with one
   extra entry) - a real but fragile/accidental behavior, not a robust fix path.
3. Kept digging and found the ACTUAL root cause: `_load_answers_from_python` splits on
   the exact byte sequence `"\n\n\n'===New Answer==='\n\n\n"`, requiring THREE
   trailing newlines after the last answer's delimiter. The committed fixtures (after
   the same formatting commit `f3bbfd3` that broke the quote-style) end with only ONE
   trailing newline, so the last delimiter never matches and `[:-1]` silently drops
   that last recorded answer from EVERY fixture file. Verified directly:
   `scrdr_expert_answers_fit` has 12 real recorded answers (confirmed via AST-based
   `extract_function_or_class_file`, independent of the delimiter), but only 11 were
   ever loaded - and fixing just the split recovers the 12th, after which the full
   101-case fit succeeds with **zero misclassifications** using only the pre-existing
   recorded answers. Not a shortage of answers at all - a loader bug.
4. Fixed `_load_answers_from_python` in `experts.py`: now splits on the bare delimiter
   marker (`self.answer_delimiter`, a new shared class attribute also used by
   `_save_to_python`) instead of an exact whitespace run, tolerant of any formatter
   trimming trailing blank lines. Commit `00bd873`.
5. TDD: added `test_expert_answer_loading.py` -
   `test_load_answers_recovers_the_last_answer_even_without_trailing_blank_lines`
   reproduces the bug directly (save 2 answers, strip trailing blank lines exactly
   like a formatter would, assert both still load). Confirmed fails pre-fix
   (`assert 1 == 2`), passes post-fix.
6. Validated: ran the four originally-failing tests
   (`test_rdr_alchemy.py::test_fit_scrdr`/`test_fit_mcrdr_stop_only`/`test_fit_grdr`,
   `test_rdr.py::test_fit_mcrdr_stop_only`) directly, unmodified, against the real
   committed fixtures - all 4 PASS now. Ran the full `test_ripple_down_rules` suite:
   86 passed, 6 skipped, 0 failed (previously this count excluded `test_rdr.py`/
   `test_rdr_alchemy.py` entirely due to these failures).
7. Ran `docformatter` on changed files. Committed, pushed (`00bd873`).
8. Updated PR #73's description to explain all 3 fixes + the merged-in Oracle infra.
   Commented on both #73 and #74 explaining the real root cause superseded #74's
   original "insufficient answers" framing (Oracle itself is unaffected/still valid,
   just wasn't actually needed to fix these 4 specific tests).

## Next

- Watching PR #73's CI (just pushed `00bd873`) to confirm it goes fully green in real
  CI, not just locally.
- Once green, this PR should be mergeable - no more known blockers.
- Also still watching PR #72 (giskardpy race fix, unrelated `test_script_launch_and_kill`
  subprocess-timeout flake seen once, not this PR's concern) and PR #74 (Oracle,
  independently useful, own progress not duplicated here).
