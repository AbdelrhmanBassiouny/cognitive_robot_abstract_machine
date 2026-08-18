# montessori_live_event_timeline_tab — PR #175 (draft)

Plan item `montessori-eql-stack` / `montessori_live_event_timeline_tab`, first
item of the `live-panels` track. Based on `montessori_fast_inline_monitor`
(#169). Full approved plan and its reasoning: the item's section in
`plans/montessori-eql-stack/roadmap.md` (2026-08-18).

## The plan

Make the viewer's lower-right frame a tab widget holding whole panels — the
knowledge graph becomes one tab, a live segmind-event timeline the other.

1. **cramera backend**, following `live/run_control.py` as the template:
   `live/events.py` (`DetectedEvent`, `LiveEventSource`,
   `NoEventSourceRegistered`), `bridge.register_event_source()` /
   `event_payload()` / an `events` flag in `status()`, and `GET /events` in
   `live/http.py`.
2. **cramera frontend**: `core/panel_tabs.js` (the container, emits
   `panel:shown`), `core/registry.js` (a layout entry may be a tab group),
   `core/timeline_layout.js` (geometry as plain arithmetic, per
   `core/split-sizing.js`'s precedent), `panels/event_timeline/panel.js`, plus
   `config.js` / `index.html` / `app.css` / `core/split-resize.js`.
3. **experiments/montessori**: `MontessoriEventMonitor.tick()` notifies a
   listener with just that tick's new events, into a thread-safe append-only
   log; a `LiveEventSource` over it registered in `_attach_cramera`.
   `progress.record_attempt(...)` untouched.

Tests first throughout: Python under `test/cramera_test` and
`test/experiments_test`, JS under `test/cramera_test/js` in the free-variable
binding style `test_graph_panel.js` documents, each new JS file wired into
`TestJsUnits` in `test_web_assets.py`.

## Done — all four steps implemented and pushed (draft PR #175)

1. `6b8062ce` cramera backend: `live/events.py`, bridge registration,
   `GET /events`, `events` flag in `/info`.
2. `458339bd` `core/panel_tabs.js` + registry tab groups; also the guard that a
   node test file with no `TestJsUnits` entry never runs.
3. `f39d8b3c` `core/timeline_layout.js`, `panels/event_timeline/panel.js`,
   `config.js`/`index.html`/`app.css`/`split-resize.js`; a panel is now handed
   its own registered id, and the graph re-fits on `panel:shown`.
4. `2da15ffd` demo side: monitor listener, `live_event_source.py`,
   `_attach_cramera` registration.

`pytest test/cramera_test` → 448 passed. Experiments tests can only be run here
with `--noconftest` (no ROS in this container).

## Next

- Nothing outstanding for this session. Awaiting review.

## Decisions worth remembering

- Two `test_web_assets.py` guards were added because this change needed them: a
  node test file with no `run_node` entry never ran and nothing said so, and a
  tab group's ids sit behind a `panel:` key the old layout reader skipped.
- `Panels.define`'s factory now takes `(root, bus, id)`. The alternative — a
  `PANEL_ID` constant in the graph panel — broke
  `test_configured_panels_are_defined`, which regex-reads the literal out of
  `Panels.define('graph', …)`.
- Timeline geometry: a run younger than the 60 s window is drawn from its own
  start so the now-bar sweeps; past that the window scrolls and marks slide left.

## Known gaps and hazards

- **Untested by design:** the two wiring lines in `franka_montessori_demo.py`.
  Covering them means starting the real bridge (fixed port + global monkey
  patches) in the suite; `_attach_cramera` has no test today for that reason.
  Stated openly in the PR description.
- Two experiments tests fail in this container and **also fail on the base
  branch**: `test_shape_falling_through_its_hole_…`
  (`MissingReferenceFrameError`) and `test_a_run_that_records_opens_the_database…`
  (no `rclpy`). Not caused by this branch.
- `config.js`, `index.html`, `app.css`, `bridge.py`, `http.py` are also touched
  by #165 — textual conflicts expected whenever the two meet.
