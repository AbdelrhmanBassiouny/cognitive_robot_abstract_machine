# PR #218 — plans-only Pages site (`stack-board-single-site`, `workflow-cutover`)

## Plan

Answer the review rounds the item was stalled on. Round one (2026-09-04) was 26 threads: four
recurring asks (hard-coded strings, `payload`, missing per-member docstrings, no common error base)
plus three questions (bash vs Python, the git command runner, the Artifact path). Round two
(2026-09-05) was one: *always use dataclasses*.

## Done — round one (`d61619ac`)

- **Blocker recorded before the resolution started**, then rewritten after it; roadmap carries both
  the finding and what the round changed. Dashboard republished.
- **Strings named**, taking #111's vocabulary wherever it already had one: `RefreshArgument`,
  `RefreshSummaryKey`, `SitePath`, `RepositoryEndpoints`, `PullRequestListFilter`, `IssueField`,
  `detail`/`body` for `payload`. New: `RefreshDashboardCommand`, `ScriptArgumentParser` + one option
  enum per script, `NotesConfigurationKey`/`NotesEnvironmentVariable`/`NotesDefault`, `PlanDocument`,
  `PagesBuildType`, `SiteFile`, `LabelField`.
- **`errors.py`** — `PlanDashboardError`, a dataclass-exception base; all six of this branch's errors
  on it with typed fields, asserted by field rather than by message text.
- **`publish_site.sh` → `publish_site.py`** on a shared `git_commands.GitCommandRunner`.
- **Tests de-duplicated**: manifests are real files under `tests/fixtures/site/`;
  `tests/workflow_document.py` models the workflow; the refresh stub declares its options from
  `RefreshArgument`.
- All 26 threads replied to, 23 resolved.
- **New plan item** `artifact-path-retirement`, at the user's direction, recorded on issue #102.

## Done — round two (`8afbbe30`)

- `PlanDataFakeApi` is a dataclass over `GitHubApi`, with no members — its `__init__` existed only to
  hold a builder function.
- That builder is now **`PullRequestDetail`** (`tests/pull_request_detail.py`), a frozen dataclass
  with `to_json()`, replacing a fixture returning a nested function that built a bare `dict`.
- The scratch repositories are **`ScratchNotesRemote`** in `tests/scratch_repositories.py` — remote,
  seed checkout and clone as named paths — and `scratch_git` is a `GitCommandRunner` pointed with the
  production `in_directory()` rather than a factory.
- `plan_files`, a fixture that existed only because `conftest` is not safely importable, is gone.
- Thread replied to and resolved. 630 tests across the four CI directories; plan-dashboard suite 312.
  PR description rewritten; PR still a draft.

## Outstanding — the user's, not this session's

- **One thread deliberately left open**: the git command runner (this package's own rather than
  `.claude/stack`'s, to avoid depending on another skill directory's `sys.path` insertion). The user
  closed the error-base and Artifact threads himself.
- CI on `8afbbe30` has not been checked — the no-scheduled-checks rule means it is not watched.
- The `d61619ac` commit message says "630 ... from 630"; the correct before-count is 611.

## Next, if asked

The open thread is a small, contained follow-up: import `.claude/stack`'s runner instead, taking the
`sys.path` dependency. Left as a question rather than decided unilaterally.
