# stack-tooling-install — Roadmap

Narrative companion to `plan.yaml`. Kept short on purpose: the size budget this split was made
under counts these lines.

## Where this plan came from

Split out of `workflow-unification` on 2026-08-30, under `plan-size-limits`'
`split-workflow-unification`. That plan had reached 59 items and 16,917 lines across its manifest
and roadmap, well past the 15-item / 2,000-line budget, and became seven plans seamed on subject.

This plan is the install half of the old `stack-tooling` track - the tooling reaching main, the
skills that install it, and the bugs about which refs the tooling reads and which branch new work is
cut from. The pass that runs *over* a live stack is `stack-maintenance`. The track was 18 items and
8,333 lines, over both halves of the budget, and the seam is chosen so no live dependency edge
crosses it: `pinned-stack-tooling` went with the maintenance half, which is what it is about.

Every item keeps its branch, pull request number, status and session verbatim. **The full predecessor
roadmap remains in the personal-notes branch's history**; what is kept here is what binds future work.

## Why this work exists

The stack workflow's machinery lived on a never-merged personal tooling branch, alongside real dead
weight: a round-robin admission subsystem whose cap had been deliberately disabled, so the fairness
ordering decided nothing while the machinery still stamped markers every run; a workflow file using a
tool the cloud environment cannot run; and a hygiene section instructing exactly what the doctrine
elsewhere forbade.

Moving it to main makes it reviewed code rather than a personal artifact, and makes it installable
somewhere other than here. **Portability is a rule rather than an aspiration**: no repository names
outside configuration defaults and documentation examples.

## Decisions this plan inherits

Numbering is the predecessor's, kept so cross-references in item notes still resolve.

**1. Code on main, per-user state as config - not per-user code branches.** A per-user branch holding
script instances has the template-drift problem the notes system avoids by holding only data.

**2. Fork-overlay install mode reconciles portability.** For a repository whose maintainers will not
take the tooling upstream, the setup skill installs the same canonical files onto a never-merged
tooling branch of the user's fork - today's pattern, but created and *updated* by the skill, so
re-running it is the drift fix. The per-user tooling branch survives as the escape hatch, not as the
default.

**3. Portability rules.** No repository names outside configuration defaults; the site's repository,
branch and upstream become repository variables. A standalone plugin or template repository is kept
open as a long-term option and not exercised.

**6. Delete the round-robin subsystem rather than fix it.** The cap was disabled deliberately, because
size and scrutiny predict review duration better than admission gating.

**7. The base pull request is tracked but not owned here.** It is the stacking base and its
prerequisite-check machinery is reused, so its live state gates the wave.

**9. The GitHub steps do not need a session.** The accounting that said otherwise was wrong: the login,
the label reads and the label creates are all plain API calls, and the "no create-label tool" limit is
true of one client rather than of the API. That is what turned the setup skill into a thin
question-asking wrapper.

**10. The upstream wave is a linear chain, not siblings.** Weighed on mechanical grounds rather than
aesthetics: a restack plan emits exactly one parent per branch, derived from the pull request base, so
a branch with two real parents is invisible to the second - when that parent moves, nothing restacks
the child onto it. A branch the stack tooling cannot maintain is a poor advertisement for the stack
tooling.

**11. Cut the restack subsystem rather than trim it.** The fallback's only remaining justification -
repositories without the stacks preview - is unnecessary, since the preview is account-wide and the
old tooling branch survives as a tagged archive. Since the named slowest-review risk was the file's
line count, cutting the engine is simultaneously the fastest path through the real bottleneck and the
most reliable one: GitHub maintains the mechanics, we maintain policy.

## What the native-stacks evaluation established

Run as a live prototype rather than read off documentation, and it re-scoped four items:

- Every stacks endpoint works from a session's installation token. Merge is a new asynchronous
  endpoint that merges everything below in one operation and auto-retargets the pull requests above,
  refusing stale stacks and drafts. The classic merge and update-branch APIs are hard-403'd for stack
  members.
- **The one gap**: no endpoint triggers the server-side cascading rebase. Cascade is UI-only or a
  local rebase and force-push, which preserves membership.
- Changing a base 422s on a stack member; unstack, then change, then restack is the recovery.
- Push-based merges are detected as merged but do *not* auto-retarget children.
- A stack's recorded base SHA lagging the real trunk head is a machine-readable staleness signal.

## Landing hazards

- **The upstream promotion is a separate manual step** from the fork-internal merge, so a gate phrased
  as "on upstream main and fork main fast-forwarded" is not met by a fork merge alone.
- **A cross-fork pull request's base-repository CI run has only one remote, pointing at the upstream**,
  so there are zero fork candidates and a configuration load that treats that as an error fails in CI
  and nowhere else.
- **Live label creation is unverified across this whole track.** This environment's token is a
  fine-grained installation token, so the create call is exercised only through a stub.
- **The package extraction carries these files.** One bug fix here is duplicated verbatim at the moved
  path, so it lands first and is picked up in the re-merge that branch already needs.

## Findings worth carrying

- **The integration break is behind clean markers, not in them.** Four base merges on one branch, and
  three times the break was a test arriving from main that installs the hook scripts it calls, while
  this branch had made one script delegate to a sibling that does not exist on main. Resolving the
  markers alone would have left the suite broken every time. The fix is to derive the siblings a
  script runs from the scripts themselves.
- **A missing ref is not "no answer".** `merge-base --is-ancestor` through a helper that cannot tell
  exit 128 from exit 1 reads a ref the pass failed to fetch as "has not landed", which suppresses the
  reparent, the restack and the promotion at once. That reverses a decision recorded for derivation,
  where a helper answering nothing on failure is correct.
- **Where a clone starts and where a work branch is cut from are separate events**, and only the second
  is a defect. That is what let the fork keep a regenerated staging branch as its default while still
  refusing a pull request based on it - and the ancestry test that had been rejected turned out to be
  right, tested against the staging branch rather than against main.
- **Read the script rather than reasoning about the deletions.** One real defect - a setup check
  requiring two constants pointing at files that exist nowhere, and reporting them present by name -
  was found that way and nothing else would have found it.

## Open

- **Sixteen review threads** on the setup script are outstanding, on one theme: literals that already
  have a named definition elsewhere, inline snippets that belong in files of their own type, and raw
  calls that should go through a structured runner.
- **Two threads sit inside an unsubmitted pending review**, so GitHub refuses every inline reply and
  submitting that draft is the user's. They are answered in code.
