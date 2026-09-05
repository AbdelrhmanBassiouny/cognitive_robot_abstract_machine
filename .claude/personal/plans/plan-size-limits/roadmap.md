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

### Second pass of the same round, resolved in e4ba75a7

Three more small threads landed on #207 after the first six were already
answered - none of them recorded in this plan's manifest until this resolve
found them live on GitHub rather than in `blockers`.

**8. No constant may just point to another constant.** (reviewer) The test's
`MANIFEST_FILENAME`, `ROADMAP_FILENAME` and `SCRIPT_NAME` module constants were
each nothing but `PlanDocument.MANIFEST`, `PlanDocument.ROADMAP` and
`HookScript.PLAN_SIZE_REPORT` under a second name. The reviewer flagged two of
the three explicitly and left the third ("same comment as above") - all three
are gone now, and every use site names the real definition directly.

**9. The rendered report itself hardcoded the two filenames.** (reviewer) The
budget line printed the literal `"plan.yaml and roadmap.md"` instead of reading
`PlanDocument.MANIFEST`/`PlanDocument.ROADMAP`. Fixed by importing
`PlanDocument` into `plan_size_budget.py` - no import cycle, since
`plan_item_bootstrap` does not import this module - and by adding
`plan_item_bootstrap` to the integration test's scratch-layout installs, since
the script now needs it too when run as a real subprocess.

Unrelated to this item: `#207`'s `giskardpy` check is red on the current head
(`test_collision_matrix_tool.py::test_script_launch_and_kill`, a
`subprocess.TimeoutExpired`), a ROS2 integration test this diff does not touch.
Left alone rather than re-run or investigated further here.

## Kickoff 2026-08-30: `split-workflow-unification` — the seams, measured

Session: https://claude.ai/code/session_019636yuByUTH6aFiEQdDztc

`size-budget-and-report` (#207) is open and non-draft, so this item's only dependency is
ready to build on.

### Measured, not assumed: the tracks alone do not get under budget

The item's notes say the five existing tracks "already name the natural seams". Measured
on the live manifest today (59 items, 5,129 manifest + 11,788 roadmap = 16,917 lines), a
straight by-track split leaves two of the five plans still over:

| track | items | manifest | roadmap | total | verdict |
|---|---|---|---|---|---|
| personal-data | 16 | 798 | 3,531 | 4,329 | over both halves |
| stack-tooling | 18 | 2,598 | 5,735 | 8,333 | over both halves |
| dashboards | 12 | 533 | 1,246 | 1,779 | within |
| bastler | 10 | 491 | 669 | 1,160 | within |
| cutover | 3 | 138 | 134 | 272 | within |

Roadmap lines are attributed by counting each `## Update` section's mentions of item ids
and pull request numbers. `stack-tooling` is over the line budget on its manifest alone,
before a word of roadmap: one item, `integration-branch`, carries 585 manifest lines.

So the split is a partition **and** a compression, and both halves need a stated rule.

### Seven plans, seamed on subject

`stack-tooling` and `personal-data` each split in two along a seam their own items already
draw; the other three tracks become plans unchanged.

1. `stack-tooling-install` (7) — the tooling on main and the skills that install it:
   `setup-personal-notes-pr101`, `stack-tooling-on-main`, `setup-stacked-prs-skill`,
   `setup-personal-notes-script`, `native-stacks-prototype`, `unfetched-parent-branches`,
   `session-branch-base`.
2. `stack-maintenance` (11) — the pass that runs over a live stack: the executor,
   reparenting, upstream review reading, manifest currency, promotion, and the whole
   integration-branch family.
3. `plan-tracking-skills` (6) — `add-plan-item-skill`, `plan-item-bootstrap`,
   `plan-item-execution-modes`, `plan-item-bootstrap-yaml-indent`, `plan-item-edit-guard`,
   `report-document-naming`.
4. `session-notes-infrastructure` (10) — the session-start hook, notes, git identity,
   settings sync and the conventions that ride in them.
5. `plan-dashboards` (12) — the `dashboards` track unchanged.
6. `bastler-package` (10) — the `bastler` track unchanged.
7. `workflow-cutover` (3) — the `cutover` track unchanged.

The seams were chosen to keep live dependency edges inside one plan, not by subject alone:
moving `pinned-stack-tooling` to `stack-maintenance` (which is what it is — the tool a
maintenance pass runs) is what removes the last live edge crossing the stack-tooling seam.

### `depends_on` cannot cross a plan, so five edges dissolve and three demote

`build_dashboard.validate_plan` raises `UnknownDependency` for any `depends_on` entry that
names no item in the same manifest, so the split cannot preserve a cross-plan edge. Nine
edges cross a track today. Five name items that are already `done` — a satisfied
dependency carries no information the dashboard acts on, so those are dropped and stated
in the depending item's `notes` instead.

Three name live items and cannot be kept without merging plans that would then be over
budget again:

- `shared-pr-state-chips` → `bastler-package`
- `bastler-github-api-unification` → `setup-personal-notes-script`
- `bastler-github-api-unification` → `shared-pr-state-chips`

These become `blockers` entries naming the other plan and item. The cost is real and worth
recording: those three items lose their dependency chips and their automatic readiness
computation, and keep only the free-text blocker a human reads. A cross-plan reference in
the schema (`<plan-id>:<item-id>`) would restore it, and is code rather than data — a
candidate item for whichever plan ends up owning the dashboard, not for this one.

### The compression rule

Splitting alone leaves `stack-tooling`'s successors far over, so each successor roadmap is
rewritten rather than sliced:

- **Keep** what binds future work: the plan's "why", the target architecture, the numbered
  design decisions, standing risks and hazards, open questions, and any conclusion a later
  item depends on.
- **Compress** the per-round implementation narrative of items that are already merged to
  a line or two naming the outcome. The pull request is that record, and it is linked.
- **Compress item `notes`** the same way, hardest on `done` items.

Nothing is destroyed: the full 11,788-line roadmap stays reachable in the personal-notes
branch's own history.

### Mechanics the split has to get right

- `save-plan.sh` writes one plan's two files and regenerates `branch-index.tsv` across
  every manifest, so the branch index self-heals. It cannot *delete* the old plan
  directory — that needs its own commit on the notes branch.
- `_generated/dashboard-urls.yaml` is keyed by plan id and is written by the
  `plan-dashboard` skill, not by `save-plan.sh`. The `workflow-unification` key is removed
  by hand; the seven new keys are minted by publishing each new dashboard.
- Every item keeps its `pull_request_number`, `branch`, `status` and `session` verbatim.
- All seven plans keep `tracking_issue: 102`. Reusing the existing mailbox keeps the
  continuity that seven new issues would scatter, and creating issues is not this item's
  to do.

### No branch and no pull request

Personal-notes data only, per the item's own notes and the `eql-roadmap-migration`
precedent. This session's designated branch stays empty; the manifest's `branch` and
`pull_request_number` stay `null`.

## Done 2026-08-30: `split-workflow-unification` — seven plans, 16,917 lines to 2,916

Pushed to the notes branch as `e69094af3`; dashboard URLs recorded in `273436cb9`. Structural record
on tracking issue #102.

| new plan | items | lines | was |
|---|---|---|---|
| `stack-tooling-install` | 7 | 435 | `stack-tooling`, install half |
| `stack-maintenance` | 11 | 737 | `stack-tooling`, pass half |
| `plan-tracking-skills` | 6 | 299 | `personal-data`, plan-item skills |
| `session-notes-infrastructure` | 10 | 415 | `personal-data`, hook and notes |
| `plan-dashboards` | 12 | 419 | `dashboards`, unchanged |
| `bastler-package` | 10 | 413 | `bastler`, unchanged |
| `workflow-cutover` | 3 | 198 | `cutover`, unchanged |

Measured against the live notes branch afterwards: every plan in the directory is now within the
budget except `rdr-refactor` (49 items, 4,282 lines), which is `split-rdr-refactor`'s work.

### What the split preserved, and how that was checked rather than trusted

All 59 items are present exactly once and none is invented, checked by set comparison against the
source manifest; every successor passes `build_dashboard.validate_plan`; and each item's `branch`,
`pull_request_number`, `status` and `session` are copied field-for-field by the builder rather than
retyped. The dashboards then rendered against live GitHub with **zero drift flags across all seven**,
which is the independent confirmation that no status was changed by the move.

### What it could not preserve

Three live `depends_on` edges crossed a plan boundary and are now `blockers`, so those items lose
their dependency chips and automatic readiness. Merging the plans that would keep them puts two of
them back over budget, so this is a cost rather than an oversight. A `<plan-id>:<item-id>` reference
in the schema would restore it, and is a candidate item for `plan-dashboards`.

### What the compression rule turned out to be worth

The manifests alone were 5,129 lines for 59 items - one item carried 585 - because notes had been
accreting per resolve session rather than being rewritten. Compressing to what binds future work took
the manifests to 2,203 and the roadmaps from 11,788 to 713. Nothing is destroyed: the full
predecessor roadmap is in the notes branch's history immediately before the split commit.

This is direct evidence for `minimal-roadmap-writing`, the item that changes what the skills ask
sessions to write: 94% of the roadmap was per-round implementation narrative about merged pull
requests, and the pull requests are that record already.

### Left alone deliberately

`_generated/branch-index.yaml` still names `workflow-unification`. Nothing reads it - `save-plan.sh`
regenerates only the `.tsv`, and a grep of `.claude/` finds no reader - so it is a dead generated file
predating this work, and deleting it is outside this item.

## Done 2026-08-30: `split-rdr-refactor` — seven plans, 4,372 lines to 1,806

Pushed to the notes branch as `397532690`. Both plans that motivated the budget are now
under it, so `refuse-oversized-save` is unblocked.

| new plan | items | lines | was |
|---|---|---|---|
| `eql-core-and-code-generation` | 6 | 177 | the EQL/codegen foundation, all merged |
| `rdr-core-engine` | 14 | 517 | the `rdr/` package stack |
| `rdr-interface-and-decorator` | 5 | 242 | the D-ui and D-deco tracks |
| `test-suite-fixes` | 3 | 180 | the flaky-marker and pytest-conversion items |
| `rdr-explanation` | 8 | 239 | the Why & Montessori wave |
| `rdr-engine-extensions` | 10 | 301 | waves 1–3 and the architecture brief |
| `rdr-expert-framework` | 3 | 150 | the expert-capabilities track |

### The item's own note predicted the wrong seam, and measuring is what caught it

The note said the plan's waves "already separate the engine work from the Why & Montessori
track and the expert framework, which is the likely seam." Measured, a by-wave split does
not get under budget: wave 0 alone holds **26 of the 49 items, 867 manifest lines and about
2,565 of the 3,259 roadmap lines** — 92% of the roadmap attributed by counting each
addendum's mentions of item ids and pull request numbers. The other six waves together are
23 items and under 700 lines. So the split had to cut *inside* wave 0, which the note did
not anticipate.

The seam it cuts on is subject: the EQL core and `code_generation` extraction under the
engine (all merged, and not RDR work at all); the `rdr/` package delivery stack itself; the
interactive shell, magics, decorator and file store on top of it; and the repository-wide
test-suite defects the stack surfaced but does not own. That last group is three items and
looks thin, but folding it anywhere would have put unrelated work in a plan already at the
budget — the same reasoning `workflow-cutover` was kept separate under.

### The cost, which is larger than the sibling split's

`depends_on` cannot cross a plan, so **seven live edges dissolve into `blockers`** here
against the sibling's three. The reason is structural rather than a partition mistake:
`d-core-backend` and `d-core-single-class` are the trunk, and six items across four
different subjects stack directly on them. Keeping any one of those dependents with the
engine pushes `rdr-core-engine` over 15 items. Three further edges name items that have
already merged and are dropped into the depending item's notes instead.

That makes ten items in this programme with no dependency chip and no automatic readiness.
The `<plan-id>:<item-id>` reference already noted as a candidate for `plan-dashboards` would
restore all of them, and this split roughly triples the case for it.

### Verified rather than trusted

All 49 items are present exactly once and none is invented, by set comparison against the
source; every successor passes `build_dashboard.validate_plan`; every item's `title`,
`branch`, `repository`, `pull_request_number`, `status` and `session` are byte-identical to
the source, checked field-by-field rather than by reading the diff; and every declared track
has at least one item. The branch index went from 125 branches to 125, with **none unmapped
and 42 remapped**, so `session-start.sh` resolves every branch exactly as before.

One warning from the index regeneration is pre-existing, not this split's:
`conditions-root-drop-dead-parent-recovery` is claimed by both `dag-facade-hardening` and
this plan's `eql-core-and-code-generation`, and it mapped to `dag-facade-hardening` before
the split too.

### The compression rule paid the same way it did on the sibling

The predecessor's roadmap was 3,259 lines, of which sections 1–4 (266 lines) are the design
and the standing conventions and the remaining 31 addenda are per-round narrative about
individual pull requests. Rewriting rather than slicing took the seven roadmaps to 855 lines
total and the manifests from 1,113 to 951. What was kept is what binds future work: the
locked engine decisions, the open design questions nobody has answered, the standing hazards
— the wedged CI merge refs, the tracked generated interface, the formatter's fourteen-instance
regression — and the programme's own working method, which is recorded once in
`rdr-core-engine`'s roadmap and referenced from the others rather than copied into each.

Second independent confirmation of `minimal-roadmap-writing`'s premise: 92% of this roadmap
was narrative about merged pull requests, against the sibling's 94%.

### Left alone deliberately

`rdr-refactor` was a live plan while this ran — another session pushed a resolve to it
mid-way through, so the source was re-read from the current tip before building. The seven
successors all keep `tracking_issue: 94`, reusing the existing mailbox rather than scattering
the continuity across seven new issues. Personal-notes data only, so no branch and no pull
request, per the item's own notes and the sibling split's precedent.

## Kickoff 2026-09-05: `refuse-oversized-save` — two more plans found over budget

Session: https://claude.ai/code/session_01XWy1uT1i7FozWdNhLEtcKk

Both declared dependencies (`split-workflow-unification`, `split-rdr-refactor`) are `done`,
but measuring the live notes branch rather than trusting the last report turned up two
plans neither split touched: `knowledge-directed-perception` (29 items, 8,146 lines — within
budget at 15/1,300 in #207's 2026-08-28 report, since grown past both halves) and
`icra-experiments` (33 items, 1,833 lines — over the item limit alone). Added as
`split-knowledge-directed-perception` and `split-icra-experiments`, siblings of the two done
splits in the `plan-splits` track, and as new entries in `refuse-oversized-save`'s
`depends_on` — the gate cannot land while any plan is still over, including these two.

`size-budget-and-report` (#207) was also added to that `depends_on`, missing from the item's
original list even though the gate's whole job is importing `SizeBudget` from the module #207
introduces. That module does not exist on `main` yet; #207 is open and non-draft, which
`plan-schema.md` already counts as ready to stack on, so this item's branch is cut from
#207's own branch (`claude/plan-size-limits-budget-alp8p2`) rather than `main`, per this
repository's stacked-PR convention of opening each PR with base = its parent branch.

## Kickoff 2026-09-05: `refuse-oversized-save` — the gate, on top of #207

Pull request: https://github.com/AbdelrhmanBassiouny/cognitive_robot_abstract_machine/pull/273

Stacked on #207's branch (`claude/plan-size-limits-budget-alp8p2`), not `main`: this item
imports `SizeBudget`/`PlanSize` from `plan_size_budget.py`, which exists only there. #207 is
open and non-draft, which `plan-schema.md` counts as ready to stack on.

`SizeBudget` gained `enforce(size)`, raising a new `PlanOverBudgetError` that names every
blown half and by how much. `plan_size_gate.py` is a new small script wrapping it as a CLI;
`save-plan.sh` calls it right after the existing `plan_manifest_tools.py read-id` check - the
seam the item's own notes named - and before the scratch worktree is even created, so a
refused save touches nothing. TDD throughout: `test_plan_size_budget.py`,
`test_plan_size_gate.py` (new) and `test_save_plan_sh.py` were all red before the
implementation. `test_plan_item_bootstrap.py`'s scratch fixture also needed the two new
scripts installed, since its `record`/`open` operations call `save-plan.sh` internally and
that call would otherwise fail with the new scripts missing from its scratch layout.

Landing this PR (merging it, not just opening it) still has to wait on
`split-knowledge-directed-perception` and `split-icra-experiments` alongside the two done
splits - both entries in `depends_on` above the found-oversized note explains.

## Done 2026-09-05: `split-icra-experiments` - three plans, 1,833 lines to 1,126

Session: https://claude.ai/code/session_01XWy1uT1i7FozWdNhLEtcKk

Pushed to the notes branch as `68da2fd2c`, `55f80a611` and `0ad970a0f` (one commit per
successor); the old plan directory and its `_generated/dashboard-urls.yaml` key removed in
`c6dc76240`.

| new plan | items | manifest | roadmap | total |
|---|---|---|---|---|
| `icra-foundation` | 10 | 150 | 324 | 474 |
| `icra-mechanism` | 12 | 186 | 135 | 321 |
| `icra-evidence` | 11 | 205 | 126 | 331 |

### The seam: by wave, and it held on both halves without cutting inside one

Unlike `split-rdr-refactor`'s wave 0 (92% of that roadmap, forcing a cut on subject
instead), `icra-experiments`' three waves - `foundation`, `mechanism`, `evidence` - were
already close to even in items (10/12/11) and the roadmap's per-round narrative turned out
to concentrate almost entirely (about 790 of 1,061 lines) on `foundation`'s four items with
open pull requests (#261, #262, #265, #271); `mechanism` and `evidence` carried almost none,
since every item there is `not_started`. Measured rather than assumed, exactly as the
sibling splits insist: a by-lane alternative (the plan's three person-assignment lanes, cut
across all three waves) was checked too and rejected - it crosses roughly as many
dependency edges as by-wave (19 against 29) while producing a lane holding exactly 15 items
with no headroom, and it breaks the wave framing the budget table's own milestones
("go/no-go Sunday evening", "every experiment has run once in simulation") are already
organized around. By-wave keeps that framing and is the plan's own existing seam.

### The cost is real, and larger than either sibling split's: 29 edges, not 3 or 7

`icra-experiments` is a single pipeline by design - foundation feeds mechanism feeds
evidence, item by item - so a wave-based cut crosses far more of its own `depends_on`
graph than the sibling splits' subject-based tracks did: 29 edges out of 33 items' worth of
graph, against the sibling splits' 3 and 7. None of the 29 crossing edges name an
already-`done` target (only one item plan-wide is `done`, and nothing depends on it), so
none could be dropped the way the sibling splits dropped their satisfied edges - all 29
became `blockers` naming the other plan and item, verbatim by script rather than retyped
(`icra-mechanism` carries 9, `icra-evidence` 20). Every not-yet-started item in
`icra-mechanism` and `icra-evidence` that depends on upstream work now reads its dependency
as free text rather than a dashboard chip with automatic readiness. This is the strongest
case yet for the `<plan-id>:<item-id>` cross-plan reference already flagged as a
`plan-dashboards` candidate by both prior splits - three programmes in a row have now paid
this same cost.

### Verified rather than trusted

All 33 items are present exactly once and none is invented, checked by a script-driven set
comparison against the source manifest (not eyeballed); every successor passes
`build_dashboard.validate_plan`; every item's `branch`, `pull_request_number`, `status`,
`session`, `repository`, `title` and `notes` are byte-identical to the source, checked by
direct field comparison via a load/transform/dump script rather than hand-retyped (a script
also built every `depends_on`/`blockers` edit, so the 29 blocker strings are generated, not
typed 29 times by hand). The branch index went from 148 branches to 148, with **none
unmapped** - the only remappings are the five `icra-*` branches now pointing at
`icra-foundation` instead of the deleted `icra-experiments`, plus a handful the sibling
`split-knowledge-directed-perception` push remapped in the same window (this session's
push and that one interleaved on the notes branch - see below - and neither broke the
other's mapping).

### The compression rule, on a plan too small to need it for budget

Unlike both prior splits, none of `icra-experiments`' three successors needed compression
to clear the line budget - even keeping every line of the source roadmap in `icra-foundation`
alone would have landed at about 1,300 lines, well under 2,000. The rule was applied anyway,
on its own terms rather than skipped: `icra-foundation`'s roadmap (324 lines, down from the
source's 1,061) keeps every standing hazard, every decision with a lasting consequence (the
`Footprint` rename precedent, the unbounded `SimulationTimePacer.sleep()`, the database
rename cost, the #231/#223 rebase left for a deliberate pass) and compresses the blow-by-blow
merge-conflict narrative - which hunk, which commit, which of six silent-conflict sweeps - to
its outcome, since the pull requests themselves carry that record. `icra-mechanism` and
`icra-evidence`'s roadmaps needed no compression at all: their items are all `not_started`,
so the source carried almost no per-round narrative to compress, only design decisions
(Experiment D's three-part rationale, the expectation-mechanism test) that were kept in
full under whichever successor owns the items they explain.

### Concurrency, as the mechanics note anticipated

`split-knowledge-directed-perception` ran on the notes branch at the same time as this item,
exactly the scenario `refuse-oversized-save`'s kickoff flagged when it added both items
together. Every push here re-fetched immediately before writing: two of this session's own
pushes landed cleanly back to back, and the final cleanup push (`c6dc76240`, deleting
`icra-experiments`) was itself followed by the sibling's `Update plan manifest for
knowledge-directed-grounding` fast-forwarding on top with no conflict - confirming the
fast-forward-only push is what the mechanics notes said it would be: a clean rejection on a
race, never silent data loss, and safe to just re-fetch and retry.

### What this leaves for `refuse-oversized-save`

Both plans `refuse-oversized-save`'s `depends_on` was waiting on are now split;
`split-knowledge-directed-perception` still shows `not_started` in this plan's own manifest
as of this write - its session had not yet flipped that item's status when this one was
written, so `refuse-oversized-save`'s own session should re-check `plan-size-limits` live
rather than trust this note once both are believed done.

## Done 2026-09-05: `split-knowledge-directed-perception` - three plans, 8,146 lines to 1,892

Session: https://claude.ai/code/session_01XWy1uT1i7FozWdNhLEtcKk

Pushed to the notes branch as `cb0c450e8`, `51c2a08d2` and `df6ef412c` (one commit per
successor); the old plan directory removed in `170d57424`; dashboard URLs recorded in
`45e13b747`.

| new plan | items | manifest | roadmap | total |
|---|---|---|---|---|
| `knowledge-directed-grounding` | 10 | 505 | 140 | 645 |
| `knowledge-directed-requests` | 14 | 815 | 84 | 899 |
| `knowledge-directed-expectation` | 5 | 293 | 58 | 351 |

### The seam: by wave, and it held without cutting inside one

`knowledge-directed-perception`'s three waves - `grounding`, `requests`, `expectation` -
were the item's own guessed seam, and measuring confirmed rather than overturned it:
10/14/5 items, all under the 15-item cap on their own. The item's own notes flagged a real
risk before measuring - `request-language` and `method-selection` together already carried
875 of the 1,661 manifest lines, so the `requests` wave's roadmap share might have forced a
cut *inside* the wave the way `split-rdr-refactor`'s wave 0 did. Attributing the roadmap's
40 `##`-level sections by their header's own item id (falling back to the item ids and pull
request numbers a section's body mentions, for the nine sections with no item in the
header) put about 3,470 of the 6,492 roadmap lines on `requests` alone against `grounding`'s
2,240 and `expectation`'s 494, plus 276 lines of plan-wide "why" attributable to none of
them - confirming the risk was real. What settled it without cutting inside `requests` was
the compression rule (below): once applied, `requests`' own roadmap fell to 84 lines
against an 815-line manifest, nowhere near its 2,000-line ceiling, so the by-wave seam held
on both the item-count and the line-count halves of the budget without needing the
subject-level cut `split-rdr-refactor` needed.

### The cost: 9 edges, between the sibling splits' 3 and `split-icra-experiments`' 29

`depends_on` cannot cross a plan, and this plan's own three waves are pipelined - a scene
grounded in wave 1 is what wave 2 asks about, and what wave 2 finds is what wave 3 expects
- so cutting by wave crosses real edges: 9 out of the graph's edges, more than
`split-workflow-unification`'s 3 but far fewer than `split-icra-experiments`' 29, since only
a handful of items reach across a wave boundary rather than every item in a pipelined
stage. All 9 name items still `in_progress` or `not_started` (nothing plan-wide is `done`
except one demo item nothing here depends on), so none could be dropped as satisfied the
way the first two splits dropped some of theirs - all 9 became `blockers` naming the other
plan and item, generated by the same build script that wrote the manifests rather than
retyped by hand. One of the 9 was not in the item's own risk assessment at all:
`robokudo-detector` (wave `expectation`) depends on `choose-detection-method` (wave
`requests`), caught only by a systematic depends_on-crosses-a-plan check run over every
item rather than by the by-hand review that found the other 8 - worth noting as a reason to
always run that check mechanically rather than trust a manual pass, on any future split.

### Verified rather than trusted

All 29 items are present exactly once and none is invented, checked by a script-driven set
comparison against the source manifest; every successor passes
`build_dashboard.validate_plan`; every item's `branch`, `pull_request_number`, `status` and
`session` are byte-identical to the source, checked by direct field comparison in the build
script rather than eyeballed; and a second, independent script assertion confirmed no
`depends_on` in any successor names an item outside that successor (the mechanism that
caught the `robokudo-detector` edge above). The branch index went from 148 branches to 148,
with **none unmapped**: the only remappings are the 22 branches this split's items carry,
now pointing at whichever of the three successors owns them, plus 5 unrelated `icra-*`
remappings from `split-icra-experiments` running on the notes branch at the same time (see
Concurrency, below).

### The compression rule paid for the `requests` wave's own headroom

The source roadmap's 6,492 lines were, on inspection, mostly elaboration on decisions
already recorded more concisely in each item's own manifest `notes` - extended
reasoning-traces, superseded intermediate measurements, and per-round "Built as
commit X, N tests pass" narrative for pull requests still open rather than merged. Each
successor's roadmap keeps only what binds future work: the plan-wide why, the three waves
and the deadline budget (kept once, in `knowledge-directed-grounding`, referenced by a
one-line pointer from the other two, following `rdr-core-engine`'s precedent of recording a
shared programme convention once rather than copying it into every successor); standing
design decisions with lasting consequence (the `RectifiedFootprint` rename hazard across
three branches, the "unmerged is not unusable" correction, the cost-measured-as-a-ratio
convention, the `PlacementRelation`/`Relation` design, a fixed ORM-generation bug that
looked plan-wide); and every question still open at the developer's own discretion. Item
`notes` were compressed the same way, hardest on the few long ones accreted over many
review rounds (`expectations-from-events` alone ran 211 manifest lines before compression).
Nothing is destroyed: the full 8,146-line predecessor is in the notes branch's history
immediately before `170d57424`.

### Concurrency, as the mechanics note anticipated

`split-icra-experiments` ran on the notes branch over the same window, exactly the scenario
`refuse-oversized-save`'s kickoff flagged when it added both items together. Every push here
re-fetched immediately beforehand; one push (recording the dashboard-URL cache) landed on
top of a base the sibling split had itself just advanced (`453021fff`, not this session's
own prior tip), and it fast-forwarded cleanly with no conflict - the same confirmation the
sibling's own roadmap section already recorded from its side.

### Left alone deliberately

The old `knowledge-directed-perception` artifact (the plan-wide dashboard, not the three new
per-wave ones) is left published and unlisted from the dashboard-URL cache, exactly as
`workflow-unification`'s and `rdr-refactor`'s own dashboards were left after their splits -
deleting a published Artifact is not something a session does unprompted. The
`<plan-id>:<item-id>` cross-plan reference both prior splits flagged as a `plan-dashboards`
candidate would have restored all 9 edges dropped here; three programmes in a row (7, then
29, now 9 more) have paid this same cost, which is a stronger case for building it than any
one of the three was alone.
