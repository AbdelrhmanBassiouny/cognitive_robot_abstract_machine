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

## Split (2026-10-02)
- Developer: #202 too big -> split into layers as its own plan `montessori-perception-split`
  (tracking issue #486, dashboard https://claude.ai/artifact/HbJxEtTJQRQzyvZoTp591u).
- 8 items: network_limits standalone; stack vocabulary -> world -> frames -> piece recognition
  -> pipeline -> captures; #202 becomes the top (ROS runtime) by merging the stack in (no file
  change) and retargeting its base. Nothing on this branch is rewritten.
- Not started; next is `/plan-item-kickoff montessori-perception-split shape-vocabulary-on-main`
  (and network-limits-on-main in parallel).
