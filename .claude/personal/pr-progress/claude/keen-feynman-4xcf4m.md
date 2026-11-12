## Plan
- Get upstream cram2#904 re-reviewed: tomsch420 and LucaKro requested changes on 9 Nov.

## Done
- 779240de9d: merged main b0e961c745 (7 conflicting files). The core boundary code is now keyword-only, as main's new rule requires, and `CodeRuleChecker.violations` now passes `path=`. `Role.is_same_semantic_entity` takes keywords. The duplicate `krrood-check` hook is dropped in favour of main's.
- 639eb3cd67, upstream review:
  - a core without `dependencies` no longer raises `KeyError` (mimic `dependency_free_core_distribution`);
  - `from_json` is now `from_pyproject_json_data` (Bass's choice over the AGENTS.md `from_json` convention);
  - `DeclarationFile` is a `PathEnumeration`;
  - `NoUserInputOrConclusionForCallableExpression` replaces the `ValueError` in `CallableExpression.__init__`;
  - `VariableVisitor.compares`, which nothing read, is removed.
- #547 restacked at b122c0104e: keyword-only drawing methods and test calls.

## Next
- Reply on the 10 upstream threads; the session can't comment upstream.
- Check CI at 639eb3cd67 and b122c0104e.
