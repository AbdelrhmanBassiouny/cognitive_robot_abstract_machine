## Plan assignments for #281, #282, #284, #285

No pull request, and none is expected: this branch changes no tracked file.
All the work landed on `claude/personal-notes` instead.

**Task.** The four pull requests belonged to no plan, so every plan-filtered
integration build read them as `no-plan-recorded`.

**Done.**
- Ran the `/add-plan-item` scope check on all four against `main`, with every
  sibling unlanded branch as a candidate.
- Created plan `integration-tip-selection` (4 items, 2 tracks, 1 wave,
  169 lines) rather than growing `stack-maintenance`, on the user's call.
- Saved it via `save-plan.sh`; the regenerated `branch-index.tsv` now names a
  plan for all four branches, which is what the filter reads.
- Published its dashboard and republished the master index.
- Recorded the structural change on tracking issue #102.

**Correction made mid-task.** The first size figures given to the user counted
each plan's `waves` and `tracks` entries as items, so `stack-maintenance` was
reported at 16 items when it holds 12. Corrected in the plan's `roadmap.md`;
the routing decision is unchanged (16 vs 15 still exceeds the item budget).

**Next.** Nothing outstanding here. Two things sit with the user: creating the
`integration-left-out` label on the fork for #282, and deciding whether #281's
flagged fold into #154 is worth revisiting.
