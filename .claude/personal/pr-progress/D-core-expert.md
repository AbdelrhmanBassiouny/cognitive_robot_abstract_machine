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
