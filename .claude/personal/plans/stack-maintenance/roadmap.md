# stack-maintenance — Roadmap

Narrative companion to `plan.yaml`. Kept short on purpose: the size budget this split was made
under counts these lines.

## Where this plan came from

Split out of `workflow-unification` on 2026-08-30, under `plan-size-limits`'
`split-workflow-unification`. That plan had reached 59 items and 16,917 lines across its manifest
and roadmap, well past the 15-item / 2,000-line budget, and became seven plans seamed on subject.

This plan is the pass half of the old `stack-tooling` track - what runs *over* a live stack, and the
integration branch built from it. Getting the tooling onto main and installing it elsewhere is
`stack-tooling-install`. The track was 18 items and 8,333 lines, over both halves of the budget; the
seam is chosen so no live dependency edge crosses it, which is why `pinned-stack-tooling` sits here.

Every item keeps its branch, pull request number, status and session verbatim. **The full predecessor
roadmap remains in the personal-notes branch's history**; what is kept here is what binds future work.

## Why this work exists

Two separate constraints, and they produced the plan's two tracks.

**The pass had no executor.** Every fetch, merge, rebase and push in the workflow was performed by a
session following prose, and the board was hand-assembled from tool output. That is the same
hand-assembled-input failure class that produced false merged/closed verdicts elsewhere: a dropped
field is indistinguishable from a legitimately absent one.

**Upstream review throughput is the binding constraint on daily work.** Pull requests are produced
faster than the upstream merges them, so shipped-but-unreviewed features are unusable, and two
in-flight features that conflict only discover it at the far end of the review queue. The integration
branch answers whether the in-flight branches coexist, by being rebuilt from scratch and worked from
rather than merged out of.

## Decisions this plan inherits

Numbering is the predecessor's, kept so cross-references in item notes still resolve.

**5. The plan data model and the stack data model stay separate.** The board is derived mechanics -
pull request bases and git ancestry; plans are intent over time.

**11. GitHub maintains the mechanics; we maintain policy.** The restack subsystem was cut rather than
trimmed. This plan executes an already-derived plan; it does not re-derive structure.

**12. The standard-library tier**, which is why the shared modules extracted here import nothing, and
why a `classproperty` was written by hand rather than imported.

**13. The package extraction moves every file here**, so each open branch merges main across that move
and re-applies its delta.

## Rules this plan established

- **Compute a write from what the pull request carries now, not from the snapshot the pass opened
  with.** This is the single most repeated defect on record here: promotion promoted a branch the same
  pass had just conflicted on and stripped the label withholding it, because both read the board
  export; and selection carried a branch the same pass had just blocked, because the stack was read
  before the restack that wrote the label. Both are the same shape, met months apart.
- **A command's exit status must agree with its own report.** A restack that hit a conflict exited 0,
  as did a run whose fast-forward was refused - and a caller acting on the status alone is precisely
  what the no-LLM endgame is. Every command derives its status from one mapping over the report.
- **A test that reads ambient state cannot assert about the state it is reading.** Met twice in one
  pull request: a local board file the pass writes, and a token a session environment exports.
- **A sentence describing what the code does has nothing holding it true**, so it is a future lie with
  a delay attached. That rule, the user's, cut the maintenance skill's central step from about 70
  lines to 30: what is left is what the agent decides.
- **The tool a pass runs must be pinned for the length of the pass**, because the in-tree path is
  tracked content and a pass switches branch in the checkout it runs from. The pin must carry every
  sibling directory the tool's modules name in a path insertion, and keep the layout - flattened, the
  same insertion resolves outside the copy.
- **A blocking label needs a clearing condition that matches how it is set.** The conflict label is
  cleared automatically when GitHub stops reporting a conflict; a semantic break never makes a pull
  request conflicted, so it needs a second label and a different clearing condition - a marked
  reproduction passing.
- **A note saying an operation is blocked is a claim with an expiry date.** One such note was carried
  verbatim through two entries and had two expiries at once: the client had changed and the target had
  moved. Attempting a recorded-as-blocked step, when it is cheap and reversible, is worth more than
  restating it.
- **A test that pins a contract must read the artifact the contract is about.** One did not, for four
  review rounds, and the tell was available the whole time: it imported nothing that produced a
  document. Related: **a reviewer returning to the same line is evidence the answer has not landed**,
  not that the question has been asked already.
- **A label that makes later passes skip a branch removes the only thing that would have retried
  it.** The conflict label was invented so a pass reports a conflict once rather than every run, and
  it clears only when GitHub stops reporting one - which only a resolution produces. So a branch it
  marks is never re-attempted by the mechanism that marked it. One branch sat conflicted for eighteen
  days and eight passes, and its recorded blocker named the most recent pass rather than the first, so
  the manifest described a one-day-old problem.
- **A repair rule needs its own evidence, not a shape match.** A blind regular expression fixing five
  broken words happened to be right; run over the whole plan it turned up seven more, one of which it
  would have corrupted.

- **A branch a pipeline creates needs a take-down rule of its own, not one hanging off the happy
  path.** Publishing dropped a build's branch, and nothing else did - so every other ending left
  one, four times a day, and eight had gathered before anyone counted. The rule that works is what
  *keeps* a thing rather than what drops it: a build branch is kept while a pull request is still
  open against it, which covers both the candidate judging it and a filtered build somebody is
  working from, and it needs no knowledge of how the run that made it ended.
- **A pipeline that publishes to the branch it runs from can delete itself, and nothing in the design
  said it could not.** The pipeline lives only on two unlanded branches, so any build that leaves them
  out has no `integration-refresh.yml` in it - and publishing moves the fork's *default* branch, which
  is where a schedule registers from. One green build assembled without those two branches would take
  the scheduled workflow down and leave nothing able to publish a later one. The guard belongs before
  every other fix here: the first candidate that can actually be judged is otherwise the one that ends
  the automation. **Built on 2026-08-31**, and the shape that works is a refusal inside the one
  function both routes to the pointer go through, testing what the tree *carries* rather than what the
  run intended - a guard on the judged path alone is one the recorded pass walks straight past, and the
  recorded pass is what publishes on the ordinary day when nothing has moved. Presence is not the whole
  test either: a workflow left with only a dispatch is a rebuild somebody has to remember to press.
- **What a thing is opened *against* is part of whether it can be measured at all.** The candidate's
  base was chosen to carry meaning - `find-candidate` tells a full build from a `--plan` one by it -
  and that made it a base nobody could check against. A discriminator and a merge target are two jobs,
  and one field doing both fails at the one that is load-bearing for the whole pipeline.
- **A measurement that explains more than one design is recorded once and referred to.** The
  candidate check timing was written out at four of the designs it shapes, in three modules, and
  each copy goes stale on its own with no reader able to tell which is current. What made the
  duplication findable was making the numbers *data* - `CandidateCheckTiming` - so a test can
  derive the figure it looks for from the record rather than carrying a second copy of it.
- **A trigger is only safe to add once you can say what stops it.** Answering to CI completing
  over a build branch starts a rebuild that opens the next candidate, whose CI completes in turn.
  It terminates because a build whose tree is already recorded as passing publishes with no
  candidate at all - the pass record, built for a different reason, is what bounds the loop.
- **Introducing a model does not retire the hand-rolled readers it replaces**, because nothing
  breaks when it lands. `workflow_document.py` was written to stop `integration-refresh.yml` being
  walked as nested string keys, and a whole section of `test_integration_verdict.py` went on doing
  exactly that through the round that introduced it and the two after. Only searching for the old
  shape finds them.
- **A fix that two unlanded branches each own half of belongs on whichever one can test it.**
  `plan_item_bootstrap`'s `update` writes item fields at a hardcoded four-space indent; #160 fixes
  that with an `ItemIndentation` read off the manifest, but predates `update` entirely, so a failing
  test for the reported reproduction cannot even be written there. This branch introduces `update`,
  `ValueStyle.SEQUENCE` and `manifest-staleness.md` - the document that tells every plan skill to run
  the broken command - so it is where the two halves meet. The user chose the fold on 2026-08-30 over
  a third branch stacked on both; a third branch editing the same emitter is the collision pattern
  this repository has already paid for twice.
- **A reported symptom is a place to look, not a fact to carry.** The report's example of the
  unquoted-scalar defect was a blocker containing `#`, and blockers turn out to round-trip: a
  sequence entry is quoted when it is short and folded when it is long, and both survive. The defect
  is real but sits on `ValueStyle.PLAIN` keys. Reproducing before recording is what separated them,
  and the same run turned up a third defect nobody had reported - `depends_on` declared `PLAIN` while
  every manifest writes it as a block sequence, so replacing it orphans its entries.

- **A discriminator set in the call that creates the thing beats one written afterwards.** Moving the
  candidate's base off `integration` needed something else to tell the build a run may publish from a
  `--plan` one, and the two candidates were a label and the title. The title won on failure mode
  rather than on structure: a label is a second call, and a candidate no reader recognises is one no
  later run settles - which is the wedge the base change exists to end, so introducing a second way
  into it would be a poor trade. It also keeps `CandidatePullRequests` denied the pass's writes, which
  is deliberate.
- **A rule that stops a run must be one something later can clear.** `CANDIDATE_UNCHECKED` was a
  correct diagnosis - nothing is starting a check - attached to the wrong action: stopping meant the
  rebuild never reached the step that would have replaced the candidate, so every later run inherited
  the same one and the pipeline could not recover from an outage it had itself detected. Closing and
  carrying on costs nothing, because the take-down already keeps only what an open pull request refers
  to, and the run still exits with the status so nobody stops looking.
- **A test that its own mutation walks past is worse than no test.** One written this round asserted
  that a candidate's description names the branch a green build moves; the name appears twice in the
  description, so replacing the load-bearing one still passed. Removed rather than kept, since a
  passing assertion is read as coverage.
- **An expectation recorded as expected rather than measured is worth measuring before acting on it.**
  This item carried a hazard about `#151` being a draft at the root of the pipeline chain. `#154` is
  based on `main`, and `#151` is not a draft; the hazard never applied. One `list_pull_requests` call
  answered it.

- **A run that stops on a failure has to say what it had built.** The first bootstrap dispatch failed
  its local suite, and `RefreshPipeline._build` prints the build's own document only on the branch
  that is *not* `TESTS_FAILED` - so the run reported `tests-failed (11)` and nothing else, swallowing
  the `left_out` that has to be read before anything can be published. The collision survived only
  because `block-branch` writes to the culprit's pull request rather than to the run's log, which is a
  different channel and a different reader.
- **The suite catching a break before a candidate exists is the design working, not the pipeline
  failing.** #110 and #80 merge cleanly and break together; no per-branch check can see that, and the
  local run answered it in two and a half minutes rather than after a matrix. What it costs is that
  the run stops there, so a cycle that hits one exercises nothing downstream of the build.

## The integration branch's design, stated once

- **It gates nothing.** Promotion asks whether a branch is ready for upstream review; integration asks
  whether the branches coexist. Gating promotion on a clean build would block A because B conflicts
  with it, with no principled reason A is the one that waits.
- **No CI gate on entry, but a known failure is excluded.** Requiring *green* deadlocks against the
  restack, since restacking rewrites heads and every restacked branch reads pending. Excluding a tip
  that has already finished red has no such deadlock and is self-limiting.
- **Conflicts skip and continue**, because a build that halts leaves nothing to work from, and the
  report names the conflicting pair rather than the casualty.
- **Only reviewed work is carried, read down the whole chain.** A tip contains its stack, so filtering
  tips alone merges a ready pull request together with the drafts beneath it.
- **The candidate pull request exists to trigger CI and nothing else.** A pushed build collects no
  checks, because CI triggers on push to main and on pull requests only. Green force-updates the
  pointer and closes the candidate unmerged; merging would give the pointer a history the next build
  cannot regenerate.
- **Judgement lives in a skill, not the script**, and the skill resolves bounded by *where the
  resolution lands* rather than by how confident it is. Asking is about whose decision it is:
  uncertainty about facts is resolved by reading, uncertainty about intent is asked.
- **A build is keyed on its git tree**, because re-assembling the same branches over the same base
  gives a new commit every time and the same tree every time. Only passes are recorded; a red is
  cleared by re-running the same commit.

## Standing risks

- **The pipeline runs from the fork's default branch, which is a build output**, so it always lags
  whatever is in flight - and a pipeline that cannot publish cannot carry its own fix. A dispatch on
  the working branch is the bootstrap.
- **Queue delay is measured in hours, not minutes** (19 minutes and 2h47m on two candidates), so no
  in-job wait can outwait it. The verdict is read by a later run - started by CI completing over the
  build branch, with the schedule left as the floor under it. The figures live in
  `CandidateCheckTiming` rather than in the prose of every design they explain.
- **A default-token-triggered event creates no workflow run**, so anything opening a candidate needs a
  provisioned token. Related trap: the checkout action persists that token as an http header that
  overrides credentials in a push URL.
- **Localisation reaches the tooling suite, not the docker matrix**, so a genuine break only the matrix
  sees is still unlocalised. That is `red-candidate-localisation`.
- **rerere replays a textually matching resolution automatically**, so a skill-authored one that is
  semantically wrong is reapplied unreviewed on every later build. Provenance is recorded and replays
  are never silent.
- **Every build so far omits the pipeline itself.** #211 conflicts with #160's branch over
  `plan_item_bootstrap.py`, so the build skips it - and it is the tip of the stack carrying #154, where
  `integration.py` and the refresh workflow live. Measured on the 2026-08-30 build: nine branches
  carried, neither of those two, no pipeline in the tree. Folding #160 is what clears it. Since
  2026-08-31 such a build is refused rather than published, so a pipeline-less build is loud and once
  per rebuild rather than fatal and once and for all. **#160 was closed the same day, superseded by
  #151**, so the collision that skipped #211 is off the board and the next build should carry the
  pipeline - expected rather than measured, since none has been assembled since.
- **A candidate opened against the branch it replaces stops being checkable once that branch falls
  behind.** `integration` is itself an older build of the same branches, so a new build conflicts with
  it, GitHub computes no merge reference, and a `pull_request` run - which checks that reference out -
  is never created. The rebuild then stops on a candidate nothing can judge and never reaches the step
  that would have replaced it. Measured on 2026-08-30: candidate #220 had no `refs/pull/220/merge` and
  no checks after eleven hours, while the same build opened against `main` had both within twenty
  seconds. This is why one build is the only one this pipeline has ever judged. **Both halves fixed on
  2026-08-31** in `c77b9ea79`: every candidate is opened against the base its build was assembled over,
  and one nothing can judge is closed and replaced rather than stopped on.

## Open

- Whether an already-registered scheduled run's notification setting can be changed in place, which
  `promotion-summaries-and-table` must know before any document tells anyone how to do it.
- The git-command vocabulary question, answered with measurements and deliberately left to
  `bastler-notes-core-python`, which owns the git seam by name and has four callers waiting - one with
  a deliberately opposite contract. Deciding the ergonomics before the raise-versus-answer-nothing
  question is settled means deciding them twice.
- The wire format of the integration reports is deliberately unguarded, recorded rather than quietly
  dropped: with writer and reader both reading the same enum, a value rename changes both identically.
  The place to close it is a consumer that actually runs.
- `integration.py`'s own line count against the 400-line rule, offered rather than done.
