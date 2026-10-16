PR #515 (draft, on #503), item actions-budget/changed-library-matrix.

Plan
- basstler: count a matrix with a run-time `exclude` by its static axes.
- basstler module: changed paths -> matrix libraries + pyproject dependents -> exclusions; tooling/docs-only -> tooling job alone; other paths -> everything.
- ci.yml: `changed-libraries` first job (replaces to-lowercase), one `lib` axis + computed exclude; drafts narrowed, everything else full.
- Keep ci.yml override 16 (worst case, user-approved), reword its comment.

Done
- Branch, draft PR, manifest + roadmap recorded.

Next
- Tests first for the counting change, then the selector, then ci.yml.
