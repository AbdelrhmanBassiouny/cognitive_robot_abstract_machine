## PR #119 - reject closed pull request data that omits merged_at

Draft, `bug` label, based on fork `main`. Tracked as `merge-timestamp-required-fix`
in the `workflow-unification` plan (dashboards track).

**Origin**: the user asked why their own plan dashboard flagged `#103`/`#105` as
"closed without merging" when both are merged. Diagnosis: `pr_data.json` is
hand-assembled by a session; `merged_at` is the only signal separating merged from
closed-unmerged; `list_pull_requests` lets `fields` drop it *and* omits it entirely
when null; `#101` escaped only because it carries the manual `merged` label.

**Done**
- TDD: 3 `from_mapping` tests + 1 loader-context test, confirmed failing first.
- `MissingMergeTimestampError` for a closed entry missing the key; key-present-and-`null`
  stays the genuine closed-unmerged case. Constructor left permissive on purpose.
- `pr-data-fetching.md` `Fields` section + module docstring line; second commit adds the
  null-omission trap found while re-fetching.
- 198 plan-dashboard + 28 hook tests green; `test_claude_dev_tooling` green on CI.
- Plan manifest + roadmap addendum saved; dashboard republished at the same Artifact URL
  with `drift_count: 0`.
- Subscribed to PR activity. Per personal notes: no scheduled check-in armed.

**CI (2026-08-02)**
- User marked it ready for review and merged `origin/main` into the branch (`2b9a0eb8`).
- `test_each_lib (semantic_digital_twin)` red: two `test_multi_sim.py` texture/material tests
  (`assert '' != ''`). Identical failure on `main` at `9b090fc1` (run 30760195910), the very
  commit merged in - pre-existing on the base, unreachable from a `.claude/`-only diff.
  Stated once on the PR; nothing to fix here.
- `test_claude_dev_tooling` green.

**Next**
- Wait for review, and for the base branch to go green - then re-run CI here.
- If review lands it, flip the item to `done` in `plan.yaml` and republish the dashboard.
