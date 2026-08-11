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
  to other people's branches), `--test` on by default.
- **`bisect`** — when the branch builds and the suite fails, adds tips back one
  at a time until it turns and names the pair. A semantic break leaves no
  conflict to attribute, so there is nothing else to go on. Probes run detached,
  so no ref is left behind.
- **`.claude/skills/integration-conflict-triage/SKILL.md`** — the judgement.
  Merge collisions: defer resolves into `rr-cache`, reconcile proposes without
  applying, stack reports. Semantic breaks: adapt / reconcile / sequence, all
  proposed. Ask by whose decision it is, not by confidence.
- `integration_test_command` in `stack.toml` + `Configuration`;
  `INTEGRATION_SCRIPT` constant; README sections.
- On #139's files: `GitCommandRunner` gains per-command config overrides (rerere
  on for the build without touching the developer's config) + two git methods;
  `print_configuration` omits empty settings as well as unset ones.

## The two findings worth remembering

**A replayed rerere resolution fails exactly like a merge that never began** —
non-zero exit, no unmerged paths, because `autoupdate` already staged them. Only
git's stderr (`using previous resolution`) separates them, so the replay marker
must be read *before* the unmerged-paths rule.

**Nothing can be recorded for a semantic break.** rerere keys on a conflict
preimage and a semantic break has none, so the collision recurs on every build
until a branch changes. Reasoning by analogy from the merge case is the trap; a
contract test pins the sentence that rules it out.

## Verified

- 479 tests across the three directories CI runs, was 428 before the item. 51
  new, TDD, each mutation-checked to fail only for its own reason.
- Live on the real fork: 22 tips, 10 merged, 12 skipped, then `tests-failed` —
  and it was real. **#110 alone passes 32, #111 alone green, merged 18 fail**
  (#111 adds a module-scope package import; #110's scratch fixture has no such
  package). Clean merge, invisible to both PRs' CI. Reported on both. `bisect`
  reproduced it independently, excluding the innocent tip.
- After every run: invoking checkout on its own branch, clean tree, pointer at
  the build, no worktree or probe branch left, nothing pushed by the tool.

## If this is picked up again

- Re-draft #154 after any push.
- CI red on `test_each_lib` is base-side: `greenlet==3.5.5` has no Linux wheel.
  This diff touches no `pyproject`/`requirements`/`uv.lock`.
- #139 is `in-review` and moving; a base merge may land underneath.
- This clone has a `cram2` remote, a local `integration` branch, and `integration`
  was pushed to the fork on request (the tool never pushes).

