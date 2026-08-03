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

## Next

Waiting on the developer's answer on the thread. Once it lands:

- **If "keep the flag"**: put the no-live-tree-mutation reason into the field's docstring
  (its design doc is on the dropped `krrood/docs/` path and will not land), correct the
  misleading evaluation comment at `backward_inference.py:82-90`, and TDD-pin whether the
  `isinstance(result, OperationResult)` branch in `holds_for` is reachable before deleting it.
- **If "wrap in `Not()`"**: the change is mechanical at the six sites, but needs a
  non-mutating negation first — coordinate with #96 rather than reparenting live nodes.
- Either way, raise placement of the `_materialize` defect (`condition_resolver.py:104`
  calls `not_()` on a live tree node — the exact mutation the flag exists to avoid).
  Not to be bundled into #41 without being asked: it is the bottom of a seven-PR stack
  and every extra commit costs a cascade.
