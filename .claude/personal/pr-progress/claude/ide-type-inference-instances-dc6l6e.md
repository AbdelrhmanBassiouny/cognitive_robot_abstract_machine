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
- [ ] Failing tests written
- [ ] Implementation
- [ ] Full test pass, push
