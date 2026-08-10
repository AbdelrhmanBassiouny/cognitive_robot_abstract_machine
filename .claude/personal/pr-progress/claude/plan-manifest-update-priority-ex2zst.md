# manifest-currency-first (workflow-unification)

Branch `claude/plan-manifest-update-priority-ex2zst` off fork `main`, draft PR
**#151**. Item is `in_progress`; manifest, roadmap and dashboard all written
before the first edit, per the ordering this item exists to generalize.

## The item

Every skill that can affect a plan writes the manifest and republishes the
dashboard first, at every transition that makes a recorded field stale.
Generalizes what `plan-item-bootstrap` (#143) did for the single kickoff moment.
Six bound surfaces: `plan-create`, `add-plan-item`, `plan-item-kickoff`,
`plan-item-resolve`, `plan-dashboard`, `stacked-pr-maintenance`.

## Approved plan

All three operations extend `.claude/hooks/plan_item_bootstrap.py` (it already
owns `PlanDocuments`, `ManifestKey`, `ItemStatus`, `apply_item_fields`,
`BootstrapReport`, `run_git`):

1. Block-styled field writing — fixes the silent `notes` corruption below.
2. `update` — write any tracked field, no mandatory roadmap section.
3. `check` — recorded fields vs local git state; own non-zero exit status.
4. `manifest-currency.md` + `MANIFEST_CURRENCY_DOCUMENT` constant, referenced in
   one subsection by each of the six skills.

## Two premises corrected at kickoff — both changed the plan

- **`sync_manifest_status.py` cannot be the reuse seam.** It imports
  `build_dashboard` → `render_common` → jinja2/markdown/nh3, so a hook cannot
  import it, and it answers a different question (post-hoc, GitHub-side, one
  direction). The split is by what each can see: dashboard vs GitHub after the
  fact; `check` vs local git before a push. Keeps the hook tier stdlib-only and
  leaves `check` importable by `plan-item-edit-guard`.
- **Writing `notes` today silently concatenates** the new note onto the old one
  and still validates. Verified against the module's own fixture.

## Progress

- [x] Branch, draft PR #151, `open` + `record`, roadmap section, dashboard
      republished, subscribed to #151 and to tracking issue #102.
- [ ] Block-styled writing (failing test first: writing `notes` preserves the
      existing note).
- [ ] `update` operation + tests.
- [ ] `check` operation + tests.
- [ ] `manifest-currency.md`, the constant, six skill references, contract test.
- [ ] Mutation-check every new test; full suite from a clean clone.

## Deferred, with reasons

- **No rename of `plan_item_bootstrap.py`** (user's call): the package migration
  that already moves it renames it once, rather than twice with three branches
  rebasing across the first attempt. Same call #106 made for splitting `stack.py`.
- **`stacked-pr-maintenance` reports, does not write** — it runs unattended under
  `--non-interactive`, and why a status changed is judgement the shared document
  keeps with a session. The one place the rule is deliberately weaker.
- **The `add-plan-item/SKILL.md` reference line** can only land here if #135
  merges first; #135 is marked ready, so it is not a session's to push to.
