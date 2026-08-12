# D-core-single-class — PR progress

**Branch cut, draft PR #159 open, bootstrap commit only — no engine code yet.**
This note replaces the 2026-08-03 plan that sat here unexecuted; that plan is
re-verified below, with the five premises that had gone stale corrected.

- PR: #159 (draft, base `D-core-expert`)
- Kickoff session: https://claude.ai/code/session_01QjvFKyqAynJmr18FPZgVZr
- Full narrative: `plans/rdr-refactor/roadmap.md` §20

## Done

1. Branch `D-core-single-class` cut from `origin/D-core-expert` (`e52d74b4`),
   bootstrap commit `d5b94c5a` pushed.
2. Draft PR #159 opened against `D-core-expert`.
3. `plan.yaml` updated by hand (`status: in_progress`, `branch`,
   `pull_request_number: 159`, `session`, rewritten `notes`) and roadmap §20
   appended. **`plan_item_bootstrap.py open` could not do this** — it writes
   patched item fields at four-space indent inside a two-space item, producing
   unparseable YAML, and still reports `{"status": "success"}`. Recorded in §20;
   not fixed here.

## Next

1. **Local baseline on `D-core-expert` before any code.** CI has queued nothing
   on that branch across six pushes, so the baseline cannot come from CI. Use
   §18/§19's recipe: `/usr/bin/python3.12` venv (the default `python3` is 3.11
   and fails in `class_diagram.py` on `make_dataclass(module=…)`), `krrood`'s
   requirements, editable `random_events`/`probabilistic_model`, `casadi`, and
   `--confcutdir=test/krrood_test`. Expect `test_eql_rdr` **150 passed / 0
   failed**. Record the collected test ids, not just the count.
2. **Tests first.** Port six files from mega-branch `e650d968`:
   `test_single_class_rdr.py` (1079), `test_condition_resolver_integration.py`
   (831), `test_ask_for_rule.py` (518), `test_backward_inference_integration.py`
   (448), `test_fit_convergence.py` (426, rewritten around
   `RDRDidNotConvergeError`), `test_corner_case_population.py` (217). Add
   `expert_doubles.py` for the stubs/scripted experts currently duplicated
   across three of them; hoist case builders onto the existing `animal.py`;
   reuse `progress.py`'s `SpyProgressReporter`.
3. **`single_class.py`** (554 lines) with its #68 threads applied — see below.
4. **`rdr/exceptions.py`**: `RDRDidNotConvergeError` + the expert-required
   exception, following the file's existing `DataclassException` shape.
5. PR body answering every "discuss with me" thread this slice touches; record
   the handoff on tracking issue #94.

## What this slice consumes from #98 (do not rebuild)

`ConditionResolver.resolve(context, target_knowledge, current_knowledge)`, the
segregated `ExpertInterface`, `NullProgressReporter`/`ProgressDescription.FITTING`,
and `ModelSaver`/`NullModelSaver`/`FileModelSaver`. All landed in `28a89ff4`.

## Engine changes, restated against current APIs

- `classify()` → `Any` returning `...`; fix the `-> Optional[Any]` signature
  defect roadmap §19 handed to this item.
- Delete `RDRConvergenceWarning` and `max_passes`; `_run_convergence` raises
  `RDRDidNotConvergeError` carrying **clashing cases + pass count only** — there
  is no save path any more — after calling `model_saver.save(self)`.
- Replace `ValueError("Expert must be supplied to fit_case")` with a typed
  `DataclassException`.
- Split `fit_case` into three named methods; build `CaseContext` once and pass
  it to the expert *and* the resolver.
- `save_path: Optional[str]` → `model_saver: ModelSaver = field(default_factory=NullModelSaver)`
  and `progress_reporter: ProgressReporter = field(default_factory=NullProgressReporter)`
  (`default_factory` — no mutable defaults). Deletes the
  `expert.interface.on_save = lambda: …` reach-through and every `is not None` guard.
- `prior_errors` is now `List[DataclassException]` — pass `[e]`.
- `_FITTING_DESCRIPTION` → `ProgressDescription.FITTING`.
- Inline `UnderspecifiedMatch` / `SelfReferentialInsertionError` imports to
  module top; `from_underspecified(template: Match)`; keep `_observe`/`_trace`;
  keep `render_tree() -> str` returning `""`; docstring sweep.
- Probe whether the `SelfReferentialInsertionError` retry loop is reachable
  (HINT-mode test). **If it cannot be provoked, delete it.**

## Standing review lenses for this plan (apply while writing tests)

- **Never compare symbolic expressions with `==`** — `__eq__` builds a truthy
  `Comparator`, so nine assertions asserted nothing (§16). Compare `_id_`.
- **Do not assert what a declaration, a sibling test, or the language already
  guarantees** — five such tests were removed under review on #98 (§18, §19).
- **Mutation-check anything load-bearing**: change the production value and
  confirm exactly the intended test fails.
- `scripts/format_docstrings.py` has five recorded deviations here and now
  mis-parses `...` as a sentence end (§19) — check its output, revert churn.
- A sweep dirties `query_graph.pdf` / `drawer_explanation.pdf` (tracked *and*
  gitignored) — revert before committing.

## Standing constraints

- Do **not** cascade the stack first; the missing commits are in
  `code_generation/` while this slice touches only `rdr/` and `test_eql_rdr/`.
- Do **not** subscribe to PR #159 and arm no timed check-ins (personal notes).
- Re-draft the PR after every push.
