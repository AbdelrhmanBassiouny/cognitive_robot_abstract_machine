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

  // the css of each role a variable plays in a query or a part plays in a statement
  const ROLE_CSS = {
    'sought': 'qs-r-sought', 'ranges over': 'qs-r-ranges', 'given': 'qs-r-given',
    'open': 'qs-r-open', 'being answered': 'qs-r-asking', 'answered': 'qs-r-answered',
  };
  const KIND_CSS = { 'plan being resolved': 'qs-k-plan', 'action': 'qs-k-action', 'motion': 'qs-k-motion' };

  // what a variable holds: its values, else that it is still open, else how far the
  // query looked through its domain
  function heldHtml(variable, answered, most) {
    if (variable.values.length) {
      const shownValues = variable.values.slice(0, most || 8);
      return shownValues.map(function (value) { return '<i>' + esc(value) + '</i>'; }).join('') +
        (variable.values.length > shownValues.length
          ? '<em>+' + (variable.values.length - shownValues.length) + ' more</em>' : '');
    }
    if (variable.role === 'sought') return answered ? '<em>no answer</em>' : '<em class="qs-pending">?</em>';
    if (variable.role === 'being answered') return '<em class="qs-pending">?</em>';
    if (variable.looked_at !== null && variable.looked_at !== undefined) {
      return '<em>' + variable.looked_at + ' looked at</em>';
    }
    return '<em>?</em>';
  }

  // a part of an enclosing statement as a chip: its name and what it holds
  function partHtml(variable) {
    return '<span class="qs-part ' + (ROLE_CSS[variable.role] || '') + '" title="' + esc(variable.role) + '">' +
      '<b>' + esc(variable.name) + '</b>' + heldHtml(variable, true) + '</span>';
  }

  // the variables of a query as rows: what each is to the query, its name and type,
  // and what it holds
  function variablesHtml(step) {
    const answered = step.moment === 'answered';
    return '<div class="qs-vars">' + (step.variables || []).map(function (variable) {
      return '<div class="qs-var ' + (ROLE_CSS[variable.role] || '') + '">' +
        '<span class="qs-role">' + esc(variable.role) + '</span>' +
        '<span class="qs-vname">' + esc(variable.name) +
        (variable.kind ? '<span class="qs-vtype">: ' + esc(variable.kind) + '</span>' : '') + '</span>' +
        '<span class="qs-held">' + heldHtml(variable, answered) + '</span></div>';
    }).join('') + '</div>';
  }

  // the statements and queries a step is asked inside, outermost first, ending in the
  // step itself with its variables
  function stackHtml(steps, step) {
    const enclosing = step.enclosing || [];
    const chain = askers(steps, step);
    let depth = 0;
    const frames = enclosing.map(function (frame) {
      return '<div class="qs-frame ' + (KIND_CSS[frame.kind] || '') + '" style="--d:' + depth++ + '">' +
        '<div class="qs-fhead"><span class="qs-fkind">' + esc(frame.kind) + '</span><b>' + esc(frame.title) + '</b></div>' +
        (frame.statement ? '<div class="qs-fstatement">' + esc(frame.statement) + '</div>' : '') +
        (frame.variables.length ? '<div class="qs-parts">' + frame.variables.map(partHtml).join('') + '</div>' : '') +
        '</div>';
    }).concat(chain.map(function (asker) {
      const sought = (asker.variables || [])[0];
      return '<div class="qs-frame qs-k-query" style="--d:' + depth++ + '" data-step="' + asker.number + '">' +
        '<div class="qs-fhead"><span class="qs-fkind">query #' + (asker.number + 1) + '</span><b>' +
        esc(questionText(asker)) + '</b></div>' +
        (sought ? '<div class="qs-parts">' + partHtml({ name: sought.name, role: 'being answered', values: [] }) + '</div>' : '') +
        '</div>';
    }));
    frames.push('<div class="qs-frame qs-current" style="--d:' + depth + '">' +
      '<div class="qs-fhead"><span class="qs-fkind">this query #' + (step.number + 1) + '</span><b>' +
      esc(questionText(step)) + '</b></div>' + variablesHtml(step) + '</div>');
    return '<div class="qs-stack">' + frames.join('') + '</div>';
  }

  window.QuerySteps = {
    stackHtml: stackHtml,
    variablesHtml: variablesHtml,
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
