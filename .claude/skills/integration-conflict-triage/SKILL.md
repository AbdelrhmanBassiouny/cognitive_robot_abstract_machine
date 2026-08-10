---
name: integration-conflict-triage
description: Judge what each collision on a personal integration branch means - whether two branches are duplicating something and one should adopt the other's abstraction, whether one genuinely depends on the other, or whether they merely touch the same lines and whoever lands second adapts - then resolve, propose or report accordingly. Invoke as "/integration-conflict-triage". Use after an integration build reports a tip left out, or when asked why two in-flight branches conflict with each other.
allowed-tools: Bash, Read, Grep, Edit, Write, AskUserQuestion, mcp__github__pull_request_read, mcp__github__list_pull_requests, mcp__github__add_issue_comment
---

# Integration conflict triage

The integration branch is the upstream base with every in-flight stack tip merged on top,
rebuilt from scratch on demand. It exists to be built *from* while the upstream review queue
lags. It is not history: nothing is ever merged out of it, and a conflict found on it is fixed
in the feature branch it belongs to - never here.

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
| `success` | every tip is in the branch; there is nothing to triage |
| `tip-left-out` | at least one tip is missing - this is your work, below |
| `tests-failed` | the branch built but does not work; a semantic collision no per-branch check could catch |
| `suspect-replay` | as above, over a resolution a skill wrote. **Report and stop** - see below |

A `suspect-replay` is the one status that forbids you to act. The build replayed a resolution
some earlier run of this skill wrote, and the result does not work. Re-resolving into the same
failure is how a build starts thrashing, so say which tip carries the suspect resolution, say
that it needs a human to look at the resolution itself, and stop.

## Step 2 - judge each pair, not each casualty

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

## What this never does

- **It never writes to a feature branch, and it never pushes.** Every branch in this collision
  belongs to somebody. The only thing you write is a resolution into the replay cache, which
  contaminates no branch and is thrown away with the next rebuild.
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
branch you took it to. Name anything you left undecided, and why, rather than picking to be
finished.
