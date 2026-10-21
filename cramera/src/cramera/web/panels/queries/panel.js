/* ============================================================================
 * panels/queries/panel.js — the queries the robot asks, step by step.
 *
 * While it resolves a plan and while it carries it out, the robot asks queries: which
 * piece, which side to take it from, which arm is free, which hole the rules
 * conclude, which joint state parks an arm, which arm holds the piece. The demo
 * publishes every query it asked to the bridge (GET /query_steps); this panel lists
 * them under the scene and, while stepping, holds the robot at each one: an
 * inspector laid over the right-hand column shows the code that asks it, the
 * question in English, the backend answering it, its answers and how the backend
 * reasoned, and the bodies the answers are about glow in the 3D scene. Next lets the
 * robot carry on to the following query.
 *
 * The panel stays hidden until a running demo has published a query.
 *
 * Bus events:
 *   listens  live:changed {on, url}     poll the bridge while a demo is attached
 *   emits    entity:highlight {ids}     the bodies the shown step's answers are about
 *   emits    scene:focus {ids, milliseconds}   frame the scene on those bodies
 * ==========================================================================*/
Panels.define('queries', function (root, bus) {
  const POLL_MILLISECONDS = 250;
  const LISTED_STEPS = 7;
  const ANSWER_SPAN = 900;
  const REASONING_SPAN = 2600;
  // the gap between this panel's column and the inspector laid beside it, in pixels
  const STAGE_GAP = 6;
  const PHASES = {
    resolution: { css: 'qs-resolution', label: 'resolving the plan' },
    expansion: { css: 'qs-expansion', label: 'expanding into motions' },
    execution: { css: 'qs-execution', label: 'carrying it out' },
  };
  const esc = QuerySteps.esc;
  const faculty = ReasoningCards.faculty;

  root.innerHTML =
    '<div class="panel-head qs-head">' +
    '  <h2>Robot\'s queries</h2>' +
    '  <span class="qs-status" id="qs-status"></span>' +
    '</div>' +
    '<div class="qs-controls">' +
    '  <label class="qs-switch"><input type="checkbox" id="qs-stepping"><span></span>Step through</label>' +
    '  <label class="qs-switch qs-small"><input type="checkbox" id="qs-nested" checked><span></span>into nested queries</label>' +
    '  <button class="qs-btn qs-next" id="qs-next" disabled>Next ▸</button>' +
    '</div>' +
    '<div class="qs-list" id="qs-list"></div>';
  const statusEl = root.querySelector('#qs-status');
  const steppingEl = root.querySelector('#qs-stepping');
  const nestedEl = root.querySelector('#qs-nested');
  const nextEl = root.querySelector('#qs-next');
  const listEl = root.querySelector('#qs-list');

  const stage = document.createElement('div');
  stage.className = 'qs-stage';
  stage.innerHTML =
    '<div class="qs-top">' +
    '  <span class="qs-phase" id="qs-phase"></span>' +
    '  <span class="qs-during" id="qs-during"></span>' +
    '  <span class="qs-count" id="qs-count"></span>' +
    '  <button class="qs-close" id="qs-close" title="close">×</button>' +
    '</div>' +
    '<div class="qs-trail" id="qs-trail"></div>' +
    '<div class="qs-askers" id="qs-askers"></div>' +
    '<div class="qs-cols">' +
    '  <section class="qs-col qs-codecol"><h3>Asked in the code</h3><div id="qs-code"></div><div class="qs-from" id="qs-from"></div></section>' +
    '  <section class="qs-col qs-asks"><h3>The question</h3><div class="qs-question" id="qs-question"></div><div class="qs-by" id="qs-by"></div></section>' +
    '  <section class="qs-col"><h3>The answer</h3><div id="qs-answers"></div><div class="qs-lit" id="qs-lit"></div></section>' +
    '</div>' +
    '<div class="qs-reasoning" id="qs-reasoning"></div>' +
    '<div class="qs-foot">' +
    '  <span class="qs-hint" id="qs-hint"></span>' +
    '  <button class="qs-btn" id="qs-run">Run to the end</button>' +
    '  <button class="qs-btn qs-next qs-big" id="qs-stagenext">Next ▸</button>' +
    '</div>';
  document.body.appendChild(stage);
  const $ = function (id) { return stage.querySelector('#' + id); };

  let published = { steps: [], held: null };
  let picked = null;        // a step picked to look back at, or null to follow the robot
  let showing = null;       // the key of the step shown, so it is only drawn again when it changes
  let liveUrl = '';
  let timer = null;

  // %% talking to the demo
  function post(path, body) {
    if (!liveUrl) return;
    fetch(liveUrl + path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body || {}),
    }).then(poll).catch(function () {});
  }
  function advance() { picked = null; post('/query_steps/next'); }
  function setMode() { post('/query_steps/mode', { stepping: steppingEl.checked, holdsNested: nestedEl.checked }); }
  steppingEl.onchange = setMode;
  nestedEl.onchange = setMode;
  nextEl.onclick = advance;
  $('qs-stagenext').onclick = function () { picked !== null && picked !== published.held ? close() : advance(); };
  $('qs-run').onclick = function () { steppingEl.checked = false; setMode(); close(); };
  $('qs-close').onclick = close;
  function close() {
    picked = null;
    if (published.held === null) hideStage();
    else showStep();
  }
  document.addEventListener('keydown', function (event) {
    if (!stage.classList.contains('qs-open')) return;
    if (/^(INPUT|TEXTAREA)$/.test((event.target || {}).tagName || '')) return;
    if (event.key === 'ArrowRight' || event.key === 'n') { event.preventDefault(); advance(); }
    if (event.key === 'Escape') close();
  });

  // %% the inspector
  function placeStage() {
    const column = (root.parentElement || root).getBoundingClientRect();
    const left = column.right + STAGE_GAP;
    stage.style.left = left + 'px'; stage.style.top = column.top + 'px';
    stage.style.width = Math.max(0, window.innerWidth - left) + 'px';
    stage.style.height = column.height + 'px';
  }
  function hideStage() {
    if (!stage.classList.contains('qs-open')) return;
    stage.classList.remove('qs-open');
    showing = null;
    bus.emit('entity:highlight', { ids: [] });
  }

  function showStep() {
    const step = QuerySteps.shown(published, picked);
    if (!step) { hideStage(); return; }
    const key = step.number + ':' + step.moment + ':' + (step.number === published.held);
    if (key === showing && stage.classList.contains('qs-open')) return;
    const fresh = !showing || showing.split(':')[0] !== String(step.number);
    showing = key;
    placeStage();
    stage.classList.add('qs-open');
    const phase = PHASES[step.phase] || PHASES.resolution;
    const f = faculty(step.faculty);
    $('qs-phase').className = 'qs-phase ' + phase.css;
    $('qs-phase').textContent = phase.label;
    $('qs-during').textContent = step.during;
    $('qs-count').textContent = 'query ' + (step.number + 1) + ' of ' + published.total;
    $('qs-trail').innerHTML = trailHtml(step);
    $('qs-askers').innerHTML = QuerySteps.askers(published.steps, step).map(function (asker) {
      return '<span class="qs-asker">asked while answering <b>#' + (asker.number + 1) + '</b> ' +
        esc(QuerySteps.questionText(asker)) + '</span>';
    }).join('');
    if (fresh) {
      $('qs-code').innerHTML = QuerySteps.codeHtml(step.code);
      $('qs-from').innerHTML = step.askedFrom
        ? 'asked by <b>' + esc(step.askedFrom.function) + '()</b> in ' + esc(step.askedFrom.module) + ', line ' + step.askedFrom.line
        : '';
      $('qs-question').innerHTML = '<div class="qs-q qs-in">' + QuerySteps.questionHtml(step) + '</div>';
    }
    $('qs-by').innerHTML = '<div class="qs-backend ' + f.css + (fresh ? ' qs-in' : '') + '"><span class="rs-icon">' + f.icon + '</span>' +
      '<div><div class="qs-bname">' + esc(step.backend) + '</div><div class="qs-bnote">' +
      (step.generates ? 'generates what the statement leaves open · ' : '') + f.note + '</div></div>' +
      (step.milliseconds !== null ? '<span class="qs-ms">' + step.milliseconds + ' ms</span>' : '') + '</div>';
    $('qs-answers').innerHTML = QuerySteps.answersHtml(step, ANSWER_SPAN);
    $('qs-lit').innerHTML = step.moment === 'answered' && step.highlight.length
      ? '<span class="qs-glow"></span>lit in the scene' : '';
    $('qs-reasoning').innerHTML = step.moment === 'answered' && step.reasoning
      ? '<div class="rs-card rs-show ' + f.css + '"><div class="rs-cardhead ' + f.css + '"><span class="rs-icon">' + f.icon + '</span><b>how ' +
        esc(step.backend) + ' reasoned</b></div><div class="rs-cardbody">' +
        ReasoningCards.html({ reasoning: step.reasoning, answers: step.answers, evidence: [] }, REASONING_SPAN) + '</div></div>'
      : '';
    const held = step.number === published.held;
    $('qs-hint').textContent = held
      ? (step.moment === 'asked' ? 'Tracy waits before answering · Next answers it' : 'Tracy waits with the answer · Next lets it go on')
      : 'looking back at an earlier query';
    $('qs-stagenext').textContent = held ? 'Next ▸' : 'Back to the robot';
    $('qs-run').style.display = published.stepping ? '' : 'none';
    bus.emit('entity:highlight', { ids: step.moment === 'answered' ? step.highlight : [] });
    if (step.moment === 'answered' && step.frame.length) bus.emit('scene:focus', { ids: step.frame, milliseconds: 700 });
  }

  // every query asked so far, as a strip of dots by faculty, the shown one ringed
  function trailHtml(step) {
    return published.steps.map(function (s) {
      return '<i class="qs-dot ' + faculty(s.faculty).css + (s.number === step.number ? ' qs-here' : '') +
        (s.depth ? ' qs-nested' : '') + (s.phase === 'execution' ? ' qs-exec' : '') +
        '" data-step="' + s.number + '" title="#' + (s.number + 1) + ' ' + esc(QuerySteps.questionText(s)) + '"></i>';
    }).join('');
  }
  $('qs-trail').onclick = function (event) {
    const number = event.target && event.target.dataset && event.target.dataset.step;
    if (number === undefined) return;
    picked = Number(number);
    showStep();
  };

  // %% the list under the scene
  function renderList() {
    const steps = published.steps.slice(-LISTED_STEPS).reverse();
    listEl.innerHTML = steps.map(function (step) {
      const f = faculty(step.faculty);
      const held = step.number === published.held;
      return '<div class="qs-item ' + f.css + (held ? ' qs-helditem' : '') + '" data-step="' + step.number + '" style="padding-left:' + (8 + step.depth * 12) + 'px">' +
        '<span class="qs-num">#' + (step.number + 1) + '</span><span class="rs-icon">' + f.icon + '</span>' +
        '<span class="qs-text">' + esc(QuerySteps.questionText(step)) + '</span>' +
        '<span class="qs-got">' + (step.moment === 'answered' ? (step.answers.length ? '→ ' + esc(step.answers[0]) : '→ ∅') : '…') + '</span></div>';
    }).join('');
  }
  listEl.onclick = function (event) {
    const item = event.target.closest && event.target.closest('.qs-item');
    if (!item) return;
    picked = Number(item.dataset.step);
    showStep();
  };

  function renderStatus() {
    nextEl.disabled = published.held === null;
    if (document.activeElement !== steppingEl) steppingEl.checked = !!published.stepping;
    if (document.activeElement !== nestedEl) nestedEl.checked = published.holdsNested !== false;
    const text = published.held !== null
      ? 'held at #' + (published.held + 1)
      : published.total + ' asked';
    statusEl.textContent = text;
    statusEl.className = 'qs-status' + (published.held !== null ? ' qs-heldstatus' : '');
  }

  // %% following the bridge
  function take(next) {
    if (!next || next.unchanged || !(next.steps || []).length) return;
    root.classList.remove('idle');
    published = next;
    renderStatus();
    renderList();
    if (picked !== null || published.held !== null) showStep();
    else hideStage();
  }
  root.classList.add('idle');
  function poll() {
    if (!liveUrl) return;
    const known = published.revision !== undefined ? '?revision=' + published.revision : '';
    fetch(liveUrl + '/query_steps' + known).then(function (r) { return r.json(); })
      .then(take).catch(function () {});
  }
  bus.on('live:changed', function (live) {
    liveUrl = live && live.on ? live.url : '';
    if (timer) { clearInterval(timer); timer = null; }
    if (liveUrl) { timer = setInterval(poll, POLL_MILLISECONDS); poll(); }
  });
  window.addEventListener('resize', function () { if (stage.classList.contains('qs-open')) placeStage(); });

  return {
    destroy: function () {
      if (timer) clearInterval(timer);
      stage.remove();
    },
  };
});
