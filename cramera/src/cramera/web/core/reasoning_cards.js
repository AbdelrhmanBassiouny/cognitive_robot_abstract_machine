/* ============================================================================
 * core/reasoning_cards.js — how a backend reasoned to an answer, drawn.
 *
 * A backend answering a statement reports its reasoning as JSON whose kind names
 * the faculty it answers from: the camera's view and how well each outline fit
 * (perception), the collision boxes it tested (working memory), the rules it walked
 * (rules) or the distribution it sampled (probabilistic). Each is drawn as markup
 * whose parts fade in over a given span of milliseconds. Pure string building, so
 * it is unit-testable without a DOM.
 * ==========================================================================*/
(function () {
  'use strict';

  // what each backend reads, by the faculty it answers from
  const FACULTIES = {
    'perception': { css: 'f-perception', icon: '◉', note: 'what the camera saw' },
    'working memory': { css: 'f-memory', icon: '◈', note: 'the twin, read off its geometry' },
    'rules': { css: 'f-rules', icon: '⋔', note: 'ripple-down rules about the board' },
    'probabilistic': { css: 'f-probabilistic', icon: '∿', note: 'a model of grasping, sampled' },
  };
  const SIDE_ORDER = ['FRONT', 'BACK', 'RIGHT', 'LEFT'];

  function esc(text) {
    return String(text).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }
  function faculty(name) { return FACULTIES[name] || FACULTIES['working memory']; }

  // %% each backend's reasoning, drawn
  // part = {reasoning, answers, evidence}: anything shaped like a resolved part
  function reasoningHtml(part, span) {
    const r = part.reasoning || {};
    if (r.kind === 'perception') return perceptionHtml(r, span);
    if (r.kind === 'working memory') return memoryHtml(r, span);
    if (r.kind === 'rules') return rulesHtml(r, span);
    if (r.kind === 'probabilistic') return samplingHtml(r, span, part.answers);
    return '<div class="rs-lines">' + (part.evidence || []).map(esc).join('<br>') + '</div>';
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

  window.ReasoningCards = { faculty: faculty, html: reasoningHtml, esc: esc, delay: delay };
})();
