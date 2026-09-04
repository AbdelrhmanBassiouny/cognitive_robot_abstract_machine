# PR #218 — plans-only Pages site (`stack-board-single-site`, `workflow-cutover`)

## Plan

Answer the 26-thread review round of 2026-09-04, which is what the item was stalled on while its
manifest called it healthy. Four recurring asks (hard-coded strings, `payload`, missing per-member
docstrings, no common error base) plus three questions (bash vs Python, the git command runner, the
Artifact path).

## Done

- **Blocker recorded before the resolution started**, then rewritten after it; roadmap carries both
  the finding and what the round changed. Dashboard republished twice.
- **Strings named**, taking #111's vocabulary wherever it already had one so the two branches'
  overlap stays an adoption: `RefreshArgument`, `RefreshSummaryKey`, `SitePath`,
  `RepositoryEndpoints`, `PullRequestListFilter`, `IssueField`, `detail`/`body` for `payload`.
  New: `RefreshDashboardCommand`, `ScriptArgumentParser` + one option enum per script,
  `NotesConfigurationKey`/`NotesEnvironmentVariable`/`NotesDefault`, `PlanDocument`,
  `PagesBuildType`, `SiteFile`, `LabelField`.
- **`errors.py`** — `PlanDashboardError`, a dataclass-exception base; all six of this branch's
  errors on it with typed fields, and the tests assert those fields rather than message text.
- **`publish_site.sh` → `publish_site.py`** on a new shared `git_commands.GitCommandRunner`, which
  `PersonalNotesBranch` and the test fixtures now use too.
- **Tests de-duplicated**: manifests are real files under `tests/fixtures/site/`, expectations read
  back off them; `tests/workflow_document.py` models the workflow; `PullRequestLabel` in the label
  assertions; the refresh stub declares its options from `RefreshArgument`.
- 630 tests pass across the four CI directories (from 611); plan-dashboard suite 312 (from 293).
  Pushed as `d61619ac`; PR still a draft; description rewritten.
- All 26 threads replied to, 23 resolved.
- **New plan item** `artifact-path-retirement` on `workflow-cutover`, at the user's direction, from
  the SKILL.md thread. Recorded on tracking issue #102.

## Outstanding — the user's, not this session's

- **CI is queued on `d61619ac`, not yet green.** Nothing failing; `mergeable_state` is `unstable`
  only because the matrix has not run.
- **Three threads deliberately left open** for the user to close: the git command runner (this
  package's rather than `.claude/stack`'s, to avoid depending on another skill directory's
  `sys.path` insertion), the error base (this branch's errors only, not `build_dashboard.py`'s
  three pre-existing ones), and the Artifact retirement (answered by the new plan item).
- The `d61619ac` commit message says "630 ... from 630"; the correct before-count is 611, as the PR
  description says.

## Next, if asked

Either of the two open engineering threads is a small, contained follow-up: import
`.claude/stack`'s runner instead, or port `build_dashboard.py`'s three errors onto
`PlanDashboardError`. Both were left as questions rather than decided unilaterally.
