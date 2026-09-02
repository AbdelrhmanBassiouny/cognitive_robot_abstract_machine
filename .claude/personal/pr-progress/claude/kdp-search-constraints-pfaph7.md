# #238 - Clip the search to the region a spatial predicate allows

Plan item `search-clipped-to-a-predicates-region` of `knowledge-directed-perception`
(tracking issue #201). Branch `claude/kdp-search-constraints-pfaph7`, stacked on #227,
with #232 and #229's tip merged in. Draft.

## What this session did

Resolved the review round of 2026-09-02 (`/plan-item-resolve`, `auto` mode). Six threads,
none of which the item's `blockers` recorded before this run - the fourth time on this plan
that a stall was a review comment nobody turned into state. They were written into the
manifest before any code, and the dashboard republished.

Pushed as `f8288bcd` and `6429626f`:

- `narrowing_relations`' docstring says what the three relations are for, plainly.
- `_is_this_surfaces` -> `_is_on_this_surface`.
- `_POSE_NOUN` / `_frame_noun` inlined into
  `HomogeneousTransformationMatrix._verbalization_noun_phrase_`.
- The demonstration is one call: `step_by_step.py` holds `show_step_by_step`,
  `WatchedCapture`, `RecordedLook` and everything the narrowing draws with;
  `watch_narrowing.py` is the statement plus `main`. `board_in` moved onto the pipeline.
- Three new tests. 467 passed, 1 skipped, 11 xfailed against 464 on the previous tip;
  sdt's failing set byte-identical, 14 lines by name.

Replied on all six threads; resolved the three answered exactly as asked.

## Outstanding, and all of it is the developer's call

1. **r3915277277** - `show_step_by_step(query)`: done as
   `show_step_by_step(statement_about_a_look, capture)`, since a statement about this scene
   cannot be built before the look is taken. Left open. If he wants it literal, either
   `RecordedLook` carries the statement or the function becomes a method on the look.
2. **r3915356623** - why answering a query needs a pipeline; discuss; consider EQL-RDRs
   (#159 open/ready, #77 open/ready but `integration-conflict`). Proposed as a new plan
   item - *"a look is planned from the request, not configured"* - stacked on #159. Not
   added: adding an item is structural.
3. **r3915631447** - rename to `DetectedMontessoriShape` and make it a `Role` for
   `MontessoriShape`. Rename is 51 references / 10 files and a conflict for #232, #236,
   #239; the role needs the look to spawn what it found into a world, which is
   `imagination-world-rejects-what-a-predicate-refuses`. Recommended both halves in that
   item; not taken.

## Next

Nothing until he answers 1-3. This session's obligation to the PR ended with the push,
the replies and the description update.

## Environment

`pip install -U uv` (0.12.9 at `/usr/local/bin/uv`), then
`uv sync --extra dev --python 3.12`. Tests need `--noconftest` - the experiments conftest
imports `rclpy` - and six modules must be excluded because they do not collect without it:
`test_control_loop_benchmark`, `test_control_loop_runtime`, `test_montessori_bag_replay`,
`test_real_stretch_demo_process_boundary`, `test_sage10k`, `test_scalability`.
`black` and `docformatter` go into the venv by hand, with `.venv/bin` on `PATH`, before
`scripts/format_docstrings.py` runs.

