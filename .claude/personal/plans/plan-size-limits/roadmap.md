# Plans stay small — Roadmap

Narrative half of `plan-size-limits`. Kept deliberately short: a plan about
size budgets that spends its own budget on prose would be its own
counter-example.

## Why

Plan size has been governed by guidance, and guidance has not held.
`plan-create/SKILL.md` already warns that "an over-modelled plan is worse than
a flat one", and it has not stopped two plans from reaching 49 and 55 items.

Measured on the personal-notes branch, 2026-08-28:

| plan | items | manifest | roadmap | total |
|---|---|---|---|---|
| eql-verbalization | 5 | 100 | 133 | 233 |
| eql-performatives | 9 | 166 | 139 | 305 |
| eql-existential-semantics | 9 | 480 | 296 | 776 |
| dag-facade-hardening | 8 | 293 | 530 | 823 |
| match-query-ergonomics | 6 | 345 | 1047 | 1392 |
| montessori-eql-stack | 13 | 389 | 1245 | 1634 |
| **rdr-refactor** | **49** | **1000** | **2676** | **3676** |
| **workflow-unification** | **55** | **4326** | **9933** | **14259** |

The distribution is bimodal, not a gradient: six plans cluster at or below 13
items and 1,634 lines, and two sit 2–9× beyond. A budget can therefore separate
them without disturbing anything healthy.

The growth mechanism matters for the design. During the single session that
created this plan, `workflow-unification` grew **51 manifest lines and 103
roadmap lines while gaining zero items** — narrative accreting onto entries that
already existed. A rule policed per new item cannot see that, which is why the
budget counts lines in both files rather than items alone.

A second cost, measured 2026-08-29. An oversized plan also makes its own
published dashboard expensive to *re*publish. 88% of `workflow-unification`'s
1.26 MB artifact is plan content — 62% the embedded `roadmap.md`, 26% item
notes — so page size tracks plan size almost directly. When another session has
published since, the `Artifact` tool refuses the publish until the live version
has been read in full: 16 reads at today's size, ~2 at the budget. That gate is
harness-side, so nothing in this repository can narrow it to a diff; shrinking
the plan is the only lever there is.

## Decisions

**1. Hard refusal, not a growth-only gate.** (user, 2026-08-28) A save leaving a
plan over budget is refused outright. The alternative considered was refusing
only saves that *add* an item, letting oversized plans keep recording state
forever. Rejected: it would have left the two outliers permanently exempt from
the rule they motivated. The cost accepted is that both must be split before the
gate can land, which is wave 2.

**2. One budget across `plan.yaml` and `roadmap.md`.** (user, 2026-08-28) Two
separate limits were considered, as was a manifest-only limit with roadmap
minimalism left to guidance. Rejected for the reason the request states: that
guidance is exactly what has not worked. `match-query-ergonomics` shows why a
combined budget is the right shape — 6 items but a 1,047-line roadmap, so an
item-count limit alone would rate it healthy.

**3. Budget set at 15 items / 2,000 combined lines.** (user, 2026-08-28) Chosen
against the table above: clear of the largest healthy plan with headroom, and
unambiguously below both outliers. A tighter 12/1,500 was considered and
rejected because it would have pulled `montessori-eql-stack` into the migration
for no benefit.

**4. Wave order is measure → migrate → refuse.** The gate cannot land first
without stranding the plans it is meant to fix, including the manifest tracking
this very work. Wave 1 is therefore report-only.

## Why this is its own plan

Every comparable plan-tooling change to date is an item in
`workflow-unification`'s `personal-data` track — `add-plan-item-skill` (#135),
`plan-item-bootstrap` (#143), `plan-item-execution-modes` (#149),
`manifest-currency-first` (#151), `setup-runs-without-asking` (#156),
`plan-item-bootstrap-yaml-indent` (#160). This is the first to break that
pattern.

The reason is mechanical rather than stylistic. Under decision 1, the moment the
gate lands, `save-plan.sh` refuses every save of `workflow-unification` until it
is split — including the saves recording the status of the items doing the
splitting. A plan cannot track the work that disables its own saving.

The `/add-plan-item` scope check supports the separation independently:
`check_scope_overlap.py --base origin/main` over the paths this work touches
returned `paths_absent_from_base: []`, so no unlanded branch introduces them and
none is a candidate owner. Grepping the four plan-tooling branches in flight
(#151, #154, #156, #185) for any size/limit/split concept returned nothing, and
no item in any of the eight plans covers it.

## Landing hazards

- ~~**`.claude/shared/plan_model.py` is not on `main`.**~~ Settled by #207: the
  budget lives in `.claude/hooks/plan_size_budget.py`, a module of its own on
  `main`, rather than as a third copy of a file that exists only on #151 and
  #154 - the #106/#110 failure. Moving it into `.claude/shared/` once that
  module lands is a rename, not a merge.
- **#185 (bastler-package) relocates the ground.** It moves
  `plan_manifest_tools.py` to `bastler/plan_manifest_tools.py` and its tests to
  `test/bastler_test/`, and edits `save-plan.sh` plus the `add-plan-item`,
  `plan-item-kickoff` and `plan-item-resolve` skill documents. Whichever lands
  second rebases.
- **#151, #154 and #156 all edit `plan-create/SKILL.md`** and the kickoff/resolve
  skills. Overlap rather than ownership, but worth coordinating before
  `minimal-roadmap-writing` starts.
- **The splits move live data every session reads.** `branch-index.tsv` and
  `dashboard-urls.yaml` are keyed by plan id; both must be regenerated, or
  `session-start.sh` stops resolving branches to plans and `/plan-dashboard`
  publishes duplicate pages under the new ids.

## Open

- Whether the budget is a single pair of constants or configurable per plan. The
  plan assumes fixed constants; a plan that genuinely needs more is the signal to
  split it, which is the whole premise.
- Whether the dashboard should show a plan's budget consumption. Not currently an
  item — it is reporting, and the gate is the enforcement.

## Review round of 2026-08-30 (#207)

Five of seven threads are answered and resolved; two are open on the reviewer's
own decision.

**5. No constant sits mid-module, and no free functions.** (reviewer) The budget
became `SizeBudget`'s own `MAXIMUM_ITEMS`/`MAXIMUM_LINES` class variables rather
than a `PLAN_SIZE_BUDGET` instance built halfway down the file - an instance
cannot move to the top, since the class has to exist first. `SizeBudget()` is
now the budget, which is what `refuse-oversized-save` will import. The eight
free functions moved onto `PlanSize`, a new `PlansDirectory` (the directory and
its two filenames, which were three loose primitives) and a new `SizeReport`
(the plans with the budget judging them).

**6. A dependency is written down once.** (reviewer) The hardcoded `import yaml`
probe is gone. `.claude/hooks/requirements.txt` is the one place the hooks' own
dependencies are stated, and `missing_requirements.py` reports whichever of a
requirements file's distributions are absent - generic, so `check-setup.sh`
dropped its inline copy of the same parse and calls it too. The file needed a
`.gitignore` exception: the repository ignores `*.txt` wholesale, so without one
it would never have reached CI, and the report's tests read it from disk.

**7. A filename is written down once too.** (reviewer) `HookScript`,
`PlanDocument` and `PLANS_DIRECTORY` already existed and were being duplicated
by the tests; they are now imported. `ScratchRepository.install_hook_modules`
names hook modules by the module objects. `resolve-personal-notes-config.sh`
gained `CREATE_PERSONAL_NOTES_BRANCH_SCRIPT`, `HOOKS_REQUIREMENTS_FILE`,
`MISSING_REQUIREMENTS_SCRIPT`, `PLAN_SIZE_BUDGET_SCRIPT` and
`PLAN_SIZE_REPORT_SCRIPT`.

### Open with the reviewer

- **Should `plan-size-report.sh` be Python?** It can be, but the notes-branch
  config resolver is bash and has no Python half, so a Python entry point has to
  shell back into it or port it. Every hook entry point needing the config is
  bash for that reason. Porting the resolver is its own item if wanted, and it
  collides with #185.
- **Do the eight scripts on `main` that spell `create-personal-notes-branch.sh`
  convert now or later?** The constant exists for them; converting here widens
  this PR into files it does not otherwise touch.
