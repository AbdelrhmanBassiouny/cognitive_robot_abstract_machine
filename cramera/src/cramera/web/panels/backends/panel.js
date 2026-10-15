/* ============================================================================
 * panels/backends/panel.js — how a plan's open parts were resolved, before the
 * robot moved.
 *
 * A plan leaves parts open (which piece, which side to take it from, which arm, which
 * hole). Before the robot carries it out, each part is asked as a statement and
 * answered by the backend that declares it can: perception, working memory,
 * ripple-down rules or a probabilistic model. The demo publishes every resolution to
 * the bridge (GET /slot_answers); this panel plays each one on a stage laid over the
 * right-hand column -- the plan as stated, the backends, the plan as resolved -- one
 * part at a time: the part lights up, flies to the backend answering it, the backend's
 * reasoning is drawn (the camera's view, the collision boxes it tested, the rules it
 * walked, the distribution it sampled), and the answer fills the resolved plan. The
 * bodies a part is about glow in the 3D scene.
 *
 * Under the scene, the panel keeps the latest resolution: its backends, the resolved
 * plan, and buttons to play it again or have the robot carry it out.
 *
 * The panel stays hidden until a running demo has published the backends it asks.
 *
 * Bus events:
 *   listens  live:changed {on, url}     poll the bridge while a demo is attached
 *   emits    entity:highlight {ids}     the bodies the part being resolved is about
 *   emits    scene:focus {ids, milliseconds}   frame the scene on those bodies
 *   emits    eql:run {code, text}       have the robot carry out a resolved plan
 * ==========================================================================*/
Panels.define('backends', function (root, bus) {
  // what each backend reads, by the faculty it answers from
  const FACULTIES = {
    'perception': { css: 'f-perception', icon: '◉', note: 'what the camera saw' },
    'working memory': { css: 'f-memory', icon: '◈', note: 'the twin, read off its geometry' },
    'rules': { css: 'f-rules', icon: '⋔', note: 'ripple-down rules about the board' },
    'probabilistic': { css: 'f-probabilistic', icon: '∿', note: 'a model of grasping, sampled' },
  };
  const DEFAULT_PRESENTATION = { partMilliseconds: 4200, beforeMilliseconds: 1600, afterMilliseconds: 2400 };
  const POLL_MILLISECONDS = 400;
  // a resolution answered longer ago than this when the viewer first sees it is not
  // played on its own; it can still be played again from the panel
  const FRESH_SECONDS = 30;
  const MARK = /⟦([^⟧]+)⟧/g;
  const SIDE_ORDER = ['FRONT', 'BACK', 'RIGHT', 'LEFT'];
  // the gap between this panel's column and the stage laid beside it, in pixels
  const STAGE_GAP = 6;

  root.innerHTML =
    '<div class="panel-head rs-head">' +
    '  <h2>Plan resolution</h2>' +
    '  <span class="rs-status" id="rs-status"></span>' +
    '</div>' +
    '<div class="rs-compact" id="rs-compact"></div>';
  const statusEl = root.querySelector('#rs-status');
  const compactEl = root.querySelector('#rs-compact');

  const stage = document.createElement('div');
  stage.className = 'rs-stage';
  stage.innerHTML =
    '<div class="rs-top">' +
    '  <div class="rs-kicker">Resolving an under-specified plan</div>' +
    '  <div class="rs-title" id="rs-title"></div>' +
    '  <div class="rs-progress" id="rs-progress"></div>' +
    '</div>' +
    '<div class="rs-cols">' +
    '  <section class="rs-col"><h3>Under-specified plan</h3><div class="rs-code" id="rs-under"></div></section>' +
    '  <section class="rs-col rs-by"><h3>Resolved by</h3><div class="rs-question" id="rs-question"></div><div class="rs-backends" id="rs-backends"></div></section>' +
    '  <section class="rs-col"><h3>Resolved plan</h3><div class="rs-code" id="rs-resolved"></div></section>' +
    '</div>' +
    '<div class="rs-card" id="rs-card"></div>' +
    '<div class="rs-token" id="rs-token"></div>' +
    '<div class="rs-foot" id="rs-foot"></div>';
  document.body.appendChild(stage);
  const $ = function (id) { return stage.querySelector('#' + id); };
  const titleEl = $('rs-title'), progressEl = $('rs-progress');
  const underEl = $('rs-under'), resolvedEl = $('rs-resolved');
  const questionEl = $('rs-question'), backendsEl = $('rs-backends');
  const cardEl = $('rs-card'), tokenEl = $('rs-token'), footEl = $('rs-foot');

  function esc(text) {
    return String(text).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }
  function faculty(name) { return FACULTIES[name] || FACULTIES['working memory']; }

  // %% the plan's lines, as stated and as resolved
  // answered: slot id -> part; mode 'under' marks open parts, 'resolved' fills them
  function renderLines(el, lines, mode, answered) {
    el.innerHTML = lines.map(function (line) {
      let text = esc(line.text);
      let comment = '';
      const hash = text.indexOf('   # ');
      if (hash >= 0) { comment = text.slice(hash + 3); text = text.slice(0, hash); }
      text = text.replace(MARK, function (_, slot) { return markHtml(slot, mode, answered[slot]); });
      const part = line.slot && answered[line.slot];
      const cls = 'rs-line' + (line.slot ? ' rs-slotline' : '') +
        (part ? ' rs-answered ' + faculty(part.faculty).css : '');
      return '<div class="' + cls + '" data-slot="' + esc(line.slot || '') + '">' + text +
        (comment ? '<span class="rs-comment">' + comment + '</span>' : '') + '</div>';
    }).join('');
  }
  function markHtml(slot, mode, part) {
    const css = part ? ' rs-filled ' + faculty(part.faculty).css : '';
    let shown;
    if (mode === 'under') shown = part ? '✓' : '…';
    else shown = part ? (part.answers.length ? esc(part.answers[0]) : '∅') : '';
    return '<span class="rs-mark' + css + '" data-mark="' + esc(slot) + '">' + shown + '</span>';
  }
  function answeredUpTo(resolution, count) {
    const answered = {};
    resolution.parts.slice(0, count).forEach(function (part) { answered[part.slotId] = part; });
    return answered;
  }

  // %% the backends column
  let backendEls = {};
  function renderBackends(backends) {
    backendEls = {};
    backendsEl.innerHTML = '';
    backends.forEach(function (backend) {
      const f = faculty(backend.faculty);
      const el = document.createElement('div');
      el.className = 'rs-backend ' + f.css;
      el.innerHTML = '<span class="rs-icon">' + f.icon + '</span><div><div class="rs-bname">' +
        esc(backend.name) + '</div><div class="rs-bnote">' + f.note + '</div></div>' +
        '<span class="rs-bcount">0</span>';
      backendsEl.appendChild(el);
      backendEls[backend.faculty] = { el: el, count: el.querySelector('.rs-bcount'), answered: 0 };
    });
  }

  // %% each backend's reasoning, drawn
  function reasoningHtml(part, span) {
    const r = part.reasoning || {};
    if (r.kind === 'perception') return perceptionHtml(r, span);
    if (r.kind === 'working memory') return memoryHtml(r, span);
    if (r.kind === 'rules') return rulesHtml(r, span);
    if (r.kind === 'probabilistic') return samplingHtml(r, span, part.answers);
    return '<div class="rs-lines">' + part.evidence.map(esc).join('<br>') + '</div>';
  }
  function delay(ms) { return 'animation-delay:' + Math.round(ms) + 'ms'; }

  function perceptionHtml(r, span) {
    let html = '';
    if (r.tableView) {
      const found = r.pieces.filter(function (p) { return p.selected; }).map(function (p) { return p.name; });
      html += '<div class="rs-views">' +
        '<figure class="rs-view rs-in" style="' + delay(0) + '"><img src="' + r.tableView + '"><figcaption>table, rectified</figcaption></figure>' +
        '<figure class="rs-view rs-in" style="' + delay(span * 0.28) + '"><img src="' + r.foundView + '"><figcaption>' +
        (found.length ? 'found · ' + esc(found.join(', ')) : 'nothing of that kind') + '</figcaption></figure></div>';
    }
    html += '<div class="rs-fits">' + r.pieces.map(function (p, i) {
      return '<div class="rs-fit rs-in' + (p.selected ? ' rs-yes' : ' rs-no') + '" style="' + delay(span * (0.45 + i * 0.08)) + '">' +
        '<span class="rs-tick">' + (p.selected ? '✓' : '✗') + '</span><span class="rs-fname">' + esc(p.name) + '</span>' +
        '<span class="rs-bar"><i style="width:' + Math.round(p.fit * 100) + '%;' + delay(span * (0.45 + i * 0.08)) + '"></i></span>' +
        '<span class="rs-pct">outline fits ' + Math.round(p.fit * 100) + '%</span></div>';
    }).join('') + '</div>';
    return html;
  }

  // a piece's collision box dropped onto its support's, seen from above at an angle
  function contactSvg(reading, index, span) {
    const s = reading.size;
    const scale = 1700;
    const w = s[0] * scale, d = s[1] * scale, h = s[2] * scale;
    const iso = function (x, y, z) { return [(x - y) * 0.866, (x + y) * 0.5 - z]; };
    const pts = function (list) { return list.map(function (p) { return p[0].toFixed(1) + ',' + p[1].toFixed(1); }).join(' '); };
    const box = function (x0, y0, z0, bw, bd, bh) {
      const c = function (x, y, z) { return iso(x0 + x, y0 + y, z0 + z); };
      return {
        top: pts([c(0, 0, bh), c(bw, 0, bh), c(bw, bd, bh), c(0, bd, bh)]),
        left: pts([c(0, bd, 0), c(bw, bd, 0), c(bw, bd, bh), c(0, bd, bh)]),
        right: pts([c(bw, 0, 0), c(bw, bd, 0), c(bw, bd, bh), c(bw, 0, bh)]),
      };
    };
    const slabW = Math.max(w, d) * 2.6, slabT = 9;
    const slab = box(-slabW / 2 + w / 2, -slabW / 2 + d / 2, -slabT, slabW, slabW, slabT);
    const piece = box(0, 0, 0, w, d, h);
    const gap = reading.gapMillimetres;
    const ok = reading.selected;
    const base = span * (0.15 + index * 0.18);
    return '<div class="rs-contact rs-in" style="' + delay(base) + '">' +
      '<svg viewBox="-120 -80 240 150" class="rs-iso">' +
      '<g class="rs-slab"><polygon points="' + slab.left + '"/><polygon points="' + slab.right + '"/><polygon class="rs-slabtop" points="' + slab.top + '"/></g>' +
      '<g class="rs-drop' + (ok ? ' rs-ok' : ' rs-bad') + '" style="' + delay(base + span * 0.08) + '">' +
      '<polygon points="' + piece.left + '"/><polygon points="' + piece.right + '"/><polygon class="rs-boxtop" points="' + piece.top + '"/></g>' +
      '<g class="rs-contactline rs-in" style="' + delay(base + span * 0.32) + '"><line x1="-70" y1="' + (iso(w / 2, d / 2, 0)[1]).toFixed(1) + '" x2="70" y2="' + (iso(w / 2, d / 2, 0)[1]).toFixed(1) + '"/></g>' +
      '</svg>' +
      '<div class="rs-ctext"><b>' + esc(reading.name) + '</b><span>' +
      (reading.support ? 'bottom on ' + esc(reading.support) + ' top · gap ' + gap + ' mm' : esc(reading.relation)) +
      '</span><span class="rs-verdict rs-in" style="' + delay(base + span * 0.36) + '">' + (ok ? '✓ supported' : '✗ not supported') + '</span></div></div>';
  }
  function memoryHtml(r, span) {
    let html = r.condition ? '<div class="rs-condition">where ' + esc(r.condition) + '</div>' : '';
    const boxes = r.readings.filter(function (x) { return x.size; });
    if (boxes.length) {
      html += '<div class="rs-contacts">' + boxes.slice(0, 3).map(function (reading, i) { return contactSvg(reading, i, span); }).join('') + '</div>' +
        '<div class="rs-note rs-in" style="' + delay(span * 0.55) + '">a geometric test, in simulation, between the bottom of each piece\'s collision box and the top of what it rests on</div>';
      return html;
    }
    return html + '<div class="rs-rows">' + r.readings.map(function (reading, i) {
      return '<div class="rs-row rs-in' + (reading.selected ? ' rs-yes' : ' rs-no') + '" style="' + delay(span * (0.1 + i * 0.15)) + '">' +
        '<span class="rs-tick">' + (reading.selected ? '✓' : '✗') + '</span><b>' + esc(reading.name) + '</b><span>' + esc(reading.relation) + '</span></div>';
    }).join('') + '</div>';
  }

  function rulesHtml(r, span) {
    const firedAt = r.rules.findIndex(function (rule) { return rule.fired; });
    const steps = Math.max(1, (firedAt < 0 ? r.rules.length : firedAt + 1));
    const step = span * 0.5 / steps;
    const cascade = r.rules.map(function (rule, i) {
      const cls = rule.fired ? ' rs-fired' : (rule.tried ? ' rs-tried' : ' rs-untried');
      return (i ? '<div class="rs-else rs-in" style="' + delay(step * i) + '">else</div>' : '') +
        '<div class="rs-rule rs-in' + cls + '" style="' + delay(step * i) + '">' +
        '<div class="rs-if">if ' + esc(rule.condition) + '</div>' +
        '<div class="rs-then">then ' + esc(rule.conclusion) + '</div>' +
        (rule.fired ? '<span class="rs-firedtag rs-in" style="' + delay(step * i + span * 0.06) + '">fires</span>' : '') +
        (rule.tried && !rule.fired ? '<span class="rs-cross rs-in" style="' + delay(step * i + span * 0.05) + '">✗</span>' : '') + '</div>';
    }).join('');
    const b = r.board, S = 900;
    const W = b.width * S, L = b.length * S;
    const map = function (p) { return [((p[1] + b.length / 2) * S).toFixed(1), ((b.width / 2 - p[0]) * S).toFixed(1)]; };
    const lit = span * 0.5 + step * 0.5;
    const holes = b.holes.map(function (hole) {
      const c = map(hole.center);
      return '<polygon class="rs-hole' + (hole.chosen ? ' rs-chosen' : '') + '" style="' + (hole.chosen ? delay(lit) : '') + '" points="' +
        hole.points.map(function (p) { const m = map(p); return m[0] + ',' + m[1]; }).join(' ') + '"/>' +
        (hole.chosen ? '<circle class="rs-ring" style="' + delay(lit) + '" cx="' + c[0] + '" cy="' + c[1] + '" r="24"/>' : '');
    }).join('');
    return '<div class="rs-rules">' +
      '<div class="rs-cascade"><div class="rs-case">case: <b>' + esc(r.case) + '</b> · kind = ' + esc(r.caseKind) + '</div>' + cascade + '</div>' +
      '<div class="rs-board rs-in" style="' + delay(span * 0.2) + '"><svg viewBox="-10 -10 ' + (L + 20).toFixed(0) + ' ' + (W + 20).toFixed(0) + '">' +
      '<rect class="rs-lid" x="0" y="0" width="' + L.toFixed(1) + '" height="' + W.toFixed(1) + '" rx="6"/>' + holes + '</svg>' +
      '<div class="rs-boardnote">the board\'s holes · ' + (r.holes.length ? esc(r.holes.join(', ')) : 'none of that kind seen') + '</div></div></div>';
  }

  function samplingHtml(r, span, answers) {
    const prior = {};
    r.prior.forEach(function (p) { prior[p.side] = p.probability; });
    const sides = SIDE_ORDER.filter(function (s) { return s in prior; });
    const top = Math.max.apply(null, sides.map(function (s) { return prior[s]; }));
    const counts = {}; sides.forEach(function (s) { counts[s] = 0; });
    const dt = span * 0.45 / Math.max(1, r.samples.length);
    const dots = {}; sides.forEach(function (s) { dots[s] = ''; });
    r.samples.forEach(function (side, i) {
      if (!(side in dots)) return;
      dots[side] += '<i class="rs-dot rs-in" style="' + delay(span * 0.25 + i * dt) + '"></i>';
      counts[side] += 1;
    });
    // the sides in the order the backend answered them, most likely first
    const ranked = answers.length ? answers : sides.slice().sort(function (a, b) { return prior[b] - prior[a]; });
    const bars = sides.map(function (side) {
      const height = Math.round(prior[side] / top * 100);
      return '<div class="rs-side' + (side === ranked[0] ? ' rs-win' : '') + '" style="--win-delay:' + Math.round(span * 0.78) + 'ms">' +
        '<div class="rs-dots">' + dots[side] + '</div>' +
        '<div class="rs-barwrap"><div class="rs-pbar" style="height:' + height + '%;' + delay(span * 0.04) + '"></div></div>' +
        '<div class="rs-p">P = ' + prior[side].toFixed(2) + '</div><div class="rs-sname">' + side + '</div>' +
        '<div class="rs-count rs-in" style="' + delay(span * 0.72) + '">' + counts[side] + ' drawn</div></div>';
    }).join('');
    return '<div class="rs-note">a prior over the four sides, narrower between the fingers is likelier · ' + r.samples.length + ' samples drawn' + '</div>' +
      '<div class="rs-sides">' + bars + '</div>' +
      '<div class="rs-ranked rs-in" style="' + delay(span * 0.8) + '">most likely first: ' + ranked.map(esc).join(' › ') + '</div>';
  }

  // %% playing a resolution on the stage
  let latest = { backends: [], resolutions: [] };
  let presentation = DEFAULT_PRESENTATION;
  const played = {};          // resolution id -> how many of its parts have been played
  const queue = [];           // resolution ids waiting to be played
  let current = null;         // the resolution id being played
  let timers = [];
  function later(fn, ms) { timers.push(setTimeout(fn, ms)); }

  // the stage covers the column beside the one this panel sits in, from its top to its
  // bottom, so the 3D scene above this panel stays in view
  function placeStage() {
    const column = (root.parentElement || root).getBoundingClientRect();
    const left = column.right + STAGE_GAP;
    stage.style.left = left + 'px'; stage.style.top = column.top + 'px';
    stage.style.width = Math.max(0, window.innerWidth - left) + 'px';
    stage.style.height = column.height + 'px';
  }
  function resolutionById(id) { return latest.resolutions.find(function (r) { return r.id === id; }); }

  function openStage(resolution) {
    placeStage();
    renderBackends(latest.backends);
    titleEl.textContent = resolution.title;
    renderLines(underEl, resolution.underspecified, 'under', {});
    renderLines(resolvedEl, resolution.resolved, 'resolved', {});
    questionEl.innerHTML = '<span class="rs-qhint">every open part is a statement, answered by the first backend that can</span>';
    footEl.innerHTML = '';
    progressEl.textContent = 'the plan as stated';
    cardEl.className = 'rs-card';
    stage.classList.add('rs-open');
    setStatus('resolving…', 'rs-busy');
  }

  function playResolution(id) {
    current = id;
    played[id] = 0;
    const resolution = resolutionById(id);
    openStage(resolution);
    renderCompact(resolution, 0);
    later(nextPart, presentation.beforeMilliseconds);
  }

  function nextPart() {
    const resolution = resolutionById(current);
    const index = played[current];
    if (index < resolution.parts.length) {
      playPart(resolution, index);
      played[current] = index + 1;
      later(nextPart, presentation.partMilliseconds);
      return;
    }
    if (!resolution.done) { later(nextPart, 300); return; }
    finishResolution(resolution);
  }

  function playPart(resolution, index) {
    const part = resolution.parts[index];
    const f = faculty(part.faculty);
    const P = presentation.partMilliseconds;
    progressEl.textContent = 'part ' + (index + 1) + ' · ' + part.slot;
    const answered = answeredUpTo(resolution, index);
    renderLines(underEl, resolution.underspecified, 'under', answered);
    // the part lights up where the plan states it
    const spot = underEl.querySelectorAll('[data-slot="' + cssEscape(part.slotId) + '"], [data-mark="' + cssEscape(part.slotId) + '"]');
    spot.forEach(function (el) { el.classList.add('rs-asking', f.css); });
    questionEl.innerHTML = '<div class="rs-q ' + f.css + '"><b>' + esc(part.slot) + '?</b><span>' + esc(part.statement) + '</span></div>';
    Object.keys(backendEls).forEach(function (name) { backendEls[name].el.classList.remove('rs-active', 'rs-dim'); });
    // the statement flies to the backend that declares it can answer it
    later(function () {
      Object.keys(backendEls).forEach(function (name) {
        backendEls[name].el.classList.add(name === part.faculty ? 'rs-active' : 'rs-dim');
      });
      const target = backendEls[part.faculty];
      if (spot.length && target) fly(spot[0], target.el, part.slot, f.css, P * 0.12);
    }, P * 0.08);
    // the backend reasons
    later(function () {
      const target = backendEls[part.faculty];
      if (target) { target.answered += 1; target.count.textContent = target.answered; }
      const span = P * 0.56;
      cardEl.innerHTML =
        '<div class="rs-cardhead ' + f.css + '"><span class="rs-icon">' + f.icon + '</span><b>' + esc(part.backend) + '</b>' +
        '<span class="rs-cardslot">' + esc(part.slot) + ' · ' + part.milliseconds + ' ms</span></div>' +
        '<div class="rs-cardbody">' + reasoningHtml(part, span) + '</div>' +
        '<div class="rs-cardfoot rs-in" style="' + delay(span * 0.86) + '">answer <span class="rs-ans ' + f.css + '">' +
        (part.answers.length ? esc(part.answers[0]) : 'nothing') + '</span>' +
        (part.answers.length > 1 ? '<span class="rs-alts">then ' + part.answers.slice(1).map(esc).join(', ') + '</span>' : '') + '</div>';
      cardEl.className = 'rs-card rs-show ' + f.css;
      bus.emit('entity:highlight', { ids: part.highlight || [] });
      if ((part.frame || []).length) bus.emit('scene:focus', { ids: part.frame, milliseconds: P * 0.25 });
    }, P * 0.18);
    // the answer goes into the resolved plan
    later(function () {
      cardEl.className = 'rs-card rs-hide ' + f.css;
      const filled = answeredUpTo(resolution, index + 1);
      renderLines(underEl, resolution.underspecified, 'under', filled);
      renderLines(resolvedEl, resolution.resolved, 'resolved', filled);
      resolvedEl.querySelectorAll('[data-mark="' + cssEscape(part.slotId) + '"]').forEach(function (el) {
        el.classList.add('rs-pop');
      });
      renderCompact(resolution, index + 1);
    }, P * 0.82);
  }

  function finishResolution(resolution) {
    const complete = resolution.executable;
    progressEl.textContent = complete ? 'every open part answered' : 'a part has no answer';
    Object.keys(backendEls).forEach(function (name) { backendEls[name].el.classList.remove('rs-active', 'rs-dim'); });
    questionEl.innerHTML = '';
    footEl.innerHTML = complete
      ? '<span class="rs-done">✓ resolved before execution</span>'
      : '<span class="rs-fail">✗ cannot be carried out: a part has no answer</span>';
    setStatus(complete ? 'resolved ✓' : 'unresolved ✗', complete ? 'rs-good' : 'rs-badstatus');
    renderCompact(resolution, resolution.parts.length);
    later(function () {
      stage.classList.remove('rs-open');
      bus.emit('entity:highlight', { ids: [] });
      current = null;
      playQueued();
    }, presentation.afterMilliseconds);
  }

  function fly(fromEl, toEl, text, css, ms) {
    const s = stage.getBoundingClientRect(), a = fromEl.getBoundingClientRect(), b = toEl.getBoundingClientRect();
    tokenEl.className = 'rs-token ' + css;
    tokenEl.textContent = text;
    tokenEl.style.transition = 'none';
    tokenEl.style.opacity = '1';
    tokenEl.style.transform = 'translate(' + (a.left - s.left + a.width / 2) + 'px,' + (a.top - s.top + a.height / 2) + 'px) translate(-50%,-50%)';
    void tokenEl.offsetWidth;
    tokenEl.style.transition = 'transform ' + ms + 'ms cubic-bezier(.5,0,.2,1), opacity ' + (ms * 0.4) + 'ms ease ' + (ms * 0.7) + 'ms';
    tokenEl.style.transform = 'translate(' + (b.left - s.left + b.width / 2) + 'px,' + (b.top - s.top + b.height / 2) + 'px) translate(-50%,-50%) scale(.85)';
    tokenEl.style.opacity = '0';
  }
  function cssEscape(text) { return String(text).replace(/["\\]/g, '\\$&'); }

  function playQueued() {
    if (current !== null || !queue.length) return;
    playResolution(queue.shift());
  }

  // %% the latest resolution, kept under the scene
  function setStatus(text, css) { statusEl.textContent = text; statusEl.className = 'rs-status ' + (css || ''); }
  function renderCompact(resolution, count) {
    const answered = answeredUpTo(resolution, count);
    const tally = {};
    resolution.parts.slice(0, count).forEach(function (p) { tally[p.faculty] = (tally[p.faculty] || 0) + 1; });
    const chips = latest.backends.map(function (b) {
      const f = faculty(b.faculty);
      return '<span class="rs-chip ' + f.css + (tally[b.faculty] ? ' rs-on' : '') + '"><i></i>' + esc(b.name.replace(/Backend$/, '')) +
        ' <b>' + (tally[b.faculty] || 0) + '</b></span>';
    }).join('');
    const canRun = resolution.done && resolution.executable && count >= resolution.parts.length;
    compactEl.innerHTML =
      '<div class="rs-ctitle">' + esc(resolution.title) + '</div>' +
      '<div class="rs-chips">' + chips + '</div>' +
      '<div class="rs-code rs-mini" id="rs-mini"></div>' +
      '<div class="rs-actions">' +
      '<button class="rs-btn" data-act="replay">▶ Show the resolution</button>' +
      (canRun ? '<button class="rs-btn rs-go" data-act="run">Execute it</button>' : '') +
      '</div>';
    renderLines(compactEl.querySelector('#rs-mini'), resolution.resolved, 'resolved', answered);
    compactEl.querySelector('[data-act="replay"]').onclick = function () {
      if (current !== null) return;
      playResolution(resolution.id);
    };
    const run = compactEl.querySelector('[data-act="run"]');
    if (run) run.onclick = function () {
      bus.emit('eql:run', {
        code: 'robot.do(backends.resolutions[' + resolution.id + '].plan, ' + JSON.stringify(resolution.title) + ')',
        text: 'Carry out: ' + resolution.title,
      });
    };
  }

  // %% following the bridge
  function take(published) {
    if (!published || !(published.backends || []).length) return;
    root.classList.remove('idle');
    latest = { backends: published.backends, resolutions: published.resolutions || [] };
    presentation = published.presentation || DEFAULT_PRESENTATION;
    const now = Date.now() / 1000;
    latest.resolutions.forEach(function (resolution) {
      if (resolution.id in played || queue.indexOf(resolution.id) >= 0 || resolution.id === current) return;
      if (!resolution.parts.length && !resolution.done) return;
      const answeredAt = resolution.parts.length ? resolution.parts[resolution.parts.length - 1].answeredAt : now;
      if (now - answeredAt > FRESH_SECONDS) {
        played[resolution.id] = resolution.parts.length;
        if (current === null) { renderCompact(resolution, resolution.parts.length); setStatus(resolution.executable ? 'resolved ✓' : 'unresolved ✗', resolution.executable ? 'rs-good' : 'rs-badstatus'); }
        return;
      }
      queue.push(resolution.id);
    });
    playQueued();
  }

  let liveUrl = '';
  let timer = null;
  root.classList.add('idle');
  function poll() {
    if (!liveUrl) return;
    fetch(liveUrl + '/slot_answers').then(function (r) { return r.json(); })
      .then(take).catch(function () {});
  }
  bus.on('live:changed', function (live) {
    liveUrl = live && live.on ? live.url : '';
    if (timer) { clearInterval(timer); timer = null; }
    if (liveUrl) { timer = setInterval(poll, POLL_MILLISECONDS); poll(); }
  });
  window.addEventListener('resize', function () { if (current !== null) placeStage(); });

  return {
    destroy: function () {
      if (timer) clearInterval(timer);
      timers.forEach(clearTimeout);
      stage.remove();
    },
  };
});
