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

Draft PR: #86 (off `main`, subscribed to all events).

Review round 1 (5 comments), addressed and pushed in 92d4a9b3:
- Code changes, threads resolved: `class_implements_own_method` redesigned to take two
  already-resolved methods instead of `(cls, base_class, method_name)` (no more
  `getattr_static`); `phrase_rule._is_guarded` reverted to the plain `is not` comparison
  (`when` is never a classmethod/staticmethod, so the util was needless indirection there).
- Explained, thread resolved (no code change): why `assert_every_callable_has_a_fragment`
  isn't redundant with Python's abstractmethod enforcement (the coverage assertion explicitly
  excludes fragment-less classes, so only this one catches them, and immediately rather than
  lazily).
- Open, awaiting developer decision (replied with reasoning + a question, NOT resolved):
  whether `SymbolicCallableOverride.operands` should narrow from `Dict[str, Any]` to a
  `(name, types: Tuple[Type,...])`-shaped list; whether the three separate `assert_*` tests
  should collapse into one `SNAPSHOT.test()` (offered an additive convenience method instead
  of replacing them).

Note: personal-notes had a save race with a concurrent P2 session — my first "P1 done" edit to
this file got clobbered by a later save from that session (which only had P2's edit, not
mine). Re-applied here; P2's own entry above was left untouched. Watch for this if working
notes concurrently with another session.

Next: watching CI on 92d4a9b3 (self check-in loop). Once the two open threads get a decision
from the developer, apply/skip accordingly, then merge before #33 rebases. P2 is already done
(PR #87) in parallel.
