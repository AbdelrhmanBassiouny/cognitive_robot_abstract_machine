PR #98 (d-core-expert), branch D-core-expert.

Note: the task/branch scaffold this session was launched with named
`claude/pr-98-review-comments-btnexe`, which doesn't exist as a remote branch
and isn't PR #98's head (that's `D-core-expert`). Checked out `D-core-expert`
directly and pushed there, since that's what actually updates the PR; the
placeholder branch was never used.

Status: round-2 review comments addressed and pushed (commit ad75cf4e).
- Removed a docstring paragraph and merged the duplicate isinstance branches
  in `ConclusionDomain.validate()`.
- Made validators first-class: `AnswerValidator` ABC in `interface.py`, with
  `ConclusionValidator`/`ConditionsValidator` concrete implementations
  replacing the old lambdas.
- Errors container is now `List[DataclassException]` everywhere (was
  `Dict[AnswerName, DataclassException]`); every validation exception now
  presets its own `answer_name`.
- Split `NoAnswerProvided` into `NoConditionsProvided`/`NoConclusionProvided`
  subclasses with preset `answer_name`.
- Folded `CASE_VARIABLE_NAME`/`CASE_INSTANCE_NAME`/`EXIT_NAME`/`_ABORT_FLAG`
  into one `NamespaceName` StrEnum in `utils.py`.
- All 144 `test_eql_rdr` tests pass; `format_docstrings.py` run on touched
  files; PR description updated to match.
- Replied to and resolved all 9 open review threads (6 new + 3 from round 1
  that this round's implementation settled).

Next: PR stays in draft (per personal notes, always draft after a push).
Nothing else pending here - wait for the next round of review activity via
the PR subscription, or for the user to ask for `d-core-single-class` /
`d-core-backend` work.
