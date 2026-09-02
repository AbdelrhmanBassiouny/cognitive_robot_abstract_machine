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

## The three threads he settled, same day

All three of the open threads went to him in session, and all three are answered:

1. **r3915277277** - `show_step_by_step(query)`: he accepted the shape as built
   (`show_step_by_step(look_for_the_cube_on_the_lid, WatchedCapture.from_command_line())`).
   Left open on the pull request, since closing a thread answered differently is his.
2. **r3915356623** - became the new plan item `how-to-look-concluded-from-the-request`,
   `request-language` track, `depends_on: [choose-detection-method,
   detector-parameters-from-knowledge]`, stacking on #159 through #239.
3. **r3915631447** - rename *and* role both folded into
   `imagination-world-rejects-what-a-predicate-refuses`, so the type is named once and
   #232 / #236 / #239 inherit no rename conflict.

Manifest saved as `9653daeb`; dashboard republished; the structural record is #201's
comment `5513403099`. All three threads carry a reply saying where each went; the two that
schedule a move are left open, per the precedent #202's plan-item threads set.

## Next

Nothing. The round is closed on both sides - the code is pushed, the description matches
it, the manifest and roadmap carry the outcome, and the only open threads are his to close.
Anything further on this branch starts from a new prompt.

## Environment

`pip install -U uv` (0.12.9 at `/usr/local/bin/uv`), then
`uv sync --extra dev --python 3.12`. Tests need `--noconftest` - the experiments conftest
imports `rclpy` - and six modules must be excluded because they do not collect without it:
`test_control_loop_benchmark`, `test_control_loop_runtime`, `test_montessori_bag_replay`,
`test_real_stretch_demo_process_boundary`, `test_sage10k`, `test_scalability`.
`black` and `docformatter` go into the venv by hand, with `.venv/bin` on `PATH`, before
`scripts/format_docstrings.py` runs.

