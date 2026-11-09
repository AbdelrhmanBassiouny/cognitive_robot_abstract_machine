Plan
- Rule + checkers (kw_only dataclasses, keyword-only methods) + pre-commit `krrood check`; migrate krrood and every caller/override it breaks (this PR, #560); then per-package PRs for the other packages' own definitions.

Done
- Draft PR AbdelrhmanBassiouny/cognitive_robot_abstract_machine#560, labels api-break + new-feature.
- Merged main (8574ddf) at 3982b9c0b + format 91ad9a382; main's new krrood code migrated; krrood tests pass (3,077) locally.

Next
- Finish rerunning the other packages against main (scratchpad all_packages.sh); fix any new failures; then read CI on #560 at the latest head.
- User discusses the break with code owners. Open: extend the rule to module-level functions (suggested follow-up PR).

