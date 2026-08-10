# integration-branch (#154) — regenerated personal integration branch

`workflow-unification` plan, `stack-tooling` track. Branch
`claude/plan-item-kickoff-workflow-ixbvxl`, based on **#139's head**
(`claude/plan-item-kickoff-workflow-koufa6`) because `maintenance.py` exists only
there. Draft PR #154. Session
https://claude.ai/code/session_01Ue4PvfV5LDxHGRRS5BZB4g.

## The plan

Build a branch that is upstream `main` with every in-flight stack tip merged on
top, regenerated from scratch on demand — something to build *from* while the
`cram2` review queue lags. It gates nothing: promotion asks whether a branch is
ready for review, integration asks whether the branches coexist.

Two deliverables, one pull request (a conflict report nothing consumes is half a
feature):

1. **`.claude/stack/integration.py`** — detects, attributes, skips. No judgement.
   Reuses `BoardExport`/`GitHubRepository`, `build_stack`/`order`,
   `has_landed_upstream`, `maintenance.restack`, `GitCommandRunner.merge` +
   `unmerged_paths`, `RestackWorktree`/`DetachedCheckout`, `merge-tree` as the
   non-mutating pair probe, and the report/exit-code shape #139 established.
   Selection is the stack tip; conflicts **skip and continue**; the report names
   the conflicting **pair**, not the casualty; rerere resolutions replay but are
   never reported as clean and carry their author.
2. **`.claude/skills/integration-conflict-triage/SKILL.md`** — the judgement.
   *defer* resolves fully into `.git/rr-cache`, *reconcile* proposes without
   applying, *stack* reports. Bounded by where the resolution lands, not by
   confidence.

Plus `INTEGRATION_SCRIPT` in `resolve-personal-notes-config.sh`,
`integration_test_command` in `stack.toml` + `Configuration`, and a README line.

Settled at kickoff: `--restack` **off** by default (it pushes to other people's
branches); `--test` **on** by default (it replaces the dropped CI gate);
`--test` runs a configurable command defaulting to CI's three tooling
directories.

## Done

- Branch cut off `04902f40`, empty bootstrap commit, pushed.
- Draft PR #154 opened against #139's branch.
- `plan.yaml` → `in_progress` with branch/session/PR; roadmap kickoff section
  appended; dashboard republished.
- Commented on #139 about the unpopulated `stack.PullRequest.ci` field.

## Next

- TDD `.claude/stack/tests/test_integration.py` against real git: clean build;
  conflict **skipped, pair named**; failed-merge-without-unmerged-paths is *not*
  a conflict (#123's false-positive class); stable order; tips-only selection;
  replay reported with author; **exit status per outcome, parametrised**;
  `--restack` off means no push (assert on git arguments); `--test` failure after
  a skill-authored resolution stops rather than re-resolving.
- Then `integration.py`, then the skill + its contract test mirroring
  `test_maintenance_skill.py`.
- Verify with the exact CI invocation (plan-dashboard + hooks + stack tests), then
  a live `build --json` from a detached worktree.

## Watch

- `greenlet==3.5.5` has no Linux wheel — `uv sync` fails before any test runs on
  **every** open PR in this repo. Red robotics jobs here are not this PR's; the
  diff touches no `pyproject`/`requirements`/`uv.lock`.
- #139 is `in-review` and still moving. A base merge may land underneath; ancestry
  answers "did I lose anything", only the suite answers "does it still pass".
- Re-draft #154 after every push.
