## `claude/paper-figures-episodes-bkfozu` — PR #297

Plan item `icra-evidence` / `paper-figures-from-episodes`, track `release`,
kicked off in `auto` mode. Based on #278 (`episodes-queried-by-eql`), which is
open and not a draft; the full plan and its reasoning are in the plan's
`roadmap.md` under "as planned 2026-09-08".

### Plan

One script regenerates every paper table from the recorded episodes. New package
`experiments/src/experiments/paper/`:

- `figure.py` — `FigureName` (a member per figure, the file stem it is written
  under), `PaperFigure` (name, caption, abstract `rows(trials)`, concrete
  `render`/`write`), `FigureSet` built by a classmethod like #295's `QuestionSet`.
- the six figures, each a `PaperFigure` subclass with its own `ExperimentResult`
  row class: trial outcome by condition, failure type by condition, failure
  prediction (precision/recall), query latency by backend, query determinism,
  trial outcome by execution type. Every rate carries a `ConfidenceInterval`.
- `LongTermMemory` gains a "recall every trial" question (an EQL select with no
  where clause, which #278's own tests show translates).
- `experiments/scripts/generate_paper_figures.py` — the one script; writes each
  `.typ` file plus its JSON manifest via `ExperimentsTable.write_manifest`.
- `generate_orm.py` ignores the new package: a figure is computed, not recorded.

Read with EQL, aggregate in Python — the figures traverse recalled objects
rather than asking the query language to join across association tables.

### Done

- Branch re-cut from #278 (it had descended from `integration`), pushed, draft
  PR #297 opened.
- `plan.yaml` updated (branch, PR, session, `in_progress`, stale blocker
  cleared) and the roadmap section appended.

### Next

1. Tests first: `test_paper_figures.py` over in-memory recorded trials.
2. The `paper` package until they pass.
3. `test_paper_figures_from_the_database.py` (CI-only) and the script.
4. `format_docstrings.py`, update the PR description, keep it a draft.

### Known

- `plan_item_bootstrap.py`'s `open`/`record` mis-indent fields into an item
  whose `title` is a folded block scalar, producing invalid YAML — worked
  around by editing `plan.yaml` by hand. Reported to the developer.
- The accuracy-per-bucket and resource-cost tables are not in scope: the
  columns they read do not exist on an episode row yet.

