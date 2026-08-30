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
  in-job wait can outwait it. The verdict is read by a later run.
- **A default-token-triggered event creates no workflow run**, so anything opening a candidate needs a
  provisioned token. Related trap: the checkout action persists that token as an http header that
  overrides credentials in a push URL.
- **Localisation reaches the tooling suite, not the docker matrix**, so a genuine break only the matrix
  sees is still unlocalised. That is `red-candidate-localisation`.
- **rerere replays a textually matching resolution automatically**, so a skill-authored one that is
  semantically wrong is reapplied unreviewed on every later build. Provenance is recorded and replays
  are never silent.

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
