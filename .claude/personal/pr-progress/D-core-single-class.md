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

1. ~~**Local baseline on `D-core-expert` before any code.**~~ **Done — and the
   expected count in this note was stale.** §18/§19's recipe rebuilt cleanly
   (`/usr/bin/python3.12` venv, `krrood`'s requirements, editable
   `random_events`/`probabilistic_model`, `casadi`, `--confcutdir=test/krrood_test`,
   `PYTHONPATH=<worktree>/krrood/src`). `test_eql_rdr` on `D-core-expert`
   `82eb69fb` is **164 passed / 0 failed in 2.51s**, not the 150 this note
   predicted: 150 was `e52d74b4`, before §21's cascade merged `D-core-support`
   (+14). §21 already records 164; this note was written before it. Collected ids
   saved to `scratchpad/baseline_expert_ids.txt`, 164 across 15 files —
   `test_aid` 3, `test_backward_inference` 18, `test_branch_semantics` 12,
   `test_conclusion_domain` 18, `test_conclusion_validator` 15,
   `test_condition_resolver` 16, `test_corner_case` 9, `test_exceptions` 12,
   `test_expert` 11, `test_observer` 12, `test_progress` 2,
   `test_rule_tree_growth` 10, `test_serialization` 10,
   `test_underspecified_match` 9, `test_zoo_loader` 7.
   Note `-o addopts=` is required: the repo-root `pytest.ini` sets `-sv`, which
   suppresses the `::`-form ids `--collect-only` otherwise prints.
2. ~~**Tests first.**~~ **Done.** All six ported, plus `expert_doubles.py` and
   `make_mammal`/`make_bird` hoisted onto `animal.py`. Two of the six shrank a lot
   rather than being copied, because #98/#67 had already landed the unit coverage
   they duplicated — recorded so a reviewer does not read the line count as a
   dropped port:
   - `test_condition_resolver_integration.py`: dropped `TestResolvedCondition`
     (frozen/equality = what `@dataclass(frozen=True)` already guarantees),
     `TestConditionResolverABC` (ABC's own semantics) and the live
     `TestCornerCaseKnowledgeResolver`/`TestChainConditionResolver` blocks, all
     covered by the 16 tests in `test_condition_resolver.py`. Kept what only the
     live engine shows.
   - `test_backward_inference_integration.py`: `test_backward_inference.py`'s 18
     tests already cover traversal, `is_satisfiable`, guard flattening and index
     caching. Kept the RDR-level wrapper and invalidation only.
3. ~~**`single_class.py`**~~ **Done**, every listed thread applied. Two decisions
   the plan left to the probe:
   - The `SelfReferentialInsertionError` retry loop **is reachable** — probe in
     `scratchpad/probe_self_ref.py` provokes it through `fit_case` with an expert
     that answers with `context.trace.firing_anchor`. So it is **kept**, not
     deleted, and pinned by two tests (HINT re-asks, AUTOMATIC surfaces).
   - That probe found a **live defect**: `ExpertInterface._render_header` reads
     `error.answer_name` on every entry of `initial_errors`, so passing the raw
     `SelfReferentialInsertionError` (an EQL-core exception) crashed the re-prompt.
     Fixed on this side rather than in `interface.py` — `initial_errors` is
     documented as errors that each name their own request, so passing one that
     does not was the bug. `_insert_rule` now raises `ConditionsNotInsertable`
     (carrying `answer_name=AnswerName.CONDITIONS` and the anchor), chained from
     the original.
   - `sufficient_conditions_for` is the RDR method name, not the mega-branch's
     `what_do_we_know_about`: `main` renamed the module-level function to
     `get_conclusion_sufficient_conditions_from_a_rule_tree` (§21), and this method
     is new here, so there is no rename — just not reintroducing the retired name.
4. ~~**`rdr/exceptions.py`**~~ **Done**: a `# %% fitting` section with
   `ExpertRequired`, `RDRDidNotConvergeError` (clashing cases + pass count) and
   `ConditionsNotInsertable`.
5. **Left to do**: finish the mutation checks, run `scripts/format_docstrings.py`
   and revert its known deviations, check the `query_graph.pdf` /
   `drawer_explanation.pdf` churn, commit, push, re-draft #159, write the PR body
   answering the "discuss with me" threads, and record the handoff on #94.

## Local result so far

`test_eql_rdr` **230 passed / 0 failed**, against the 164-passing baseline — 66 new
tests, no baseline test changed. One convergence-loop decision worth review: the
pending recompute skips cases whose target is `...`, so `fit(cases, [...] * n)`
stays single-pass rather than never converging.

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
