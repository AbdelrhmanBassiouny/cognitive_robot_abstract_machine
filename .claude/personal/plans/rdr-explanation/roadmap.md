# rdr-explanation — standing rules

- Follow `.claude/personal/notes.md` and this repository's `AGENTS.md`.
- SOLID is a review gate: a new capability enters as an abstraction plus small dataclass implementations, and strategies stay substitutable without touching the engine.
- TDD: failing test first, and no test is modified to make something pass.
- `krrood` stays self-contained; world-like scenarios are mimicked in `test/krrood_test/dataset`.
- The programme's working method — run the probe rather than reasoning, compare sorted collected test ids rather than counts, stage by explicit path — is recorded in `rdr-core-engine`'s roadmap and applies here unchanged.
