P1 of the EQL verbalization follow-up (surface-verification API polish), off `main`.

Plan: extract the surface-verification framework from `eql-symbolic-function-sdt` onto `main`
so #33 can drop it on rebase, applying the agreed API polish.

Done:
- `entity_query_language/verbalization/surface_verification.py` — `VerbalizationSurface`,
  `SymbolicCallableOverride` (typed per-class value operands), `SymbolicSurfaceSnapshot`.
- `class_diagrams/utils.py` — general `class_implements_own_method` (classmethod/staticmethod
  aware) + unit test `test_class_diagram/test_class_implements_own_method.py`.
- `has_fragment` uses it; `module_and_class_name` replaces local `qualified_name`; param docs.
- DRY: `phrase_rule._is_guarded` reuses the util. Docstring added to `module_and_class_name`.
- krrood surface test/snapshot rewired onto the framework.
- black + `scripts/format_docstrings.py` run; committed (human identity) and pushed.

Verified: surface test 3/3, util test 7/7, `test_verbalization/` green bar 2 pre-existing
`jpt`-import env failures (unrelated).

Next: open the draft PR off `main` (per personal-notes workflow: draft, session link,
subscribe to all events). Then P2 (operand-naming architecture) is the keystone that gates #33.
