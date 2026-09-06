PR #282 (draft), base `claude/plan-item-kickoff-workflow-unification-wg4w4x` (PR #211's
head - this is NOT a main-based PR; .claude/stack/integration_*.py does not exist on
main at all, it's unlanded tooling built across the plan-item-kickoff-workflow-* stack).

Status: DONE, pushed, PR opened as draft. One red check, NOT this PR's - see below.
Nothing else outstanding from this session.

CI: "Rebuild the integration branch and publish it if it is green" (integration-refresh.yml)
is red, but it's pre-existing and unrelated - fails identically on scheduled `integration`
runs from before this PR existed and on unrelated PRs (#281, #260), same error every time:
`.claude/stack/integration.py: No such file or directory` after refresh's restack step
checks branches out directly in the pipeline's own working directory (no worktree) and
never restores it to one carrying `.claude/stack/`. An open fix exists (#158, "Pin the
stack tooling for the length of a maintenance pass") but its own CI is red and it sits on
an unrelated, unstacked branch, so I did not port it in unilaterally - posted a diagnosis
comment on #282 instead: https://github.com/AbdelrhmanBassiouny/cognitive_robot_abstract_machine/pull/282#issuecomment-5558055687
This PR's own suite (test_claude_dev_tooling, every test_each_lib job) is green.

What it does:
- Links the branch a semantic break is against in the existing "breaks another branch"
  comment (IntegrationTestFailure.comment / block_the_branch_that_causes_it), falling
  back to the bare branch name when no open PR publishes it any more.
- New module integration_left_out.py comments once per branch per reason for every
  other silent left-out case (raw SKIPPED conflict, INTEGRATION_FAILED, and cascaded
  BLOCKED/BLOCKED_WITHOUT_RECORD/CHECKS_FAILED/UNREVIEWED - only when attributed to an
  ancestor, never a branch's own label/red-check/draft). Gated by a new purely
  informational `integration-left-out` label (not in blocking_labels) that clears
  silently on rejoin, same pattern as needs-resolution's auto-clear.
- New `build --report-left-out` flag; only RefreshPipeline's unfiltered rebuild passes
  it (never plan-filtered rebuilds, never ad-hoc/triage `build` runs) - so
  /integration-conflict-triage's existing "never comments for a defer" behavior is
  unaffected. Added a short note to that skill's SKILL.md distinguishing the two.

Known follow-up NOT done here (told the user in the PR body): the
`integration-left-out` label needs to be created by hand on the fork on GitHub, the
same way needs-resolution/integration-conflict were - nothing here can create a
missing label.

Branch-base scope check performed per the mechanical rule: `.claude/stack/` and this
skill's tooling do not exist on origin/main (`git ls-tree origin/main -- .claude/stack`
is near-empty vs. ~77 files on the stack this PR builds on) - confirmed this is real,
separable work on top of PR #211 (candidate-failure localisation), not a change to
#211 itself: removing this PR's edits leaves #211 fully coherent, and this PR's own
diff (909 insertions across 15 files, one new module) stands on its own.
