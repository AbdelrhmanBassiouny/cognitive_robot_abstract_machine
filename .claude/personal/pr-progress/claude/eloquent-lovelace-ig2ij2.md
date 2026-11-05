Plan
- Rule + checkers (kw_only dataclasses, keyword-only methods) + pre-commit `krrood check`, then migrate krrood and every caller/override it breaks, then per-package PRs.
- Decisions: EQL predicates/symbolic functions go keyword everywhere; mechanical migration commits use --no-verify; `@called_positionally` marks methods Python calls positionally.

Done
- 735c4b833 checkers/rules/hook; 6a25ea55b WIP migration (~5k call sites); 4b671b77f marker + keyword-only SymbolicCallable.__new__ and symbolic_callable_to_function.

Next
- Run scratchpad/predicate_calls.py --write (rewrites positional predicate calls), review MANUAL lines.
- Loop: scratchpad/migrate.py runtime on krrood tests (source scratchpad/env.sh) until green; then other packages; regenerate ORM; format; commit --no-verify; open draft PR.
