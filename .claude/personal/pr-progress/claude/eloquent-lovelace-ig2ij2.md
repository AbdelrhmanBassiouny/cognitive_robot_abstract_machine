Plan
- Rule + checkers (kw_only dataclasses, keyword-only methods) + pre-commit `krrood check`, then migrate krrood and every caller/override it breaks, then per-package PRs.
- Decisions: EQL predicates/symbolic functions go keyword everywhere; mechanical migration commit uses --no-verify; add an explicit opt-out marker the checker honours for methods Python calls positionally (e.g. `@rdr.decorator`).

Done
- Commit 735c4b833 pushed: checkers, rules, hook, dev tools migrated, 53 dev-tool tests pass.
- Uncommitted WIP (616 files, patch at scratchpad/wip_krrood_migration.patch): krrood definitions kw-only, ~5k call sites, overrides renamed, callbacks wrapped in lambdas, NodeVisitor exemption, SpecificityRule uses **subject.

Next
- Add positional opt-out marker to checker + rule + test; restore `decorator` methods with it.
- Fix predicate.py `__new__`/symbolic_callable_to_function binding for kw_only; convert positional predicate calls.
- Loop: scratchpad/migrate.py runtime on krrood tests (stubs on PYTHONPATH) until green; then other packages; regenerate ORM; format; commit --no-verify; open draft PR.
