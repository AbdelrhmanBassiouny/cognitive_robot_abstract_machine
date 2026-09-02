## integration block defects (branch claude/integration-block-defects-zrdua3)

Scope check: every file touched (.claude/stack/integration_*.py, the triage skill) is absent
from main and introduced by #154 / rewritten by #211, so this is #211's work. Branch is cut
from #211's head (claude/plan-item-kickoff-workflow-unification-wg4w4x); draft PR opened
against that branch, to be folded into #211 on the user's word.

Root cause chosen: a block is a label that records nothing about the tree it was measured
in, so nothing can tell when that tree is gone and selection honours it for ever. The
pipeline blocks automatically (RefreshPipeline._build), so refusing a block without a
reproduction test is not an option - the lifting has to be automatic too.

Fix: record the heads the break was measured over as refs/integration/blocked/<pr>/<pr>
(like refs/integration/passed); a build honours the block only while every recorded head is
still the fork's head; once one moved, the branch is carried again on trial and reported as
readmitted; a green suite over a build carrying it lifts the label and forgets the record.
A label with no record is reported as blocked-without-record so a hand-lifted block is loud.

Done: reading, design. Next: failing tests (block record, selection, failure, build,
lifting), then implementation, skill doc, format_docstrings, full suite, commit, push, PR.
