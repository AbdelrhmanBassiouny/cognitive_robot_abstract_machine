## #317: ORMatic dropped a field typed as an unparameterized generic (2026-09-11, done, pushed)

**Session.** https://claude.ai/code/session_0155Lgy4BZ7QcZHiRuxxJJyA

**What this is.** The `krrood` half of the fix that made #265's experiments CI job green, cut
off `main` as its own `bug`-labelled PR at the developer's request. One commit, `7599ef771`,
cherry-picked from #265's `5d9049212`; one conflict on the way, `example_classes.py`'s import
block, where `main` has since dropped `AbstractContextManager`.

**Root cause.** `WrappedTable.parse_field` skipped any field whose type is a generic class with
free type parameters. Sound for a field stored in a table, wrong for one stored by value, where
the value decides everything (a `SubclassJSONSerializer` names its own subclass in its JSON).
`is_stored_as_a_value` now exempts that case.

**Verified on this base, which #265's own measurement could not do.** Regenerating all five ORM
interfaces on `main` with and without the change gives byte-identical files — `main` has no field
of this shape yet — and `test/krrood_test` is 2352 passed, 34 skipped, 0 failed. The four new
tests fail with the change reverted and pass with it.

**Next steps.** Read CI on `7599ef771` directly; nothing is armed to watch it. #265 keeps its own
copy of the commit meanwhile, so it stays green without waiting on this PR; once this lands, the
next merge of `main` into #265 no-ops on it.

**Not tracked as a plan item**, by design: one bug-fix PR off `main` with a single root cause.
It is recorded in `icra-foundation`'s `roadmap.md` (2026-09-11 night section), which is where it
surfaced.
