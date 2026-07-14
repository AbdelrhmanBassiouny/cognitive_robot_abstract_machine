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

### Next

- Wait for review comments / CI signal; scheduled check-in ~1h out.
- Mark ready for review only when explicitly asked to.
- If the maintainer wants any of the 19 fallback files fixed by hand instead
  of left black-only, do that as a follow-up rather than blocking this PR.
