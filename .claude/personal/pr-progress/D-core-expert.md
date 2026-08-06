PR #98 (d-core-expert), branch D-core-expert.

Note: sessions working this item are launched with scaffold branches that
are not PR #98's head (that's `D-core-expert`). Check out `D-core-expert`
directly and push there - that is what actually updates the PR. The
plan-dashboard tooling only exists on `main`, so switch back to the
session branch to run save-plan.sh / the dashboard scripts.

## Status: all four handed-back items landed (2026-08-06, commit 28a89ff4)

A /plan-item-resolve session found that #98 was not stalled on code:
mergeable_state clean, and **all 27 review threads resolved** - including
PRRT_kwDOQhJw3c6VZoGj (interface.py L127, "why keep the __call__ methods?")
which the previous version of this note recorded as still open and waiting.
The developer had resolved it without a counter-argument. **Decision: keep
AnswerValidator.__call__.** Do not remove it.

What was actually outstanding was roadmap section 11's four handed-back
items, none of which had been implemented. Item 4 had no answer anywhere
(PR, tracking issue #94, roadmap); put to the developer, who chose to
**segregate ExpertInterface**.

Landed:

1. `ConditionResolver.resolve(context, target_knowledge, current_knowledge)`
   across all four definitions - eight flattened params to three. Firing
   anchor read off `context.trace.firing_anchor`; `_active_path` guards on
   both an absent trace and an absent anchor (the trace-is-None case is new,
   it is what an empty rule tree produces). All 10 call sites in
   test_condition_resolver.py moved over, plus one new test.
2+4. `ExpertInterface` cut down to the Q&A surface. `on_save`, `save()` and
   `make_progress_reporter()` are gone. `ModelSaver`/`NullModelSaver`/
   `FileModelSaver` landed in **serialization.py** (beside save_rdr_with_case,
   not in a new persistence.py - a new module would have had to import it
   anyway); `NullProgressReporter` in progress.py. The RDR holds both.
3. `ProgressDescription(StrEnum)` in progress.py replaces
   `_FITTING_DESCRIPTION`. Note the tension: that global does not exist on
   this branch, so this ships a type whose consumer arrives with
   d-core-single-class. Same shape as CaseContext in round 1.

## Verification (this container needs setup)

The default interpreter is 3.11; pyproject requires >=3.12,<3.13, and 3.11
fails in class_diagram.py on `make_dataclass(module=...)`. Build a 3.12 venv
and install the dependency set; `probabilistic_model`'s `relational.rspn`
submodule is missing from the PyPI release and blocks 6 test_eql_rdr tests
either way (roadmap section 9's documented gap).

Compare before/after, never absolute counts:
- test_eql_rdr: 6 failed/113 passed before, 6 failed/125 passed after -
  identical failure set, +12 exactly the new tests.
- test_eql: failure sets byte-for-byte identical (211 entries) both sides.

## CI is a real, unsolved problem on this PR

No workflow run has ever been queued since b772e959 (2026-07-30). ad75cf4e,
ed805dc7 and 28a89ff4 all triggered nothing. It is not repo-wide (ci.yml ran
on a dozen other branches through 2026-08-05) and ci.yml has no
workflow_dispatch, so it cannot be forced. **"Push a commit to get a
baseline" does not work - that was tried and failed.** Best lead: right
after the push GitHub reported mergeable_state `unknown`, and a
pull_request workflow runs against refs/pull/98/merge, which cannot exist
while mergeability is unresolved. See roadmap section 14.

## Not this PR's problem, but watch it

D-core-support (#67), this item's base, is now mergeable_state dirty with
needs-resolution - D-core-serialization moved to 08f2fbdd on 2026-08-03
while #67 stayed at 8eb7518a. #98 is still clean against its own unchanged
base. Steward's job.

## Done this session

PR description rewritten to cover all four items; #76 told what it must
absorb (comment 5201827158: interactive.py:231/335/440, magics.py:171);
plan.yaml + roadmap.md section 14 updated and saved; dashboard republished.
PR left in draft per convention.

Next: nothing pending from this session. d-core-single-class can start - it
consumes NullModelSaver/NullProgressReporter/ProgressDescription and is
where FileModelSaver gets its engine-level round-trip coverage.
