## Plan
- Get #66 green on `main` so it can be promoted: follow `main`'s backward-inference rename and keyword-only calls.

## Done
- Retargeted #66 onto `main` (D-core-corner-case merged); merge probe clean at `7f9247f19`.
- `345b5fbfa`: test import -> `get_conclusion_sufficient_conditions_from_a_rule_tree`, `evaluate_against(shared_variable=, case=)`; `render(template_name=)` and `generate(function=)` in `serialization.py`. Local `test_eql_rdr` + `test_code_generation`: 170 passed.

## Next
- Read CI on `345b5fbfa`. If `test_each_lib (krrood)` is green, remove the `integration-conflict` label (2026-09-29) so the pass can promote.
- `save_rdr_with_case`'s FunctionCase path gets its test with the engine slice (`rdr.function_case` is not on this branch).
