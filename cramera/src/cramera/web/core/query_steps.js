/* ============================================================================
 * core/query_steps.js — the queries a running robot asked, as markup.
 *
 * Each step the bridge publishes (GET /query_steps) is one query the robot asked:
 * the code that writes it, the question it asks in English, what answers it and its
 * answers. These helpers build the markup the queries panel shows for a step and
 * pick which step to show. Pure string building, so it is unit-testable without a
 * DOM.
 * ==========================================================================*/
(function () {
  'use strict';

  // the query language's own words, picked out in the code a query is written in
  const QUERY_WORDS = /\b(an|a|the|entity|variable|set_of|where|exists|for_all|not_|and_|or_|ordered_by|distinct|from_|evaluate|tolist|first|inference|deduced_variable|alternative|add)\b(?=\s*\()/g;
  const PYTHON_WORDS = /\b(def|return|for|in|if|else|elif|with|yield|from|import|None|True|False|not|and|or|lambda|self)\b/g;

  function esc(text) {
    return String(text).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }

  // one line of Python, its strings and comments kept whole and the words that matter
  // coloured
  function lineHtml(text) {
    const parts = String(text).split(/("[^"]*"|'[^']*'|#.*$)/);
    return parts.map(function (part, index) {
      if (index % 2 === 1) {
        return '<span class="qs-' + (part[0] === '#' ? 'comment' : 'string') + '">' + esc(part) + '</span>';
      }
      return esc(part)
        .replace(QUERY_WORDS, '<span class="qs-eql">$1</span>')
        .replace(PYTHON_WORDS, '<span class="qs-kw">$1</span>');
    }).join('');
  }

  // code = {file, function, firstLine, lines, focus: [first, last]}
  function codeHtml(code) {
    if (!code) return '<div class="qs-nocode">the code that asked this is not in the repository</div>';
    const rows = code.lines.map(function (text, index) {
      const number = code.firstLine + index;
      const focused = number >= code.focus[0] && number <= code.focus[1];
      return '<div class="qs-codeline' + (focused ? ' qs-focus' : '') + '" style="--i:' + index + '">' +
        '<span class="qs-ln">' + number + '</span><span class="qs-src">' + (lineHtml(text) || '&nbsp;') + '</span></div>';
    }).join('');
    return '<div class="qs-file"><span class="qs-path">' + esc(code.file) + '</span>' +
      '<span class="qs-fn">' + esc(code.function) + '()</span></div>' +
      '<div class="qs-code">' + rows + '</div>';
  }

  // the step the panel shows: the one picked to look back at, else the one the robot
  // is held at
  function shown(published, picked) {
    const steps = (published && published.steps) || [];
    const number = picked !== null && picked !== undefined ? picked : published && published.held;
    if (number === null || number === undefined) return null;
    return steps.find(function (step) { return step.number === number; }) || null;
  }

  // the steps whose answering asked the given one, outermost first
  function askers(steps, step) {
    const byNumber = {};
    steps.forEach(function (s) { byNumber[s.number] = s; });
    const chain = [];
    let asker = step && byNumber[step.asker];
    while (asker) {
      chain.unshift(asker);
      asker = byNumber[asker.asker];
    }
    return chain;
  }

  // the question a step asks, as plain words
  function questionText(step) {
    return (step.question && step.question.text) || ('a query answered by ' + step.backend);
  }

  // the question a step asks, coloured by krrood's verbalizer where it was worded
  function questionHtml(step) {
    return (step.question && step.question.html) || esc(questionText(step));
  }

  // the answers of a step, each fading in after the one before it over the span
  function answersHtml(step, span) {
    if (step.moment !== 'answered') {
      return '<div class="qs-waiting"><i></i><i></i><i></i><span>being answered…</span></div>';
    }
    if (!step.answers.length) return '<div class="qs-none qs-in">no answer</div>';
    const shownAnswers = step.answers.slice(0, 12);
    const each = span / Math.max(1, shownAnswers.length);
    return '<div class="qs-answers">' + shownAnswers.map(function (answer, index) {
      return '<span class="qs-answer qs-in' + (index === 0 ? ' qs-first' : '') + '" style="animation-delay:' +
        Math.round(index * each) + 'ms">' + esc(answer) + '</span>';
    }).join('') + (step.answers.length > shownAnswers.length
      ? '<span class="qs-more">+' + (step.answers.length - shownAnswers.length) + ' more</span>' : '') + '</div>';
  }

  window.QuerySteps = {
    codeHtml: codeHtml,
    lineHtml: lineHtml,
    shown: shown,
    askers: askers,
    questionText: questionText,
    questionHtml: questionHtml,
    answersHtml: answersHtml,
    esc: esc,
  };
})();
