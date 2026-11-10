Plan
- Rule + checkers (kw_only dataclasses, keyword-only methods) + pre-commit `krrood check`; migrate krrood and every caller/override it breaks (this PR, #560); then per-package PRs for the other packages' own definitions.

Done
- Draft PR AbdelrhmanBassiouny/cognitive_robot_abstract_machine#560, labels api-break + new-feature.
- Merged main (8574ddf); head 3e6cedfb4. Local runs vs main: no new failures in any package that runs here (coraplex not comparable: ROS stand-ins). CI at 3e6cedfb4: all 18 checks green.
- Promoted upstream: cram2/cognitive_robot_abstract_machine#923 (no reviews yet when read on 2026-11-10).
- Main fast-forwarded to 6fa88b1 made #560 conflict (rule_module.py, evaluation_context.py, logical_quantifiers.py, symbolic_math/exceptions.py). Merged it at da9a056: kept main's correlated-quantifier rewrite (drops the branch's Exists helpers) with keyword-only signatures/calls; migrated main's new krrood tests (kw_only dataclasses, keyword calls). Merge probe clean at da9a056. krrood local: 3139 passed; 2 failures + 1 error are environment-only (no graphviz dot, no SDT in venv). Other packages not rerun; static scan of main's new code found no positional krrood calls.

Next
- Read CI on #560 at da9a056 when the user prompts.
- User discusses the break with code owners. Open: extend the rule to module-level functions (suggested follow-up PR).
