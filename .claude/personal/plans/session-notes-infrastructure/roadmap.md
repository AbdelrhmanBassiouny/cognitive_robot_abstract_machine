# session-notes-infrastructure — Roadmap

Narrative companion to `plan.yaml`. Kept short on purpose: the size budget this split was made
under counts these lines.

## Where this plan came from

Split out of `workflow-unification` on 2026-08-30, under `plan-size-limits`'
`split-workflow-unification`. That plan had reached 59 items and 16,917 lines across its manifest
and roadmap, well past the 15-item / 2,000-line budget, and became seven plans seamed on subject.

This plan is the half of the old `personal-data` track that is about the notes branch and the
session-start hook; the half about the plan-item skills is `plan-tracking-skills`. The two were split
because the track was 16 items and 4,329 lines, over both halves of the budget.

Every item keeps its branch, pull request number, status and session verbatim. **The full predecessor
roadmap remains in the personal-notes branch's history**; what is kept here is what binds future work.

## Why this work exists

The original review found `cram-notes.md` loading roughly 10,000 tokens of one project's living
roadmap into *every* session on *every* branch - the single largest recurring token cost, and exactly
the pattern the plan system had been built to replace. Slimming it was the first item.

What the track became is larger than slimming, and the shape is the same each time: **a convention
the notes stated in prose, turned into something the hook does.** A session was supposed to check its
setup, know its plan, commit under the right identity, and work from a fresh base. Each of those was
a sentence somebody had to remember, and each was missed at least once before it became a mechanism.

Three of these items exist because a process failure was recorded rather than shrugged at: work
implemented and pushed before its plan item existed; a clone committing under the container's default
assistant identity; and every session in a fork that had drifted 86 commits behind planning against a
stale base, invisibly, because the clone was consistent with itself.

## Decisions this plan inherits

Numbering is the predecessor's, kept so cross-references in item notes still resolve.

**1. Code on main, per-user state as config - not per-user code branches.** A per-user branch holding
instances of a script has the template-drift problem the notes system avoids by holding only data.
Personal configuration lives on the notes branch and is written into the clone at session start.

**12. The hook tier.** `session-start.sh` is bash so it degrades rather than disappears: with
`python3` off `PATH` entirely it still prints every line and exits 0, losing only one row - measured
rather than asserted, and the reason it was not converted when a review round asked. The Python floor
of 3.11 is taken deliberately by `bastler-session-start-python`, behind a shim that probes for it.

## Rules this track settled

- **A clone whose owner wants neither plans nor personal notes must see none of this.** That needed no
  new setting: everything added sits after the hook's existing early exit, and within the group that
  does use the branch, whether the generated branch index exists separates notes-but-no-plans from
  plans-in-use.
- **Report ambiguity rather than collapsing it.** "plan: none" reads as "no plan applies here" when it
  can equally mean "the plan you were told about has no item for this branch yet". There are five
  distinct plan-line outcomes now, including an index entry whose manifest has gone missing.
- **Write only when nothing is there.** The git identity is written when no repository-local one
  exists: a fresh clone has none and someone who set one deliberately keeps it, which is precise where
  blocklisting known assistant identities would be brittle.
- **Report, do not perform, a judgement call.** The hook fast-forwards the default branch but does not
  merge or rebase the checked-out branch, because whether to take a moved base into work in progress
  can conflict.
- **Wording is not pinned by tests.** A test added specifically to replace the guard that
  single-sourcing the summary wording had removed was cut on the user's instruction; what survives
  asserts each message renders non-empty. A reword is invisible to the suite, deliberately. It is the
  reviewer's call whether wording is worth pinning.
- **A session never subscribes to a pull request's activity**, and opening one is terminal for the
  session that opened it. A plan's tracking issue is different - a coordination mailbox several
  sessions read, not a pull request one session owns - and the planning skills keep theirs.
- **The setup runs without being offered.** A user who invoked a planning skill has already said what
  they want; the questions that survive are the ones that pick a destination to write to.

## Findings worth carrying

- **A conflict report understates a conflict against a restructured document.** A branch cut before a
  378-to-140-line rewrite had an earlier merge resolve that rewrite hunk by hunk, resurrecting two
  superseded sections beside their replacements and stranding a list's closing sentence 75 lines from
  its list. Re-author against main rather than merging, and read the merged file end to end.
- **The manifest was the least accurate source, five times.** Every stalled item on this track sat on
  blockers its entry did not record, while everything needed to diagnose them was on the pull request.
  That observation is what produced `manifest-currency-first`, now in `stack-maintenance`.
- **A rule that lives in prose is reinstated silently by a new file.** Two pull requests carried a
  superseded sentence in files that did not exist yet, so no merge could flag them. A test that
  *discovers* documents rather than listing them is what makes landing order stop mattering - and the
  prediction held exactly.
- **The repository ignores `*.txt`**, so a fixture requirements file needs a `.gitignore` exception,
  and only diffing the staged tree against main catches it - the local suite passes either way.
- **Review threads inside an unsubmitted pending review reject inline replies with a 422**, since
  GitHub allows one pending review per user. Explain the resolution in a conversation comment instead.

## Standing risks

- **The identity fix cannot reach commits made outside a session.** Merge commits landing from the
  merge button or a scheduled run are beyond any local hook; that half needs the GitHub account's own
  commit-email setting. Environment variables set at the environment level are stronger where they
  apply - they beat both local and global config and are in force before any hook runs - but they are
  per-environment and do not travel to another contributor's clone.
- **Tag pushes and branch deletes get a 403 through a session's git proxy** and no tool substitutes.
  One throwaway branch is still outstanding for out-of-harness deletion.

## Open

- One item, `always-read-upstream-reviews`, carried no recorded detail before the split beyond its
  title. Its pull request is the record.
