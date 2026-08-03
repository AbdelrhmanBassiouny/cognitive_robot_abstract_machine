# rdr-backward-inference (#41) — resolving the `negated`-vs-`Not()` design thread

This session's designated branch carries no PR of its own; the work is a
`/plan-item-resolve` on `rdr-refactor` / `rdr-backward-inference`, whose PR is **#41**
on branch `rdr-backward-inference`. No code has been written on either branch.

## Plan

Answer review thread `r3702021144` (`backward_inference.py:64`): should
`GuardCondition.negated` be replaced by wrapping the guard expression in `Not()`?
The developer asked for a discussion considering every use of the guard across the
plan, so the deliverable is a recommendation, not a commit.

## Done

- Verified #41's live state: reparented onto `main` 2026-08-02, `mergeable_state: clean`,
  CI green 20/20 on head `cbbf7bf3`. The `plan.yaml` note claiming "ready for the steward
  to merge" was stale — #41 is blocked on this design question.
- Found the recorded rationale: `backward_inference_design.md` on `rdr-engine`, "Key Design
  Decisions" #1 — the flag exists to avoid live tree mutation. Re-verified the hazard:
  `factories.not_` → `_invert_` → `Not(self)` → `base_expressions.py:299`
  `child._parent_ = self`. Same defect class as `dag-facade-hardening` (#96).
- Mapped all eight guard use sites. `Not()`-wrapping is cleaner at four of six concrete
  sites; the flag wins on the structural hazard alone.
- Established that verbalization does not decide it: `ConditionAssembler.predicate(
  comparator, *, negated)` is already the `(expression, polarity)` pair, and
  `NotComparatorRule`/`NotBooleanAttributeRule` render `Not(Comparator)` natively.
- Replied at `r3702169709` recommending the field be kept, with the expiry condition
  (`Not()`-wrapping wins once #96 lands a non-mutating negation). Thread left unresolved
  deliberately — the call is the developer's.
- `plan.yaml` note + roadmap §12 updated and saved (`569a3552`); dashboard republished.
- Subscribed to #41 activity. No scheduled check armed, per the standing rule; confirmed
  no stale triggers are armed (every `send_later` has already fired).

## Resolved (same day)

The developer resolved the thread without counter-argument and marked #41 ready for review:
**keep the flag**. They then chose to take all three follow-ups onto #41 now, and to file
`_materialize` on `dag-facade-hardening`.

- Pushed `29c27cca` to `rdr-backward-inference`: the field docstring now carries the
  reparenting reason, `holds_for`'s comment describes the real mechanism, and the dead
  `isinstance(OperationResult)` branch plus its import are gone. Two tests added first —
  `test_guard_expressions_evaluate_to_plain_values_never_operation_results` and
  `test_guard_condition_holds_for_a_not_wrapped_expression`.
- Converted #41 back to draft per convention. All 23 threads resolved, `mergeable_state: clean`.
- **Corrected an earlier claim of mine** on the thread: `evaluate()` does *not* only yield true
  results. A leaf predicate yields a literal `False` when it fails, so `bool(result)` is
  load-bearing; "simplifying" to `any(expression.evaluate())` would have made every false leaf
  guard read as true. Only the `isinstance` branch was dead. Probed, not reasoned.
- Verified per §8's method: 206 failed / 935 passed on the previous head vs 206 / 937 after —
  identical failures, +2 exactly the new tests.
- `scripts/format_docstrings.py` deliberately not run: it rewrites the whole module (125
  unrelated lines) and regresses `:return: ``True``` to `:return:``True```. Flagged on the
  thread as deserving its own pass.
- Filed `non-mutating-negation` on `dag-facade-hardening`, reported at #96 comment 5164248289.
  Both plans saved (`335b4d76`) and both dashboards republished.

## Next

Nothing outstanding on my side. #41 is the developer's to mark ready and merge as the stack
bottom. When `non-mutating-negation` lands, `rdr-refactor` should reopen the
`GuardCondition.negated` question — the recommendation was explicitly conditional on it.

Environment note for any follow-up in a fresh container: this repo's tests need **python3.12**
(`make_dataclass(module=...)`), and no interpreter here ships the deps. What worked:
`python3.12 -m venv --system-site-packages`, install the krrood requirements plus
`antlr4-python3-runtime==4.9.3` before `omegaconf`, install `random_events` from PyPI (the
workspace copy's compiled `random_events_lib` is the wrong version), then run with
`PYTHONPATH=krrood/src` and `--confcutdir=test/krrood_test` to bypass the root conftest's
`semantic_digital_twin` import.
