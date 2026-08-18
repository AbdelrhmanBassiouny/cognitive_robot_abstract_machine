# montessori_plan_graph_tab (plan item of montessori-eql-stack)

Branch `claude/plan-graph-executing-node-hqkt32`, based on #175
(`montessori_live_event_timeline_tab`). Draft PR #178.

## Plan

1. Check whether the plan tab already in the graph panel works. -- done: it polls
   `/plan` and colours rings, but it never shows *which* node is executing (running
   bubbles up the whole path), and its live path is gated on the recorded plan view
   loading, so a bundle whose plan view errors never shows the running plan.
2. Publish the executing nodes from the bridge. -- done: `PlanSnapshot.executing`
   (running, no running child) on `/plan`, with three tests in `test_live_bridge.py`.
3. Make the renderer per-container so two panels can draw graphs. -- done:
   `GraphView.create(container, legend)` replaces `window.Graph`/`attach()`;
   `core/split-resize` emits `panel:resized` instead of reaching for the global.
4. Extract the plan tree into `panels/plan_graph`, mount it as a tab beside Graph and
   Events, drop the graph panel's Plan tab. -- done, with the EXECUTING ring, the head
   line naming the step, and follow-the-step centring.
5. Tests. -- done: new `test_plan_graph_panel.js` (19 cases), updated graph/split tests,
   registered in `test_web_assets.py`. All 205 node tests green.

## Environment

The cramera pytest suite cannot run in this container: `random_events` needs its
`random_events_lib` C++ extension built from the workspace, and pip's `random_events` is
a different project. Python tests are left to CI; node tests run fine (`node --test`).

## Next

- Nothing outstanding. #178 is a draft, as every PR in this plan is; re-draft it after
  any further push.
- `montessori_detachable_panels` builds on this: each tab now holds a whole panel, which
  is what makes detaching one meaningful.
