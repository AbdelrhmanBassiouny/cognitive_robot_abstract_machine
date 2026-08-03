# PR #110 — /setup-stacked-prs (plan item `setup-stacked-prs-skill`)

Branch `claude/setup-stacked-prs-skill`, based on `claude/setup-personal-notes-script` (#107).
Plan: `workflow-unification`, stack-tooling track, upstream wave. Tracking issue #102.

## Plan

Stack-side counterpart of `/setup-personal-notes`, following #107's script/skill split:
`check-stack-setup.sh` (read-only), `setup-stacked-prs.sh` (all mechanical steps, no session),
`write-branch-files.sh`, and the skill plus its `prerequisite-check.md`.

## Done

- Original five deliverables, TDD. Draft PR #110 opened and subscribed.
- **Rebased onto #106's review round (2026-08-03, `eecd765d` + `b9f8f752`).** Five conflicts, all
  under `.claude/stack/`, all resolved in favour of the parent: `ROUTINE.md` delete accepted, this
  branch's `routine-prompt.md` deleted as a duplicate of the skill's, `stack.py`'s
  `config`/`print_config`/`BOARD_FREE_COMMANDS` dropped for #106's `configuration`, `stack.toml`
  and `test_stack.py` taken from the parent. `cram2_link_sent_label` survives — the one thing this
  branch had that #106 does not.
- **Base stays #107**, not retargeted to #106: `setup-stacked-prs.sh:44` sources `github-api.sh`,
  which lives only on #107, and `git merge-tree` gives the identical conflict set either way.
- **The one real defect fixed**: `check-stack-setup.sh` required two files that exist nowhere, so
  it reported `needs-setup` on a correct checkout. Both constants repointed at
  `.claude/skills/stacked-pr-maintenance/`; written failing first. Fixed fork-overlay for free.
- **Second defect nobody had recorded**: `write_personal_config` wrote the whole file, so it and
  the maintenance skill silently erased each other's `fork_repository`. It merges now.
- **~120-line remote inference deleted**, closing #106's `stack.toml:23` and `stack.py:84`
  threads (replied to, resolved). `RemoteResolution` is symmetric; setup writes `fork_repository`
  at install time. `--fork`/`--upstream` take an owner/name, a URL, or a remote.
- 408 tests pass across the three CI directories (was 334). `test_claude_dev_tooling` green on the
  push. Description rewritten, `needs-resolution` cleared, PR back to draft.
- New plan item `stack-maintenance-executor` registered; manifest + roadmap saved, dashboard
  republished (`drift_count: 0`), structural record on #102.

## Next

- Watch #110's CI. `test_claude_dev_tooling` is green; the robotics matrix was still queued at
  hand-off and is the known-unrelated flake population.
- Self-review and un-draft when ready — that is the approval gate for promotion.
- Still unverified: live label creation, for the same fine-grained-token reason as #107.
- `stack-maintenance-executor` starts with the credential probe (label writes, issue comments,
  body-only PATCH through `GH_TOKEN`) before any design is committed.
