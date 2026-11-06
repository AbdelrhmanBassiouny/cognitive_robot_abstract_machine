Plan
- Rule + checkers (kw_only dataclasses, keyword-only methods) + pre-commit `krrood check`; migrate krrood and every caller/override it breaks (this PR, #560); then per-package PRs for the other packages' own definitions.

Done
- Draft PR AbdelrhmanBassiouny/cognitive_robot_abstract_machine#560 at 34c541868, labels api-break + new-feature; no new test failures vs pre-migration in any runnable package.

Next
- Wait for CI on #560 (ROS, ORM and libEGL tests were unverifiable locally); user discusses the break with code owners.
- Open question: extend the rule to module-level functions (suggested as a follow-up PR).
