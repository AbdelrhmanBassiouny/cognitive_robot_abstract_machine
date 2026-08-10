# integration-branch (#154) — regenerated personal integration branch

`workflow-unification` plan, `stack-tooling` track. Branch
`claude/plan-item-kickoff-workflow-ixbvxl` on **#139's head** (`maintenance.py`
exists only there). Draft PR #154, head `80e40e0f`. Session
https://claude.ai/code/session_01Ue4PvfV5LDxHGRRS5BZB4g.

## Status: implemented, pushed, awaiting review

Both deliverables are in one commit. Nothing is outstanding for this session; the
PR is a draft and the plan manifest, roadmap and dashboard are all current.

## What shipped

- **`.claude/stack/integration.py`** — builds the upstream base plus every
  in-flight stack tip. Tips only, ascending PR number. Conflicts skip and
  continue; the report names the **pair**. `--restack` off by default (it pushes
  to other people's branches), `--test` on by default (`--no-test` to skip).
- **`.claude/skills/integration-conflict-triage/SKILL.md`** — the judgement.
  defer resolves into `rr-cache`, reconcile proposes without applying, stack
  reports. Ask by whose decision it is, not by confidence.
- `integration_test_command` in `stack.toml` + `Configuration`;
  `INTEGRATION_SCRIPT` constant; README section.
- On #139's files: `GitCommandRunner` gains per-command config overrides (rerere
  on for the build without touching the developer's config) + two git methods;
  `print_configuration` omits empty settings as well as unset ones.

## The finding worth remembering

A **replayed rerere resolution fails exactly like a merge that never began** —
non-zero exit, no unmerged paths, because `autoupdate` already staged them. Only
git's stderr (`using previous resolution`) separates them, so the replay marker
must be read *before* the unmerged-paths rule. The mutation that proves it:
disabling the marker turns every replay into `integration-failed`.

## Verified

- 470 tests across the three directories CI runs, was 428. 42 new, TDD, each
  mutation-checked to fail only for its own reason.
- Live against the real fork from a detached worktree: 23 tips, 11 merged, 12
  skipped, exit `tip-left-out (10)`. Afterwards: invoking checkout untouched,
  pointer at the build, merged tips ancestors and skipped ones not, no leftover
  worktree, **nothing pushed**.

## If this is picked up again

- Re-draft #154 after any push.
- CI red on `test_each_lib` is base-side: `greenlet==3.5.5` has no Linux wheel,
  so `uv sync` fails before any test runs on every open PR. This diff touches no
  `pyproject`/`requirements`/`uv.lock`.
- #139 is `in-review` and moving; a base merge may land underneath. Ancestry
  answers "did I lose anything", only the suite answers "does it still pass".
- The live run left local `integration` / `integration-20260810-224716` branches
  and a `cram2` remote in this clone. All local, all harmless.

