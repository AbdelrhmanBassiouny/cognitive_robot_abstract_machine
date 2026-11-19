# PR #613 — namespace-package (krrood-light-core), krrood-distributions folded in

## Done
- Merged main (conflicts in krrood/utils.py, test_version_consistency.py); import_scope, new on main, gets its own module logger.
- CI's 35 krrood failures (generated RDR/EQL source importing `entity_query_language` without `krrood.`): `get_import_root_from_path` now steps over a namespace-package portion. Test first in test_namespace_package.py. Full krrood suite locally: same 4 failures + 1 error as main in this environment (no `dot` binary, symbolic-math jacobians), nothing new.

## Decisions (user, 2026-11-19)
- krrood-distributions folded into this item.
- EQL ↔ ORMatic cycle broken in this PR: SQL backend (entity_query_language/backends.py's eql_to_sql user), entity_query_language/orm/model.py and testing/result_verification.py's ORMatic use move to krrood.ormatic.
- Layout krrood/<distribution>/src/krrood/<part>; krrood/pyproject.toml becomes the `krrood` meta distribution.
- Mine: source_analysis.property_return_statement moves into EQL (its only user is entity_query_language/predicate.py); the rest of source_analysis stays core.

## Next
1. Break EQL → ORMatic (tests first: a fresh interpreter importing krrood.entity_query_language loads no krrood.ormatic module).
2. Move property_return_statement into EQL.
3. Declare the per-distribution map (one place), move files with git mv, write each pyproject, meta distribution, workspace wiring, CI per distribution on Linux and Windows.
