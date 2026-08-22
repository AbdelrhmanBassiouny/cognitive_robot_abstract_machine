## PR #184 — `deferred-dependency-drift-check` (workflow-unification / dashboards)

Draft PR #184 off `main`, `bug` label. Branch
`claude/deferred-dependency-drift-pr-qxpfsm`, head `453795a6`. Full reasoning in the
plan's `roadmap.md` entries of 2026-08-20 (kickoff + implementation) and 2026-08-22
(this review round).

**The bug.** `build_dashboard.py` had no cross-item check: `_drift_description_of`
only compared an item's own `status` against its own live PR state, so an item
stacked on a dependency that will never land was never flagged.

**Design calls already settled — do not re-litigate**
- The stall predicate is *deferred, or PR closed unmerged*. Deliberately **not** a
  reuse of `is_ready_to_unblock_dependents()`, which is also false for a not-started
  or open-draft dependency; the item's original notes were wrong on this and the
  manifest no longer preserves that half.
- Drift is a **list**, because an item can carry manifest drift and a stalled
  dependency at once; `DashboardSummary.drift_flag_count` exists because the banner
  counts flags, not items.
- **Direct** `depends_on` only, naming the stalled dependency's own `depends_on` as
  the reparent target.
- Out of scope, checked rather than assumed: `_compute_next_steps` (no change
  needed), the `example/` fixture and screenshots (no new flag there),
  `check_dependency_readiness.py`.

**Review, 2026-08-22 — first round, eight threads, all resolved (`453795a6`)**
- Seven were one finding: the tests retyped the drift sentences production builds.
  `drift_descriptions` became `drift_flags` — a `ManifestDrift` carrying the
  `ManifestDriftCause` its `match` decides, or a `StalledDependencyDrift` carrying
  the dependency, its `StallReason` and the reparent targets — with the wording on
  `DriftFlag.description`. `_drift_description_of` split into
  `ManifestDrift._cause_of` + `.description`, the `match` and its case ordering
  untouched.
- `Item.stall_reason` replaced a condition that was written twice (once in
  `is_stalled()`, once in the `if/else` that picked the wording); `is_stalled()` is
  derived from it. `StalledDependencyDrift.of` raises `NotStalledDependencyError`
  rather than inventing a reason.
- Wording is pinned in exactly one place now, `test_drift_flag_describes_itself` —
  that test *is* the replacement for the guard the retyped copies were accidentally
  providing. Do not delete it without replacing it.
- The two markup tests read the page through an `html.parser` helper instead of
  matching strings, which also removed a `markupsafe.escape()` call that existed
  only to reproduce Jinja's autoescaping in the expectation.

**Second round the same day — three threads (`97ee004d3`), one left open**
- The wording assertions are **cut**, on the user's argument that nobody parses a
  drift description. Their own precedent: #121's second round did exactly this to
  `test_every_summary_message_reads_as_written`. Do not re-add sentence pinning here.
- What replaced it is the half that was never wording: `description` is a `match`
  with no `case _`, so a member added later without a branch returns `None` silently
  and the card renders the word "None". Two parametrised tests over
  `list(ManifestDriftCause)` and `list(StallReason)` assert each renders something —
  parametrised off the enum, so a future member needs no test edit.
- That thread (`PRRT_kwDOQhJw3c6bYJwp`) is **left open**: a replacement is not the
  deletion it asked for, so it is the user's to close.
- `drift_lines_in` strips the `⚠` (named at `DRIFT_LINE_MARKER`); the marker's
  presence is deliberately no longer asserted anywhere.
- `TextOfElementsWithClass` is a dataclass. Its `__post_init__` is load-bearing:
  `@dataclass` generates `__init__` rather than extending the base's, so
  `HTMLParser.reset()` would never run and `feed()` would fail.

**The docformatter finding, which is the one to carry**
- On the previous head `scripts/format_docstrings.py` left `build_dashboard.py`
  byte-identical while `docformatter` disagreed with **48 hunks of `main`'s own
  copy** — the documented non-convergent case, the whole disagreement being one
  blank line at the `AVAILABLE_MODELS` docstring immediately before the decorated
  `class Item`.
- This round's new classes sit at exactly that adjacency, so the file **converges
  now** and the pre-commit hook formats it. The ~500-line docstring reflow in
  `453795a6` is that first run, not a choice. The user was asked and chose to let it
  land rather than arrange code to preserve a formatter bug.
- Consequence: `build_dashboard.py` is house-style clean; `stack.py` is still in the
  identical non-convergent state and is untouched.

**State**
- 248 tests in `.claude/skills/plan-dashboard/tests` (was 239), 107 hooks, 154 stack.
  `format_docstrings.py` a no-op on both touched files afterwards, `docformatter
  --diff` 0 hunks on each, `black --check` clean.
- Live check unchanged by the round: `rdr-refactor` flags `D-ui-rendering` and only
  it; `workflow-unification` flags none.
- PR description rewritten to match. Still a draft, and stays one until the user
  marks it ready.

**Outstanding**
- CI on `97ee004d3` not yet observed. At `453795a6`, `test_claude_dev_tooling` passed
  and one robotics job was red — `test_each_lib (robokudo)` →
  `test_run_semdt_raytracer_ae_successfully`, `assert 3 == 2` object hypotheses from
  point-cloud clustering, 1 of 830 tests. Unreachable from a diff confined to
  `.claude/skills/plan-dashboard/`, and green at `40d9d6dd`.
- **Landing hazard, deliberately not pre-resolved**: decision 13 names #184 among the
  pull requests touching files the `bastler` migration moves. #185 is open, draft and
  unmerged, and that decision's doctrine is *"don't pre-resolve against it before it
  exists"* — so #184 merges `main` and re-applies its delta inside the package once
  #185 lands.
- Conflict-adjacent with #157 (same test file, sidebar template region) — both
  additive; whichever-lands-second merges.

**Watch out**
- Never subscribe to PR activity. Subscribing to tracking-issue #102 was refused by
  the permission classifier in both sessions so far.
- The notes branch moved twice mid-session (another session added
  `report-document-naming`); re-fetch and re-apply before any `save-plan.sh`.
- This container needs `pip install pytest tqdm black docformatter typing_extensions`
  plus the plan-dashboard requirements before the suites and the formatter will run.
- Filtering a docformatter run by *hunk* over-reaches — it groups neighbouring
  docstrings with context and drags `main`'s along. Filter at `difflib` opcode
  granularity if that is ever needed again.
