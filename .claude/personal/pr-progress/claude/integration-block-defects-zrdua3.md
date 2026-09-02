## integration block defects (branch claude/integration-block-defects-zrdua3)

Scope check: every file touched (.claude/stack/integration_*.py, the triage skill) is absent
from main and introduced by #154 / rewritten by #211, so this is #211's work. Branch is cut
from #211's head (claude/plan-item-kickoff-workflow-unification-wg4w4x); draft PR opened
against that branch, to be folded into #211 on the user's word.

Root cause chosen: a block is a label that records nothing about the tree it was measured
in, so nothing can tell when that tree is gone and selection honours it for ever. The
pipeline blocks automatically (RefreshPipeline._build), so refusing a block without a
reproduction test is not an option - the lifting has to be automatic too.

Fix (implemented): integration_block_record.py records the heads the break was measured
over as refs/integration/blocked/<blocked pr>/<pr>; stack_to_build annotates
Branch.block_standing; select_for_build carries a stale-blocked branch again and names it
in BuildSelection.readmitted / IntegrationReport.readmitted; BuildCommand lifts the label and
forgets the record when the suite passes over a build the branch reached; a label with no
record is reported as blocked-without-record. locate-failure / block-branch read the stack
the way the build does, so the search covers a readmitted branch.

Done: tests (failing first), implementation, skill + README, format_docstrings.
Next: full suite green -> commit -> push -> draft PR (bug label, session link) -> stop.
