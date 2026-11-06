Plan
- Rule + checkers (kw_only dataclasses, keyword-only methods) + pre-commit `krrood check`; migrate krrood and every caller/override it breaks (this PR, #560); then per-package PRs for the other packages' own definitions.

Done
- Draft PR AbdelrhmanBassiouny/cognitive_robot_abstract_machine#560, labels api-break + new-feature.
- CI at 34c541868: all 1,298 failures (6 packages) came from a positional LeftOf/RightOf call in robot_part_mixins.py; fixed in 10bad04db.

Next
- Read CI on #560 at 10bad04db; fixing the robot loading may expose failures it masked (PR2/xacro tests cannot run locally). User discusses the break with code owners.
- Open question: extend the rule to module-level functions (suggested as a follow-up PR).
