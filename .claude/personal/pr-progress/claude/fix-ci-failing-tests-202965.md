## claude/fix-ci-failing-tests-202965 - krrood import-scope tolerance

**Root cause (found by reading CI, not guessing).** Fork `main` CI is fully
green; the only red thing in the repo was PR #169
(`montessori_fast_inline_monitor`). Its four failing lib jobs
(semantic_digital_twin, giskardpy, coraplex, experiments) are exactly the four
that run the `Build ORM` step, and all four die the same way:

    NameError: name 'InferenceExplanation' is not defined
      -> krrood resolve_name_in_hierarchy -> get_scope_from_imports
      -> ModuleNotFoundError: No module named
         'semantic_digital_twin.orm.ormatic_interface'

krrood's `_handle_import_from_node` already tolerated *a name missing from an
imported module* (logs once, skips) but let *the module missing altogether*
raise straight out of the AST walk, losing the whole scope.

`main` only escapes this because `scripts/regenerate_all_orm.py` empties the
interface file rather than deleting it ("so that a stale version cannot be
imported while the new one is being generated"). #169 replaces that script with
`cognitive_robot_abstract_machine/orm_interfaces.py`, whose `remove()` calls
`path.unlink()` - a deliberate design change (interfaces ignored, not tracked
empty). Under that design the module is genuinely absent and krrood's
intolerance becomes a hard blocker.

**Done.** Fix committed and pushed as `a4990cfe`:
- failing test first: `test_get_scope_from_imports.py::
  test_scope_holds_the_other_imports_when_one_targets_a_missing_module`, with
  mimic `dataset/type_checking_import_of_missing_module.py` (snippet in its own
  .py file, per AGENTS.md - no inline string)
- `_handle_import_from_node` now skips a from-import whose module cannot be
  imported, logging once, same as the missing-name case
- renamed `_warn_about_unresolvable_type_checking_import_once` ->
  `_log_unresolvable_import_once` (it is no longer TYPE_CHECKING-specific)
- a plain `import x` of a missing module still raises, so the existing
  `test_get_scope_from_imports_invalid` keeps its meaning, unmodified

**Verified.** Whole collectible krrood suite before/after in this container:
zero newly broken, 9 newly passing (`test_wrapped_field.py` x8 and
`test_cyclic_imports.py::test_unfinished_type_field_info` - they were failing
here through this exact bug, on the very same `InferenceExplanation` NameError).
Remaining failures in this container are environment-only: missing robotics
deps, and `make_dataclass(module=...)` which needs Python 3.12 (container has
3.11, CI has 3.12).

**Next / open.**
- No PR opened - not asked for. Branch is pushed and ready if wanted (draft +
  `bug` label + session link, per notes).
- This fix does *not* by itself make #169 green: it removes the hard abort, but
  #169's `InferenceExplanation` forward reference is still unresolvable at
  runtime, and that is #169's own code on #169's branch. Worth telling whoever
  owns #169.
- Not subscribed to any PR and no check-ins armed, per notes.
