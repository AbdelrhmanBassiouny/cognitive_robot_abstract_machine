# PR plan: D-deco — @rdr decorator (Wave 0, S2b)

Decorator half of the @rdr path, stacked on D-store (#80). Base: `D-store`.
PR: #77 (draft).

## Scope

- `rdr/decorator.py` — `rdr()` factory, `RDRWrapper`, `empty_rule_tree_source`,
  `function_bound_to_its_own_name`.
- `rdr/templates/rdr_empty.py.jinja` — the rule-tree section of a model file
  that has no rules yet.
- `test_rdr_decorator.py` (27 tests) + `function_decorated_at_import.py`, the
  module that applies `@rdr` at import time so importing it is the exercise.
- `doc/eql/{developer,user}/rdr_decorator.md`.

## Split history (2026-07-16)

The original single D-deco PR bundled two unrelated commits — the real @rdr
feature + an "umbrella-closure sweep" of 5 orphan files. Feature split into
#80 (file store) + #77 (decorator); sweep dissolved, its two keepers landed
on #76 by the steward (commit bf5b63c3).

## Stack

main … D-core-backend (#210) -> D-ui-rendering (#79) -> D-ui (#76)
     -> D-store (#80) -> D-deco (#77)

## 2026-08-31 resolve — rebuilt onto the rebuilt D-store

What the item's record was missing, recorded as blockers before any work:
#77's head was from 2026-07-19, still merging D-store's *pre-rebuild* tip
`07cb6831`, so it carried #78's `cfe32ad0`. GitHub read the PR `dirty`,
16,493 additions across 52 files, and two maintenance passes (11:18Z,
12:30Z) had each hit 44 conflicting files and left it `needs-resolution`.

Rebuilt as a **branch reset** onto `D-store` (`ae3fdb05`), per roadmap
decision 1, never a merge. Pre-rebuild tip `c46c0c5b`. The slice's own work
replays as one commit; #77 should now read ~1.5k lines in 6 files.

### Interface drift brought up to the base

Same class #79/#76/#80 each hit: `rdr.utils.UNSET` -> `...`;
`EQLSingleClassRDR.save_path` -> the `ModelSaver` strategy, so the wrapper
hands the store to `rdr.model_saver`; `RDRFileStore.func` -> `function`;
`FunctionInterface(answer_fn=)` -> `answer_function`; answer keys are
`AnswerName` members; `("self","cls")` -> `PythonBuiltinParameterNames`;
generation now passes `base_class=FunctionCase` (the rdr layer's own), which
is #80's decision-11 defect applied on the generate path.

### The defect this slice surfaced

**`@rdr` could not work as a decorator at all on the rebuilt base.** The
model file imports the decorated function back by name; the decorator reads
that file *during* decoration, while the defining module is still executing,
so the `@` has not bound the name yet and the import fails on a partially
initialized module. Broken for every function, in a real module and in
`__main__` alike — not just for locals.

Developer chose the fix in `decorator.py` (asked, 3 candidate homes):
`function_bound_to_its_own_name` binds the undecorated function under its own
name for the duration of the read and restores what was there. Covered by
`function_decorated_at_import.py` + 2 tests, failing first.

### Deliberate behaviour change

`classify` returning `None` is now a real conclusion; only `...` means "no
rule fired". The old code treated `None` as no-rule, which is a leftover from
the `UNSET` sentinel and contradicts the base's `ConclusionDomain`. Pinned by
`test_rule_concluding_none_is_answered_with_none`.

## Verification (Python 3.12, matching CI)

- `test_eql_rdr`: **576 passed, 2 skipped**, against **549 passed, 2 skipped**
  measured on the base itself — exactly the 27 added, nothing else moved.
- Both guides' code cells extracted and executed; the user guide is a CI job
  via `test_eql_documentation.sh`, so this is not optional.
- `scripts/format_docstrings.py` run over the new modules; no `:return:``x```
  regression this round.

## Known gaps, recorded not fixed

- Neither guide is in `krrood/doc/_toc.yml`, matching #76's
  `eql_rdr_conclusion_asking.md`. Left to whoever lands the stack rather than
  making `_toc.yml` a conflict point across five branches.
- `decorator.py` imports three module-private names from `serialization.py`
  (`_FACTORY_IMPORT`, `_CLASS_AND_RULES_SEPARATOR`, `_TEMPLATES_DIRECTORY`).
  Real smell; `serialization.py` is #66's file, so decision 5 says not here.
- `plan_item_bootstrap.py update` writes 4-space-indented fields when an
  item's block ends in a list (`depends_on`), producing invalid YAML.
  Worked around by editing `plan.yaml` directly. Belongs to the
  plan-tracking tooling, not to this PR.

## Next

- Push, restore #77 to draft, update its description.
- CI has never run on this branch's current stack; every figure above is a
  local measurement.
