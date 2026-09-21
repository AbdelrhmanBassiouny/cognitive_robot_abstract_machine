/* ============================================================================
 * panels/plan_graph/panel.js — the robot's plan, and the step it is on.
 *
 * Attached to a running demo, the tree is re-read from the bridge several times
 * a second. The nodes execution has actually reached are drawn as EXECUTING and
 * named above the tree; the ancestors they run underneath stay merely running,
 * which is why highlighting the running nodes alone would light up a whole path
 * instead of the step being done. Detached, the plan recorded in the scene
 * bundle is shown instead.
 *
 * A structure change (the plan grows as actions expand) rebuilds the tree; a
 * pure status change only re-colours the rings, so the layout never jumps.
 *
 * Bus events:
 *   emits    entity:select {id, detail, relations}   node clicked
 *   listens  live:changed {on, url}                  follow a demo, or stop
 *   listens  panel:shown {id}                        this tab became visible
 *   listens  panel:resized {}                        the frame was given a new size
 *
 * Rendering is delegated to panels/graph/graph.js (window.GraphView).
 * ==========================================================================*/
Panels.define('plan-graph', function (root, bus, panelId) {
  const POLL_MILLISECONDS = 500;
  /* How often the bridge is asked where execution has got to. Short enough that
     a step of the plan is not over before its node lights up. */

  const RECORDED_PLAN_URL = '/api/knowledge/view?name=plan';
  /* The plan of the recorded episode, shown while no demo is attached. */

  const EXECUTING = 'EXECUTING';
  /* The status graph.js draws a reached node with, as opposed to 'RUNNING'. */

  const ZOOM_STEP = 1.3;
  /* One step in and its exact inverse out, so + then − lands where it started. */

  const RECORDED = 'the recorded plan';
  const NOTHING_EXECUTING = 'nothing is being executed right now';
  const NO_PLAN_YET = 'Attached, but the demo has not started its plan yet.';
  const NO_RECORDED_PLAN = 'No plan to show.';

  root.innerHTML =
    '<div class="graph-wrap">' +
    '  <div class="plan-head">' +
    '    <span id="plan-executing" class="plan-executing"></span>' +
    '    <label class="plan-follow" title="centre the tree on the step being executed">' +
    '      <input type="checkbox" id="plan-follow" checked /> follow' +
    '    </label>' +
    '    <span class="gt-live" id="plan-live" title="the plan is streaming from the running demo">◉ live</span>' +
    '  </div>' +
    '  <div id="plan-canvas" class="graph-canvas"></div>' +
    '  <div class="graph-zoom">' +
    '    <button id="plan-zoom-in" title="Zoom in — or pinch on a touchpad">+</button>' +
    '    <button id="plan-zoom-out" title="Zoom out — or pinch on a touchpad">−</button>' +
    '    <button id="plan-zoom-fit" title="Fit the whole plan">⤡</button>' +
    '  </div>' +
    '  <div id="plan-empty" class="graph-empty" style="display:none"></div>' +
    '  <div class="legend" id="plan-legend"></div>' +
    '</div>';

  const emptyEl = root.querySelector('#plan-empty');
  const executingEl = root.querySelector('#plan-executing');
  const followEl = root.querySelector('#plan-follow');
  const liveBadge = root.querySelector('#plan-live');
  const graph = GraphView.create(root.querySelector('#plan-canvas'),
                                 root.querySelector('#plan-legend'));

  root.querySelector('#plan-zoom-in').addEventListener('click', function () { graph.zoomBy(ZOOM_STEP); });
  root.querySelector('#plan-zoom-out').addEventListener('click', function () { graph.zoomBy(1 / ZOOM_STEP); });
  root.querySelector('#plan-zoom-fit').addEventListener('click', function () { graph.fit(); });

  let liveUrl = '';
  let view = null;            // the payload currently drawn
  let structure = null;       // signature of the tree that was last built
  let executing = [];         // ids the drawn payload says are being executed
  let pollTimer = null;

  // %% the plan as the graph renderer takes it
  // drop the redundant 'Action' suffix only — a label that merely contains the word,
  // such as 'ActionNode', must survive intact. Mirrors
  // PlanViewPayload._shorten_action_label: the bridge sends the raw designator name,
  // so the live path shortens it here.
  function shortenActionLabel(label) {
    const shortened = label.replace(/Action$/, '');
    return shortened || label;
  }

  function livePayload(live) {
    const reached = {};
    (live.executing || []).forEach(function (id) { reached[id] = 1; });
    const nodes = [], edges = [], details = {};
    (live.nodes || []).forEach(function (node) {
      const label = shortenActionLabel(node.label || '?');
      const lines = ['a ' + node.kind,
                     'status: ' + node.status + (node.derived ? ' (derived from the motion statechart)' : '')];
      if (node.arm) lines.push('arm: ' + node.arm);
      if (node.target) lines.push('target: ' + node.target);
      nodes.push({ id: node.id, label: label, group: node.group,
                   title: [label].concat(lines).join('\n'),
                   status: reached[node.id] ? EXECUTING : node.status });
      details[node.id] = { label: label, group: node.group, lines: lines };
      if (node.parent) edges.push({ from: node.parent, to: node.id, kind: 'property', label: 'has step' });
    });
    return { nodes: nodes, edges: edges, details: details, legend: live.legend || [],
             layout: 'hier', arrows: true, statusLegend: true, key: 'plan-live',
             structure: live.signature, executing: live.executing || [],
             heading: NOTHING_EXECUTING, empty: NO_PLAN_YET };
  }

  function recordedPayload(recorded) {
    recorded.key = 'plan-recorded';
    recorded.structure = 'recorded';
    recorded.executing = [];
    recorded.heading = RECORDED;
    recorded.empty = recorded.empty || NO_RECORDED_PLAN;
    return recorded;
  }

  // %% drawing
  function setView(payload) {
    view = payload;
    structure = payload.structure;
    const empty = !payload.nodes.length;
    emptyEl.style.display = empty ? '' : 'none';
    emptyEl.textContent = empty ? payload.empty : '';
    graph.build({
      nodes: payload.nodes, edges: payload.edges, legend: payload.legend,
      layout: payload.layout, arrows: !!payload.arrows,
      statusLegend: !!payload.statusLegend, key: payload.key,
    });
  }

  function show(payload) {
    if (payload.structure !== structure) {
      setView(payload);                          // the tree itself changed → rebuild
      return announce(payload);
    }
    const statuses = {};
    payload.nodes.forEach(function (node) { statuses[node.id] = node.status; });
    if (!graph.setStatuses(statuses)) {
      setView(payload);                          // a node the drawn tree does not have
      return announce(payload);
    }
    view = payload;                              // same tree: keep the details in sync
    announce(payload);
  }

  function sayNothingToShow(message) {
    emptyEl.style.display = '';
    emptyEl.textContent = message;
  }

  function labelOf(id) {
    return (view && view.details[id] && view.details[id].label) || id;
  }

  function announce(payload) {
    const reached = payload.executing;
    executingEl.textContent = reached.length
      ? 'executing: ' + reached.map(labelOf).join(', ')
      : payload.heading;
    if (reached.join('|') === executing.join('|')) return;
    executing = reached;
    if (followEl.checked && reached.length) graph.focus(reached[0]);
  }

  // %% following the bridge, or falling back to the recorded plan
  async function refreshLive() {
    let live;
    try {
      live = await fetch(liveUrl + '/plan').then(ResponseUtil.parseJson);
    } catch (err) {
      return;                                    // bridge gone — the 3D side handles it
    }
    if (!live || !live.nodes) return;
    show(livePayload(live));
  }

  async function showRecordedPlan() {
    let recorded;
    try {
      recorded = await fetch(SceneContext.withScene(RECORDED_PLAN_URL))
        .then(ResponseUtil.parseJson);
    } catch (err) {
      return sayNothingToShow('Could not load the recorded plan: ' + ((err && err.message) || err));
    }
    if (!recorded.ok) return sayNothingToShow(recorded.error || NO_RECORDED_PLAN);
    show(recordedPayload(recorded));
  }

  function stopFollowing() {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = null;
  }

  bus.on('live:changed', function (state) {
    stopFollowing();
    liveUrl = state.on ? (state.url || '') : '';
    liveBadge.classList.toggle('on', !!liveUrl);
    structure = null;                            // what is drawn came from the other source
    executing = [];
    if (!liveUrl) return showRecordedPlan();
    pollTimer = setInterval(refreshLive, POLL_MILLISECONDS);
    refreshLive();
  });

  // vis-network measures its container as it draws, and a tab body that is not the
  // visible one has no size, so a tree drawn behind a closed tab stays wrong until it
  // is told the tab opened
  bus.on('panel:shown', function (shown) { if (shown.id === panelId) graph.resize(); });
  bus.on('panel:resized', function () { graph.resize(); });

  // %% node click → describe in whatever panel listens
  graph.onSelect(function (id) {
    const detail = view && view.details && view.details[id];
    if (!detail) return;
    const relations = (view.edges || [])
      .filter(function (edge) { return edge.from === id || edge.to === id; })
      .map(function (edge) {
        return { s: labelOf(edge.from), p: edge.label || edge.kind, o: labelOf(edge.to) };
      });
    bus.emit('entity:select', { id: id, detail: detail, relations: relations });
  });

  showRecordedPlan();

  return { destroy: stopFollowing };
});
