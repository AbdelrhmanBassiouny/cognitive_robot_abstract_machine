# D-core-single-class — PR progress

**Status: not started.** No branch cut, no code written. This note is the
approved implementation plan from a `/plan-item-kickoff rdr-refactor
d-core-single-class` session, saved so another session can pick the work up.

Kickoff session: https://claude.ai/code/session_01FJUE2ePxVHbFSVegZ9WRtP

## Next steps

1. Cut `D-core-single-class` from `origin/D-core-expert` (not from `main`).
2. Work through the plan below, tests first.
3. Update `plan.yaml`'s `d-core-single-class` item (`status`, `branch`,
   `session`, `pull_request_number`) and run `save-plan.sh rdr-refactor` +
   `/plan-dashboard rdr-refactor` as state changes.

---

# d-core-single-class — `EQLSingleClassRDR` core inference engine

## Context

`rdr-refactor`'s Wave-0 stack is landing the EQL-native RDR engine bottom-up. The
`D-core-engine` mega-PR (#68) carried the whole remaining core in one slice; its review
(71 inline threads) asked for a topic split into three stacked PRs — `d-core-expert` →
**`d-core-single-class`** → `d-core-backend` (roadmap §6). `d-core-expert` landed as PR #98
(open, non-draft, `mergeable_state: clean`), which extracted `expert.py`, the
`DataclassException` hierarchy, `AnswerName`/`NamespaceName`, `AnswerValidator`, `RuleAnswer`,
and moved `CaseContext` construction to the caller.

This item is the middle slice: bring `single_class.py` (the engine) and its six engine-level
test files across from the mega-branch, adapted to #98's API and to the design decisions the
#68 review locked in. Nothing on `D-core-expert` has an engine yet — #98's own tests build
`CaseContext` by hand precisely because the engine that will build it lands here.

Outcome: `EQLSingleClassRDR` exists on the stack with its full engine test suite, and every
#68 review thread filed against `single_class.py` and its tests is answered.

## Assumptions and flags

- **Dependency is ready.** `d-core-expert` (#98) is open, non-draft, `mergeable_state: clean`
  → `open_ready` by `plan-schema.md`'s rule. Checked by hand against the live PR rather than
  via `check_dependency_readiness.py`: that script imports `build_dashboard` → `render_common`,
  which needs `markdown` + `nh3`, and `check-setup.sh` reports both missing in this clone
  (`pip install -r .claude/skills/plan-dashboard/requirements.txt` fixes it — also needed
  before `/plan-dashboard` can republish).
- **Base is `D-core-expert`, not `main`.** Branch: `D-core-single-class` (your choice; matches
  `plan.yaml` and every sibling). The pre-created `claude/rdr-refactor-d-core-single-class-t3f2ds`
  branch is unused and currently just `main`'s tip.
- Could not subscribe to tracking issue #94 — both `subscribe_pr_activity` tools return
  "Could not subscribe to this PR". Not a blocker; the PR itself will be subscribed normally.
- **Scope expansion, flagged for your call:** thread `single_class.py:239` asks for `CaseContext`
  to be given to the condition resolver too, not just the expert. That changes
  `ConditionResolver.resolve`'s 8 flattened parameters and touches `condition_resolver.py` plus
  `test_condition_resolver.py` (383 lines, 10 `.resolve(` call sites) — files owned by a lower PR
  in the stack. Included below; say the word and it moves to a follow-up. (#98 set the precedent
  by touching `interface.py` when its review required it.)

## Decisions already settled (do not re-litigate)

From roadmap §6, carried by the split PRs: `classify()` returns `UNSET` not `None`;
non-convergence raises `RDRDidNotConvergeError` (a `DataclassException`) and `max_passes` is
removed; conclusion validation lives on `ConclusionDomain`; `CaseContext` is built by the engine
and threaded down; progress and save use Null-Object defaults; docs stop restating field docs and
stop mentioning plans/phases/history. The auto condition-resolver and `resolution_mode` are
**kept, minimally tidied** — the "should `ConditionResolver` be an `Expert`?" and "should
`resolution_mode` live on the resolver/interface?" threads are already deferred to the
`expert-capabilities` track.

From this session: branch `D-core-single-class`; tests stay on `unittest.TestCase` to match #98;
Null-Object stays on `ExpertInterface` (no promotion to `Expert`); `_observe`/`_trace` both kept.

## Work

### 1. Branch + plan state

Cut `D-core-single-class` from `origin/D-core-expert`. Update `plan.yaml`'s item
(`status: in_progress`, `session`, later `pull_request_number`), run `save-plan.sh rdr-refactor`,
then `/plan-dashboard rdr-refactor` — after installing the two missing dashboard deps.

### 2. Tests first (TDD — every file fails on `ImportError` until step 3)

Port from mega-branch `e650d968`, adapting each to #98's API (`ask_for_conditions(context, …)`,
`ask_for_rule(context) -> RuleAnswer`, `AnswerName`, exceptions-not-strings):

| file | lines | notes |
|---|---|---|
| `test_single_class_rdr.py` | 1079 | core engine behaviour; `classify` → `UNSET` assertions |
| `test_condition_resolver_integration.py` | 831 | already pytest-style; resolver signature change |
| `test_ask_for_rule.py` | 518 | the file #98 deliberately left for this slice |
| `test_backward_inference_integration.py` | 448 | already pytest-style |
| `test_fit_convergence.py` | 426 | **rewritten**: `RDRConvergenceWarning`/`max_passes` → `RDRDidNotConvergeError` |
| `test_corner_case_population.py` | 217 | already pytest-style |

All under `test/krrood_test/test_eql_rdr/`, reusing the existing `animal.py` and `zoo_loader.py`.

**De-duplication** (thread `test_single_class_rdr.py:28`): `FEATURE_FIELDS`, `first()`,
`labelling_expert()`, `scripted_expert()`, `SpyFunctionInterface` and the animal builders are
copy-pasted across three files. Hoist the case builders onto `animal.py` and put the interface
stubs / scripted experts in a new `test/krrood_test/test_eql_rdr/expert_doubles.py`, named after
the behaviour they stand in for (AGENTS.md), imported relatively (the documented test exception).
No catch-all `utils.py`.

**Per-file review threads to clear while porting:** module docstrings become high-level (no API
walkthroughs, no phases/plans); no abbreviations (`sp`→`species`, `f`, `r`, `scs`, `gc`, `i`→`index`);
missing type hints and `:param:`/`:return:` docs added; inline imports moved to module top; the
`Tuple[Any, Any, Any]` rule-tree fixtures in `test_backward_inference_integration.py` become a
small dataclass; the word "live" removed from docstrings.

**New coverage this slice must add:**
- `classify()` on an empty RDR and on a no-rule-fired case returns `UNSET` (not `None`), and
  `None` survives as a legitimate conclusion value.
- Oscillation raises `RDRDidNotConvergeError` carrying the clashing cases and pass count; the
  partially-fitted model is still saved when `save_path` is set.
- Termination: a convergent fit ends without any pass cap.
- Fitting with no expert raises the new typed exception, not `ValueError`.
- Null-Object progress/save: fitting with an interface that reports no progress makes the same
  `start/update/finish` calls against the null reporter, and `save()` no-ops without `on_save`.
- Whether the `SelfReferentialInsertionError` retry loop in `fit_case` is reachable
  (thread `single_class.py:271`): a HINT-mode test that provokes it. If it cannot be provoked,
  delete the loop rather than keep untested code.

### 3. `krrood/src/krrood/entity_query_language/rdr/single_class.py`

Port the 554-line module, then apply its review threads:

- `classify()` → `UNSET` when no rule fires (`Any` return, `UNSET` documented).
- Delete `RDRConvergenceWarning` and `max_passes`; `_run_convergence` raises
  `RDRDidNotConvergeError` (new, in `rdr/exceptions.py`, carrying clashing cases, pass count and
  save path) on a repeated pending-set signature. Loop until converged or oscillating.
- Replace `raise ValueError("Expert must be supplied to fit_case")` with a new typed
  `DataclassException` in `rdr/exceptions.py`.
- Split `fit_case` (thread `:207`) into three named methods: build the `CaseContext`, resolve
  target + condition, run the insert loop. Build `CaseContext` once and pass it to
  `Expert.ask_for_conditions`/`ask_for_rule` — and, per the scope flag above, to the resolver.
- Move the inline `UnderspecifiedMatch` and `SelfReferentialInsertionError` imports to module top
  (verified non-circular: `underspecified.py` does not import `single_class`).
- `from_underspecified(template: Match)` instead of `Any` (`query/match.py`).
- Keep `_observe` and `_trace`; document exactly when each applies and why `classify` takes the
  cheap path (the convergence loop calls it per case per pass).
- Keep `render_tree`'s `-> str` returning `""` for an empty tree, documented as the deliberate
  null rendering (thread `:191` — my proposed answer, not a settled one: `None` would force every
  caller to guard a display value). Keep the `*` keyword-only marker and explain it in the PR body.
- Docstring sweep: drop "live"; stop restating `:param expert:` prose in the method summary; stop
  naming other methods (`ask_for_rule`) in prose; `:return:` on `conditions_root` and
  `conclusion_domain`; complete or drop the `species`/`what_do_we_know_about` examples;
  `:param:` docs on `_insert_rule`.
- `_FITTING_DESCRIPTION` module global (thread `:67`) → a `ProgressDescription` `StrEnum` in
  `progress.py` (enum over string, no module global, and it belongs with progress reporting).

### 4. Supporting modules

- `rdr/exceptions.py`: `RDRDidNotConvergeError` + the expert-required exception, following the
  existing `error_message()`/`suggest_correction()` shape.
- `rdr/progress.py`: `NullProgressReporter` (no-op `ProgressReporter`) + `ProgressDescription`.
- `rdr/interface.py`: `make_progress_reporter()` returns `NullProgressReporter` instead of
  `Optional[...]`; `on_save` defaults to a no-op so `save()` needs no guard. Both stay on
  `ExpertInterface`.
- `rdr/condition_resolver.py`: `resolve(context, target_knowledge, current_knowledge)` — only if
  the scope flag above is accepted.

### 5. PR

Draft PR against `D-core-expert`, session link in the body, `bug` label not applicable. The body
carries the answers to every "discuss with me" thread this slice touches (the pattern #98 used).
Then, per your note, comment on **#98** — it owns `Expert` — asking whether `save()` /
`make_progress_reporter()` should be promoted onto `Expert` so the engine stops reaching through
`expert.interface.…`; it changes #98's public API, so it is cheaper to settle while #98 is still
open. Record the same question on tracking issue #94 as the structural record. Subscribe to the
new PR's activity; write the pr-progress note.

## Verification

- `pytest test/krrood_test/test_eql_rdr` — the full RDR suite, expected 144 (from #98) plus the
  ~100 tests this slice adds.
- `pytest test/krrood_test/test_eql` and `test_ripple_down_rules` — nothing outside `rdr/` should
  move; known pre-existing failures in this sandbox are the missing
  `probabilistic_model…relational.rspn` submodule and the missing `dot` binary (roadmap §9).
- `grep` that no file in this slice imports `rdr.backend` (that is `d-core-backend`'s slice).
- `scripts/format_docstrings.py` on every touched file.
- CI green on the PR before asking for review.
