# Which tips the integration build takes — Roadmap

Narrative half of `integration-tip-selection`. Created 2026-09-06 to give four
already-open pull requests a home: #281, #282, #284 and #285 belonged to no
plan, so every plan-filtered integration build reported them
`no-plan-recorded` — the filter could not answer for them either way, because
`_generated/branch-index.tsv` named no plan for their branches.

## Why its own plan rather than stack-maintenance

`stack-maintenance`'s `integration` track is the obvious home: these four are
all changes to the integration build, and all four stack on that track's own
items (#281 and #284 on #154, #282 and #285 on #211). It was not chosen
because of size: that plan holds 12 items and 1,493 lines against
`plan-size-limits`' budget of 15 items and 2,000 combined lines, so four more
would have taken it to 16 — one over the item half, which is precisely the
case `new-plan-when-full` (#277) exists to divert, and which
`refuse-oversized-save` (#273) will eventually refuse outright.

The first version of this section said 16 items becoming 20, from a count that
read each plan's `waves` and `tracks` entries as items too. The corrected
figures still route the work here, by one item rather than by five; recorded
because the overstated version is what the routing decision was taken on.

The seam is real rather than administrative: `stack-maintenance`'s integration
track is about a build existing at all — assembling it, giving it a CI verdict,
labelling what it carried. This plan is about the step *inside* that build
which decides what goes in.

## The two tracks

**Which tips a build takes** is one causal chain plus one refusal. #281 gives a
tip a priority tier so a collision is decided by what a branch is rather than
by which pull request numbered lower; #284 stops that tier depending on someone
having remembered to apply the label, by reading it off the files the pull
request changes. #285 sits in the same track because it also decides what gets
merged, but it is a refusal rather than an ordering — a tip is discarded
outright when merging it costs the build its own pipeline.

**What a build says about the rest** holds #282 alone. It is separated because
it changes no selection at all: the same tips are taken and left out, and the
only difference is that a branch's owner is told why.

## Decisions recorded at intake

**1. #281 was flagged as a fold candidate and kept as a real item.** Its entire
179-line diff edits files that #154 introduces and nothing else, which is the
shape that produced this fork's earlier folds (#133 into #117, #117 into #106).
It was kept separate on the user's call, for three reasons worth writing down:
it adds a mechanism (`BranchPriority`, two labels) rather than correcting a
defect in #154; #154 is coherent and runnable without it, merging by pull
request number; and #284 already bases on it, so folding would cascade into a
second open pull request. The general rule still prefers the fold — this is an
exception with its reasons, not a counter-example to it.

**2. The tracking issue is #102, reused rather than newly created.** #102 is
`workflow-unification`'s mailbox, inherited by every plan that plan's split
produced — `stack-maintenance` among them. This plan is a further split of the
same subject matter, so it reads the same mailbox rather than adding a
thirteenth one for four items.

**3. Cross-plan bases are recorded in `notes`, not in `depends_on`.**
`depends_on` resolves only within a plan, and three of these four stack on
`stack-maintenance` items (#154, #211). Only #284's dependency on #281 is
expressible, and it is the one that is expressed. Anyone reading readiness off
this plan alone will see three items with no prerequisites and should read
their notes before believing it.

## Still outstanding

- #282 needs the `integration-left-out` label created on the fork by hand; the
  write API does not create a missing label. #281's own `tooling` label, which
  its description asked for the same way, now exists.
- All four had no commit statuses at intake, so nothing is claimed here about
  their CI; the dashboard fetches that live on every run.
