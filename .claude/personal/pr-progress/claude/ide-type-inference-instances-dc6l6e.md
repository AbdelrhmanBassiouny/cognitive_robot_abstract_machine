# IDE type inference for a/an/the(ClassName)

## Problem
`a/an/the(ClassName)` returns `Match[T]` statically, so IDEs suggest Match's
attributes after `.` instead of ClassName's, and constructor-style kwargs in
`a(ClassName)(field=...)` aren't recognized. Reproduced with mypy: attribute
access errors with [attr-defined]; call result union makes `.from_` chains
error.

## Plan
1. TDD: extend the mypy fixture (test_typing/quantifier_overloads_fixture.py)
   with the desired instance-like contract; add runtime tests for direct
   symbolic attribute access on Match (currently AttributeError).
2. Fix: overloads for the Type[T]/Callable paths return Union[T, Match[T]]
   (house "static lie" idiom, cf. variable()); Match.__call__ ->
   Union[T, Self]; add runtime Match.__getattr__ delegating to
   .expression (dunder guard via SymbolicDunderAccessError, underscore names
   raise AttributeError); new exception for __call__ after the match was
   already lowered.
3. Run typing test + test_match.py + broader EQL suite; format docstrings;
   commit + push.

## Status
- [x] Environment set up (venv312, krrood + deps editable)
- [x] Baseline typing test passes; complaint reproduced under mypy
- [x] Failing tests written (new fixture sections + 6 runtime tests in test_match.py)
- [x] Implementation: overloads return Union[T, Match[T]]; Match.__getattr__/__dir__
      delegate to expression; noun state renamed to _x_ convention (Match,
      AbstractMatchExpression, AttributeMatch, HasFactoryAndKwargs) so public
      namespace belongs to the matched class (parent/child/name no longer shadowed);
      CalledMatchAfterResolution guard; consumers updated (backends, parameterizer,
      verbalization match planner, coraplex plan_node)
- [x] krrood suite green (992 passed; assembler doctest fixed to _variable_ form
      because delegated attrs verbalize as "the battery of the Robot" not "its")
- [x] Final full-suite confirmation: 2154 passed, 6 skipped, 0 failed
      (test_object_diagram deselected - `dot` binary missing in container,
      fails identically on clean main)
- [x] Committed (147d098d2) and pushed to
      claude/ide-type-inference-instances-dc6l6e. No PR opened (not requested).

## Plan linkage (added 2026-08-19)
This branch is now item `match-underscore-rename-and-forwarding` of the
`match-query-ergonomics` plan (tracking issue #181) - it implemented that
item ahead of its dependency. Verified: `q.where(q.battery >= 50)` via the
new forwarding silently does not filter (the plan's wave-1 bug,
`where-query-rooted-attribute-no-filter`), so this branch must not land
before that bug fix.

## Next steps
- Blocked on plan item `where-query-rooted-attribute-no-filter` (fix off
  main, bug label) before any PR for this branch.
- Reconcile before PR: decide whether to restore `variable` /
  `matches_with_variables` as transitional public properties (D-core
  stack's test_underspecified_match.py consumes both) or time the landing
  after the stack cascades; add the old-names-are-really-gone guard test.
- Cosmetic follow-ups for item 3: doc examples still teach
  `.expression.parent`; delegated attributes verbalize as "the battery of
  the Robot" rather than "its battery".
