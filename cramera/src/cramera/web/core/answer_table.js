/* ============================================================================
 * core/answer_table.js — an EQL answer as one table.
 *
 * Answer rows are objects whose keys depend on what the query asked for: a set_of()
 * names its own columns, an entity query answers with a named thing and its fields.
 * Both read far better as a table with stable columns than as a run of chips, so this
 * settles the columns once and classifies every value by what it is, leaving only the
 * markup and the colours to the panel.
 * ==========================================================================*/
(function () {
  'use strict';

  const ENTITY_NAME = '__entity__';
  const ENTITY_TYPE = '__type__';
  const NAME_COLUMN = 'name';
  const EMPTY_CELL = '—';

  // the columns of an entity answer are its name followed by its own fields; of any
  // other answer, every key any row carries, in the order the rows introduce them
  function columnsOf(rows) {
    const columns = [];
    rows.forEach(function (row) {
      if (row[ENTITY_NAME] !== undefined && columns.indexOf(NAME_COLUMN) < 0) {
        columns.push(NAME_COLUMN);
      }
      Object.keys(row).forEach(function (key) {
        if (key === ENTITY_NAME || key === ENTITY_TYPE) return;
        if (columns.indexOf(key) < 0) columns.push(key);
      });
    });
    return columns;
  }

  function cellOf(row, column) {
    const named = row[ENTITY_NAME];
    if (column === NAME_COLUMN && named !== undefined) {
      return { text: String(named), kind: 'name' };
    }
    return valueCell(row[column]);
  }

  function valueCell(value) {
    if (value === null || value === undefined || value === '') {
      return { text: EMPTY_CELL, kind: 'empty' };
    }
    if (typeof value === 'boolean') return { text: String(value), kind: String(value) };
    if (typeof value === 'number') return { text: String(value), kind: 'number' };
    return { text: String(value), kind: 'text' };
  }

  function of(rows) {
    const all = rows || [];
    const columns = columnsOf(all);
    return {
      columns: columns,
      rows: all.map(function (row) {
        return {
          type: row[ENTITY_TYPE] === undefined ? null : String(row[ENTITY_TYPE]),
          cells: columns.map(function (column) { return cellOf(row, column); }),
        };
      }),
    };
  }

  window.AnswerTable = { of: of };
})();
