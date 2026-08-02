# D-core-single-class — PR progress

**Status: not started.** No branch cut, no code written. This note is the
approved implementation plan from a `/plan-item-kickoff rdr-refactor
d-core-single-class` session, saved so another session can pick the work up.

Kickoff session: https://claude.ai/code/session_01FJUE2ePxVHbFSVegZ9WRtP

## Next steps

1. Get a CI or local-test baseline on `D-core-expert` first — PR #98 has never
   had CI run on it (see the assumptions below). Without it the new PR's first
   CI result cannot be separated from anything inherited.
2. Check whether #98 has picked up the "Handed to #98" items below before
   implementing anything that touches `condition_resolver.py`, `interface.py`
   or `progress.py`.
3. Cut `D-core-single-class` from `origin/D-core-expert` (not from `main`).
   Do *not* cascade the stack first — see the staleness assumption below.
4. Work through the plan below, tests first.
5. Update `plan.yaml`'s `d-core-single-class` item (`status`, `branch`,
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

- **Dependency is ready by the rule, but unverified.** `d-core-expert` (#98) is open, non-draft,
  `mergeable_state: clean` → `open_ready` by `plan-schema.md`'s rule. Checked by hand against the
  live PR rather than via `check_dependency_readiness.py`: that script imports `build_dashboard` →
  `render_common`, which needs `markdown` + `nh3`, and `check-setup.sh` reports both missing in
  this clone (`pip install -r .claude/skills/plan-dashboard/requirements.txt` fixes it — also
  needed before `/plan-dashboard` can republish).
  **#98 has never had CI run on it**: `get_status` on head `ed805dc7` returns
  `state: pending, total_count: 0`, and `get_check_runs` returns an empty list. Get a baseline
  before writing code on top — trigger CI on `D-core-expert`, or run
  `pytest test/krrood_test/test_eql_rdr` on it and record the count — so the new PR's first CI
  result is separable from anything inherited.
- **Base is `D-core-expert`, not `main`.** Branch: `D-core-single-class` (your choice; matches
  `plan.yaml` and every sibling). The pre-created `claude/rdr-refactor-d-core-single-class-t3f2ds`
  branch is unused and currently just `main`'s tip.
- **The stack is stale, and that is fine to build on.** Verified live 2026-08-02, unchanged since
  roadmap §10: `D-core-support` `8eb7518a` (2026-07-19) still does not contain
  `D-core-serialization` `2577a2e3`, `D-core-expert` `ed805dc7` sits on that stale support, and
  `main` `82501888` is not an ancestor of the serialization tip either. Do **not** run the cascade
  before starting: `git merge-tree --write-tree origin/D-core-expert origin/D-core-serialization`
  exits 0 with no conflicts and a merged tree carrying zero stale `code_generation.type_hints`
  references, the missing commits are entirely in `code_generation/` while this item touches only
  `rdr/` and `test_eql_rdr/`, and the cascade is the S0-steward's own tracked job that has to be
  redone before anything merges anyway.
- Could not subscribe to tracking issue #94 — both `subscribe_pr_activity` tools return
  "Could not subscribe to this PR". Not a blocker; the PR itself will be subscribed normally.
- **Handed to #98 — see the section below.** The condition-resolver `CaseContext` change and the
  `interface.py`/`progress.py` Null-Object work target files that already exist on
  `D-core-expert`, so they belong to that PR's topic rather than this one.

## Handed to #98 (`D-core-expert`) — not built here

Every file below already exists on `D-core-expert`, so these changes belong to the PR that owns
the parameter-object/Null-Object topic. Reported on #98 so that session can pick them up. This
slice consumes the results and must not re-implement them.

1. **`ConditionResolver.resolve` takes `CaseContext`** (thread `single_class.py:239`, comment 2 of
   3). Four definitions change — abstract `ConditionResolver` (`condition_resolver.py:72`),
   `TargetKnowledgeResolver` (`:115`), `CornerCaseKnowledgeResolver` (`:172`),
   `ChainConditionResolver` (`:208`) — from eight flattened parameters to
   `resolve(context, target_knowledge, current_knowledge)`. Five of the eight are already
   `CaseContext` fields (`case`→`case_instance`, `case_variable`, `target_conclusion`,
   `current_conclusion`, `corner_case`) and `firing_anchor` comes off `context.trace.firing_anchor`.
   Plus `test_condition_resolver.py` (383 lines, 10 `.resolve(` call sites). The import is
   type-only and cycle-free: `interface.py:38` already imports `ResolvedCondition` under
   `TYPE_CHECKING`, and `condition_resolver.py` has `from __future__ import annotations` plus its
   own `TYPE_CHECKING` block.
2. **Null-Object defaults on `interface.py` + `progress.py`.** `make_progress_reporter()` returns
   `Optional[ProgressReporter]` today (`interface.py:310`, returns `None`); `on_save` is
   `Optional[Callable[[], None]] = None` (`:181`) with `save()` guarding
   `if self.on_save is not None` (`:190`). Add `NullProgressReporter` to `progress.py` (alongside
   the existing `SpyProgressReporter`), make the return type non-`Optional`, default `on_save` to
   a no-op, drop the guard.
3. **`ProgressDescription` `StrEnum` in `progress.py`** (thread `single_class.py:67`) — replaces
   the `_FITTING_DESCRIPTION` module global. The enum belongs with progress reporting; only the
   engine consumes it.
4. **Open question, not a decision:** should `save()` and `make_progress_reporter()` be promoted
   from `ExpertInterface` onto `Expert`, so the engine stops reaching through
   `expert.interface.…`? This session's default is no — they stay on `ExpertInterface`
   (`expert.py` has no reference to either today). It changes #98's public API, so it is cheaper
   to settle while #98 is open than after this slice depends on it.

Staying here: `RDRDidNotConvergeError` and the expert-required exception in `rdr/exceptions.py`.
Both are engine-specific and only meaningful once the convergence loop exists.

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

`progress.py`, `interface.py` and `condition_resolver.py` are handed to #98 (see the section
above). If #98 lands without them, implement them here and say so in the PR body — but check
#98 first.

### 5. PR

Draft PR against `D-core-expert`, session link in the body, `bug` label not applicable. The body
carries the answers to every "discuss with me" thread this slice touches (the pattern #98 used),
and notes which threads were answered on #98 instead. Record the handoff on tracking issue #94 as
the structural record. Subscribe to the new PR's activity; write the pr-progress note.

## Verification

- `pytest test/krrood_test/test_eql_rdr` — the full RDR suite, expected 144 (from #98) plus the
  ~100 tests this slice adds.
- `pytest test/krrood_test/test_eql` and `test_ripple_down_rules` — nothing outside `rdr/` should
  move; known pre-existing failures in this sandbox are the missing
  `probabilistic_model…relational.rspn` submodule and the missing `dot` binary (roadmap §9).
- `grep` that no file in this slice imports `rdr.backend` (that is `d-core-backend`'s slice).
- `scripts/format_docstrings.py` on every touched file.
- CI green on the PR before asking for review.
