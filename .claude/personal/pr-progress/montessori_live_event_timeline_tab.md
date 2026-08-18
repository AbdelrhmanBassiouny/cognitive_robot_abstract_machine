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

## Done

- Branch opened off #169, draft PR #175 created, manifest and roadmap recorded.

## Next

- Step 1: the `live/events.py` tests, then the module.

## Watch out

- `test_web_assets.py::test_configured_panels_are_defined` regex-parses the
  `layout` block of `config.js`. Extend it to read ids out of a tab group too,
  or it silently stops checking them.
- `.slot > .panel-graph { flex: 1 1 0 }` stops matching once the graph is
  nested inside the container; `core/split-resize.js` counts a slot's children
  by `dataset.panel`, which the container will not have.
- The graph's vis-network renders at zero size while hidden, so it has to
  re-fit on `panel:shown`.
- `config.js`, `index.html`, `app.css`, `bridge.py`, `http.py` are also touched
  by #165 — textual conflicts expected whenever the two meet.
