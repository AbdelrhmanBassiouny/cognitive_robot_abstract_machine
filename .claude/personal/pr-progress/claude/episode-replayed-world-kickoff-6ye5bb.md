# #246 — `episode-replayed-into-the-world` (plan `knowledge-directed-perception`, track `events`)

Branch `claude/episode-replayed-world-kickoff-6ye5bb`, based on #244. Draft, and
staying a draft. This session resolved the review round of 2026-09-03; the item was
built in session `01Udpwca`.

## What was stalling it

Four review threads opened 2026-09-03 17:50–17:55, none of them recorded in the item's
`blockers`. Nothing else: CI green on all 23 checks, `mergeable_state` clean, base #244
open and out of draft. Fifth time on this plan that a stall was a review comment nobody
had turned into state.

## Done

- `3b3e3f53` — `RosbagPlayer._sample` (50 lines, two nested functions closing over four
  pieces of state) became `RecordedMessage`, `RecordedState` and `RecordingSampler`, plus
  `RosbagTopic.advances_the_clock` and `.message_type` for the branch that was in the
  message loop. Six ROS message-type strings became `RosbagMessageType` members, reused by
  both the reader and the test dataset. Docstrings and type hints everywhere missing.
  `TransformsAt`/`JointPositionsAt` share a `PublishedMessage` base. Five tests added,
  each mutation-checked.
- `f9a961fc` — the JSON player's `_pause`/`_resume` docstrings and `UNROOTED_FRAME`, the
  last two gaps an AST sweep found.
- Replied to all four threads; resolved three. Manifest `blockers`/`notes` updated,
  roadmap section appended, dashboard republished, PR description rewritten.

`test/segmind_test`: 53 passed, 1 skipped (48 passed, 1 skipped before).

## Outstanding — the developer's, not this session's

- **r3927219116 left open on purpose.** Two places are deliberately undocumented: the two
  new exceptions' `error_message`/`suggest_correction` overrides (no `DataclassException`
  subclass in the workspace documents theirs, and the abstract base states both contracts)
  and `DataPlayer.__post_init__`/`FilePlayer.__post_init__` (untouched by this branch).
  Offered on the thread to add either.
- CI was still running on `f9a961fc` when this session finished; `mergeable_state` was
  `unstable` for that reason rather than for a red check.

## Environment, for whoever picks this up

`pip install -U uv` → 0.12.9 at `/usr/local/bin/uv`; `uv sync --extra dev --python 3.12`
builds the workspace and now brings `rosbags` with it. `black` and `docformatter` by hand
with `.venv/bin` on `PATH`. Tests with `--orm-build never`.
`plan_item_bootstrap.py` in this branch's checkout has no `update` subcommand, so the
manifest was edited directly and pushed with `save-plan.sh --manifest`.
