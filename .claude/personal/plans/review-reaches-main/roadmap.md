# Getting a review back to main — roadmap

## Why this plan exists, and why it is not one of the existing plans

#265 is an integration branch that will never merge. Three pull requests (#286, #299,
#355) plus a nineteen-deep chain are based on it, and 269 non-merge commits on it are in
no open pull request at all.

The obvious reading — "#265 is the problem, take it apart" — is wrong, and so is its
opposite. What is actually true is one level up:

> **Four plans each stack over the same files, and none of them owns the join.**

Perception is `knowledge-directed-grounding` (#202 → #205 → #221 → #225 → #232 → #236 →
#270, plus #223), `knowledge-directed-requests` (#231 → #239 → #266 → #275, plus #259),
`knowledge-directed-expectation` (#257), `icra-foundation` (#296) and `icra-evidence`
(#295). Those plans' own descriptions say why the edges between them are missing:
*"those depends_on edges could not cross the plan boundary and are recorded as blockers
instead."* The plan split of 2026-09-05, done for the size budget, cut a single
programme into plans that share files. #265 is where the join happened instead — 36
times, off-review.

So the missing work is the join, and no existing plan can own it by construction. That
is the whole reason this plan exists. Everything that *is* owned elsewhere stays there:
the predicate rebase is `eql-verbalization`'s `p4-sdt-migration`, and detecting the next
duplication automatically is `design-overlap`'s (tracking issue #102), whose
`definition-catalogue` and `overlap-detector` items are exactly the three scripts
described below.

## The measurements this plan rests on

Taken 2026-09-19.

| | |
|---|---|
| open pull requests | 148 |
| bottoming out on `main` | 119 |
| bottoming out on a #265-family branch | 27 |
| based on `main` directly | 36 |
| median distance from `main` | 124 commits |
| deepest chain | 11 |
| #265's unique content (not on main, in no open pull request) | 269 non-merge commits |
| of 36 closed sub-pull-requests, tracked as plan items | 5 |
| of 122 open pull requests outside the #265 family: current with main | 82 |
| … more than 200 commits behind | 35 |

The headline is that the graph is far healthier than the queue looks, and that the
binding constraint is **landing**, not deciding. Which is also what the one real
collision turned out to be.

## Three scans, and why the third is what makes the result trustworthy

1. **Pairwise trial merge** (`git merge-tree` between chain tips whose own diffs share a
   `.py` file). 78 tips, 166 candidate pairs, 119 collide. Low value alone: dominated by
   staleness hubs — #257 collides with fourteen pull requests over the same five files
   because it is 200+ commits behind, not because fourteen designs duplicate. And it is
   structurally blind to a pull request colliding with `main`, so it missed #296 entirely.
2. **Per-pull-request divergence from main** — which of `main`'s symbols does this branch
   remove (AST, top-level plus `Class.method`), and how far behind is it. This is the one
   that works: it is what sees #296, and it yielded 31 candidate duplication pairs from
   shared removals.
3. **Removal attribution** — for each shared removal, which commit on each branch removed
   it. **Same commit means the two branches inherit one removal from a shared ancestor,
   which is not duplication at all.** This cuts 31 pairs to 9, and the 9 are all one
   collision.

Step 3 is not optional. Without it the scan reports a whole chain as a cluster, and the
first reading of this output did exactly that — claiming six duplication clusters
(`world.py`/`test_world.py`, `base_expressions.py`, `example_classes.py`, the setup
scripts, and wrongly tying that last one to the #106/#110/#117 precedent). All of those
were inherited removals: one piece of work on several branches. Retracted.

## The one real duplication was already decided a month ago

`predicates.py` was converted from functions to classes twice, independently:

- **#229** (`cbf45ab529`): `InContactWith`, `InsideRegion`, `PlaceIsOccupied`,
  `Reachable`, `Stable`, `SupportedBy`, `Supports`, `VisibleTo`. Off `main`, current with
  it. Inherited by #227, #238 and #257 — so those are one piece of work on four branches,
  not four duplicates. #238/#257 extend it (`Between`, `Colored`, `Near`, `Turned`, …).
- **#33** and **#35** (`9da08b2cfb` / `8c584bef0f` / `84b0d096b6`): `Contact`,
  `IsSupportedBy`, `Visible`, `AllClose`, `OccludingBodies`, and additionally
  `robot_predicates.py`'s eight functions. 413 and 2,103 commits behind `main`.

The scan rediscovered this independently, which is a good check on the method — and then
both pull requests turned out to record the developer's decision of **2026-08-31, in
#229's favour**, with #33's rebase tracked as `p4-sdt-migration`. #33's own description
states the blocker exactly: *"#229 has not merged yet, so that rebase cannot start."*

So there was never a recommendation to make here. The item is a merge. That is the
clearest evidence for this plan's ordering: the queue is blocked on landing.

## Decisions taken, and premises that turned out wrong

- **Re-cutting perception: proposed, then withdrawn.** The initial recommendation was to
  take #265's final `perception/` tree as the spec and rebuild it as a short stack. That
  was based on reading the four lineages as accidental. They are not: they are eight
  tracked plan items, and `knowledge-directed-grounding`'s chain is already correctly
  stacked, matching its own `depends_on` exactly. Re-cutting would have destroyed eight
  items' review work for nothing. The fix is a join pull request per collision.
- **Re-cutting the tracy demo: stands.** Different situation — untracked, so no item's
  history is lost, and the history is a demo evolving rather than reviewable changes.
- **Reopening the closed sub-pull-requests: impossible.** #363 is `merged: true`; GitHub
  cannot reopen a merged pull request. The branches and the descriptions are the assets.
- **#229 vs #296 misattributed.** A comment was posted on both saying they collided over
  `PlaceAction._grasp_description`. #229 does not touch `placing.py` at all. Corrected on
  both pull requests and in #422's commit messages; the resolution itself was always
  right, only its rationale was wrong.
- **Two commits were pushed onto #244's branch after #244 had closed.** Its state was not
  checked first. See `foldins-rehomed`.

## The method lesson, worth carrying beyond this plan

**"Which open pull request introduces each file the commit changes" is necessary but not
sufficient, and a clean cherry-pick is not evidence.** A commit also needs the symbols it
*imports* and the fields it passes as *keywords*, which live in files it never touches.
Three wrong outcomes came from missing this: #286 reparented onto #275 (would
`ModuleNotFoundError`, reverted), #415 opened against `main` (closed, folded), and the
`InsertAction` extraction nearly shipped twice on bases where it would have raised
`TypeError`.

Two AST verifiers were written for it — one resolving every workspace `ImportFrom`
against a target tree, one checking `ImportedClass.attr` and `ImportedClass(kw=...)`
against the class and its resolvable bases. They belong with `design-overlap`'s items
alongside the three scans.

Per-branch detail for the work this plan recovers stays in
`.claude/personal/pr-progress/`, which keeps working independently of this manifest.

## What would make this plan unnecessary next time

`base-rule`, the last item: a pull request is based on `main` or on an approved pull
request, and building on unapproved work means merging the dependency in and saying so.
Every collision in this plan is a convergence decision that was deferred past the point
where it was cheap.
