## Plan (PR #74, branch claude/krrood-oracle-expert)

Follow-up to PR #73. User's instruction after PR #73's CI showed 4
`NonInteractiveTerminalError` failures (delimiter + race fixes confirmed working, but
recorded expert-answer fixtures still run out mid-fit): "create a function answerable
version where you yourself write a programmatic answer function (an oracle) that
mimics a human that generates these missing or fixes these incorrect expert answers...
But make this in a new PR not this PR. Also investigate first why the tests are
failing now when they used to run correctly find the real issue, the real change that
caused this."

## Done

1. Investigated the "used to pass" claim: found a historical CI run (commit
   `40e04f44`, pre-#71-merge, delimiter already broken) where
   `test_fit_scrdr`/`test_fit_mcrdr_stop_only`/`test_fit_grdr` reported PASSED in
   suspiciously fast times. Reproduced locally in an isolated worktree + live zoo
   dataset fetch: confirmed 0 answers load from the broken-delimiter fixture (exactly
   as expected), and confirmed hitting the old `IPythonShell.run()` retry loop with
   non-tty stdin genuinely spins forever (59MB of output in 20s) - so this exact
   scenario provably hangs locally. Could NOT reconcile this with that one historical
   CI run reporting a clean fast PASS despite the same code+data - ruled out
   PyQt6/RDRCaseViewer state leakage (PyQt6 isn't even an installed dependency,
   confirmed via pyproject/uv.lock), ruled out leaked test mocks (only my own
   properly-scoped ones exist), ruled out dataset-load failure/class skip (no
   "Failed to load dataset" in the log, tests explicitly report PASSED not SKIPPED).
   Left as an open, unresolved anomaly in that one specific historical run after
   extensive direct empirical testing - did not block moving forward since...
2. ...directly reproduced the REAL, current, live problem instead: with the
   delimiter genuinely fixed (11 real answers load from `scrdr_expert_answers_fit`),
   fitting the full 101-case/7-species zoo dataset locally exhausts all 11 loaded
   answers and falls through to the interactive shell needing a 12th - this is a
   concrete, reproducible confirmation that the recorded fixtures are simply too
   small for the real dataset, independent of the delimiter/race bugs PR #73 fixed.
3. Designed and implemented `Oracle(Expert)` in `krrood/.../experts.py`: answers
   `ask_for_conditions` by diffing the case's simple (bool/int/float/str) attributes
   against the corner case its rule conflicts with (via `row_to_dict`/
   `dataclass_to_dict`/`create_case` depending on case type) and returning a condition
   on the first differing attribute; returns `return True` when there's no corner case
   yet (bootstrap rule). `ask_for_conclusion` never guesses - returns the case query's
   already-known target or raises `OracleCannotInferConclusionWithoutTarget`. Added
   `NoDistinguishingAttributeFound`/`OracleCannotInferConclusionWithoutTarget` to
   `exceptions.py`.
4. TDD: added `test_oracle_expert.py` (unit tests against a small dataclass+Enum mimic
   dataset, not the real zoo dataset - covers condition-true-for-case/false-for-corner,
   attribute-exclusion of the predicted field, bootstrap unconditional rule, the
   no-distinguishing-attribute exception, and never-guesses-a-conclusion). Confirmed
   these fail with a clean `ImportError` before the implementation existed (stashed
   experts.py/exceptions.py and re-ran).
5. Added `test_fit_scrdr_with_oracle_expert_needs_no_pre_recorded_answers` to
   `TestAlchemyRDR` in `test_rdr_alchemy.py`: fits a `SingleClassRDR` against the full
   real 101-case zoo dataset with `Oracle()` and zero pre-recorded answers, asserts
   every case classifies correctly. Passes locally - this is the direct proof the
   approach closes the gap.
6. Ran the full `test_ripple_down_rules` suite (excluding the pre-existing, still-open
   Human-based full-dataset fit tests tracked by #73): 46 passed, 6 skipped, no
   regressions. Confirmed the 3 pre-existing Human-based tests still fail with the
   same `NonInteractiveTerminalError` as in real CI (unrelated to my changes, already
   tracked by #73).
7. Ran `docformatter` on all changed files (had to manually fix one docstring
   docformatter mangled - split a multi-line first sentence awkwardly).
8. Branched fresh off latest `main` (not off PR #73's branch, per instruction to make
   this a new PR) - resolved one stash-pop merge conflict in `test_rdr_alchemy.py`
   caused by PR #73's own not-yet-merged test method not existing on `main`; kept only
   the Oracle test. Committed (`d527dd5`), pushed, opened draft PR #74 against `main`,
   labeled `bug`, session link included, subscribed to PR activity. CI running.

## Next

- Watching PR #74's CI (just started, matrix over 9 libs) and any review comments.
- PR #73 itself is untouched by this PR; its own "answers insufficient" caveat/next
  steps are tracked separately (see PR #73 for that thread, not duplicated here).
- Also still watching PR #72 (giskardpy race fix) - separate branch-keyed progress
  file, not duplicated here.
