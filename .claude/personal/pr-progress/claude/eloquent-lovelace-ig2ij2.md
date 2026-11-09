Plan
- Rule + checkers (kw_only dataclasses, keyword-only methods) + pre-commit `krrood check`; migrate krrood and every caller/override it breaks (this PR, #560); then per-package PRs for the other packages' own definitions.

Done
- Draft PR AbdelrhmanBassiouny/cognitive_robot_abstract_machine#560, labels api-break + new-feature.
- Merged main (8574ddf); head 3e6cedfb4. Local runs vs main: no new failures in any package that runs here (coraplex not comparable: ROS stand-ins).

Next
- Read CI on #560 at 3e6cedfb4 when the user prompts.
- User discusses the break with code owners. Open: extend the rule to module-level functions (suggested follow-up PR).

