## PR progress: claude/trusting-clarke-32il0l (AbdelrhmanBassiouny/cognitive_robot_abstract_machine#492, draft, base main)

Goal: stack maintenance restacks keep one restack merge per branch instead of adding one per pass.

Done:
- Re-cut branch from main (was cut from integration).
- SupersededMerges in maintenance_restack_steps.py; IntegrateParent merges onto the commit beneath
  superseded tip merges, falling back to the tip on failure; PublishBranch leases the push when the
  published tip is no longer contained (ProposedPush.publishing(replaces_superseded_merges=...)).
- 8 tests in test_maintenance.py; full .claude/stack/tests suite green (162).
- Docs: README section, SKILL.md force-push exception, stack.py docstrings.

Next:
- Await review. Possible follow-up if wanted: report how many merges a push replaced in BranchOutcome.
- In-flight branches (integration) also edit maintenance_restack_steps.py; expect a merge there.
