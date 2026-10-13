## Next
- **Nothing on the branch.** #222 is green on all 23 checks, `mergeable_state: clean`,
  out of draft, and **all nine review threads are now resolved** — the developer closed
  r3893312001 and its two follow-ups himself, so the five-open state this note used to
  describe is gone.
- **The `needs-resolution` label is still on #222** and is what still withholds it from
  promotion. The routine clears it on its own next pass now that the branch merges
  cleanly (`maintenance_restack_steps.py`'s `WithholdBlockedBranch` clears it as a side effect), so it was left alone
  rather than removed by hand.
- **Do not re-draft this pull request.** The developer took it out of draft himself, which
  in the stack workflow is how a branch is approved for promotion; re-drafting would undo
  that approval.


## Watch out for
- Base is #221, not #205. Do not restack onto #205.
- **`main`'s entity query language now moves under this track.** #227, #238 and everything
  stacked past them meet the same three krrood files when the merge reaches them; the
  resolution is in the plan's `roadmap.md` so it is not re-derived four times.
- **Native evaluation returns nothing for a `Match` carrying an ellipsis attribute**, so
  the ellipsis attributes must be dropped from the check and the stated ones re-applied.
- **Native evaluation does not narrow a domain by the declared type**, so the backend
  does it (`LookRequest.admits`). Verified, not assumed.
