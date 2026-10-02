# PR #202 - montessori_perception_on_main (knowledge-directed-grounding / montessori-perception-on-main)

## State (2026-10-02)
- All 14 review threads resolved (two rounds, 2026-08-29); CI green on 7223b8d68 (2026-09-22).
- Stall 2026-09-23 -> 2026-10-02: merging `main` conflicted in `.gitignore` (main's coverage
  block vs this branch's rosbags block, same spot). The maintenance routine labelled it
  `needs-resolution` and skipped it on every pass (10 identical PR comments).
- Resolved by 4653fe32e (/plan-item-resolve): main merged, both blocks kept. Branch's own
  tests: 154 passed, 1 skipped (`--noconftest`, venv with workspace packages installed).

## Next
- CI on 4653fe32e; the routine should clear `needs-resolution` on its next clean pass.
- PR left out of draft on purpose (item notes: a draft would show dependents #205 etc. as
  blocked on the dashboard) - user to confirm or flip.
- Upstream: `cram2-link-sent`, not `in-review`; promotion is the user's click.
