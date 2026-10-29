PR #534 (draft, base `main`). Upstream: cram2#826 (approved by Tigul, sunava, LucaKro).

Plan
- Top-level `PullRequestLabelsRules` in `agent_rules.py`, regenerated `AGENTS.md`: kind-of-change labels only; framework labels left to upstream's `.github/labeler.yml`.
- Enums in the root package: `pull_request_labels.py` (`ChangeKindLabel`) and `repository_files.py` (`RepositoryFile.CODE_OWNERS`, `.LABELER_CONFIGURATION`); kept out of `agent_rules.py` because `RuleModule.import_from` caches `agent_rules` by bare name.

Done
- b0b2b07cc: merged main (cramera removed upstream, labeler added in 611d45f73); dropped `FrameworkLabel`, the member-less `PullRequestLabel` base and their test; new rule never to set/suggest framework labels. Answers LucaKro's "combine with jonas' labeler".

Next
- User: update cram2#826 title/description to the fork PR's, reply to LucaKro, add `dev-tools`/`new-feature`.
- Possible follow-up: basstler promotion links pass `labels=`.
