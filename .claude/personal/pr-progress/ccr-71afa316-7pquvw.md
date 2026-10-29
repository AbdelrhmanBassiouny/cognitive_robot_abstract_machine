PR #534 (draft, base `claude/festive-pascal-g09gl3` = #517). No upstream PR yet.

Plan
- Top-level `PullRequestLabelsRules` in `agent_rules.py` (#517's agents layout), regenerated `AGENTS.md`.
- Labels and the CODEOWNERS path come from enums in the root package: `cognitive_robot_abstract_machine/pull_request_labels.py` (`PullRequestLabel` base, `ChangeKindLabel`, `FrameworkLabel` named by directory, value = label text) and `repository_files.py` (`RepositoryFile.CODE_OWNERS`).

Done
- Merged #517 head (ddf666cb94); review thread (suggest labels on PRs not opened) fixed, resolved.
- 85235f3b9: StrEnum/PathEnumeration review threads (3) fixed, replied, resolved. Enums kept out of `agent_rules.py` because `RuleModule.import_from` caches `agent_rules` by bare name per process (a test importing it broke krrood's `test_agents_instructions` in a shared run). AGENTS.md byte-identical.

Next
- Re-merge #517 when it moves; retarget to `main` once it merges; `dev-tools` label upstream on promotion.
- Possible follow-up: basstler promotion links pass `labels=`; Basstler could import `PullRequestLabel` once it depends on krrood/this package.
