## Next / outstanding
- **Nothing is blocking.** CI was green before the merge and the merge is now
  pushed; the new run should be watched by the user, not by this session.
- **The PR is out of draft** and nothing on record says who flipped it. Not
  re-drafted after this push, to avoid undoing a deliberate signal — the user's
  call.
- The two 2026-08-12 review threads stay open on purpose: their outcome was a
  deferral (the dedup belonged to #149), not a change here.
- Worth carrying to #194: the upstream-reviews action exits 1 on the clean
  "no upstream pull request" answer, which reads as a failed run to any caller
  checking the exit status before the log.
- The `## Promote` link could not be written back from this session: the
  upstream `cram2` compare URL, and everything after it, is stripped on write
  (reproduced twice, read back through a second tool). Left absent on purpose —
  `description_with_promotion_link` re-appends heading and link when neither is
  present, so the next maintenance pass restores it from the runner.
- CI on `e0362dae`: 20 of 23 checks green including `test_claude_dev_tooling`;
  the three still running are unrelated robotics jobs.
- `needs-resolution` is left for the next pass to clear itself, which is the
  loop it exists to close.

## The plan
The item was stalled on a merge conflict, not on review or CI. Resolve it per the
resolution the 2026-08-12 review round already recorded, then carry this branch's
rule into the two documents that forked the superseded wording while it was open.
