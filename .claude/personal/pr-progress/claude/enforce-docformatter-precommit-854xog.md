## PR #69: Enforce docformatter repo-wide via pre-commit

Status: draft PR open, CI green, no review comments yet, subscribed to
activity. Merge is blocked while draft — mark ready only when told to.

### Done

- Diagnosed a real docformatter 1.7.8 bug: `_get_attribute_docstring_newlines()`
  doesn't skip decorators, so it always forces 1 blank line before a
  `@dataclass`-decorated top-level class/def where black wants 2 - this
  oscillates forever with black for any static setup.
- Built `scripts/format_docstrings.py`: a local pre-commit hook that runs
  black -> docformatter -> black again per file, and only keeps
  docformatter's docstring changes if that final black pass is a no-op.
  No hardcoded exclude list; the ~19 conflicting files are found dynamically
  every run.
- Hand-fixed 2 files (collection_reader.py,
  outlier_removal_objecthypothesis.py) whose stray orphan strings (used like
  comments) were tripping a separate docformatter corruption bug.
- Reformatted the repo (737 files) and verified `pre-commit run --all-files`
  passes and is idempotent.
- Ran krrood's full test suite: 1672 passed, 9 pre-existing skips, no
  regressions.
- Opened PR #69 against `AbdelrhmanBassiouny/cognitive_robot_abstract_machine`
  main, converted to draft, added session link, subscribed to PR activity.
- User resynced `main` with `cram2` (fast-forward, 22 new unrelated commits
  from the EQL SymbolicFunction stack). Merged the new `main` into this
  branch (rebase kept getting blocked by the auto-mode classifier as
  "discarding incoming changes" even after explicit go-ahead - merge worked
  instead). Resolved the 3 conflicting files (predicate.py,
  parts_of_speech.py, test_symbolic_function_verbalization.py) by taking
  main's content and re-running scripts/format_docstrings.py on it.
- Also caught and fixed: 9 files (RDR expert-answer fixtures +
  entity_query_language/core/bound_value.py) that had never actually been
  correctly formatted in the original commit - a `git checkout --` revert of
  test-run pollution earlier had restored a stale unformatted snapshot
  instead of the real formatted content. Fixed in a follow-up commit.
- Pushed the merge (f3bbfd3). PR base now matches current main. krrood suite
  re-verified: 1675 passed (+3 from the merged-in EQL tests), 9 skipped, no
  regressions.

### Next

- Wait for review comments / fresh CI signal on the updated head; scheduled
  check-in ~1h out.
- Mark ready for review only when explicitly asked to.
- If the maintainer wants any of the 19 fallback files fixed by hand instead
  of left black-only, do that as a follow-up rather than blocking this PR.
- Watch for any test-run side effects (RDR expert-answer fixtures, generated
  PDFs, dataset ormatic_interface.py) polluting the working tree again if
  krrood's tests get re-run locally - revert them before committing.
