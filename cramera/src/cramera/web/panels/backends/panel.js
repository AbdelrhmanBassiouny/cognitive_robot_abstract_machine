/* ============================================================================
 * panels/backends/panel.js — who answered what the running plan left open.
 *
 * A plan leaves parts open (which piece, which side to grasp it from, which hole)
 * and each is answered, when its step comes, by whichever backend declares it can:
 * perception, working memory, rules or a probabilistic model. The demo publishes
 * every answer to the bridge (GET /slot_answers); this panel plays them one at a
 * time: the open part is stated, flies to the backend that answers it, and the
 * backend's lane shows what it answered and what it read to answer it.
 *
 * The panel stays hidden until a running demo has published an answer.
 *
 * Bus events:
 *   listens  live:changed {on, url}     poll the bridge while a demo is attached
 * ==========================================================================*/
Panels.define('backends', function (root, bus) {
  // the lanes, in the order the backends are preferred; their colours are used for
  // the backends alone
  const LANES = [
    { faculty: 'perception', title: 'Perception', icon: '◉', note: 'what the camera saw' },
    { faculty: 'working memory', title: 'Working memory', icon: '◈', note: 'the twin, read off its geometry' },
    { faculty: 'rules', title: 'Rules · RDR', icon: '⋔', note: 'ripple-down rules about the board' },
    { faculty: 'probabilistic', title: 'Probabilistic', icon: '∿', note: 'a model of grasping, sampled' },
  ];
  // ?pace=0.2 plays every animation five times slower, to film a demo that runs
  // slower than the clock and is sped up afterwards
  const PACE = Number(new URLSearchParams(window.location.search).get('pace')) || 1;
  const POLL_MILLISECONDS = 400;
  // how long one answer is shown before the next is played; a long queue plays faster
  const PLAY_MILLISECONDS = 2200 / PACE;
  const FASTEST_PLAY_MILLISECONDS = 700 / PACE;
  const FLIGHT_MILLISECONDS = 650 / PACE;
  root.style.setProperty('--bk-pace', String(1 / PACE));
  const TRAIL_LENGTH = 9;

  root.innerHTML =
    '<div class="panel-head bk-head">' +
    '  <h2>Who answers the open parts of the plan</h2>' +
    '  <span class="bk-step" id="bk-step"></span>' +
    '</div>' +
    '<div class="bk-stage" id="bk-stage">' +
    '  <div class="bk-question" id="bk-question">' +
    '    <div class="bk-slot" id="bk-slot"></div>' +
    '    <div class="bk-statement" id="bk-statement"></div>' +
    '  </div>' +
    '  <div class="bk-lanes" id="bk-lanes"></div>' +
    '  <div class="bk-token" id="bk-token"></div>' +
    '</div>' +
    '<div class="bk-trail" id="bk-trail"></div>';

  const stepEl = root.querySelector('#bk-step');
  const stageEl = root.querySelector('#bk-stage');
  const questionEl = root.querySelector('#bk-question');
  const slotEl = root.querySelector('#bk-slot');
  const statementEl = root.querySelector('#bk-statement');
  const lanesEl = root.querySelector('#bk-lanes');
  const tokenEl = root.querySelector('#bk-token');
  const trailEl = root.querySelector('#bk-trail');

  const laneEls = {};
  LANES.forEach(function (lane, index) {
    const el = document.createElement('div');
    el.className = 'bk-lane bk-lane-' + index;
    el.innerHTML =
      '<div class="bk-lane-head"><span class="bk-icon">' + lane.icon + '</span>' +
      '<div><div class="bk-lane-title">' + lane.title + '</div>' +
      '<div class="bk-lane-note">' + lane.note + '</div></div>' +
      '<span class="bk-count">0</span></div>' +
      '<div class="bk-lane-body"><div class="bk-idle">waiting…</div></div>';
    lanesEl.appendChild(el);
    laneEls[lane.faculty] = { el: el, body: el.querySelector('.bk-lane-body'),
                              count: el.querySelector('.bk-count'), index: index, answered: 0 };
  });

  function escape(text) {
    return String(text).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }

  // %% playing one answer
  function play(answer) {
    const lane = laneEls[answer.faculty];
    if (!lane) return;
    root.classList.remove('idle');
    stepEl.textContent = answer.step;
    slotEl.textContent = answer.slot + '?';
    statementEl.textContent = answer.statement;
    questionEl.className = 'bk-question bk-asking bk-q-' + lane.index;
    // the question flies from where it is stated to the lane of the backend answering it
    const stage = stageEl.getBoundingClientRect();
    const from = questionEl.getBoundingClientRect();
    const to = lane.el.getBoundingClientRect();
    tokenEl.className = 'bk-token bk-t-' + lane.index;
    tokenEl.textContent = answer.slot;
    tokenEl.style.transition = 'none';
    tokenEl.style.opacity = '1';
    tokenEl.style.transform = 'translate(' + (from.left - stage.left + from.width / 2) + 'px,' +
      (from.top - stage.top + from.height / 2) + 'px) translate(-50%,-50%) scale(1)';
    void tokenEl.offsetWidth;
    tokenEl.style.transition = 'transform ' + FLIGHT_MILLISECONDS + 'ms cubic-bezier(.5,0,.2,1), opacity ' + 250 / PACE + 'ms ease ' + (FLIGHT_MILLISECONDS - 100 / PACE) + 'ms';
    tokenEl.style.transform = 'translate(' + (to.left - stage.left + to.width / 2) + 'px,' +
      (to.top - stage.top + 28) + 'px) translate(-50%,-50%) scale(.8)';
    tokenEl.style.opacity = '0';
    Object.keys(laneEls).forEach(function (faculty) {
      laneEls[faculty].el.classList.toggle('bk-active', faculty === answer.faculty);
    });
    setTimeout(function () { answerInLane(lane, answer); }, FLIGHT_MILLISECONDS - 120 / PACE);
    addToTrail(answer, lane);
  }

  function answerInLane(lane, answer) {
    lane.answered += 1;
    lane.count.textContent = lane.answered;
    lane.el.classList.remove('bk-pulse'); void lane.el.offsetWidth; lane.el.classList.add('bk-pulse');
    const answers = answer.answers.length
      ? answer.answers.map(function (a, i) {
          return '<span class="bk-answer' + (i === 0 ? ' bk-first' : '') + '" style="animation-delay:' + (120 + i * 90) / PACE + 'ms">' + escape(a) + '</span>';
        }).join('')
      : '<span class="bk-answer bk-none">nothing</span>';
    const evidence = answer.evidence.map(function (line, i) {
      const kind = /^▶|^✓/.test(line) ? ' bk-yes' : (/^✗/.test(line) ? ' bk-no' : '');
      return '<div class="bk-evidence' + kind + '" style="animation-delay:' + (300 + i * 110) / PACE + 'ms">' + escape(line) + '</div>';
    }).join('');
    lane.body.innerHTML =
      '<div class="bk-card">' +
      '  <div class="bk-card-slot">' + escape(answer.slot) + '<span class="bk-ms">' + answer.milliseconds + ' ms · ' + escape(answer.backend) + '</span></div>' +
      '  <div class="bk-answers">' + answers + '</div>' +
      '  <div class="bk-evidences">' + evidence + '</div>' +
      '</div>';
  }

  function addToTrail(answer, lane) {
    const chip = document.createElement('span');
    chip.className = 'bk-chip bk-c-' + lane.index;
    chip.innerHTML = '<i></i>' + escape(answer.slot) + ' <b>→ ' + escape(answer.faculty) + '</b>';
    trailEl.appendChild(chip);
    while (trailEl.children.length > TRAIL_LENGTH) trailEl.removeChild(trailEl.firstChild);
  }

  // %% the queue of answers still to be played
  const queue = [];
  let played = 0;          // how many of the published answers have been queued
  let playing = null;
  function playNext() {
    playing = null;
    if (!queue.length) return;
    play(queue.shift());
    const wait = Math.max(FASTEST_PLAY_MILLISECONDS, PLAY_MILLISECONDS - queue.length * 250 / PACE);
    playing = setTimeout(playNext, wait);
  }

  function take(published) {
    const answers = (published && published.answers) || [];
    if (answers.length < played) played = 0;          // a new run started over
    answers.slice(played).forEach(function (answer) { queue.push(answer); });
    played = answers.length;
    if (!playing && queue.length) playNext();
  }

  // %% following the bridge
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

  return {
    destroy: function () {
      if (timer) clearInterval(timer);
      if (playing) clearTimeout(playing);
    },
  };
});
