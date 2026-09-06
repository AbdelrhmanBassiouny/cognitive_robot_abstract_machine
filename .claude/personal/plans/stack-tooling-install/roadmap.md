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

- **A test that passes on output it did not produce is not testing its subject.** The test asserting
  the setup run *says* how to record a git identity passed with that guidance deleted, because
  `check-setup.sh`'s own row already names both flags and the script ends by printing that report - so
  it had been satisfied by somebody else's message throughout. The tell was that it matched free text
  in a whole subprocess's stdout rather than a parsed field of a named check. The same class recurred
  in the label round, where a description parser splitting on whitespace read only each sentence's
  first word, and those happened to be distinct. Both were found by mutation, not by reading.
- **A label list is about how labels read, not whether they work.** The fork's own labels are the
  evidence: the ones created by hand carry descriptions, while one that arrived some other way is the
  default grey with none, and a fourth does not exist at all despite being referenced throughout the
  tooling. So a setup that creates them is buying the explanation, and every label it declares needs a
  description of its own - which is why an unknown one is refused rather than given a generic sentence.
- **A list is only checkable if everything in it has a reader.** `integration-conflict` was asked for
  and left out because it lives only on the integration-branch pull requests: naming labels no code
  applies turns the list into a wish nothing can hold to anything.

## Open

- **One review thread stays open by the standing rule**, answered differently from what it asked:
  whether one git runner should serve every caller. The raw calls are gone onto the scratch repository,
  but the shared runner lives under `.claude/stack/`, so reaching it costs a production `sys.path`
  insert the package migration is deleting the last of. That seam is `bastler-notes-core-python`'s by
  name and now has five callers waiting; the deciding question - whether one runner can serve a caller
  that must never raise and one for which a silent failure is the bug - would be settled in the wrong
  item here.
- **Two threads sit inside an unsubmitted pending review**, so GitHub refuses every inline reply and
  submitting that draft is the user's. They are answered in code.
- **Live label creation is still exercised only through a stub**, since this environment's token is a
  fine-grained installation token.

## The stall on `setup-stacked-prs-skill`, as found on 2026-08-30

Two causes at once, and the manifest recorded neither: the pull request was `dirty` against its own
base, whose review round had added two commits it never merged, and the pending review its previous
session could not reply into had since been submitted - turning two invisible threads into 27
unresolved ones, 25 of them a round dated the same day.

**The two are one piece of work, not two.** The round is almost entirely a single rule - a literal
naming a fixed thing where a named definition belongs - and the base's own round is what created the
definitions to name it with (`.claude/hooks/tooling_files.py`, and `RepositoryLabel` in
`tests/github_api.py`). Applying the round before merging the base would have built a second copy of
exactly the thing the reviewer was asking not to have two of.

Both were cleared the same day. What the pass added to what this plan already knew:

- **Fifth occurrence of the duplicated-mechanism shape, and the first where both copies were whole
  subsystems.** The four before it were a fix applied at three call sites; this time each branch had
  built the same "install the siblings a script runs" mechanism, independently, in the same week. The
  tell is that neither conflict marker said so - the merge conflicted on four files and the duplication
  was in none of them.
- **A retyped copy of a value the run under test used is worse than a literal**, because both copies
  move together and the test keeps passing while agreeing with itself. Two turned up: a printed report
  compared against a dict retyping what the fixture had just set, and a default branch restated beside
  the script that declares it. Neither would have been found by grepping for hardcoded strings; both
  were found by asking what each assertion's source of truth is.
- **The review's rule reached production, where the duplication was worse than in the tests it was
  raised against**: the GitHub host was written out in two places in `stack.py`. A comment about test
  literals is worth carrying into the code the tests are about.

### `setup-personal-notes-script` (#107) and `setup-stacked-prs-skill` (#110): stale integration-conflict labels cleared, 2026-09-06

Both pull requests had fallen behind `main` (107 by 103 commits) and both carried an
`integration-conflict` label from an automated integration build on 2026-08-31, blocking
promotion. Resolved via `/plan-item-resolve`, not by guessing:

- **The reported rebase conflict was real, but only under `git rebase`.** This branch's
  history already contains one merge commit that resolved an add/add conflict on
  `.claude/hooks/tests/stubs/{curl,gh}.sh` against `main` (documented on #107 as "the two
  stub files united"). A linear `git rebase` replays the original commits and discards
  that resolution, so it re-hits the same conflict against a `main` that has since moved
  further. A plain `git merge` - the convention this whole stack otherwise uses - does not
  reopen it. `main` merged into #107 clean (`053de8eb`), #110 merged onto the new #107
  head clean (`9a192041`), both green on the `integration_test_command` scope.
- **The integration-conflict finding no longer reproduces.** #107 was blocked against
  `D-deco`, #110 against `D-store` - both unrelated `krrood`/RDR feature branches whose
  diffs touch nothing outside `test/krrood_test/` and `AGENTS.md`. Neither pull request
  ever had a reproduction test pushed (`@pytest.mark.integration_conflict`), so nothing
  had re-verified either finding since the day it was recorded. Reconstructing each pair
  by hand (merging `main` + the D-branch + the fork branch in a scratch worktree and
  running the exact suite `integration.py build` runs) found both merges clean and both
  suites green. Both `D-deco` and `D-store` record being rebuilt as a branch reset on
  2026-08-31 - the same day - to drop a symbol forbidden by a later `main` change; the
  likely explanation is the original build tested their pre-rebuild tips. Labels removed
  from both pull requests with the evidence posted as a PR comment on each.
- **Process note for later reads of this history:** `block-branch`'s own step 5 (push a
  reproduction test, record on the item, republish) was never completed for either
  finding - only the automated comment-and-label half ran. A finding with no reproduction
  test is one nothing will ever re-check on its own; it has to be revisited by hand, which
  is what happened here five days later.
