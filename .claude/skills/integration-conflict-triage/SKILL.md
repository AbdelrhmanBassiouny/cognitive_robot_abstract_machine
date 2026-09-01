---
name: integration-conflict-triage
description: Judge what each collision on a personal integration branch means - whether two branches are duplicating something and one should adopt the other's abstraction, whether one genuinely depends on the other, or whether they merely touch the same lines and whoever lands second adapts - then resolve, propose or report accordingly. Invoke as "/integration-conflict-triage". Use after an integration build reports a tip left out, or when asked why two in-flight branches conflict with each other.
allowed-tools: Bash, Read, Grep, Edit, Write, AskUserQuestion, mcp__github__pull_request_read, mcp__github__list_pull_requests, mcp__github__add_issue_comment
---

# Integration conflict triage

The integration branch is the upstream base with every reviewed in-flight stack tip merged on
top, rebuilt from scratch on demand. It exists to be built *from* while the upstream review
queue lags. It is not history: nothing is ever merged out of it.

**A conflict is fixed in the feature branch it belongs to; the integration branch is never
where a fix lives.** That is about feature branches and the build - it is not a rule against
writing anything at all. A *defer* verdict records its resolution in the replay cache, which
is a throwaway artifact belonging to your clone, contaminates no branch, and is thrown away
with the next rebuild. Keep the two apart: no feature branch is ever edited here, and the cache
is written to routinely.

`integration.py` builds it. It detects a collision, attributes it to the **pair** of branches
it is between, skips the later one and carries on. It makes no judgement about what the
collision means. That is your job, and it is the whole of your job.

**Why a judgement is needed at all.** A branch conflicting with the upstream base is simply
stale: one owner, one obvious fix. Two *siblings* conflicting is different. Both are based on
the same base, both are destined upstream, and neither is wrong. Worse, the obvious fix is a
trap: adapting B to an unlanded A makes B depend on unmerged work, which is exactly the
stacking this workflow exists to avoid. So there is often no correct branch to change today,
and deciding that is not something a script can do.

## Step 0 - make the tooling present rather than assuming it

Every step below shells out to `.claude/stack/`. If `ls .claude/stack/integration.py` fails,
`git fetch` the ref you were told to resolve this document from and restore it **into the
working tree only**:

```bash
git restore --source=<ref> --worktree -- .claude/stack/
```

Never reach for `git checkout` with a ref and a path here. That form writes the index as well,
so on a branch that does not carry the tooling the files end up staged, where the next commit
made on that branch would carry them in.

## Step 1 - get a build to triage

Either you were handed one, or you make one:

```bash
python .claude/stack/integration.py build --json
```

Act on the status the document leads with and the process exits with:

| status | what it means for you |
|---|---|
| `success` | every tip is in the branch and it works; there is nothing to triage |
| `tip-left-out` | at least one tip is missing - a merge collision, step 2 |
| `tests-failed` | the branch built and does not work - a *semantic* collision, step 4 |
| `suspect-replay` | as `tests-failed`, over a resolution a skill wrote. **Report and stop** |

Both kinds can be present at once: a build can leave a tip out *and* fail its suite. Work step
2 and step 4 independently - they are different collisions between different pairs.

A `suspect-replay` is the one status that forbids you to act. The build replayed a resolution
some earlier run of this skill wrote, and the result does not work. Re-resolving into the same
failure is how a build starts thrashing, so say which tip carries the suspect resolution, say
that it needs a human to look at the resolution itself, and stop.

## Step 2 - a `tip-left-out` build: judge each pair, not each casualty

For every tip the document reports as `skipped` or `replayed`, it names the branch it collided
with. Judge the **pair**. "B was skipped" is not actionable; which of the two should change is
the question, and neither branch's own state answers it.

Read both sides properly before deciding: the two diffs, both pull request descriptions, and
the plan roadmap if the branches belong to tracked items. There are three verdicts.

**reconcile** - the two are building the same thing under different names, and one should adopt
the other's abstraction. This is a real design call. It has happened on this repository more
than once and cost a duplicated artifact each time, which is why it is worth looking for rather
than assuming a collision is incidental.

**stack** - B genuinely depends on A. The existing tooling already models this as a base
change, and it is not yours to make.

**defer** - they touch the same lines incidentally, both are correct, and whoever lands second
adapts. This is the common case.

### When to ask, and when not to

Not by how sure you are. A skill that asks whenever it is unsure becomes a prompt generator,
and a question that arrives without a recommendation gets rubber-stamped - which is worse than
not asking, because it launders your guess as the developer's decision.

Ask by **whose decision it is**:

- **Facts** - what a branch does, whether two implementations really are the same abstraction,
  which landed first. Resolve these by reading. Never ask.
- **Intent** - which abstraction is the right one, whether two branches should have been one
  pull request. Ask.

That lands almost exactly on *reconcile*, and the question comes **before** the proposal: a
proposal already encodes the choice it would be asking about.

## Step 3 - act, bounded by where the answer lands

The bound is the artifact, not your confidence. A confident change written onto a published
pull request is more dangerous than an uncertain one written into a cache that is thrown away
and rebuilt.

**defer - resolve it fully.** Nothing about this touches a feature branch. Stage the collision,
write the resolution into the conflicted files, and record it:

```bash
python .claude/stack/integration.py stage-conflict --tip <skipped> --against <other>
# resolve the conflicted files it names, in the worktree it names, then:
python .claude/stack/integration.py record-resolution \
    --tip <skipped> --worktree <the worktree> --author skill
```

Always record a resolution you wrote as `--author skill`, whatever else the flag accepts. That
is what lets a later build say a replay was machine-written, and it is the only reason a wrong
one can ever be found again - a resolution nobody claimed is read as a developer's, which is
the one case that was always acceptable.

Then rebuild and confirm the branch is whole and its suite passes.

**reconcile - propose, do not apply.** Say what should change, in which branch, and why the
other is the one to adopt. Do not edit either branch: resetting an approval to apply a design
call its author has not agreed to is the wrong default however good the change is. Take the
verdict to the owner of the branch that should change.

**stack - report.** Say which branch should sit on which. Do not retarget anything.

## Step 4 - a `tests-failed` build: the failure the merge could not see

Two branches can each pass their own checks, merge with no conflict at all, and not work
together - one renames what the other calls, one removes what the other's test imports, one
adds a dependency the other's fixture does not provide. Per-branch checks structurally cannot
catch this: neither branch is wrong, and the failure exists only in a tree neither of them is.

**Find the pair before judging it.** A failing suite over ten merged tips names nothing:

```bash
python .claude/stack/integration.py locate-failure --json
```

It re-assembles the tips in the same order and runs the suite after each, so what it reports
describes the build that failed. It names the tip whose arrival turned the suite, and narrows
to the earlier tip that alone reproduces it. Do not search by hand - it is several worktrees
and several suite runs, and getting it subtly wrong is easy.

Confirm what it hands you rather than taking it: each of the two on its own should pass the
suite. If one fails alone, that branch is simply red and this is not a collision at all - tell
its owner that instead.

### The one thing that is different here

**Nothing can be recorded for an integration test failure.** `rerere` replays *merge conflict*
resolutions, and this has no conflict and therefore no preimage to key one on. So
the `defer` verdict from step 3 does not exist here, and reaching for it is the mistake this
section is written to prevent. Until one of the two branches changes, **every future build
carries the failure**. Rebuilding does not help, and saying it might would be a lie with a delay
attached.

### The verdicts

**adapt** - one branch's assumption has been made untrue by the other, and that branch changes
to match. This is the common case, and unlike `reconcile` it is **fixed, not proposed**. A break
is a defect: one branch's code cannot run in the presence of the other's, somebody has to fix it,
and this pass is what found it. Handing it back as a question leaves the integration branch red
and costs a round trip to be told the obvious.

*Which* branch changes is usually a fact rather than intent, and it is settled by reading: it is
the branch whose **own stated contract** the break violates. A pin that promises "every file the
tool needs to run" and copies one directory is defective against its own promise the moment the
tool reaches a second one - nothing about that needs deciding. Read both pull requests' own words
for what each undertakes, and fix where the undertaking is broken.

Ask only when no contract settles it - when the fix would change what a pull request **promises**
rather than what it **delivers**, so either branch could defensibly absorb it. That is intent, and
it is the developer's.

**reconcile** - as in step 3. A break can reveal a duplicated abstraction just as a conflict
can, and it is worth looking for before settling for `adapt`.

**sequence** - the failure exists only because both are unlanded. Once the first lands, fixing
the second is ordinary work on a normal base, with a real review behind it. Nothing to do now
but record it where the plan's state lives, and say which order makes it go away.

A fix carries a **reproduction test** with it, and the test goes wherever the rule it states can
be stated - which is not always the branch being fixed and not always the branch that broke it.
Neither branch holds the merged tree, so a test that needs it cannot be written on either; what
can always be written is the rule, against a small tree the test builds itself. A fix without one
is a fix the next build cannot tell from a break that went away on its own.

Whichever it is, say plainly whether the integration branch is red until somebody acts, and which
area of the suite is affected - a developer can still work from a branch whose breakage they
know the shape of, and cannot from one they do not.

### Step 5 - block the branch, because a comment alone is missed

This step is for a break left standing - one whose `adapt` had no contract to settle it and went
to the developer, or a `sequence`. A break you fixed needs no block: the reproduction is what
says it is gone, and blocking a branch whose fix is already pushed withholds it from the next
build for nothing.

A failure nobody acts on is carried by every later build. So the branch that causes it is
**blocked**, not merely mentioned, and blocking it is one command rather than four steps done
by hand:

```bash
python .claude/stack/integration.py block-branch --json
```

It applies the `integration-conflict` label to the breaking branch's pull request and comments
on it naming the branch it breaks, addressed to the session in its description. Both halves
matter: `needs-resolution` is cleared automatically once a pull request stops reporting a
conflict, and a failure between two cleanly merging branches never makes one conflicted - so
reusing that label would have
the very next maintenance pass strip it, silently reopening the loop the label exists to close.
`integration-conflict` blocks through the same code path and nothing clears it automatically.

Then make the failure reproducible and record it where the plan's state lives:

1. **Push a failing test to the *breaking* branch.** Not to the branch that relies on the
   thing: it cannot express a test against an import that does not exist on it yet. The worked
   case is a branch adding a module-scope import of a package another branch's fixture does not
   build - which is testable on the breaking branch alone, with no merge involved.
2. **Record it on the item**, with `plan_item_bootstrap.py block --branch <branch>`, so the
   dashboard shows the branch as blocked rather than leaving the fact in a comment.
3. **Republish**, with `/plan-dashboard <plan-id>`, in the same turn - a dashboard older than
   the manifest behind it is worse than none.

This is the one place the workflow writes to somebody else's branch, and it is deliberate: a
test that reproduces the failure is not a design decision, and it is the only artifact that
makes the failure visible from inside the branch that causes it. It is a test and nothing else - never
a fix, which is a design call and stays proposed.

## What this never does

- **It never writes a fix to a feature branch.** Every branch in this collision belongs to
  somebody, and which of them should change is their call. The two things it does write are
  bounded and neither is a fix: a resolution into the replay cache, which contaminates no
  branch and is thrown away with the next rebuild, and a failing test onto the branch that
  breaks another, which makes the failure reproducible without deciding anything.
- **It never treats the integration branch as work.** Nothing is merged out of it; it is
  regenerated from scratch every time. A fix that lives only there is not a fix.
- **It never gates promotion on a clean build.** Promotion asks whether one branch is ready for
  review; integration asks whether the branches coexist. A collision is not a reason to hold
  either branch back, and saying so would block one branch for another's sake with no principled
  reason that one is the one to wait.
- **It never comments on a pull request for a `defer`.** A deferred collision asks nothing of
  anybody, and a pull request nobody is watching is the wrong place for a note. Record it where
  the plan's own state lives. Only *reconcile* and *stack* give an owner something to do, and
  only those earn a comment.

## Finish

Report every pair, with its verdict and the reason. For a *defer*, say that the resolution is
recorded and that the collision is still live for whoever lands second - a replay buys a working
daily driver, not a discharged obligation upstream. For a *reconcile* or a *stack*, say which
branch you took it to. For an integration test failure, say that the branch stays red until
somebody acts,
since nothing can be recorded for it. Name anything you left undecided, and why, rather than
picking to be finished.
