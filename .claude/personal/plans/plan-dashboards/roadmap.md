# plan-dashboards — Roadmap

Narrative companion to `plan.yaml`. Kept short on purpose: the size budget this split was made
under counts these lines.

## Where this plan came from

Split out of `workflow-unification` on 2026-08-30, under `plan-size-limits`'
`split-workflow-unification`. That plan had reached 59 items and 16,917 lines across its manifest
and roadmap, well past the 15-item / 2,000-line budget, and became seven plans seamed on subject.

This plan is the `dashboards` track, carried across unchanged. Every item keeps its branch, pull
request number, status and session verbatim. **The full predecessor roadmap remains in the
personal-notes branch's history**; what is kept here is what binds future work.

## Why this work exists

Two dashboard pipelines existed - a stack board and the plan dashboards - each fetching pull request
state and rendering it. The one-dashboard decision of 2026-07-31 retired the board: GitHub's native
stack map covers derived stack mechanics, so the plan dashboards are the single surface. That made
this renderer the only page anyone reads about in-flight work, and its computation bugs stopped
being cosmetic.

Most items here are bug fixes with the same shape: a predicate that was *nearly* right, whose
failure inverted the intent rather than merely narrowing it. Dependency-free items dropped out of
the ready list entirely; a dependency becoming more finished made its dependent look less reviewable;
an item stacked on a dead base had no signal anywhere. Each was fixed on its own root cause, one
pull request each, per the standing rule for bug fixes.

## Decisions this plan inherits

Numbering is the predecessor's, kept so cross-references in item notes still resolve.

**5. The plan data model and the stack data model stay separate.** The board is derived mechanics
now - pull request bases and git ancestry; plans are intent over time, with waves, tracks and
dependencies. Only the fetch and render layer unifies, which is what `shared-pr-state-chips` is.

**3. Portability.** A plan without an upstream configured renders no promotion group and no links;
no repository is named outside configuration defaults.

**13. The bastler pivot inverted one dependency.** `shared-pr-state-chips` no longer creates the
tooling package - `bastler-package` does, off main - so that branch rebases onto it and folds its
modules in under the package's naming. What stays this item's own is the feature half.

## Conventions this track settled

- **Whichever lands second merges.** Seven items here edit `build_dashboard.py` and its template with
  no dependency between them. That is textual overlap, not ownership, and it has been the working
  arrangement throughout.
- **Bug-fix pull requests carry the `bug` label; tooling that never existed does not.** An item that
  *surfaces* bug fixes is not itself a bug fix.
- **Wording is not pinned by tests.** Twice a round added a test asserting a rendered sentence, and
  twice the user cut it: nobody parses a drift description or a summary line, so pinning the sentence
  buys a failing test per reword and catches no defect. What survives asserts that each case renders
  *something*, and pins rules rather than phrasings.
- **Check the neighbours before defending a guard.** Three rounds argued about one test, and what
  ended it was reading how the module already treats the identical pattern - not reasoning about what
  the test was worth.

## Landing hazards

- **The formatter's non-convergence is positional.** An attribute docstring directly before a
  decorated definition makes `docformatter` drop a blank line, `black` restore it, and
  `format_docstrings.py` discard the lot - so the whole file is silently declined. Two changes here
  hit it by placing a new class at exactly that adjacency, and the fix both times was placement.
  `stack.py` is in the identical state and is left alone.
- **The package extraction moves this file wholesale.** Every open item here merges main across that
  move and re-applies its delta.
- **Screenshots are binary and regenerated from the committed example**, so two branches that both
  regenerate them conflict. Whoever lands second re-regenerates, which is mechanical since the image
  is deterministic from the fixture.

## Open

- **No automated audit of the dashboard URL cache.** The recording fix validates at write time and
  nothing re-checks later, and an entry has already gone dead on its own afterwards. Worth having,
  because a stale entry costs a duplicate artifact rather than an error.
- **No recorded rule for an ambiguous title.** The recorder refuses when two artifacts share a plan's
  title and demands an explicit URL, which is right, but leaves the caller with nothing to choose by.
  Most-recently-updated is what both hand corrections have used.
- **Cross-plan dependencies are not representable** - now the item `cross-plan-dependencies`,
  added 2026-09-03 at the developer's direction with the reference form `<plan-id>/<item-id>`
  (the colon suggested here earlier is superseded). Until it lands, a precondition in another plan
  stays a `blockers` entry, as `shared-pr-state-chips`, rdr-explanation's `rdr-why-answer` and
  three items of `icra-experiments` record today.

## shared-pr-state-chips: the fold onto bastler, 2026-09-02

The manifest called this item blocked on the bastler dependency and on a `main` conflict; what
had actually stalled it was the 2026-08-30 review round - nineteen threads the manifest never
mentioned. Recorded first, resolved second.

The resolution was the fold decision 13 already described, done as a merge of #185's head rather
than a re-cut: #185 already contained this branch's last merge of `main`, so the merge brought no
stray `main` commits into the diff against the new base. Check
`git merge-base --is-ancestor <this branch's main merge-base> <parent head>` before choosing
merge over re-cut; it decides whether the diff stays clean.

Two threads were answered differently from what they asked and are left open for the user:
`GitCommandRunner` in the tests, and the request to discuss the rebase options.

**The formatter hazard above, explained.** `format_docstrings.py` declines a file whenever
docformatter would expand a one-line member docstring at the end of a class body: the expansion
eats the blank line black then restores, and the script keeps the black-only result. A file
converges only if its member docstrings already carry the three-line form the tool produces. The
position matters only because the last member of a class is where the eaten blank line sits.
`stack.py` and `build_dashboard.py` were already declined on #185's head and stay black-only.

## cross-plan-dependencies: the settled plan, 2026-09-03

Kicked off in `auto` mode, so this is the record the approval step never produced.

**The reference form** is `<plan-id>/<item-id>`, decided by the developer; a bare id keeps
meaning this plan, and a reference naming this plan's own id is rejected rather than
accepted as a synonym, so one item has one spelling. A second separator is malformed
rather than read as a nested path.

**Validation resolves, it does not trust.** `validate_plan` gains the referenced plans as
a second input and rejects an unknown plan, an unknown foreign item, a self-plan
reference and a malformed reference. Because a reference cannot be resolved without the
other manifests, a cross-plan entry with no plans directory available is itself rejected -
the alternative, passing it unchecked, is the same silent-ready fault this item fixes.
The cycle check runs over the union graph, keyed by canonical reference; a node in the
plan under validation keeps its bare id, so a same-plan cycle is reported exactly as it
was before.

**The plans directory is the one new input**, and the dashboard URL cache is read from
inside it (`_generated/dashboard-urls.yaml`) rather than passed separately: it already
lives in the directory the plans live in, so a second argument would be a second way to
say the same thing. Threaded through `build_dashboard.py`,
`check_dependency_readiness.py` and - found by reading rather than assumed -
`sync_manifest_status.py`, which validates the manifest too and would otherwise fail the
refresh before rendering. `refresh_dashboard.sh` passes it on.

**One resolver, `items_by_reference`**, serves every reader of `depends_on`, so the
readiness rule, the chips, the two sidebar lists and the readiness script cannot disagree
about what a reference means. A foreign item is classified against its own plan's
`default_repository`.

**Stacking depth stays same-plan.** An indent level is a position on this page, and a
foreign parent is not on it.

**The latent fault fixed on the way**: `_dependencies_are_ready` skipped an identifier it
could not resolve, so a mistyped dependency counted as ready and its dependent got a
"Start now" button.

### What is deliberately not in this pull request

The five recorded cross-plan blockers this item exists to convert - `icra-experiments`'
`integrated-simulation-pipeline`, `failure-taxonomy-and-typing` and
`experiment-c-in-simulation`, this plan's `shared-pr-state-chips`, and
`rdr-explanation`'s `rdr-why-answer` - are plan data on the personal-notes branch, not
code on this branch. They are also **sequenced after this lands**: every session runs the
tooling from its own checkout, so a manifest carrying `<plan-id>/<item-id>` before `main`
can resolve it fails validation on every `/plan-dashboard` run for those plans. All five
target ids were checked to resolve: `montessori-eql-stack/montessori_fast_inline_monitor`,
`knowledge-directed-perception/expectations-from-events`,
`bastler-package/bastler-package` (#185) and `rdr-core-engine/d-core-backend` (#210).

### Landing hazards, both recorded rather than pre-resolved

`#185` moves every `.claude/` Python module into the `bastler` package, and `#184`, `#157`,
`#206` and `#111` also edit `build_dashboard.py`. The track's rule is that whichever lands
second merges, so this is based off `main`.

Worth naming because it is the same idea under a different name: `#184` introduces
`_resolved_dependencies_of`, absorbing the `depends_on`-resolution comprehension its
callers each wrote out. That is the resolution *call site*; `items_by_reference` is what a
reference resolves *through*. Whichever lands second should compose them into one path
rather than leave two, and `#184`'s `stall_reason` becomes another reader of the resolver
in that merge.

`#184`'s review also produced two conventions this item follows without importing their
code: rendered wording is never pinned by a test, and a rendered page is read by class
rather than matched as a string. The `TextOfElementsWithClass` helper that does the second
lives on `#184`'s branch, so this branch asserts the chip's own fields and leaves adopting
that helper to the merge - building a second copy of it is how two branches end up with
one artifact twice.

Note for that merge: `items_by_reference` is now `DependencyResolver`, so the one path the
two branches should converge on is a class, not a dict.

### What the review round settled, 2026-09-03

Seven threads and one note on the review itself, applied in `b9e53be9`. Three of them
changed a decision recorded above rather than only the code, so they belong here.

**Read what a reference names, not what the directory holds.** The first cut loaded every
manifest under the plans directory up front. The reviewer's objection is the one this
plan's sibling `plan-size-limits` exists for: a per-plan budget is defeated the moment one
plan's dashboard run pulls in every other plan's contents. `PlanDirectory` now opens the
directory - reading only the small URL cache - and reads one manifest the first time
something names its plan, so a plan nothing depends on costs what an absent plan costs.
The skill's extraction narrowed to match: `*/plan.yaml` and the URL cache, never a
roadmap, and step 1 now says in as many words not to read any of them by hand. What
reaches the page from a foreign plan was already bounded to one chip - reference, title,
plan title, live state - and `plan-schema.md` now writes that down so it stays that way.

**An entry that names nothing is a class, not a hole.** The silent-ready fault was fixed
by returning `None` per unresolvable entry and having every caller refuse to treat `None`
as satisfied - which works, and puts the same guard in three places. `Dependency` is now
an ABC over `ResolvedDependency` and `UnresolvedDependency`: an entry always resolves to
*something*, the something answers `False` to both readiness questions, and the guards,
the `zip` over `depends_on` and the renderer's `_dashboard_url_of` all disappear. The
general lesson, since it is the third time this file has hit it: when a hole in a
collection needs the same check at every reader, the hole wanted to be a subclass.

**One resolver means one class, not one dict.** `items_by_reference` was a dict the
renderer built and every reader indexed; `check_dependency_readiness.py` had its own
`_resolve` doing the same job beside it. Both are `DependencyResolver` now, so the claim
that every reader of `depends_on` goes through one resolver is enforced rather than
observed.

The rest were fixed strings and nested functions: `ManifestKey`, `PlanFile`,
`SUPPORTED_SCHEMA_VERSION`, `DependencyReadiness`/`ReadinessField` in place of a
four-key dict written twice, and `DependencyGraph`/`CycleSearch`/`VisitState` in place of
a function holding two closures and three bare integers. On the test side the rule that
paid off is worth keeping: **assert against the file that declares the value, not a
retyped copy** - the fixture plans' repository, titles and pull request numbers are read
back out of their manifests through a shared `tests/fixture_plans.py`, and only the ids
are named in code, because an id is how a test points at a fixture at all.
