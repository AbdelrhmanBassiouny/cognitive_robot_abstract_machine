# setup-runs-without-asking — PR #156

**Plan item:** `workflow-unification` / `setup-runs-without-asking`
**Branch:** `claude/auto-run-setup-notes-02nhxv` (base `main`)
**Mode:** `auto`, from the committed default (no personal override exists).

## The plan

The item was stalled on a merge conflict, not on review or CI. Resolve it per the
resolution the 2026-08-12 review round already recorded, then carry this branch's
rule into the two documents that forked the superseded wording while it was open.

## Done

- Merged `origin/main`. Three conflicts, all in the step-0 setup instruction:
  - `plan-item-{kickoff,resolve}/SKILL.md` — took `main`'s deletion (the section
    moved into `plan-dashboard/plan-item-gathering.md` with #149). Verified against
    the merge base that the branch's only edit to either file was that wording.
  - `.claude/hooks/README.md` — kept this branch's wording, added `main`'s
    `/add-plan-item` to the list.
  - `prerequisite-check.md` auto-merged correctly (rewrite + the added name).
- Carried "run it, don't ask" into `plan-dashboard/plan-item-gathering.md` and
  `add-plan-item/SKILL.md`, which `test_setup_prerequisite_documents.py` flagged
  the moment `main` came in — exactly the case the guard was written for.
- 533 tests pass across the four CI directories (was 464 pre-merge).
- Pushed `e0362dae`; rewrote the PR description; updated `plan.yaml` notes and
  appended the resolution to `roadmap.md`; republished the dashboard.
- `/upstream-reviews` run: `cram2` has no pull request with this head, so there is
  no upstream review to read. The `cram2-link-sent` label means the compare link
  was built, not that Create was clicked.

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
