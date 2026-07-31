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

Round 3 (commit ed805dc7, thread PRRT_kwDOQhJw3c6VZE0H now resolved): dev
pushed back on my "keep the logic on ConclusionDomain" recommendation,
proposing instead that ConclusionValidator.validate() own the actual checks
(reading self.domain) while ConclusionDomain.validate() becomes a one-line
delegation (`return self.validator(allow_unset).validate(value)`) - keeping
the direct-entry-point tests working without duplicating logic. Agreed and
implemented, plus the previously-agreed rename: AnswerValidator.__call__ is
now a concrete forwarder to a newly-abstract `validate()`;
ConclusionValidator/ConditionsValidator implement `validate()` instead of
`__call__`. All 144 tests still pass.

Open discussion (unresolved, thread PRRT_kwDOQhJw3c6VZoGj, interface.py L127,
AnswerValidator.__call__): dev asked "why keep the __call__ methods?" after
round 3's rename. Replied explaining it's kept so `request.validate(value)`
still works as a plain callable in `ExpertInterface._validate()` (the field
is literally named `validate`, so without `__call__` that call site becomes
the stutter `request.validate.validate(value)`). Offered to drop `__call__`
entirely and call `.validate()` explicitly everywhere if they'd rather.
Waiting on their answer - do NOT remove `__call__` until they confirm which
way they want it.

PR marked ready for review by the dev themselves (not a draft-after-push
situation, so left as-is - the always-draft-after-my-own-push rule doesn't
apply to their own explicit action). mergeable_state clean as of this check.

Nothing else pending - wait for the next round of review activity via the PR
subscription, or for the user to ask for `d-core-single-class` /
`d-core-backend` work.
