# Writing a roadmap section against the budget, not against completeness

Shared by `plan-create`, `plan-item-kickoff`, `plan-item-resolve` and
`add-plan-item` — every skill that adds text to a plan's `roadmap.md`. Each
previously defaulted to writing down everything, on the theory that dropping
content loses information. That default is what spends the budget every
plan is now held to (`SizeBudget` in `.claude/hooks/plan_size_budget.py`):
the budget bounds a plan's `plan.yaml` and `roadmap.md` together, but the
guidance telling sessions what to write against it was unbounded, so a
healthy plan drifts back over regardless of how carefully any one session
writes.

Measured, not assumed: during the single session that created
`plan-size-limits`, `workflow-unification` grew 51 manifest and 103 roadmap
lines while gaining zero items — narrative accreting onto entries that
already existed. The plan's own splits found the same pattern independently
three times: 94%, 92%, and most of a third oversized roadmap turned out to
be per-round narrative about pull requests that had already merged, with
each pull request already carrying that record.

## Keep

- The plan's own "why" — the problem it exists to solve, and why it is its
  own plan rather than an item elsewhere.
- A design decision with a lasting consequence: what was decided, the
  alternative considered, and why it was rejected. A decision a future
  session would otherwise have to re-litigate is the one thing a compressed
  roadmap cannot afford to drop.
- Standing risks, hazards, and landing conditions that bind future work.
- Open questions nobody has answered yet.
- A conclusion a later item's plan depends on — the kind of thing a kickoff
  or resolve would otherwise have to re-derive from scratch.

## Compress

- Per-round implementation narrative — which commit, which test, which
  review comment was addressed how — once the round it describes has
  merged. A line naming the outcome is enough; the pull request is the
  detailed record already, and it is linked.
- Item `notes` the same way, hardest on `done` items: what the item shipped
  as, not the history of how it got there.

Nothing is destroyed by compressing: the personal-notes branch's own commit
history keeps every uncompressed version reachable.

## Where this applies

- **`plan-create`**, migrating a source doc: apply this rule from the
  start rather than carrying over everything the source said. Structured
  facts (branch, PR, base, status, blockers) still become `plan.yaml`
  items as before; this changes only what becomes `roadmap.md` narrative.
- **`plan-item-kickoff`**, writing an item's first roadmap section: write
  what a later kickoff or resolve would actually need — the plan and its
  reasoning — not a transcript of how this session reached it.
- **`plan-item-resolve`**, appending an update: append the same way, not a
  narrated round-by-round account of the investigation.
- **`add-plan-item`**, recording a new item: the same discipline applies to
  the section its `record` call writes.

If a plan is already close to the budget, err further toward compression,
not less — that plan is exactly the one this rule exists to protect first.
