# rdr-engine-extensions — standing rules

- Follow `.claude/personal/cram-notes.md` and this repository's `AGENTS.md`.
- SOLID is a review gate: a new capability enters as an abstraction plus small dataclass implementations, and strategies stay substitutable without touching the engine.
- TDD: failing test first, and no test is modified to make something pass.
- `krrood` stays self-contained; world-like scenarios are mimicked in `test/krrood_test/dataset`.
- Sessions may run in parallel only if their pull requests touch disjoint files *and* neither needs the other's branch as a base. Everything below `main` here is stacked, so "parallel" means parallel tracks, each internally sequential.
- The programme's working method — run the probe rather than reasoning, compare sorted collected test ids rather than counts, stage by explicit path — is recorded in `rdr-core-engine`'s roadmap and applies here unchanged.
