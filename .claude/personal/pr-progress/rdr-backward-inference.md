# PR #41 — `UNSET` → `...` (Ellipsis) unification

## The decision (2026-08-09)

`UNSET` is being replaced by `...`. My first answer was "no, it collides",
argued from *a sentinel over `Any` must sit outside the value space*. Wrong
principle for this codebase — `CountRange` (`operators/aggregators.py:234,268`)
already counts `value is ...` over evaluated results and domains, widening an
`int` to a closed `SimpleInterval`. EQL deliberately puts "undetermined"
**inside** the value space. The developer's framing holds: `...` means *an
oracle must supply this value*, and the oracle may be a human expert, a
probabilistic model, or an RDR (`rdr/backend.py` is `ProbabilisticBackend`'s
RDR-shaped sibling).

Checked before agreeing: every other Ellipsis check in `krrood/src` reads the
*query template*, never a case instance; `type(Ellipsis)` is already an ormatic
`leaf_type`; both are singletons compared with `is`; no `UNSET` display
consumers on `D-ui`.

## Done

- `efc8a0679` on `rdr-backward-inference`: deleted `rdr/utils.py` (dead here —
  `UNSET` had zero consumers on #41; also cleared the catch-all `utils`
  filename), and restored `query_graph.pdf` to `main`'s blob.
- PR #41 back to draft (4th time). Summary comment + reply on the
  `query_graph.pdf` thread, **left unresolved** — its ask had two halves and
  only the revert is in scope.
- `plan.yaml` + `roadmap.md` §17 saved (`1b29ffbb3`); dashboard republished;
  #94 comment posted.

## Closed (2026-08-09)

Developer marked #41 **ready for review** at 13:20Z → this session's job on it
is over. CI green **20/20** on `efc8a0679`, `mergeable_state: clean`,
11 files / +1,946. Unsubscribed; **no check-in armed** (the subscription notice
asked for one; the personal notes forbid timed checks and override it).

Correction worth keeping: the `total_count: 0` reading right after the push was
just *too early*, not a repeat of §14's #98 CI-trigger problem. Don't
generalise §14 from it.

#41 is ready for the steward to merge as the stack bottom; the next pass should
cascade it through #63–#67/#98. Everything under "Next" below now belongs to
whoever picks up `d-core-expert` (#98) — start a fresh session for it.

## Next — belongs on `d-core-expert` (#98) and above, not here

1. **Probe first**: can an unclassified case whose conclusion attribute is
   outside `random_events` `compatible_types` reach
   `parameterizer._handle_literal_attribute_match`? `parameterizer.py:167`
   raises `InvalidEllipsis` there, and `UNSET` had no such restriction.
   Instrument it (§15's method) — do not reason about it.
2. **Substitute** `is UNSET` → `is ...` across ~40 sites: `rdr/backend.py:124`,
   `expert.py:94,143,191,224,254,259`, `interface.py:70,75,118,123,152`,
   `observer.py:137,238`, `single_class.py:208,226,228,240,308,381,436,502`,
   plus the five `test_eql_rdr` files.
3. **Fix the exposed defect**: `single_class.classify` is `-> Optional[Any]`
   with *"or `None` if no rule fires"* while it returns the sentinel
   (`observer.py:132-137`). §6 locked in `UNSET`; the signature never followed.
4. TDD per AGENTS.md: pin `classify()` on an empty tree, the validator's
   `...`/`None`/domain ladder, and `has_target` against a falsy-but-real
   conclusion (`0`, `""`, `False`) so the `is`-identity check is load-bearing.

## Open, for the developer

- Expert delegation — once `...` is the sentinel, `conclusion = ...` in the
  shell means "generate it", which `make_conclusion_validator` rejects. Filed
  on `no-rule-fired-resolution`.
- Untracking the generated PDFs (`query_graph.pdf`, `drawer_explanation.pdf` —
  both gitignored *and* tracked) is a `main`-level fix. Offered on the thread,
  not done.
- The branch-semantics family thread stays unresolved by design (§16).

## Environment note

This container had no dependency set at all. A 3.12 interpreter plus the
workspace requirements got `test_eql_rdr` running (45/45), but the root
`test/conftest.py` needs `giskardpy_bullet_bindings`, which is not installable
here — so sweeps must run with `--confcutdir=test/krrood_test`. CI stays the
load-bearing check.
